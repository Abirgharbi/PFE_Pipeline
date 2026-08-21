param(
    [string]$PythonExe = "python"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$baseScript = Join-Path $scriptDir "Prepare_Manual_Files_Splits.ps1"

if (-not (Test-Path -LiteralPath $baseScript)) {
    throw "Base split script not found: $baseScript"
}

& $baseScript \
    -PythonExe $PythonExe \
    -OutputDir "datasets/07_delivery/st_ready/manual_upload/files_json_split_tuned" \
    -Pattern "st_ready_files_stm32cubeh7.json" \
    -SplitAll \
    -CleanOutput \
    -TargetParts 50 \
    -MaxPayloadKB 0
