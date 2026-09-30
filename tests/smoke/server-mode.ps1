$ErrorActionPreference = "Stop"
. "$PSScriptRoot\common.ps1"

$root = (Resolve-Path "$PSScriptRoot\..\..").Path
$composeFiles = @(
    (Join-Path $root "docker-compose.yml"),
    (Join-Path $root "docker-compose.server.yml"),
    (Join-Path $root "tests\smoke\docker-compose.test.yml")
)
$project = "ccm-server-smoke"
$webPort = Get-CcmFreePort
$postgresPort = Get-CcmFreePort
$baseUrl = "http://127.0.0.1:$webPort"
$suffix = [guid]::NewGuid().ToString("N")
$adminEmail = "admin-$suffix@example.com"
$editorEmail = "editor-$suffix@example.com"
$viewerEmail = "viewer-$suffix@example.com"
$adminPassword = "Admin-smoke-$suffix!"
$editorPassword = "Editor-smoke-$suffix!"
$viewerPassword = "Viewer-smoke-$suffix!"
$postgresPassword = "Postgres-smoke-$suffix!"
$sourceFile = Join-Path $root "backend\demo-files\demo-quarterly-access-review.txt"
$tempRoot = Join-Path ([IO.Path]::GetTempPath()) "ccm-smoke-server-$suffix"

$environmentNames = @(
    "CCM_WEB_BIND", "CCM_WEB_PORT", "CCM_POSTGRES_TEST_PORT", "CCM_POSTGRES_PASSWORD",
    "CCM_BOOTSTRAP_ADMIN_EMAIL", "CCM_BOOTSTRAP_ADMIN_DISPLAY_NAME",
    "CCM_BOOTSTRAP_ADMIN_PASSWORD", "CCM_SERVER_LOAD_DEMO", "CCM_ALLOWED_ORIGINS",
    "CCM_ALLOWED_HOSTS", "CCM_TEST_DATABASE_URL", "CCM_E2E_TEAM_BASE_URL",
    "CCM_E2E_ADMIN_EMAIL", "CCM_E2E_ADMIN_PASSWORD", "CCM_E2E_EDITOR_EMAIL",
    "CCM_E2E_EDITOR_PASSWORD", "CCM_E2E_VIEWER_EMAIL", "CCM_E2E_VIEWER_PASSWORD"
)
$previousEnvironment = @{}
foreach ($name in $environmentNames) {
    $previousEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, "Process")
}

