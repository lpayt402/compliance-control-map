$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Assert-Ccm {
    param([bool]$Condition, [string]$Message)
    if (-not $Condition) { throw $Message }
}

function Get-CcmFreePort {
    $listener = [System.Net.Sockets.TcpListener]::new(
        [System.Net.IPAddress]::Loopback,
        0
    )
    $listener.Start()
    try { return ([System.Net.IPEndPoint]$listener.LocalEndpoint).Port }
    finally { $listener.Stop() }
}

function Invoke-CcmCompose {
    param(
        [string]$Project,
        [string[]]$Files,
        [string[]]$Arguments
    )
    $dockerArguments = @("compose", "-p", $Project)
    foreach ($file in $Files) { $dockerArguments += @("-f", $file) }
    $dockerArguments += $Arguments
    & docker @dockerArguments
    if ($LASTEXITCODE -ne 0) {
        throw "docker compose failed for isolated project '$Project'."
    }
}

function Wait-CcmUrl {
    param([string]$Url, [int]$TimeoutSeconds = 120)
    $deadline = [DateTimeOffset]::UtcNow.AddSeconds($TimeoutSeconds)
    do {
        try {
            $response = Invoke-WebRequest -Uri $Url -TimeoutSec 4 -SkipHttpErrorCheck
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) { return }
        } catch {
            # The container can accept connections a moment after its health check begins.
        }
        Start-Sleep -Milliseconds 750
    } while ([DateTimeOffset]::UtcNow -lt $deadline)
    throw "Timed out waiting for $Url"
}

function New-CcmSession {
    param([string]$BaseUrl)
    $session = [Microsoft.PowerShell.Commands.WebRequestSession]::new()
    $response = Invoke-RestMethod -Uri "$BaseUrl/api/v1/auth/csrf" -WebSession $session
    return @{
        Session = $session
        Token = [string]$response.data.csrf_token
    }
}

function Invoke-CcmJson {
    param(
        [ValidateSet("GET", "POST", "PATCH", "PUT", "DELETE")]
        [string]$Method,
        [string]$Uri,
        [Microsoft.PowerShell.Commands.WebRequestSession]$Session,
        [string]$Token = "",
        [string]$Origin = "",
        [object]$Body = $null
    )
    $request = @{
        Uri = $Uri
        Method = $Method
        WebSession = $Session
    }
    if ($Method -in @("POST", "PATCH", "PUT", "DELETE")) {
        $request.Headers = @{
            "X-CSRF-Token" = $Token
            "Origin" = $Origin
        }
    }
    if ($null -ne $Body) {
        $request.ContentType = "application/json"
        $request.Body = ConvertTo-Json -InputObject $Body -Depth 12 -Compress
    }
    return Invoke-RestMethod @request
}

function Connect-CcmUser {
    param([string]$BaseUrl, [string]$Email, [string]$Password)
    $client = New-CcmSession -BaseUrl $BaseUrl
    $login = Invoke-CcmJson -Method POST -Uri "$BaseUrl/api/v1/auth/login" `
        -Session $client.Session -Token $client.Token -Origin $BaseUrl `
        -Body @{ email = $Email; password = $Password }
    $client.Token = [string]$login.data.csrf_token
    return $client
}

function Invoke-CcmMultipartUpload {
    param(
        [string]$Uri,
        [string]$Origin,
        [Microsoft.PowerShell.Commands.WebRequestSession]$Session,
        [string]$Token,
        [string]$FilePath,
        [string]$MediaType,
        [hashtable]$Fields
    )
    $cookieHeader = @(
        $Session.Cookies.GetCookies([Uri]$Origin) |
            ForEach-Object { "$($_.Name)=$($_.Value)" }
    ) -join "; "
    $arguments = @(
        "--silent", "--show-error", "--fail-with-body",
        "--request", "POST",
        "--header", "Origin: $Origin",
        "--header", "X-CSRF-Token: $Token",
        "--cookie", $cookieHeader
    )
    foreach ($name in @($Fields.Keys | Sort-Object)) {
        $arguments += @("--form", "$name=$($Fields[$name])")
    }
    $arguments += @("--form", "file=@$FilePath;type=$MediaType", $Uri)
    $json = & curl.exe @arguments
    if ($LASTEXITCODE -ne 0) { throw "Multipart upload failed for $Uri" }
    return $json | ConvertFrom-Json
}

function Remove-CcmComposeProject {
    param([string]$Project, [string[]]$Files)
    $volumeNames = @(
        & docker volume ls --filter "label=com.docker.compose.project=$Project" --format "{{.Name}}"
    )
    if ($LASTEXITCODE -ne 0) { throw "Could not inspect Docker volumes for '$Project'." }
    foreach ($volumeName in $volumeNames) {
        $metadata = @(& docker volume inspect $volumeName | ConvertFrom-Json)[0]
        Assert-Ccm `
            ($metadata.Labels.'com.docker.compose.project' -eq $Project) `
            "Refusing to remove volume '$volumeName': project label mismatch."
    }
    Invoke-CcmCompose -Project $Project -Files $Files `
        -Arguments @("down", "--volumes", "--remove-orphans")
}
