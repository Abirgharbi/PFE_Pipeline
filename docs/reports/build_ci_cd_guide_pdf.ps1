param(
    [string]$TexFile = "CI_CD_Workflows_Architecture_Guide.tex"
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location $scriptDir

try {
    if (-not (Get-Command pdflatex -ErrorAction SilentlyContinue)) {
        throw "pdflatex not found in PATH. Install a LaTeX distribution (TeX Live or MiKTeX) and retry."
    }

    Write-Host "Compiling $TexFile (pass 1)..."
    & pdflatex -interaction=nonstopmode -halt-on-error $TexFile | Out-Null

    Write-Host "Compiling $TexFile (pass 2)..."
    & pdflatex -interaction=nonstopmode -halt-on-error $TexFile | Out-Null

    $pdf = [System.IO.Path]::ChangeExtension($TexFile, ".pdf")
    if (-not (Test-Path $pdf)) {
        throw "Compilation finished but PDF was not generated."
    }

    Write-Host "PDF generated: $scriptDir\$pdf"
}
finally {
    Pop-Location
}
