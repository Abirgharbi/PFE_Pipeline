param(
    [string]$PythonExe = "python",
    [switch]$WithSimilarity,
    [switch]$WithChunking
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $repoRoot

function Run-Step {
    param(
        [string]$Label,
        [string[]]$CmdArgs
    )

    Write-Host "\n=== $Label ==="
    if (-not $CmdArgs -or $CmdArgs.Count -eq 0) {
        throw "Run-Step '$Label' called without python arguments"
    }

    & $PythonExe @CmdArgs
    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed with exit code $LASTEXITCODE"
    }
}

Run-Step -Label "Cleaning issues" -CmdArgs @("-m", "pipeline.cleaning.clean_issues")
Run-Step -Label "Enrichment issues V2" -CmdArgs @("-m", "pipeline.enrichment.issues_to_docs_v2")

if ($WithSimilarity) {
    Run-Step -Label "Similarity issues V2" -CmdArgs @("-m", "pipeline.similarity.compute_issue_similarity_v2")
}

if ($WithChunking) {
    Run-Step -Label "Chunking issues V2" -CmdArgs @("-m", "pipeline.chunking.docs_to_chunks_issues_v2")
}

Run-Step -Label "Export ST-ready issues" -CmdArgs @("-m", "pipeline.delivery.export_st_ready_issues")

Write-Host "\nDone: issues pipeline completed for all repos in config."
