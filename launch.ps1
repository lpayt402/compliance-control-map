[CmdletBinding()]
param(
    [ValidateSet("start", "status", "down", "export", "restore")]
    [string]$Mode = "start",
    [ValidateSet("local", "server")]
    [string]$Deployment = "local",
    [switch]$Refresh,
    [switch]$Yes,
    [string]$Archive = ""
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $ProjectRoot

function Ensure-EnvironmentFile {
    if (-not (Test-Path -LiteralPath ".env")) {
        Copy-Item -LiteralPath ".env.example" -Destination ".env"
        Write-Host "Created .env from the safe local defaults."
    }
}

function Get-ComposeFiles {
    $files = @("compose", "--env-file", ".env", "-f", "docker-compose.yml")
    if ($Deployment -eq "server") { $files += @("-f", "docker-compose.server.yml") }
    return $files
}

function Invoke-Compose([string[]]$Arguments) {
    $prefix = Get-ComposeFiles
    & docker @prefix @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Docker Compose command failed." }
}

function Get-EnvValue([string]$Name, [string]$Fallback) {
    if (-not (Test-Path -LiteralPath ".env")) { return $Fallback }
    $line = Get-Content -LiteralPath ".env" | Where-Object { $_ -match "^$([regex]::Escape($Name))=" } | Select-Object -Last 1
    if (-not $line) { return $Fallback }
    $value = ($line -split "=", 2)[1].Trim()
    if ($value) { return $value }
    return $Fallback
}

function Get-ProjectName {
    $configured = Get-EnvValue "COMPOSE_PROJECT_NAME" ""
    if ($configured) { return $configured }
    $leaf = Split-Path -Leaf $ProjectRoot
    return (($leaf.ToLowerInvariant() -replace "[^a-z0-9_-]", "") -replace "^[^a-z0-9]+", "")
}

function Test-ServerConfiguration {
    if ($Deployment -ne "server" -or $Mode -ne "start") { return }
    $postgresPassword = Get-EnvValue "CCM_POSTGRES_PASSWORD" ""
    $bootstrapEmail = Get-EnvValue "CCM_BOOTSTRAP_ADMIN_EMAIL" ""
    $bootstrapPassword = Get-EnvValue "CCM_BOOTSTRAP_ADMIN_PASSWORD" ""
    $allowedOrigins = Get-EnvValue "CCM_ALLOWED_ORIGINS" ""
    $allowedHosts = Get-EnvValue "CCM_ALLOWED_HOSTS" ""

    if (-not $postgresPassword -or -not $allowedOrigins -or -not $allowedHosts) {
        throw "Server mode requires CCM_POSTGRES_PASSWORD, CCM_ALLOWED_ORIGINS, and CCM_ALLOWED_HOSTS in .env."
    }
    foreach ($value in @($postgresPassword, $bootstrapPassword, $allowedOrigins, $allowedHosts)) {
        if ($value -match "CHANGE_ME") { throw "Replace every CHANGE_ME value in .env before starting server mode." }
    }
    if ($allowedOrigins -match "example\.com" -or $allowedHosts -match "example\.com") {
        throw "Replace the example.com origin and host with the real browser-facing hostname."
    }
    if ([bool]$bootstrapEmail -ne [bool]$bootstrapPassword) {
        throw "Set both bootstrap Admin values for a fresh server, or clear both after the first Admin can sign in."
    }
    if ($bootstrapPassword -and $bootstrapPassword.Length -lt 15) {
        throw "The bootstrap Admin password must contain at least 15 characters."
    }
    if (-not $bootstrapEmail) {
        Write-Warning "Bootstrap Admin credentials are cleared. This start will succeed only if an active Admin already exists."
    }
}

function Write-ServerLoginHint {
    if ($Deployment -ne "server") { return }
    $bootstrapEmail = Get-EnvValue "CCM_BOOTSTRAP_ADMIN_EMAIL" ""
    if ($bootstrapEmail) {
        Write-Host "Login email: $bootstrapEmail"
        Write-Host "Initial password: use the value in .env (not displayed)."
    } else {
        Write-Host "Login email: use an existing Admin account."
    }
}

function Invoke-LocalRefresh {
    if ($Deployment -eq "server") { throw "server mode cannot be refreshed; use a reviewed PostgreSQL backup/restore procedure" }
    $volumeKeys = @("ccm_sqlite_data", "ccm_file_data")
    $project = Get-ProjectName
    $targets = @()
    foreach ($key in $volumeKeys) {
        $resolved = @(& docker volume ls --quiet --filter "label=com.docker.compose.project=$project" --filter "label=com.docker.compose.volume=$key")
        foreach ($name in $resolved) {
            if (-not $name) { continue }
            $label = & docker volume inspect --format '{{ index .Labels "com.docker.compose.volume" }}' $name
            if ($LASTEXITCODE -ne 0 -or $label -ne $key) { throw "Refusing to remove an unverified volume: $name" }
            $targets += $name
        }
    }
    Write-Host "Refresh targets (and nothing else):"
    if ($targets.Count -eq 0) { Write-Host "  No existing local data volumes found." }
    foreach ($target in $targets) { Write-Host "  $target" }
    Write-Warning "This permanently removes local test data from ccm_sqlite_data and ccm_file_data."
    if (-not $Yes) {
        $answer = Read-Host "Type REFRESH to continue"
        if ($answer -cne "REFRESH") { throw "Refresh cancelled." }
    }
    Invoke-Compose -Arguments @("down", "--remove-orphans")
    foreach ($target in $targets) {
        & docker volume rm $target
        if ($LASTEXITCODE -ne 0) { throw "Could not remove verified volume $target" }
    }
}

function Wait-ForApplication {
    $port = Get-EnvValue "CCM_WEB_PORT" "3000"
    $health = "http://127.0.0.1:$port/api/v1/health/ready"
    $deadline = [DateTime]::UtcNow.AddSeconds(60)
    while ([DateTime]::UtcNow -lt $deadline) {
        try {
            $response = Invoke-WebRequest -UseBasicParsing -Uri $health -TimeoutSec 2
            if ($response.StatusCode -eq 200) {
                Write-Host "Ready: http://localhost:$port"
                return
            }
        } catch { Start-Sleep -Milliseconds 500 }
    }
    Invoke-Compose -Arguments @("ps")
    throw "The application did not become ready within 60 seconds."
}

function New-LocalApiClient {
    $port = Get-EnvValue "CCM_WEB_PORT" "3000"
    $baseUri = "http://127.0.0.1:$port"
    $handler = [System.Net.Http.HttpClientHandler]::new()
    $handler.UseCookies = $true
    $client = [System.Net.Http.HttpClient]::new($handler)
    $csrfJson = $client.GetStringAsync("$baseUri/api/v1/auth/csrf").GetAwaiter().GetResult() | ConvertFrom-Json
    $client.DefaultRequestHeaders.Add("X-CSRF-Token", [string]$csrfJson.data.csrf_token)
    $client.DefaultRequestHeaders.Add("Origin", $baseUri)
    return @{ Client = $client; BaseUri = $baseUri }
}

function Export-Workspace {
    $target = if ($Archive) { [System.IO.Path]::GetFullPath($Archive, $ProjectRoot) } else { Join-Path $ProjectRoot "compliance-control-backup.zip" }
    [System.IO.Directory]::CreateDirectory([System.IO.Path]::GetDirectoryName($target)) | Out-Null
    $api = New-LocalApiClient
    try {
        $response = $api.Client.PostAsync("$($api.BaseUri)/api/v1/exports", $null).GetAwaiter().GetResult()
        if (-not $response.IsSuccessStatusCode) { throw "Export failed with HTTP $([int]$response.StatusCode)." }
        [System.IO.File]::WriteAllBytes($target, $response.Content.ReadAsByteArrayAsync().GetAwaiter().GetResult())
        Write-Host "Backup written to $target"
    } finally { $api.Client.Dispose() }
}

function Restore-Workspace {
    if (-not $Archive) { throw "Restore requires -Archive <path>." }
    $source = [System.IO.Path]::GetFullPath($Archive, $ProjectRoot)
    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { throw "Backup archive not found: $source" }
    $api = New-LocalApiClient
    try {
        $content = [System.Net.Http.MultipartFormDataContent]::new()
        $bytes = [System.IO.File]::ReadAllBytes($source)
        $part = [System.Net.Http.ByteArrayContent]::new($bytes)
        $content.Add($part, "file", [System.IO.Path]::GetFileName($source))
        $response = $api.Client.PostAsync("$($api.BaseUri)/api/v1/exports/restore", $content).GetAwaiter().GetResult()
        if (-not $response.IsSuccessStatusCode) { throw "Restore failed with HTTP $([int]$response.StatusCode). Restore only works in an untouched workspace." }
        Write-Host "Backup restored."
    } finally { $api.Client.Dispose() }
}

Ensure-EnvironmentFile
Test-ServerConfiguration
if ($Refresh) { Invoke-LocalRefresh }

switch ($Mode) {
    "start" { Invoke-Compose -Arguments @("up", "-d", "--build"); Wait-ForApplication; Write-ServerLoginHint }
    "status" { Invoke-Compose -Arguments @("ps") }
    "down" { Invoke-Compose -Arguments @("down", "--remove-orphans") }
    "export" { Export-Workspace }
    "restore" { Restore-Workspace }
}
