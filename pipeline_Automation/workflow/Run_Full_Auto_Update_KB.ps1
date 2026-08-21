<#
.SYNOPSIS
    Full automated pipeline: Ingestion → Preprocessing → Export → Validation → KB Upload.
    Keeps the ST GitHub Analyzer persona always up-to-date.

.DESCRIPTION
    This script chains all pipeline stages for all configured MCU series,
    validates outputs, and uploads to KB #793 datasources.

    Run weekly (Task Scheduler) or on-demand after major firmware releases.

.PARAMETER Series
    MCU series to process. Default: all (f4, h5, h7, u5, wl).

.PARAMETER SkipIngestion
    Reuse existing raw data (faster re-processing).

.PARAMETER SkipUpload
    Run pipeline only, do not upload to KB.

.PARAMETER ApiKey
    ST AI Bridge API key. Falls back to ST_CHATGPT_API_KEY env var.

.PARAMETER RemoteUser
    Email for API authentication.

.EXAMPLE
    .\Run_Full_Auto_Update_KB.ps1 -RemoteUser "abir.gharbi@st.com"
    .\Run_Full_Auto_Update_KB.ps1 -Series f4,h5 -SkipIngestion
    .\Run_Full_Auto_Update_KB.ps1 -Series h7 -SkipUpload
#>

