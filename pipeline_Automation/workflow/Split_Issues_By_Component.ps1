<#
.SYNOPSIS
    Split ST-ready issues JSON by peripheral/component for one series or all series.

.DESCRIPTION
    - Reads ST-ready issues-with-images JSON (prefers Alfred-enriched files).
    - Creates per-component JSON files in issues_json/by_component.
    - Does not modify existing export files.

.EXAMPLES
    .\Split_Issues_By_Component.ps1 -Series H7
    .\Split_Issues_By_Component.ps1 -AllSeries
#>

param(
    [string]$Series,

    [switch]$AllSeries,
    [string]$PythonExe = "",
    [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $repoRoot

$cfgAllPath = "shared/config/config_all_series.json"
$cfgAll = Get-Content -LiteralPath $cfgAllPath -Raw | ConvertFrom-Json
$seriesMap = @{}
foreach ($seriesFull in @($cfgAll.all_series)) {
    $name = [string]$seriesFull
    if (-not $name.StartsWith("STM32Cube")) {
        continue
    }
    $seriesCode = $name.Substring(9).ToUpperInvariant()
    $seriesMap[$seriesCode] = $name.ToLowerInvariant()
}

if (-not $AllSeries -and -not $Series) {
    throw "Use -Series <name> or -AllSeries."
}

if (-not $AllSeries) {
    $Series = $Series.ToUpperInvariant()
    if (-not $seriesMap.ContainsKey($Series)) {
        $allowed = ($seriesMap.Keys | Sort-Object) -join ", "
        throw "Unsupported series '$Series'. Allowed (from $cfgAllPath): $allowed"
    }
}

if (-not $PythonExe) {
    $venvPy = Join-Path $repoRoot ".venv\Scripts\python.exe"
    if (Test-Path -LiteralPath $venvPy) {
        $PythonExe = $venvPy
    } else {
        $PythonExe = "python"
    }
}

$splitScript = "pipeline/delivery/split_st_ready_issues_by_component.py"
$splitModule = "pipeline.delivery.split_st_ready_issues_by_component"
if (-not (Test-Path -LiteralPath $splitScript)) {
    throw "Missing script: $splitScript"
}

function Invoke-Split {
    param([string]$Slug)

    $seriesRoot = "datasets/07_delivery/st_ready/by_series/$Slug"
    if (-not (Test-Path -LiteralPath $seriesRoot)) {
        Write-Host "[skip] series delivery root not found for $Slug" -ForegroundColor Yellow
        return
    }

    # Split every matching issues payload under the whole series tree
    # (root repo + drivers/subrepos), not only the root issues_json folder.
    $args = @("-m", $splitModule, "--input-root", $seriesRoot)
    if ($DryRun) {
        $args += "--dry-run"
    }

    Write-Host "[split] $Slug -> $seriesRoot" -ForegroundColor Cyan
    & $PythonExe @args
    if ($LASTEXITCODE -ne 0) {
        throw "Split failed for $Slug"
    }
}

$targets = @()
if ($AllSeries) {
    $targets = $seriesMap.Values | Sort-Object -Unique
} else {
    $targets = @($seriesMap[$Series])
}

foreach ($slug in $targets) {
    Invoke-Split -Slug $slug
}

Write-Host "Split by component completed." -ForegroundColor Green
