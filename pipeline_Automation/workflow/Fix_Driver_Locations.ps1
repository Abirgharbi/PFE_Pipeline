<#
.SYNOPSIS
    Moves misplaced driver repos from by_series/ root back into their correct series/drivers/ location.

.DESCRIPTION
    Some driver repos were generated directly under by_series/ instead of by_series/<series>/drivers/.
    This script detects them using a known mapping and merges their category subfolders (issues_json,
    diagnostic_cards_json, resolver_cases_json) into the correct location, preserving any existing files.

.EXAMPLE
    .\pipeline_Automation\workflow\Fix_Driver_Locations.ps1
    .\pipeline_Automation\workflow\Fix_Driver_Locations.ps1 -DryRun
#>

param(
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$ScriptDir = $PSScriptRoot
$RepoRoot  = (Resolve-Path "$ScriptDir\..\..\").Path
$BySeriesRoot = Join-Path $RepoRoot "datasets\07_delivery\st_ready\by_series"

# Mapping: misplaced repo name -> correct series folder under by_series
$Mapping = @{
    "cmsis_device_g4"      = "stm32cubeg4"
    "cmsis_device_l0"      = "stm32cubel0"
    "cmsis_device_l1"      = "stm32cubel1"
    "cmsis_device_l4"      = "stm32cubel4"
    "stm32l0xx-hal-driver" = "stm32cubel0"
    "stm32l0xx-nucleo-bsp" = "stm32cubel0"
    "stm32l1xx-hal-driver" = "stm32cubel1"
    "stm32l1xx-nucleo-bsp" = "stm32cubel1"
    "stm32l4xx-hal-driver" = "stm32cubel4"
    "stm32l4xx-nucleo-bsp" = "stm32cubel4"
}

$moved   = 0
$skipped = 0
$errors  = 0

foreach ($RepoName in $Mapping.Keys | Sort-Object) {
    $SeriesName = $Mapping[$RepoName]
    $SourceDir  = Join-Path $BySeriesRoot $RepoName
    $TargetDir  = Join-Path $BySeriesRoot "$SeriesName\drivers\$RepoName"

    if (-not (Test-Path $SourceDir)) {
        Write-Host "  [SKIP] $RepoName - source dir not found (already moved?)" -ForegroundColor DarkGray
        $skipped++
        continue
    }

    Write-Host ""
    Write-Host "Processing: $RepoName  ->  $SeriesName/drivers/$RepoName" -ForegroundColor Cyan

    # Ensure target driver dir exists
    if (-not (Test-Path $TargetDir)) {
        if (-not $DryRun) {
            New-Item -ItemType Directory -Path $TargetDir -Force | Out-Null
        }
        Write-Host "  Created target dir: $TargetDir" -ForegroundColor DarkGray
    }

    # Iterate each category subfolder in source
    $subFolders = Get-ChildItem -Path $SourceDir -Directory

    foreach ($sub in $subFolders) {
        $srcSub = $sub.FullName
        $dstSub = Join-Path $TargetDir $sub.Name

        if (-not (Test-Path $dstSub)) {
            # Target subfolder doesn't exist: move entire folder
            Write-Host "  [MOVE FOLDER] $($sub.Name) -> target" -ForegroundColor Green
            if (-not $DryRun) {
                try {
                    Move-Item -Path $srcSub -Destination $dstSub -Force
                    $moved++
                } catch {
                    Write-Warning "  ERROR moving $srcSub : $_"
                    $errors++
                }
            } else {
                Write-Host "    DRY-RUN: Move-Item '$srcSub' -> '$dstSub'" -ForegroundColor Yellow
                $moved++
            }
        } else {
            # Target subfolder exists: move individual files that are missing in target
            $srcFiles = Get-ChildItem -Path $srcSub -File
            foreach ($f in $srcFiles) {
                $dstFile = Join-Path $dstSub $f.Name
                if (-not (Test-Path $dstFile)) {
                    Write-Host "  [MOVE FILE ] $($sub.Name)/$($f.Name)" -ForegroundColor Green
                    if (-not $DryRun) {
                        try {
                            Move-Item -Path $f.FullName -Destination $dstFile -Force
                            $moved++
                        } catch {
                            Write-Warning "  ERROR moving $($f.FullName) : $_"
                            $errors++
                        }
                    } else {
                        Write-Host "    DRY-RUN: Move-Item '$($f.FullName)' -> '$dstFile'" -ForegroundColor Yellow
                        $moved++
                    }
                } else {
                    Write-Host "  [EXISTS    ] $($sub.Name)/$($f.Name) - already in target, skipping" -ForegroundColor DarkYellow
                    $skipped++
                }
            }
            # Remove the (now possibly empty) source subfolder
            if (-not $DryRun) {
                $remaining = @(Get-ChildItem -Path $srcSub)
                if ($remaining.Count -eq 0) {
                    Remove-Item -Path $srcSub -Force
                } else {
                    Write-Warning "  Source subfolder not empty after move: $srcSub"
                }
            }
        }
    }

    # Remove the source repo dir if now empty
    if (-not $DryRun) {
        $remaining = @(Get-ChildItem -Path $SourceDir)
        if ($remaining.Count -eq 0) {
            Remove-Item -Path $SourceDir -Force
            Write-Host "  Removed empty source dir: $SourceDir" -ForegroundColor DarkGray
        } else {
            Write-Warning "  Source dir NOT empty after moves: $SourceDir (remaining: $($remaining.Count) items)"
        }
    }
}

Write-Host ""
$summaryColor = "Green"
if ($errors -gt 0) {
    $summaryColor = "Red"
}
Write-Host "Done. Moved: $moved  |  Skipped: $skipped  |  Errors: $errors" -ForegroundColor $summaryColor
if ($DryRun) {
    Write-Host "(DRY-RUN - no changes applied)" -ForegroundColor Yellow
}
