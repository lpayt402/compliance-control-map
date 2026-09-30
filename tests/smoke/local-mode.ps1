$ErrorActionPreference = "Stop"
. "$PSScriptRoot\common.ps1"

$root = (Resolve-Path "$PSScriptRoot\..\..").Path
$composeFile = Join-Path $root "docker-compose.yml"
$project = "ccm-local-smoke"
$webPort = Get-CcmFreePort
$baseUrl = "http://127.0.0.1:$webPort"
$sourceFile = Join-Path $root "backend\demo-files\demo-access-policy.txt"
$tempRoot = Join-Path ([IO.Path]::GetTempPath()) "ccm-smoke-local-$([guid]::NewGuid().ToString('N'))"
$files = @($composeFile)

$previousWebPort = $env:CCM_WEB_PORT
$previousDemo = $env:CCM_LOAD_DEMO
$env:CCM_WEB_PORT = [string]$webPort
$env:CCM_LOAD_DEMO = "true"

try {
    New-Item -ItemType Directory -Path $tempRoot | Out-Null
    Invoke-CcmCompose -Project $project -Files $files `
        -Arguments @("up", "-d", "--build", "--wait")
    Wait-CcmUrl -Url "$baseUrl/api/v1/health/ready"

    $client = New-CcmSession -BaseUrl $baseUrl
    $search = Invoke-CcmJson -Method GET `
        -Uri "$baseUrl/api/v1/requirements?search=CC8.1" -Session $client.Session
    $requirement = @($search.data)[0]
    Assert-Ccm ($requirement.external_id -eq "CC8.1") "CC8.1 was not loaded."

    $noteText = "Local smoke persistence $([guid]::NewGuid().ToString('N'))"
    $updated = Invoke-CcmJson -Method PATCH `
        -Uri "$baseUrl/api/v1/requirements/$($requirement.id)/assessment" `
        -Session $client.Session -Token $client.Token -Origin $baseUrl `
        -Body @{
            revision = [int]$requirement.assessment.revision
            status_code = "READY"
            implementation_notes = $noteText
            due_date = "2030-01-15"
        }
    Assert-Ccm ($updated.data.assessment.status_code -eq "READY") "Status update failed."

    $upload = Invoke-CcmMultipartUpload -Uri "$baseUrl/api/v1/documents" `
        -Origin $baseUrl -Session $client.Session -Token $client.Token `
        -FilePath $sourceFile -MediaType "text/plain" `
        -Fields @{
            name = "Local smoke access policy"
            document_type = "POLICY"
            version = "smoke-1"
        }
    $documentId = [string]$upload.data.id
    $sourceHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $sourceFile).Hash
    Assert-Ccm ($upload.data.file.sha256.ToUpperInvariant() -eq $sourceHash) `
        "Uploaded file hash did not match the source."

    $mapped = Invoke-CcmJson -Method POST `
        -Uri "$baseUrl/api/v1/documents/$documentId/requirements" `
        -Session $client.Session -Token $client.Token -Origin $baseUrl `
        -Body @{ requirement_ids = @([string]$requirement.id); rationale = "Smoke mapping" }
    Assert-Ccm (@($mapped.data.requirements).Count -ge 1) "Document mapping failed."

    Invoke-CcmCompose -Project $project -Files $files -Arguments @("restart", "api", "web")
    Wait-CcmUrl -Url "$baseUrl/api/v1/health/ready"

    $afterRestart = Invoke-CcmJson -Method GET `
        -Uri "$baseUrl/api/v1/requirements/$($requirement.id)" -Session $client.Session
    Assert-Ccm ($afterRestart.data.assessment.implementation_notes -eq $noteText) `
        "Assessment data did not survive a container restart."

    $documentAfterRestart = Invoke-CcmJson -Method GET `
        -Uri "$baseUrl/api/v1/documents/$documentId" -Session $client.Session
    Assert-Ccm ($documentAfterRestart.data.id -eq $documentId) `
        "Document metadata did not survive a container restart."

    $downloadPath = Join-Path $tempRoot "downloaded.txt"
    Invoke-WebRequest -Uri "$baseUrl/api/v1/documents/$documentId/download" `
        -WebSession $client.Session -OutFile $downloadPath
    $downloadHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $downloadPath).Hash
    Assert-Ccm ($downloadHash -eq $sourceHash) "Downloaded file content changed after restart."

    $backupPath = Join-Path $tempRoot "backup.zip"
    Invoke-WebRequest -Method POST -Uri "$baseUrl/api/v1/exports" `
        -WebSession $client.Session `
        -Headers @{ "X-CSRF-Token" = $client.Token; "Origin" = $baseUrl } `
        -OutFile $backupPath
    Assert-Ccm ((Get-Item -LiteralPath $backupPath).Length -gt 500) "Backup archive is empty."
    $archive = [IO.Compression.ZipFile]::OpenRead($backupPath)
    try {
        Assert-Ccm ($null -ne $archive.GetEntry("manifest.json")) `
            "Backup archive is missing manifest.json."
    } finally { $archive.Dispose() }

    Write-Host "local mode smoke passed: SQLite, files, mappings, restart persistence, export"
} finally {
    try { Remove-CcmComposeProject -Project $project -Files $files } catch { Write-Warning $_ }
    if (Test-Path -LiteralPath $tempRoot) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force
    }
    $env:CCM_WEB_PORT = $previousWebPort
    $env:CCM_LOAD_DEMO = $previousDemo
}
