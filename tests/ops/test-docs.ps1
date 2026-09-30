$ErrorActionPreference = "Stop"
$root = Resolve-Path "$PSScriptRoot\..\.."
$required = @(
    "README.md",
    "AGENTS.md",
    "docs/security.md",
    "docs/framework-packs.md",
    "docs/backup-and-restore.md",
    "docs/model-assistance.md",
    "docs/field-test-checklist.md",
    "agents/README.md",
    "agents/schema/agent-profile.schema.json",
    "skills/README.md",
    "skills/schema/skill-manifest.schema.json"
)

foreach ($relative in $required) {
    $path = Join-Path $root $relative
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Missing required documentation: $relative" }
}

foreach ($relative in @("agents/schema/agent-profile.schema.json", "skills/schema/skill-manifest.schema.json")) {
    $path = Join-Path $root $relative
    $schema = Get-Content -Raw -LiteralPath $path | ConvertFrom-Json
    if ($schema.additionalProperties -ne $false) { throw "$relative must reject unknown fields" }
    if ($schema.properties.enabled.type -ne "boolean") { throw "$relative enabled field must remain an explicit boolean" }
}

foreach ($relative in @(
    "agents/compliance-assistant/agent.json",
    "skills/requirement-summary-next-actions/manifest.json",
    "skills/draft-implementation-notes/manifest.json",
    "skills/draft-evidence-playbook/manifest.json",
    "skills/control-review/manifest.json"
)) {
    if (-not (Test-Path -LiteralPath (Join-Path $root $relative) -PathType Leaf)) { throw "Missing bounded assistance definition: $relative" }
}

$readme = Get-Content -Raw -LiteralPath (Join-Path $root "README.md")
if ($readme -notmatch 'Local mode: no login') { throw "Local credentials are not explicit" }
if ($readme -notmatch 'CCM_BOOTSTRAP_ADMIN_EMAIL') { throw "Server login email is not documented" }
if ($readme -notmatch 'Fresh internal deployment') { throw "Fresh deployment path is not documented" }
if ($readme -notmatch 'Promote genuine local work') { throw "Promotion path is not documented" }

$markdown = Get-ChildItem -LiteralPath $root -Filter "*.md" -File
$markdown += Get-ChildItem -LiteralPath (Join-Path $root "docs") -Filter "*.md" -File
$markdown += Get-ChildItem -LiteralPath (Join-Path $root "agents") -Filter "*.md" -File
$markdown += Get-ChildItem -LiteralPath (Join-Path $root "skills") -Filter "*.md" -File
$markdown += Get-ChildItem -LiteralPath (Join-Path $root "framework-packs\soc2") -Filter "*.md" -File

foreach ($document in $markdown) {
    $content = Get-Content -Raw -LiteralPath $document.FullName
    foreach ($match in [regex]::Matches($content, '\[[^\]]+\]\(([^)]+)\)')) {
        $target = $match.Groups[1].Value
        if ($target -match '^(https?://|mailto:|#)') { continue }
        $withoutFragment = ($target -split '#', 2)[0]
        if (-not $withoutFragment) { continue }
        $resolved = Join-Path $document.DirectoryName $withoutFragment
        if (-not (Test-Path -LiteralPath $resolved)) {
            throw "Broken local link in $($document.FullName): $target"
        }
    }
}

Write-Host "documentation contracts passed"
