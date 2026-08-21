$ErrorActionPreference = 'Stop'

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $here

$texFile = 'cmsis_cleaning_v3_concrete_examples.tex'

pdflatex -interaction=nonstopmode -halt-on-error $texFile | Out-Host
pdflatex -interaction=nonstopmode -halt-on-error $texFile | Out-Host

Write-Host "PDF generated:" (Join-Path $here 'cmsis_cleaning_v3_concrete_examples.pdf')
