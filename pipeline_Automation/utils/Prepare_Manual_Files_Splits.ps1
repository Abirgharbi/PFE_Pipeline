param(
    [string]$PythonExe = "python",
    [string]$InputDir = "datasets/07_delivery/st_ready/files_json",
    [string]$OutputDir = "datasets/07_delivery/st_ready/manual_upload/files_json_split",
    [string]$Pattern = "st_ready_files_*.json",
    [double]$MinSourceSizeKB = 350,
    [int]$MaxDocsPerPart = 8,
    [int]$MaxPayloadKB = 220,
    [int]$TargetParts = 0,
    [switch]$SplitAll,
    [switch]$CleanOutput
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $repoRoot

$cmdArgs = @(
    "-m", "pipeline.delivery.split_st_ready_files_for_manual_upload",
    "--input-dir", $InputDir,
    "--output-dir", $OutputDir,
    "--pattern", $Pattern,
    "--min-source-size-kb", $MinSourceSizeKB,
    "--max-docs-per-part", $MaxDocsPerPart,
    "--max-payload-kb", $MaxPayloadKB
)

if ($TargetParts -gt 0) {
    $cmdArgs += @("--target-parts", $TargetParts)
}

if ($SplitAll) {
    $cmdArgs += "--split-all"
}

if ($CleanOutput) {
    $cmdArgs += "--clean-output"
}

Write-Host "\n=== Prepare manual split files_json payloads ==="
& $PythonExe @cmdArgs
if ($LASTEXITCODE -ne 0) {
    throw "Manual files split failed with exit code $LASTEXITCODE"
}

Write-Host "\nDone: manual split files are ready in $OutputDir"
