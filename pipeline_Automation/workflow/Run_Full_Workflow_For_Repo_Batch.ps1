param(
    [string]$PythonExe = "python",
    [string[]]$Repos = @("STM32CubeF4", "STM32CubeH5", "STM32CubeU5", "STM32CubeWL"),
    [switch]$SkipIngestion,
    [switch]$ContinueOnError,
    [switch]$NoExportStReady
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $repoRoot

$configPath = Join-Path $repoRoot "shared/config/config.json"
if (-not (Test-Path $configPath)) {
    throw "Config not found at $configPath"
}

$originalConfigJson = Get-Content -Raw -Encoding utf8 $configPath

try {
    $cfg = $originalConfigJson | ConvertFrom-Json
    if (-not $cfg) {
        throw "Unable to parse JSON config at $configPath"
    }

    $cfg.repos = @($Repos)
    $batchConfigJson = $cfg | ConvertTo-Json -Depth 100
    [System.IO.File]::WriteAllText($configPath, $batchConfigJson, (New-Object System.Text.UTF8Encoding $false))

    Write-Host "Using repo batch:" -ForegroundColor Cyan
    foreach ($repo in $Repos) {
        Write-Host " - $repo"
    }

    $cmdArgs = @("-m", "pipeline.run_full_workflow")
    if ($SkipIngestion) {
        $cmdArgs += "--skip-ingestion"
    }
    if ($ContinueOnError) {
        $cmdArgs += "--continue-on-error"
    }
    if (-not $NoExportStReady) {
        $cmdArgs += "--export-st-ready"
    }

    Write-Host "`nRunning: $PythonExe $($cmdArgs -join ' ')" -ForegroundColor Cyan
    & $PythonExe @cmdArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Workflow failed with exit code $LASTEXITCODE"
    }

    Write-Host "`nBatch workflow completed successfully." -ForegroundColor Green
}
finally {
    [System.IO.File]::WriteAllText($configPath, $originalConfigJson, (New-Object System.Text.UTF8Encoding $false))
    Write-Host "Config restored: $configPath" -ForegroundColor Yellow
}
