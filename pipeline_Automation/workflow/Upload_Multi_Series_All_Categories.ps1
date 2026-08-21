<#
.SYNOPSIS
    One-shot uploader for multiple STM32Cube series.

.DESCRIPTION
    Runs Upload_Series_All_Categories.ps1 sequentially for each requested series.
    Designed for "one command" execution during bulk KB upload.

.EXAMPLE
    .\pipeline_Automation\workflow\Upload_Multi_Series_All_Categories.ps1 -Series L0,L1,L4
#>

param(
    [ValidateSet("G4", "L0", "L1", "L4", "L5", "N6", "U0", "U3")]
    [string[]]$Series = @("L0", "L1", "L4"),

    [string]$RemoteUser = "abir.gharbi@st.com",
    [string]$PythonExe = "",
    [int]$KbId = 793,
    [int]$JsonSplitSize = 1000
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $repoRoot

$singleScript = Join-Path $PSScriptRoot "Upload_Series_All_Categories.ps1"
if (-not (Test-Path -LiteralPath $singleScript)) {
    throw "Missing script: $singleScript"
}

Write-Host "`n===== One-shot upload for series: $($Series -join ', ') =====" -ForegroundColor Cyan

$failures = @()
foreach ($s in $Series) {
    Write-Host "`n----- Running series $s -----" -ForegroundColor Cyan
    try {
        & $singleScript `
            -Series $s `
            -RemoteUser $RemoteUser `
            -PythonExe $PythonExe `
            -KbId $KbId `
            -JsonSplitSize $JsonSplitSize

        if ($LASTEXITCODE -ne 0) {
            throw "Series $s failed with exit code $LASTEXITCODE"
        }
    }
    catch {
        Write-Host "`n[FAILED] Series $s" -ForegroundColor Red
        $_.Exception.Message -split "`n" | ForEach-Object { Write-Host "  $_" -ForegroundColor Red }
        $failures += $s
    }
}

if ($failures.Count -gt 0) {
    throw "One-shot upload completed with failures for series: $($failures -join ', ')"
}

Write-Host "`n===== One-shot upload completed successfully =====" -ForegroundColor Green
