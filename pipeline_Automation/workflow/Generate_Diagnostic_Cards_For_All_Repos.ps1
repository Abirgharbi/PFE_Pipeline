param(
    [string]$PythonExe = "python",
    [string[]]$Repos,
    [switch]$IncludeAllIssues
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $repoRoot

$cmdArgs = @("-m", "pipeline.delivery.export_st_ready_diagnostic_cards")

if ($IncludeAllIssues) {
    $cmdArgs += "--include-all-issues"
}

if ($Repos) {
    foreach ($repo in $Repos) {
        if ($repo) {
            $cmdArgs += @("--repo", $repo)
        }
    }
}

Write-Host "\n=== Export ST-ready diagnostic cards ==="
& $PythonExe @cmdArgs
if ($LASTEXITCODE -ne 0) {
    throw "Diagnostic cards export failed with exit code $LASTEXITCODE"
}

Write-Host "\nDone: ST-ready diagnostic cards exported."