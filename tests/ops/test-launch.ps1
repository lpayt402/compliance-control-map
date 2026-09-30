$ErrorActionPreference = "Stop"
$root = Resolve-Path "$PSScriptRoot\..\.."
$launcher = Join-Path $root "launch.ps1"
$shellLauncher = Join-Path $root "launch.sh"
$apiEntrypoint = Join-Path $root "docker\entrypoint-api.sh"

if (-not (Test-Path -LiteralPath $launcher)) { throw "launch.ps1 is missing" }
if (-not (Test-Path -LiteralPath $shellLauncher)) { throw "launch.sh is missing" }
if (-not (Test-Path -LiteralPath $apiEntrypoint)) { throw "API entrypoint is missing" }

$script = Get-Content -Raw -LiteralPath $launcher
$shell = Get-Content -Raw -LiteralPath $shellLauncher

if ($script -notmatch '\[switch\]\$Refresh') { throw "Launcher must expose -Refresh" }
if ($script -notmatch '\[switch\]\$Yes') { throw "Launcher must expose -Yes" }
if ($script -notmatch 'server mode cannot be refreshed') { throw "Server refresh guard is missing" }
if ($script -notmatch 'ccm_sqlite_data' -or $script -notmatch 'ccm_file_data') { throw "Refresh must name only the two local data volumes" }
if ($script -notmatch 'This permanently removes local test data') { throw "Refresh confirmation is not explicit" }
if ($shell -notmatch '--refresh' -or $shell -notmatch '--yes') { throw "Shell launcher flags are missing" }
if ($shell -notmatch 'server mode cannot be refreshed') { throw "Shell server refresh guard is missing" }
if ($script -notmatch 'CreateDirectory') { throw "PowerShell export must create its destination directory" }
if ($shell -notmatch 'mkdir -p') { throw "Shell export must create its destination directory" }
if ($script -notmatch 'Test-ServerConfiguration' -or $shell -notmatch 'check_server_configuration') { throw "Server placeholder preflight is missing" }
if ($script -notmatch 'Login email:' -or $shell -notmatch 'Login email:') { throw "Server login-email guidance is missing" }
if ($script -match 'Write-Host.+BOOTSTRAP_ADMIN_PASSWORD' -or $shell -match "printf.+BOOTSTRAP_ADMIN_PASSWORD") { throw "Launcher must not print the password" }
if ([Text.Encoding]::UTF8.GetString([IO.File]::ReadAllBytes($apiEntrypoint)).Contains("`r`n")) {
    throw "Linux API entrypoint must use LF line endings"
}

Write-Host "launcher contract passed"