$env:CCM_WEB_BIND = "127.0.0.1"
$env:CCM_WEB_PORT = [string]$webPort
$env:CCM_POSTGRES_TEST_PORT = [string]$postgresPort
$env:CCM_POSTGRES_PASSWORD = $postgresPassword
$env:CCM_BOOTSTRAP_ADMIN_EMAIL = $adminEmail
$env:CCM_BOOTSTRAP_ADMIN_DISPLAY_NAME = "Smoke administrator"
$env:CCM_BOOTSTRAP_ADMIN_PASSWORD = $adminPassword
$env:CCM_SERVER_LOAD_DEMO = "true"
$env:CCM_ALLOWED_ORIGINS = "[`"$baseUrl`"]"
$env:CCM_ALLOWED_HOSTS = '["localhost","127.0.0.1"]'

try {
    New-Item -ItemType Directory -Path $tempRoot | Out-Null
    Invoke-CcmCompose -Project $project -Files $composeFiles `
        -Arguments @("up", "-d", "--build", "--wait")
    Wait-CcmUrl -Url "$baseUrl/api/v1/health/ready" -TimeoutSeconds 180

    $admin = Connect-CcmUser -BaseUrl $baseUrl -Email $adminEmail -Password $adminPassword
    $editor = Invoke-CcmJson -Method POST -Uri "$baseUrl/api/v1/users" `
        -Session $admin.Session -Token $admin.Token -Origin $baseUrl `
        -Body @{
            email = $editorEmail
            display_name = "Smoke editor"
            password = $editorPassword
            role = "EDITOR"
        }
    $viewer = Invoke-CcmJson -Method POST -Uri "$baseUrl/api/v1/users" `
        -Session $admin.Session -Token $admin.Token -Origin $baseUrl `
        -Body @{
            email = $viewerEmail
            display_name = "Smoke viewer"
            password = $viewerPassword
            role = "VIEWER"
        }
    Assert-Ccm ($editor.data.role -eq "EDITOR") "Editor account was not created."
    Assert-Ccm ($viewer.data.role -eq "VIEWER") "Viewer account was not created."

    $env:CCM_BOOTSTRAP_ADMIN_EMAIL = ""
    $env:CCM_BOOTSTRAP_ADMIN_PASSWORD = ""
    Invoke-CcmCompose -Project $project -Files $composeFiles `
        -Arguments @("up", "-d", "--force-recreate", "--no-deps", "api")
    Wait-CcmUrl -Url "$baseUrl/api/v1/health/ready" -TimeoutSeconds 120
    $admin = Connect-CcmUser -BaseUrl $baseUrl -Email $adminEmail -Password $adminPassword

    $viewerClient = Connect-CcmUser -BaseUrl $baseUrl -Email $viewerEmail -Password $viewerPassword
    $viewerRequirements = Invoke-CcmJson -Method GET `
        -Uri "$baseUrl/api/v1/requirements?search=CC8.1" -Session $viewerClient.Session
    $requirement = @($viewerRequirements.data)[0]
    Assert-Ccm ($requirement.external_id -eq "CC8.1") "Viewer could not read requirements."
    $viewerPatch = Invoke-WebRequest -Method PATCH `
        -Uri "$baseUrl/api/v1/requirements/$($requirement.id)/assessment" `
        -WebSession $viewerClient.Session -SkipHttpErrorCheck `
        -Headers @{ "X-CSRF-Token" = $viewerClient.Token; "Origin" = $baseUrl } `
        -ContentType "application/json" `
        -Body (ConvertTo-Json @{ revision = [int]$requirement.assessment.revision; status_code = "READY" })
    Assert-Ccm ($viewerPatch.StatusCode -eq 403) "Viewer mutation was not rejected."

    $editorClient = Connect-CcmUser -BaseUrl $baseUrl -Email $editorEmail -Password $editorPassword
    $editorRequirements = Invoke-CcmJson -Method GET `
        -Uri "$baseUrl/api/v1/requirements?search=CC8.1" -Session $editorClient.Session
    $editorRequirement = @($editorRequirements.data)[0]
    $changed = Invoke-CcmJson -Method PATCH `
        -Uri "$baseUrl/api/v1/requirements/$($editorRequirement.id)/assessment" `
        -Session $editorClient.Session -Token $editorClient.Token -Origin $baseUrl `
        -Body @{
            revision = [int]$editorRequirement.assessment.revision
            status_code = "READY"
            implementation_notes = "PostgreSQL team-mode smoke"
        }
    Assert-Ccm ($changed.data.assessment.status_code -eq "READY") `
        "Editor could not update a requirement."

    $upload = Invoke-CcmMultipartUpload -Uri "$baseUrl/api/v1/evidence" `
        -Origin $baseUrl -Session $editorClient.Session -Token $editorClient.Token `
        -FilePath $sourceFile -MediaType "text/plain" `
        -Fields @{
            name = "Server smoke access review"
            description = "Team-mode upload and download test"
        }
    $evidenceId = [string]$upload.data.id
    $downloadPath = Join-Path $tempRoot "downloaded.txt"
    Invoke-WebRequest -Uri "$baseUrl/api/v1/evidence/$evidenceId/download" `
        -WebSession $viewerClient.Session -OutFile $downloadPath
    Assert-Ccm (
        (Get-FileHash -Algorithm SHA256 -LiteralPath $sourceFile).Hash -eq
        (Get-FileHash -Algorithm SHA256 -LiteralPath $downloadPath).Hash
    ) "Team-mode upload/download round-trip changed the file."

    $env:CCM_E2E_TEAM_BASE_URL = $baseUrl
    $env:CCM_E2E_ADMIN_EMAIL = $adminEmail
    $env:CCM_E2E_ADMIN_PASSWORD = $adminPassword
    $env:CCM_E2E_EDITOR_EMAIL = $editorEmail
    $env:CCM_E2E_EDITOR_PASSWORD = $editorPassword
    $env:CCM_E2E_VIEWER_EMAIL = $viewerEmail
    $env:CCM_E2E_VIEWER_PASSWORD = $viewerPassword
    Push-Location (Join-Path $root "frontend")
    try {
        corepack pnpm exec playwright test e2e/permissions.spec.ts
        if ($LASTEXITCODE -ne 0) { throw "Browser role tests failed." }
    } finally { Pop-Location }

    $containerTestDatabase = (
        "postgresql+psycopg://ccm:$postgresPassword@postgres:5432/compliance_control"
    )
    Invoke-CcmCompose -Project $project -Files $composeFiles `
        -Arguments @(
            "run", "--rm", "--build", "--no-deps",
            "--env", "CCM_TEST_DATABASE_URL=$containerTestDatabase",
            "backend-tests"
        )

    Write-Host "server mode smoke passed: PostgreSQL, login, roles, uploads, API and browser tests"
} finally {
    try { Remove-CcmComposeProject -Project $project -Files $composeFiles } catch { Write-Warning $_ }
    if (Test-Path -LiteralPath $tempRoot) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force
    }
    foreach ($name in $environmentNames) {
        [Environment]::SetEnvironmentVariable($name, $previousEnvironment[$name], "Process")
    }
}