param(
    [string[]]$Series = @(),
    [string]$PythonExe = "python",
    [int]$KbId = 793,
    [string]$RemoteUser = "",
    [string]$ApiKey = "",
    [switch]$SkipIngestion,
    [switch]$SkipUpload,
    [switch]$ContinueOnError,
    [int]$JsonSplitSize = 1000,
    [switch]$EnableIssuesByComponentFlow,
    [switch]$ComponentIssuesOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $repoRoot

$globalConfigPath = Join-Path $repoRoot "shared/config/config_all_series.json"
if (-not (Test-Path -LiteralPath $globalConfigPath)) {
    throw "Missing global series config: $globalConfigPath"
}

$cfgAll = ((Get-Content -LiteralPath $globalConfigPath -Raw).TrimStart([char]0xFEFF)) | ConvertFrom-Json
$seriesSlugMap = @{}
foreach ($seriesFull in @($cfgAll.all_series)) {
    $name = [string]$seriesFull
    if (-not $name.StartsWith("STM32Cube")) {
        continue
    }
    $seriesCode = $name.Substring(9).ToUpperInvariant()
    $seriesSlugMap[$seriesCode] = $name.ToLowerInvariant()
}

if ($seriesSlugMap.Count -eq 0) {
    throw "No valid STM32Cube series found in: $globalConfigPath"
}

$normalizedSeries = @()
if ($Series.Count -eq 0) {
    $normalizedSeries = @($seriesSlugMap.Keys | Sort-Object)
} else {
    foreach ($item in $Series) {
        $raw = [string]$item
        if ([string]::IsNullOrWhiteSpace($raw)) {
            continue
        }
        if ($raw.StartsWith("STM32Cube")) {
            $code = $raw.Substring(9).ToUpperInvariant()
        } else {
            $code = $raw.ToUpperInvariant()
        }
        $normalizedSeries += $code
    }
}

$normalizedSeries = @($normalizedSeries | Select-Object -Unique)
foreach ($s in $normalizedSeries) {
    if (-not $seriesSlugMap.ContainsKey($s)) {
        $allowed = ($seriesSlugMap.Keys | Sort-Object) -join ", "
        throw "Unsupported series '$s'. Allowed (from config_all_series.json): $allowed"
    }
}

$Series = $normalizedSeries

$timestamp = Get-Date -Format "yyyy-MM-dd_HH-mm"
$logDir = Join-Path $repoRoot "logs"
New-Item -ItemType Directory -Force $logDir | Out-Null
$logFile = Join-Path $logDir "auto_update_kb_$timestamp.log"

function Log {
    param([string]$Message, [string]$Level = "INFO")
    $entry = "[$Level] $(Get-Date -Format 'HH:mm:ss') $Message"
    Write-Host $entry
    Add-Content -Path $logFile -Value $entry
}

function Run-Step {
    param([string]$Label, [string[]]$CmdArgs)
    Log "=== $Label ==="
    & $PythonExe @CmdArgs 2>&1 | Tee-Object -Append -FilePath $logFile
    if ($LASTEXITCODE -ne 0) {
        if ($ContinueOnError) {
            Log "$Label FAILED (exit code $LASTEXITCODE) - continuing" "WARN"
            return $false
        }
        throw "$Label failed with exit code $LASTEXITCODE"
    }
    Log "$Label completed successfully"
    return $true
}

function Run-PowerShellStep {
    param([string]$Label, [string[]]$CmdArgs)
    Log "=== $Label ==="
    & powershell @CmdArgs 2>&1 | Tee-Object -Append -FilePath $logFile
    if ($LASTEXITCODE -ne 0) {
        if ($ContinueOnError) {
            Log "$Label FAILED (exit code $LASTEXITCODE) - continuing" "WARN"
            return $false
        }
        throw "$Label failed with exit code $LASTEXITCODE"
    }
    Log "$Label completed successfully"
    return $true
}

# ============================================================
# STEP 1: Full pipeline (ingestion + preprocessing + export)
# ============================================================
Log "Starting full auto-update for series: $($Series -join ', ')"

$pipelineArgs = @("-m", "pipeline_Automation.workflow.run_all_series", "--series") + $Series + @("--export-st-ready", "--skip-chunking")

if ($SkipIngestion) {
    $pipelineArgs += "--skip-ingestion"
}
if ($ContinueOnError) {
    $pipelineArgs += "--continue-on-error"
}

$pipelineOk = Run-Step -Label "Full Pipeline (all series)" -CmdArgs $pipelineArgs

if (-not $pipelineOk -and -not $ContinueOnError) {
    Log "Pipeline failed. Aborting." "ERROR"
    exit 1
}

# ============================================================
# STEP 2: Schema Validation Gate
# ============================================================
$validationOk = Run-Step -Label "Schema Validation" -CmdArgs @("-m", "pipeline.evaluation.validate_schemas")

if (-not $validationOk) {
    Log "Schema validation FAILED. KB upload blocked." "ERROR"
    if (-not $ContinueOnError) { exit 2 }
}

# ============================================================
# STEP 3: Upload to KB (if not skipped and validation passed)
# ============================================================
if ($SkipUpload) {
    Log "Upload skipped (--SkipUpload flag)."
} elseif (-not $validationOk) {
    Log "Upload skipped due to validation failure."
} else {
    Log "Starting KB upload..."

    $artifactTypes = @(
        @{ type = "issues";     dir = "issues_json";           pattern = "st_ready_issues_*.json";           rootTag = "issues" }
        @{ type = "files";      dir = "files_json";            pattern = "st_ready_files_*.json";            rootTag = "files" }
        @{ type = "resolver";   dir = "resolver_cases_json";   pattern = "st_ready_resolver_cases_*.json";   rootTag = "resolver_cases" }
        @{ type = "diagnostic"; dir = "diagnostic_cards_json"; pattern = "st_ready_diagnostic_cards_*.json"; rootTag = "diagnostic_cards" }
    )

    $uploaderScript = Join-Path $repoRoot "pipeline_Automation\upload\Add_Data_Source_Files.py"

    function Get-OptionalPositiveIntValue {
        param(
            [AllowNull()][object]$Target,
            [Parameter(Mandatory = $true)][string]$Name
        )

        if ($null -eq $Target) {
            return 0
        }
        $prop = $Target.PSObject.Properties[$Name]
        if ($null -eq $prop -or $null -eq $prop.Value) {
            return 0
        }
        $parsed = 0
        if ([int]::TryParse([string]$prop.Value, [ref]$parsed) -and $parsed -gt 0) {
            return $parsed
        }
        return 0
    }

    foreach ($s in $Series) {
        $seriesCode = [string]$s
        $seriesKey = "STM32Cube$seriesCode"
        $slug = $seriesSlugMap[$seriesCode]
        $seriesDir = Join-Path $repoRoot "datasets\07_delivery\st_ready\by_series\$slug"

        $idsEntry = $null
        if ($null -ne $cfgAll.kb_datasource_ids) {
            $idsProp = $cfgAll.kb_datasource_ids.PSObject.Properties[$seriesKey]
            if ($null -ne $idsProp) {
                $idsEntry = $idsProp.Value
            }
        }

        if (-not (Test-Path $seriesDir)) {
            Log "Series directory not found: $seriesDir - skipping" "WARN"
            continue
        }

        foreach ($artifact in $artifactTypes) {
            if ($ComponentIssuesOnly -and $artifact.type -eq "issues") {
                Log "Skipping monolithic issues upload for $seriesCode due to -ComponentIssuesOnly"
                continue
            }

            $artifactKey = if ($artifact.type -eq "diagnostic") { "diagnostic" } else { $artifact.type }
            $dsId = Get-OptionalPositiveIntValue -Target $idsEntry -Name $artifactKey
            if ($dsId -le 0) {
                Log "No datasource ID configured for $seriesKey/$($artifact.type) in config_all_series.json - skipping" "WARN"
                continue
            }

            $artifactDir = Join-Path $seriesDir $artifact.dir
            $files = @(Get-ChildItem -Path $artifactDir -Filter $artifact.pattern -File -ErrorAction SilentlyContinue)

            if ($files.Count -eq 0) {
                Log "No $($artifact.type) files for $seriesCode - skipping" "WARN"
                continue
            }

            $inputPath = $files[0].FullName
            $uploadArgs = @(
                $uploaderScript,
                "--input", $inputPath,
                "--datasource-id", $dsId,
                "--type", "kb-datasource-add",
                "--root-tag-path", $artifact.rootTag,
                "--json-split-size", $JsonSplitSize
            )

            if ($ApiKey) {
                $uploadArgs += @("--api-key", $ApiKey)
            }
            if ($RemoteUser) {
                $uploadArgs += @("--remote-user", $RemoteUser)
            }

            Run-Step -Label "Upload $seriesCode $($artifact.type) (DS#$dsId)" -CmdArgs $uploadArgs
        }

        if ($EnableIssuesByComponentFlow) {
            $seriesUpper = $s.ToUpperInvariant()
            $splitScript = Join-Path $repoRoot "pipeline_Automation/workflow/Split_Issues_By_Component.ps1"
            $uploadScript = Join-Path $repoRoot "pipeline_Automation/workflow/Upload_Issues_By_Component.ps1"

            Run-PowerShellStep -Label "Split issues by component ($seriesUpper)" -CmdArgs @(
                "-ExecutionPolicy", "Bypass",
                "-File", $splitScript,
                "-Series", $seriesUpper,
                "-PythonExe", $PythonExe
            ) | Out-Null

            $uploadPsArgs = @(
                "-ExecutionPolicy", "Bypass",
                "-File", $uploadScript,
                "-Series", $seriesUpper,
                "-PythonExe", $PythonExe,
                "-KbId", "$KbId",
                "-JsonSplitSize", "$JsonSplitSize"
            )
            if ($RemoteUser) {
                $uploadPsArgs += @("-RemoteUser", $RemoteUser)
            }
            Run-PowerShellStep -Label "Upload issues by component ($seriesUpper)" -CmdArgs $uploadPsArgs | Out-Null
        }
    }
}

# ============================================================
# SUMMARY
# ============================================================
Log "============================================"
Log "AUTO-UPDATE COMPLETE"
Log "  Series processed: $($Series -join ', ')"
Log "  Pipeline: $(if ($pipelineOk) {'OK'} else {'FAILED'})"
Log "  Validation: $(if ($validationOk) {'PASS'} else {'FAIL'})"
Log "  Upload: $(if ($SkipUpload) {'SKIPPED'} else {'DONE'})"
Log "  Log: $logFile"
Log "============================================"
