$ErrorActionPreference = "Stop"
$root = Resolve-Path "$PSScriptRoot\..\.."
$localPath = Join-Path $root "docker-compose.yml"
$serverPath = Join-Path $root "docker-compose.server.yml"
$apiDockerfilePath = Join-Path $root "backend/Dockerfile"
$testDockerfilePath = Join-Path $root "backend/Dockerfile.test"
$nginxPath = Join-Path $root "docker/nginx.conf"

if (-not (Test-Path -LiteralPath $localPath)) { throw "docker-compose.yml is missing" }
if (-not (Test-Path -LiteralPath $serverPath)) { throw "docker-compose.server.yml is missing" }

$local = Get-Content -Raw -LiteralPath $localPath
$server = Get-Content -Raw -LiteralPath $serverPath
$apiDockerfile = Get-Content -Raw -LiteralPath $apiDockerfilePath
$testDockerfile = Get-Content -Raw -LiteralPath $testDockerfilePath
$nginx = Get-Content -Raw -LiteralPath $nginxPath

if ($local -notmatch '127\.0\.0\.1:\$\{CCM_WEB_PORT:-3000\}:8080') { throw "Local mode must publish only loopback port 3000" }
if ($local -notmatch 'ccm_sqlite_data:' -or $local -notmatch 'ccm_file_data:') { throw "Named local volumes are missing" }
if ($local -notmatch 'condition: service_healthy') { throw "Web must wait for API health" }
if ($local -notmatch 'CCM_AUTH_MODE: disabled') { throw "Local auth default is not explicit" }
if ($local -notmatch 'CCM_ALLOWED_ORIGINS:') { throw "Local CSRF origins must follow configuration" }
if ($local -notmatch 'host\.docker\.internal:host-gateway') { throw "API container must be able to reach an explicitly allowlisted host provider" }
if ($local -notmatch 'CCM_INFERENCE_ENABLED:') { throw "Inference kill switch must be explicit in Compose" }
if ($local -notmatch 'CCM_INFERENCE_ALLOWED_BASE_URLS:') { throw "Inference destination allowlist must be explicit in Compose" }
if ($server -notmatch 'postgres:') { throw "Server overlay must add PostgreSQL" }
if ($server -notmatch 'CCM_AUTH_MODE: local') { throw "Server overlay must enable local authentication" }
if ($server -notmatch 'CCM_POSTGRES_PASSWORD') { throw "PostgreSQL password must come from the environment" }
if ($server -notmatch 'CCM_BOOTSTRAP_ADMIN_EMAIL: \$\{CCM_BOOTSTRAP_ADMIN_EMAIL:-\}') { throw "Server restarts must allow the cleared bootstrap email" }
if ($server -notmatch 'CCM_BOOTSTRAP_ADMIN_PASSWORD: \$\{CCM_BOOTSTRAP_ADMIN_PASSWORD:-\}') { throw "Server restarts must allow the cleared bootstrap password" }
if ($server -notmatch 'CCM_ALLOWED_ORIGINS' -or $server -notmatch 'CCM_ALLOWED_HOSTS') { throw "Server origin and host allowlists must be explicit" }
if ($server -notmatch 'ccm_postgres_data:') { throw "PostgreSQL persistence volume is missing" }
if ($apiDockerfile -notmatch 'COPY agents /app/agents' -or $apiDockerfile -notmatch 'COPY skills /app/skills') { throw "Runtime agent and skill definitions are missing from the API image" }
if ($testDockerfile -notmatch 'COPY agents /workspace/agents' -or $testDockerfile -notmatch 'COPY skills /workspace/skills') { throw "Runtime agent and skill definitions are missing from the backend test image" }
if ($nginx -notmatch 'location = /api/v1/inference/runs/stream' -or $nginx -notmatch 'proxy_buffering off') { throw "Inference streaming proxy contract is missing" }

Write-Host "compose contract passed"
