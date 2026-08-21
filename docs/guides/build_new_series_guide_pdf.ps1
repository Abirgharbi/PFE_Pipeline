param(
    [string]$TexFile = "new_series_onboarding_and_runner_setup.tex"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

if (-not (Test-Path -LiteralPath $TexFile)) {
    throw "LaTeX source not found: $TexFile"
}

$pdflatex = Get-Command pdflatex -ErrorAction SilentlyContinue
if ($null -eq $pdflatex) {
    throw "pdflatex not found. Install MiKTeX or TeX Live, then re-run."
}

Write-Host "Building PDF from $TexFile ..." -ForegroundColor Cyan
& $pdflatex.Source -interaction=nonstopmode $TexFile | Out-Host
if ($LASTEXITCODE -ne 0) {
    throw "pdflatex pass 1 failed"
}

& $pdflatex.Source -interaction=nonstopmode $TexFile | Out-Host
if ($LASTEXITCODE -ne 0) {
    throw "pdflatex pass 2 failed"
}

$pdf = [System.IO.Path]::ChangeExtension($TexFile, ".pdf")
Write-Host "PDF generated: $scriptDir\$pdf" -ForegroundColor Green
