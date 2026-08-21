<#
.SYNOPSIS
    Run the complete STM32Cube preprocessing pipeline and KB upload for one series.

.DESCRIPTION
    One debuggable command per series:
      1. sync parent repo and audit/fix submodule repos in config files
            2. run the full preprocessing workflow with Alfred PDF enrichment
            3. export ST-ready issues/resolver/diagnostic and V3 files for parent and subrepos
            4. run Alfred issue image enrichment for every issue-image JSON under the series
            5. patch Alfred PDF descriptions into root and driver delivery files
            6. validate schemas and fail on unresolved image/PDF placeholders
            7. create KB datasources with operation new, or add to existing IDs when provided
            8. upload driver/subrepo issues/files/diagnostic/resolver outputs into the parent series datasources

.EXAMPLES
    .\pipeline_Automation\workflow\Run_Single_Series_Full_Pipeline_And_Upload.ps1 -Series G4
    .\pipeline_Automation\workflow\Run_Single_Series_Full_Pipeline_And_Upload.ps1 -Series L0 -Mode Prepare
    .\pipeline_Automation\workflow\Run_Single_Series_Full_Pipeline_And_Upload.ps1 -Series L4 -Mode Upload -SkipDrivers
#>

param(
    [Parameter(Mandatory = $true)]
    [string]$Series,

    [ValidateSet("Full", "Prepare", "Upload")]
    [string]$Mode = "Full",

    [string]$RemoteUser = "abir.gharbi@st.com",
    [string]$ApiKey = "",
    [string]$ClientAppName = "",
    [int]$KbId = 793,
    [string]$PythonExe = "",
    [int]$JsonSplitSize = 1000,
    [int]$IssuesDatasourceId = 0,
    [int]$FilesDatasourceId = 0,
    [int]$DiagnosticDatasourceId = 0,
    [int]$ResolverDatasourceId = 0,
    [switch]$SkipDrivers,
    [switch]$SkipSchemaValidation,
    [switch]$ContinueOnWorkflowError,
    [ValidateSet("Replace", "Add")]
    [string]$ExistingDatasourceMode = "Replace",
    [ValidateSet("Fail", "Warn", "Off")]
    [string]$PlaceholderPolicy = "Fail",
    [switch]$SkipAlfredEnrichment,
    [switch]$SkipPlaceholderGate,
    [switch]$RunAlfredBeforeUpload,
    [switch]$UseAlfredProxy,
    [switch]$EnableIssuesByComponentFlow,
    [switch]$ComponentIssuesOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $repoRoot
$globalConfigPath = "shared/config/config_all_series.json"

# Auto-detect venv python if not specified.
if (-not $PythonExe) {
    $venvPy = Join-Path $repoRoot ".venv\Scripts\python.exe"
    if (Test-Path -LiteralPath $venvPy) {
        $PythonExe = $venvPy
        Write-Host "Using venv python: $PythonExe" -ForegroundColor DarkCyan
    } else {
        $PythonExe = "python"
        Write-Host "Warning: .venv not found, using system python" -ForegroundColor Yellow
    }
}

$cfgAll = ((Get-Content -LiteralPath $globalConfigPath -Raw).TrimStart([char]0xFEFF)) | ConvertFrom-Json
$seriesMap = @{}
foreach ($seriesFull in @($cfgAll.all_series)) {
    $name = [string]$seriesFull
    if (-not $name.StartsWith("STM32Cube")) {
        continue
    }
    $seriesCode = $name.Substring(9).ToUpperInvariant()
    $cfgFile = $cfgAll.series_config_files.$name
    if (-not $cfgFile) {
        continue
    }
    $seriesMap[$seriesCode] = @{
        Slug = $name.ToLowerInvariant()
        Repo = $name
        Config = "shared/config/$cfgFile"
    }
}

$Series = $Series.ToUpperInvariant()
if (-not $seriesMap.ContainsKey($Series)) {
    $allowed = ($seriesMap.Keys | Sort-Object) -join ", "
    throw "Unsupported series '$Series'. Allowed (from $globalConfigPath): $allowed"
}

$seriesInfo = $seriesMap[$Series]
$slug = $seriesInfo.Slug
$seriesRepo = $seriesInfo.Repo
$configPath = $seriesInfo.Config
$deliveryRoot = "datasets/07_delivery/st_ready/by_series/$slug"
$uploader = "pipeline_Automation/upload/Add_Data_Source_Files.py"
$idsOutput = Join-Path $deliveryRoot "upload_datasource_ids_$slug.json"
$uploadMaxRetries = 5
$uploadTimeoutSeconds = 60
$script:EffectiveDatasourceMode = $ExistingDatasourceMode

function ConvertFrom-JsonSafeText {
    param(
        [AllowNull()]
        [string]$RawText,
        [string]$Source = "JSON payload"
    )

    if ([string]::IsNullOrWhiteSpace($RawText)) {
        throw "Invalid or empty JSON in ${Source}."
    }

    # Strip UTF-8 BOM if present. PowerShell 5 Set-Content -Encoding UTF8 writes BOM.
    $normalized = $RawText.TrimStart([char]0xFEFF)
    return $normalized | ConvertFrom-Json
}

function Get-UploadAuthArgs {
    $authArgs = @()
    if ($ApiKey) {
        $authArgs += @("--api-key", $ApiKey)
    }
    if ($ClientAppName) {
        $authArgs += @("--client-app-name", $ClientAppName)
    }
    return $authArgs
}

function Invoke-Step {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Label,
        [Parameter(Mandatory = $true)]
        [string[]]$Args
    )

    Write-Host "`n===== $Label =====" -ForegroundColor Cyan
    Write-Host ($Args -join " ") -ForegroundColor DarkGray
    $pythonArgs = @("-u") + $Args
    & $PythonExe @pythonArgs
    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed with exit code $LASTEXITCODE"
    }
}

function Invoke-CapturedPython {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Label,
        [Parameter(Mandatory = $true)]
        [string[]]$Args
    )

    Write-Host "`n===== $Label =====" -ForegroundColor Cyan
    Write-Host ($Args -join " ") -ForegroundColor DarkGray

    $tmpOut = [System.IO.Path]::GetTempFileName()
    $tmpErr = [System.IO.Path]::GetTempFileName()

    try {
        $pythonArgs = @("-u") + $Args
        $argLine = ($pythonArgs | ForEach-Object {
            if ($_ -match '[\s"]') {
                '"' + ($_ -replace '"', '\\"') + '"'
            } else {
                $_
            }
        }) -join ' '

        $proc = Start-Process -FilePath $PythonExe `
            -ArgumentList $argLine `
            -NoNewWindow `
            -Wait `
            -PassThru `
            -RedirectStandardOutput $tmpOut `
            -RedirectStandardError $tmpErr

        $stdout = @()
        if (Test-Path -LiteralPath $tmpOut) {
            $stdout = @(Get-Content -LiteralPath $tmpOut)
        }
        $stderr = @()
        if (Test-Path -LiteralPath $tmpErr) {
            $stderr = @(Get-Content -LiteralPath $tmpErr)
        }

        $stdout | ForEach-Object { Write-Host $_ }
        $stderr | ForEach-Object { Write-Host $_ -ForegroundColor Red }

        $exitCode = $proc.ExitCode
        $output = @($stdout + $stderr)
    }
    finally {
        Remove-Item -LiteralPath $tmpOut -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $tmpErr -ErrorAction SilentlyContinue
    }

    if ($exitCode -ne 0) {
        $tail = @($output | Select-Object -Last 25)
        $tailText = if ($tail.Count -gt 0) { "`n" + ($tail -join "`n") } else { "" }
        throw "$Label failed with exit code $exitCode$tailText"
    }
    return @($output | ForEach-Object { [string]$_ })
}

function Get-DatasourceIdFromOutput {
    param([string[]]$OutputLines)

    foreach ($line in $OutputLines) {
        if ($line -match "Datasource ID returned:\s*(\d+)") {
            return [int]$Matches[1]
        }
    }
    return $null
}

function New-ProcessorParamsArg {
    param(
        [string]$RootTagPath,
        [string]$LinkUrlTemplate,
        [string]$LinkLabelTemplate
    )

    $params = @{
        rootTagPath = $RootTagPath
        externalURL = $LinkUrlTemplate
        label = $LinkLabelTemplate
    }
    $json = $params | ConvertTo-Json -Compress
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($json)
    return "base64:$([Convert]::ToBase64String($bytes))"
}

function Test-JsonRootIsEmpty {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [Parameter(Mandatory = $true)]
        [string]$RootKey
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        return $true
    }

    $json = ((Get-Content -LiteralPath $Path -Raw).TrimStart([char]0xFEFF)) | ConvertFrom-Json
    if ($null -eq $json) {
        return $true
    }

    # Some exports are root arrays (e.g. []), others are objects with root tag.
    if ($json -is [System.Array]) {
        return @($json).Count -eq 0
    }

    $prop = $json.PSObject.Properties[$RootKey]
    if ($null -eq $prop -or $null -eq $prop.Value) {
        return $true
    }

    return @($prop.Value).Count -eq 0
}

function Assert-RequiredFile {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Required file not found: $Path"
    }
}

function Get-ConfigRepos {
    param([string]$Path)
    $cfg = ((Get-Content -LiteralPath $Path -Raw).TrimStart([char]0xFEFF)) | ConvertFrom-Json
    return @($cfg.repos | ForEach-Object { [string]$_ })
}

function Get-ReposWithIssueDocs {
    param([string[]]$Repos)

    $withIssueDocs = @()
    foreach ($repo in $Repos) {
        $repoSlug = $repo.ToLowerInvariant()
        $docsFile = "data/docs_issues_${repoSlug}_v2.json"
        if (Test-Path -LiteralPath $docsFile) {
            $withIssueDocs += $repo
        }
    }
    return $withIssueDocs
}

function Assert-SeriesFilesCoverage {
    param([string[]]$Repos)

    Write-Host "`n===== V3 files coverage gate for $Series =====" -ForegroundColor Cyan
    $missingDocs = @()
    $missingDelivery = @()

    foreach ($repo in $Repos) {
        $repoSlug = $repo.ToLowerInvariant()
        $docsFile = "data/docs_files_${repoSlug}_v3.json"

        if ($repo -eq $seriesRepo) {
            $deliveryFile = "$deliveryRoot/files_json/st_ready_files_${repoSlug}_v3.json"
        } else {
            $deliveryFile = "$deliveryRoot/drivers/$repoSlug/files_json/st_ready_files_${repoSlug}_v3.json"
        }

        $hasDocs = Test-Path -LiteralPath $docsFile
        if (-not $hasDocs) {
            $missingDocs += "docs missing: $docsFile"
            continue
        }

        if (-not (Test-Path -LiteralPath $deliveryFile)) {
            $missingDelivery += "delivery missing: $deliveryFile"
        }
    }

    if ($missingDocs.Count -gt 0) {
        Write-Host "[WARN] Some repos have no docs_files_*_v3 input; they are skipped for this gate:" -ForegroundColor Yellow
        $missingDocs | ForEach-Object { Write-Host "  $_" -ForegroundColor Yellow }
    }

    if ($missingDelivery.Count -gt 0) {
        $missingDelivery | ForEach-Object { Write-Host "  $_" -ForegroundColor Red }
        throw "V3 files coverage incomplete for $Series. Do not upload or move to next series yet."
    }

    Write-Host "OK: all repos with docs_files_*_v3.json have matching st_ready_files_*_v3.json" -ForegroundColor Green
}

function Invoke-ParentRepoDeliveryExports {
    Write-Host "`n===== Export parent ST-ready delivery for $Series ($seriesRepo) =====" -ForegroundColor Cyan

    Invoke-Step "Export parent issues JSON" @(
        "-m", "pipeline.delivery.export_st_ready_issues",
        "--repo", $seriesRepo
    )

    Invoke-Step "Export parent resolver cases JSON" @(
        "-m", "pipeline.delivery.export_st_ready_resolver_cases",
        "--repo", $seriesRepo
    )

    Invoke-Step "Export parent diagnostic cards JSON" @(
        "-m", "pipeline.delivery.export_st_ready_diagnostic_cards",
        "--repo", $seriesRepo
    )

    Invoke-Step "Export parent issues with image URLs" @(
        "-m", "pipeline.delivery.export_st_ready_issues_with_images",
        "--repo", $seriesRepo
    )
}

function Invoke-SubrepoIssueDeliveryExports {
    param([string[]]$Repos)

    $issueRepos = @(Get-ReposWithIssueDocs -Repos $Repos | Where-Object { $_ -ne $seriesRepo })
    if ($issueRepos.Count -eq 0) {
        Write-Host "[SKIP] No driver/subrepo issue docs found for $Series" -ForegroundColor Yellow
        return
    }

    $repoArgs = @()
    foreach ($repo in $issueRepos) {
        $repoArgs += @("--repo", $repo)
    }

    Invoke-Step "Export driver/subrepo issues JSON" (@("-m", "pipeline.delivery.export_st_ready_issues") + $repoArgs)
    Invoke-Step "Export driver/subrepo resolver cases JSON" (@("-m", "pipeline.delivery.export_st_ready_resolver_cases") + $repoArgs)
    Invoke-Step "Export driver/subrepo diagnostic cards JSON" (@("-m", "pipeline.delivery.export_st_ready_diagnostic_cards") + $repoArgs)
    Invoke-Step "Export driver/subrepo issues with image URLs" (@("-m", "pipeline.delivery.export_st_ready_issues_with_images") + $repoArgs)
}

function Invoke-AlfredIssueImageDescriptionsForSeries {
    $issueImageFiles = @(Get-ChildItem -Path $deliveryRoot -Recurse -Filter "st_ready_issues_with_images_*.json" -ErrorAction SilentlyContinue |
        Where-Object { $_.Directory.Name -eq "issues_json" -and $_.Name -notmatch "summary" } |
        Sort-Object FullName)

    if ($issueImageFiles.Count -eq 0) {
        Write-Host "[SKIP] No issue image JSON files found for Alfred under $deliveryRoot" -ForegroundColor Yellow
        return
    }

    foreach ($file in $issueImageFiles) {
        $alfredArgs = @(
            "pipeline_Automation/alfred/enrich_json_images_with_alfred.py",
            "--input", $file.FullName,
            "--remote-user", $RemoteUser,
            "--inplace"
        )
        if ($UseAlfredProxy) {
            $alfredArgs += "--use-proxy"
        }
        Invoke-Step "Alfred issue image descriptions for $($file.Directory.Parent.Name)" $alfredArgs
    }
}

function Invoke-AlfredPdfFigureDescriptions {
    param([string[]]$Repos)

    $targetRepos = @($Repos | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
    if ($targetRepos.Count -eq 0) {
        $targetRepos = @(Get-ConfigRepos $configPath)
    }

    if ($targetRepos.Count -eq 0) {
        Write-Host "[SKIP] No repos resolved for Alfred PDF figure descriptions (series=$Series)." -ForegroundColor Yellow
        return
    }

    foreach ($repo in $targetRepos) {
        $args = @("pipeline_Automation/alfred/enrich_pdf_figures_with_alfred.py", "--repo", $repo)
        if ($UseAlfredProxy) {
            $args += "--use-proxy"
        }
        Invoke-Step "Alfred PDF figure descriptions for $repo" $args
    }
}

function Invoke-PlaceholderGate {
    Write-Host "`n===== Placeholder gate for $Series (policy=$PlaceholderPolicy) =====" -ForegroundColor Cyan
    if ($PlaceholderPolicy -ne "Off") {
        $placeholderMatches = Select-String -Path "$deliveryRoot/**/*.json" `
            -Pattern "IMAGE DESCRIPTION UNAVAILABLE|\[FIGURE DETECTED\]|Figure detected on page|no technical description is available yet" `
            -ErrorAction SilentlyContinue

        if ($placeholderMatches) {
            $reportPath = Join-Path $deliveryRoot "alfred_placeholder_report_$slug.txt"
            $placeholderLines = @($placeholderMatches | ForEach-Object { $_.Line })
            $placeholderLines | Set-Content -LiteralPath $reportPath -Encoding UTF8

            Write-Host "Found unresolved Alfred placeholders: $($placeholderLines.Count)" -ForegroundColor Yellow
            Write-Host "Report: $reportPath" -ForegroundColor Yellow

            $placeholderLines | Select-Object -First 5 | ForEach-Object { Write-Host $_ -ForegroundColor Red }
            if ($placeholderLines.Count -gt 5) {
                Write-Host "... ($($placeholderLines.Count - 5) more lines in report)" -ForegroundColor DarkYellow
            }

            if ($PlaceholderPolicy -eq "Fail") {
                throw "Unresolved Alfred image/PDF placeholders found for $Series"
            }

            Write-Host "[WARN] Continuing despite unresolved placeholders (PlaceholderPolicy=Warn)" -ForegroundColor Yellow
        } else {
            Write-Host "OK: no unresolved Alfred image/PDF placeholders for $Series" -ForegroundColor Green
        }
    } else {
        Write-Host "[SKIP] Placeholder gate disabled (PlaceholderPolicy=Off)" -ForegroundColor Yellow
    }
}

function Invoke-PrepareSeries {
    if (-not (Test-Path -LiteralPath $configPath)) {
        throw "Config not found: $configPath"
    }

    $env:STM32CUBE_CONFIG = $configPath
    Write-Host "`nPreparing $Series using $configPath" -ForegroundColor Green

    Invoke-Step "Sync configured repos" @("-m", "pipeline.ingestion.repo_sync_service")
    Invoke-Step "Audit/fix submodule repos" @("-m", "pipeline.evaluation.audit_config_submodules", "--fix")
    Invoke-Step "Audit submodule repos gate" @("-m", "pipeline.evaluation.audit_config_submodules")

    $workflowArgs = @("-m", "pipeline.run_full_workflow", "--skip-chunking")
    if ($SkipAlfredEnrichment) {
        $workflowArgs += "--no-enrich-pdf"
    }
    if ($ContinueOnWorkflowError) {
        $workflowArgs += "--continue-on-error"
    }
    Invoke-Step "Full preprocessing workflow with Alfred PDF" $workflowArgs

    $repos = Get-ConfigRepos $configPath
    Invoke-ParentRepoDeliveryExports
    Invoke-SubrepoIssueDeliveryExports -Repos $repos
    if ($SkipAlfredEnrichment) {
        Write-Host "[SKIP] Alfred issue image enrichment disabled by -SkipAlfredEnrichment" -ForegroundColor Yellow
    } else {
        Invoke-AlfredIssueImageDescriptionsForSeries
    }

    $exportArgs = @("-m", "pipeline.delivery.export_st_ready_files", "--v3")
    foreach ($repo in $repos) {
        $exportArgs += @("--repo", $repo)
    }
    Invoke-Step "Export V3 ST-ready files for configured repos" $exportArgs
    Assert-SeriesFilesCoverage -Repos $repos

    if ($SkipAlfredEnrichment) {
        Write-Host "[SKIP] Patch Alfred PDF descriptions disabled by -SkipAlfredEnrichment" -ForegroundColor Yellow
    } else {
        Invoke-Step "Patch Alfred PDF descriptions into root and driver delivery files" @("pipeline_Automation/patch_pdf_descriptions_in_delivery.py", "--series", $Series)
    }

    if (-not $SkipSchemaValidation) {
        Invoke-Step "Schema validation" @("-m", "pipeline.evaluation.validate_schemas")
    }

    if ($SkipPlaceholderGate) {
        Write-Host "[SKIP] Placeholder gate disabled by -SkipPlaceholderGate" -ForegroundColor Yellow
    } else {
        Invoke-PlaceholderGate
    }

    if ($EnableIssuesByComponentFlow) {
        Invoke-IssuesByComponentSplit
    }
}

function Invoke-IssuesByComponentSplit {
    $splitScript = Join-Path $repoRoot "pipeline_Automation/workflow/Split_Issues_By_Component.ps1"
    if (-not (Test-Path -LiteralPath $splitScript)) {
        throw "Issues-by-component split script not found: $splitScript"
    }

    Write-Host "`n===== Split issues by component for $Series =====" -ForegroundColor Cyan
    & powershell -ExecutionPolicy Bypass -File $splitScript -Series $Series -PythonExe $PythonExe
    if ($LASTEXITCODE -ne 0) {
        throw "Split issues by component failed for $Series"
    }
}

function Invoke-IssuesByComponentUpload {
    $uploadScript = Join-Path $repoRoot "pipeline_Automation/workflow/Upload_Issues_By_Component.ps1"
    if (-not (Test-Path -LiteralPath $uploadScript)) {
        throw "Issues-by-component upload script not found: $uploadScript"
    }

    Write-Host "`n===== Upload issues by component for $Series =====" -ForegroundColor Cyan
    $uploadArgs = @(
        "-ExecutionPolicy", "Bypass",
        "-File", $uploadScript,
        "-Series", $Series,
        "-PythonExe", $PythonExe,
        "-RemoteUser", $RemoteUser,
        "-KbId", "$KbId",
        "-JsonSplitSize", "$JsonSplitSize",
        "-ExistingDatasourcePolicy", "add"
    )
    if (-not [string]::IsNullOrWhiteSpace($ApiKey)) {
        $uploadArgs += @("-ApiKey", $ApiKey)
    }
    if (-not [string]::IsNullOrWhiteSpace($ClientAppName)) {
        $uploadArgs += @("-ClientAppName", $ClientAppName)
    }

    & powershell @uploadArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Upload issues by component failed for $Series"
    }
}

function Invoke-PreUploadAlfredFinalize {
    if (-not (Test-Path -LiteralPath $configPath)) {
        throw "Config not found: $configPath"
    }
    if (-not (Test-Path -LiteralPath $deliveryRoot)) {
        throw "Delivery root not found for ${Series}: $deliveryRoot. Upload mode requires pre-generated delivery artifacts. Run -Mode Full, or run -Mode Prepare then upload from the same workflow run/artifacts."
    }

    $env:STM32CUBE_CONFIG = $configPath

    if ($SkipAlfredEnrichment) {
        Write-Host "[SKIP] Pre-upload Alfred finalize disabled by -SkipAlfredEnrichment" -ForegroundColor Yellow
    } else {
        $repos = Get-ConfigRepos $configPath
        Invoke-AlfredPdfFigureDescriptions -Repos $repos
        Invoke-AlfredIssueImageDescriptionsForSeries
        Invoke-Step "Patch Alfred PDF descriptions into root and driver delivery files" @("pipeline_Automation/patch_pdf_descriptions_in_delivery.py", "--series", $Series)
    }

    if (-not $SkipSchemaValidation) {
        Invoke-Step "Schema validation" @("-m", "pipeline.evaluation.validate_schemas")
    }

    if ($SkipPlaceholderGate) {
        Write-Host "[SKIP] Placeholder gate disabled by -SkipPlaceholderGate" -ForegroundColor Yellow
    } else {
        Invoke-PlaceholderGate
    }
}

function Invoke-UploadJsonNew {
    param(
        [string]$Label,
        [string]$FilePath,
        [string]$RootKey,
        [string]$DatasourceName,
        [string]$ProcessorParams,
        [int]$ExistingDatasourceIdHint = 0,
        [switch]$AllowEmpty
    )

    Assert-RequiredFile $FilePath
    if ((Test-JsonRootIsEmpty -Path $FilePath -RootKey $RootKey) -and $AllowEmpty) {
        Write-Host "[SKIP] $Label is empty: $FilePath" -ForegroundColor Yellow
        return $null
    }

    $args = @(
        $uploader,
        "--kb", "$KbId",
        "--operation", "new",
        "--datasource-name", $DatasourceName,
        "--datasource-classification", "PUBLIC",
        "--remote-user", $RemoteUser,
        "--processor", "JSON",
        "--processor-params", $ProcessorParams,
        "--json-root-mode", "auto",
        "--empty-json-policy", "skip",
        "--json-split-size", "$JsonSplitSize",
        "--existing-datasource-policy", $script:EffectiveDatasourceMode.ToLowerInvariant(),
        "--skip-auth-precheck",
        "--max-retries", "$uploadMaxRetries",
        "--timeout", "$uploadTimeoutSeconds",
        "--files", (Resolve-Path $FilePath).Path
    )
    if ($ExistingDatasourceIdHint -gt 0) {
        $args += @("--existing-datasource-id-hint", "$ExistingDatasourceIdHint")
    }
    $args += @(Get-UploadAuthArgs)

    $output = Invoke-CapturedPython "Create datasource and upload $Label" $args
    $id = Get-DatasourceIdFromOutput $output
    if ($null -eq $id) {
        throw "Could not parse datasource ID for $Label"
    }
    return $id
}

function Invoke-UploadJsonAdd {
    param(
        [string]$Label,
        [string]$FilePath,
        [string]$RootKey,
        [int]$DatasourceId,
        [string]$ProcessorParams,
        [string]$DatasourceNameForFallback = "",
        [switch]$AllowEmpty
    )

    if ($DatasourceId -le 0) {
        throw "Invalid datasource ID for ${Label}: $DatasourceId"
    }

    if (-not (Test-Path -LiteralPath $FilePath)) {
        if ($AllowEmpty) {
            Write-Host "[SKIP] $Label file not found (allowed empty): $FilePath" -ForegroundColor Yellow
            return $DatasourceId
        }
        Assert-RequiredFile $FilePath
    }
    if ((Test-JsonRootIsEmpty -Path $FilePath -RootKey $RootKey) -and $AllowEmpty) {
        Write-Host "[SKIP] $Label is empty: $FilePath" -ForegroundColor Yellow
        return $DatasourceId
    }

    if ($script:EffectiveDatasourceMode -eq "Replace") {
        if ([string]::IsNullOrWhiteSpace($DatasourceNameForFallback)) {
            throw "Replace mode requires -DatasourceNameForFallback for $Label to recreate datasource and refresh ID."
        }

        Write-Host "[REPLACE] Refreshing datasource for ${Label}: requesting recreate with same name from uploader logic (no pre-delete in workflow)." -ForegroundColor DarkCyan

        try {
            $newDatasourceId = Invoke-UploadJsonNew `
                -Label "$Label (recreated)" `
                -FilePath $FilePath `
                -RootKey $RootKey `
                -DatasourceName $DatasourceNameForFallback `
                -ProcessorParams $ProcessorParams `
                -ExistingDatasourceIdHint $DatasourceId `
                -AllowEmpty:$AllowEmpty

            Write-Host "[REPLACE] Datasource ID updated for ${Label}: DS#$DatasourceId -> DS#$newDatasourceId" -ForegroundColor DarkCyan
            return $newDatasourceId
        }
        catch {
            $replaceError = $_.Exception.Message
            if ($replaceError -match "Replace fallback exhausted for datasource") {
                Write-Host "[WARN] Replace fallback exhausted for ${Label}; continuing with in-place add on existing DS#$DatasourceId." -ForegroundColor Yellow
            } else {
                throw
            }
        }
    } else {
        Write-Host "[ADD] Existing datasource mode is Add for $Label (DS#$DatasourceId): appending files." -ForegroundColor DarkCyan
    }

    $args = @(
        $uploader,
        "--kb", "$KbId",
        "--operation", "add",
        "--datasource-id", "$DatasourceId",
        "--remote-user", $RemoteUser,
        "--processor", "JSON",
        "--processor-params", $ProcessorParams,
        "--json-root-mode", "auto",
        "--empty-json-policy", "skip",
        "--json-split-size", "$JsonSplitSize",
        "--skip-auth-precheck",
        "--max-retries", "$uploadMaxRetries",
        "--timeout", "$uploadTimeoutSeconds",
        "--files", (Resolve-Path $FilePath).Path
    )
    $args += @(Get-UploadAuthArgs)

    try {
        Invoke-CapturedPython "Upload $Label into existing DS#$DatasourceId" $args | Out-Null
        return $DatasourceId
    }
    catch {
        $errorText = $_.Exception.Message
        $normalized = $errorText.ToLowerInvariant()

        $isDatasourceMissing = (
            $normalized -match "could not find any entity of type .*kbdatasourceentity" -or
            $normalized -match "datasource not found" -or
            $normalized -match "cannot upload files to deleted datasource" -or
            $normalized -match "errorcode=3000"
        )

        if ($isDatasourceMissing -and $DatasourceNameForFallback) {
            throw "Upload failed because DS#$DatasourceId for $Label does not exist in Add mode. Use Replace mode to recreate datasource and refresh ID, or fix configured datasource ID."
        }

            if ($isDatasourceMissing -and (-not $DatasourceNameForFallback)) {
                throw "Upload failed because DS#$DatasourceId for $Label does not exist, and no fallback datasource name was provided."
            }

        throw
    }
}

function Get-SubrepoDeliveryFiles {
    param(
        [string]$SubDirectory,
        [string]$Pattern
    )

    $selected = @()
    $driverDirs = @(Get-ChildItem "$deliveryRoot/drivers" -Directory -ErrorAction SilentlyContinue | Sort-Object FullName)

    foreach ($driverDir in $driverDirs) {
        $targetDir = Join-Path $driverDir.FullName $SubDirectory
        if (-not (Test-Path -LiteralPath $targetDir)) {
            continue
        }

        $selected += @(Get-ChildItem $targetDir -Filter $Pattern -File -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -notmatch "summary" } |
            Sort-Object FullName)
    }

    return @($selected)
}

function Get-NonEmptyJsonFiles {
    param(
        [System.IO.FileInfo[]]$Files,
        [string]$RootKey
    )

    $selected = @()
    foreach ($file in @($Files)) {
        if (-not (Test-JsonRootIsEmpty -Path $file.FullName -RootKey $RootKey)) {
            $selected += $file
        }
    }
    return @($selected)
}

function Get-SubrepoIssueUploadFiles {
    $selected = @()
    $driverDirs = @(Get-ChildItem "$deliveryRoot/drivers" -Directory -ErrorAction SilentlyContinue | Sort-Object FullName)

    foreach ($driverDir in $driverDirs) {
        $issuesDir = Join-Path $driverDir.FullName "issues_json"
        if (-not (Test-Path -LiteralPath $issuesDir)) {
            continue
        }

        $withImages = @(Get-ChildItem $issuesDir -Filter "st_ready_issues_with_images_*.json" -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -notmatch "summary" } |
            Sort-Object FullName)
        if ($withImages.Count -gt 0) {
            $selected += $withImages
            continue
        }

        $plainIssues = @(Get-ChildItem $issuesDir -Filter "st_ready_issues_*.json" -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -notmatch "summary" -and $_.Name -notmatch "with_images" } |
            Sort-Object FullName)
        $selected += $plainIssues
    }

    return @($selected)
}

function Invoke-UploadSubrepoDeliveryAdd {
    param(
        [string]$Label,
        [System.IO.FileInfo[]]$Files,
        [string]$RootKey,
        [AllowNull()][object]$DatasourceId,
        [string]$ProcessorParams
    )

    $effectiveDatasourceId = 0
    $filesList = @($Files)
    if ($null -ne $DatasourceId) {
        $effectiveDatasourceId = [int]$DatasourceId
    }

    if ($SkipDrivers) {
        Write-Host "[SKIP] Driver/subrepo upload disabled by -SkipDrivers" -ForegroundColor Yellow
        return
    }

    if ($ComponentIssuesOnly -and $Label -eq "issues") {
        Write-Host "[SKIP] Driver/subrepo issues upload to monolithic datasource disabled by -ComponentIssuesOnly (issues are handled by per-component datasources)." -ForegroundColor Yellow
        return
    }

    if ($effectiveDatasourceId -le 0) {
        if ($filesList.Count -gt 0) {
            Write-Host "[SKIP] No datasource ID available for $Label; $($filesList.Count) driver/subrepo file(s) not uploaded" -ForegroundColor Yellow
        }
        return
    }

    if ($filesList.Count -eq 0) {
        Write-Host "[SKIP] No driver/subrepo $Label found for $Series under $deliveryRoot/drivers" -ForegroundColor Yellow
        return
    }

    foreach ($file in $filesList) {
        $args = @(
            $uploader,
            "--kb", "$KbId",
            "--operation", "add",
            "--datasource-id", "$effectiveDatasourceId",
            "--remote-user", $RemoteUser,
            "--processor", "JSON",
            "--processor-params", $ProcessorParams,
            "--json-root-mode", "auto",
            "--empty-json-policy", "skip",
            "--json-split-size", "$JsonSplitSize",
            "--skip-auth-precheck",
            "--max-retries", "$uploadMaxRetries",
            "--timeout", "$uploadTimeoutSeconds",
            "--files", $file.FullName
        )
        $args += @(Get-UploadAuthArgs)
        Invoke-CapturedPython "Upload driver/subrepo $($file.Directory.Parent.Name) $Label into ${Series} DS#$effectiveDatasourceId" $args | Out-Null
    }
}

function Set-OrAddProperty {
    param(
        [Parameter(Mandatory = $true)]
        [object]$Target,
        [Parameter(Mandatory = $true)]
        [string]$Name,
        [AllowNull()][object]$Value
    )

    $prop = $Target.PSObject.Properties[$Name]
    if ($null -eq $prop) {
        $Target | Add-Member -NotePropertyName $Name -NotePropertyValue $Value
    } else {
        $prop.Value = $Value
    }
}

function Get-OptionalPositiveIntProperty {
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

function Sync-GlobalConfigDatasourceIds {
    param(
        [Parameter(Mandatory = $true)]
        [object]$Ids
    )

    if (-not (Test-Path -LiteralPath $globalConfigPath)) {
        Write-Host "[WARN] Global config not found, skip datasource sync: $globalConfigPath" -ForegroundColor Yellow
        return
    }

    try {
        $cfg = ((Get-Content -LiteralPath $globalConfigPath -Raw).TrimStart([char]0xFEFF)) | ConvertFrom-Json
        if ($null -eq $cfg -or $null -eq $cfg.kb_datasource_ids) {
            Write-Host "[WARN] Invalid global config structure, skip datasource sync: $globalConfigPath" -ForegroundColor Yellow
            return
        }

        $seriesKey = $seriesRepo
        $seriesProp = $cfg.kb_datasource_ids.PSObject.Properties[$seriesKey]
        if ($null -eq $seriesProp) {
            $entry = [pscustomobject]@{}
            $cfg.kb_datasource_ids | Add-Member -NotePropertyName $seriesKey -NotePropertyValue $entry
        } else {
            $entry = $seriesProp.Value
        }

        foreach ($name in @("issues", "files", "diagnostic", "resolver")) {
            $value = $Ids.$name
            if (($value -as [int]) -gt 0) {
                Set-OrAddProperty -Target $entry -Name $name -Value ([int]$value)
            }
        }

        $cfg | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $globalConfigPath -Encoding UTF8
        Write-Host "[UPLOAD] Global datasource IDs synced for ${seriesKey}: $globalConfigPath" -ForegroundColor DarkCyan
    }
    catch {
        Write-Host "[WARN] Failed to sync global datasource IDs: $($_.Exception.Message)" -ForegroundColor Yellow
    }
}

function Save-DatasourceIdsSnapshot {
    param(
        [Parameter(Mandatory = $true)]
        [object]$Ids,
        [string]$Reason = ""
    )

    New-Item -ItemType Directory -Force -Path $deliveryRoot | Out-Null

    # Preserve previously known IDs when current stage does not provide them.
    $existingSnapshot = $null
    if (Test-Path -LiteralPath $idsOutput) {
        try {
            $existingSnapshot = ((Get-Content -LiteralPath $idsOutput -Raw).TrimStart([char]0xFEFF)) | ConvertFrom-Json
        } catch {
            $existingSnapshot = $null
        }
    }

    foreach ($name in @("issues", "files", "diagnostic", "resolver")) {
        $currentValue = $Ids.$name
        $currentId = 0
        if ([int]::TryParse([string]$currentValue, [ref]$currentId) -and $currentId -gt 0) {
            continue
        }

        if ($null -ne $existingSnapshot) {
            $existingValue = $null
            $existingProp = $existingSnapshot.PSObject.Properties[$name]
            if ($null -ne $existingProp) {
                $existingValue = $existingProp.Value
            }
            $existingId = 0
            if ([int]::TryParse([string]$existingValue, [ref]$existingId) -and $existingId -gt 0) {
                $Ids[$name] = $existingId
            }
        }
    }

    $Ids["uploaded_at"] = (Get-Date).ToString("s")
    if ($Reason) {
        $Ids["last_update_reason"] = $Reason
        $Ids["last_successful_stage"] = $Reason
    }

    $Ids | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $idsOutput -Encoding UTF8
    if ($env:GITHUB_ACTIONS -eq "true") {
        Write-Host "[UPLOAD] Skipping shared/config/config_all_series.json update in GitHub Actions (runner-local state must stay immutable)." -ForegroundColor DarkYellow
    } else {
        Sync-GlobalConfigDatasourceIds -Ids $Ids
    }

    if ($Reason) {
        Write-Host "[UPLOAD] Datasource ID registry updated ($Reason): $idsOutput" -ForegroundColor DarkCyan
    } else {
        Write-Host "[UPLOAD] Datasource ID registry updated: $idsOutput" -ForegroundColor DarkCyan
    }
}

function Sync-DatasourceIdsFromKbLive {
    param(
        [int]$CurrentIssuesId,
        [int]$CurrentFilesId,
        [int]$CurrentDiagnosticId,
        [int]$CurrentResolverId
    )

    $resolverScript = "pipeline_Automation/upload/Resolve_Live_Datasource_Ids.py"
    if (-not (Test-Path -LiteralPath $resolverScript)) {
        Write-Host "[WARN] Live KB ID resolver script not found: $resolverScript" -ForegroundColor Yellow
        return @{
            issues = $CurrentIssuesId
            files = $CurrentFilesId
            diagnostic = $CurrentDiagnosticId
            resolver = $CurrentResolverId
            live_issues_resolved = $false
            live_files_resolved = $false
            live_diagnostic_resolved = $false
            live_resolver_resolved = $false
        }
    }

    $args = @(
        $resolverScript,
        "--kb", "$KbId",
        "--series", $Series,
        "--remote-user", $RemoteUser,
        "--timeout", "60"
    )
    $args += @(Get-UploadAuthArgs)

    try {
        $output = Invoke-CapturedPython "Resolve live datasource IDs from KB for $Series" $args
        $rawJson = ($output | Where-Object { $_ -and $_.Trim().StartsWith("{") } | Select-Object -Last 1)
        if (-not $rawJson) {
            throw "Resolver returned no JSON payload."
        }

        $resolved = ConvertFrom-JsonSafeText -RawText $rawJson -Source "live resolver output"
        $ids = $resolved.resolved_ids
        if ($null -eq $ids) {
            throw "Resolver JSON does not contain resolved_ids."
        }

        $newIssues = $CurrentIssuesId
        $newFiles = $CurrentFilesId
        $newDiagnostic = $CurrentDiagnosticId
        $newResolver = $CurrentResolverId
        $liveIssuesResolved = $false
        $liveFilesResolved = $false
        $liveDiagnosticResolved = $false
        $liveResolverResolved = $false

        $tmp = 0
        if ([int]::TryParse([string]$ids.issues, [ref]$tmp) -and $tmp -gt 0) {
            $newIssues = $tmp
            $liveIssuesResolved = $true
        }
        if ([int]::TryParse([string]$ids.files, [ref]$tmp) -and $tmp -gt 0) {
            $newFiles = $tmp
            $liveFilesResolved = $true
        }
        if ([int]::TryParse([string]$ids.diagnostic, [ref]$tmp) -and $tmp -gt 0) {
            $newDiagnostic = $tmp
            $liveDiagnosticResolved = $true
        }
        if ([int]::TryParse([string]$ids.resolver, [ref]$tmp) -and $tmp -gt 0) {
            $newResolver = $tmp
            $liveResolverResolved = $true
        }

        $liveResolvedCount = @($liveIssuesResolved, $liveFilesResolved, $liveDiagnosticResolved, $liveResolverResolved | Where-Object { $_ }).Count
        if ($liveResolvedCount -eq 0) {
            Write-Host "[WARN] Live KB resolver returned no datasource IDs for ${Series}. Keeping current IDs: issues=$newIssues files=$newFiles diagnostic=$newDiagnostic resolver=$newResolver" -ForegroundColor Yellow
        } else {
            Write-Host "[SYNC] Live KB datasource IDs resolved for ${Series} ($liveResolvedCount/4 from KB): issues=$newIssues files=$newFiles diagnostic=$newDiagnostic resolver=$newResolver" -ForegroundColor DarkCyan
        }

        return @{
            issues = $newIssues
            files = $newFiles
            diagnostic = $newDiagnostic
            resolver = $newResolver
            live_issues_resolved = $liveIssuesResolved
            live_files_resolved = $liveFilesResolved
            live_diagnostic_resolved = $liveDiagnosticResolved
            live_resolver_resolved = $liveResolverResolved
        }
    }
    catch {
        Write-Host "[WARN] Live KB ID sync failed for ${Series}: $($_.Exception.Message)" -ForegroundColor Yellow
        return @{
            issues = $CurrentIssuesId
            files = $CurrentFilesId
            diagnostic = $CurrentDiagnosticId
            resolver = $CurrentResolverId
            live_issues_resolved = $false
            live_files_resolved = $false
            live_diagnostic_resolved = $false
            live_resolver_resolved = $false
        }
    }
}

function Invoke-UploadSeries {
    if (-not (Test-Path -LiteralPath $deliveryRoot)) {
        throw "Delivery root not found for ${Series}: $deliveryRoot. Upload mode requires pre-generated delivery artifacts. Run with -Mode Full, or run with -Mode Prepare then upload from the same workflow run/artifacts."
    }

    # Reuse datasource IDs from the previous run when available.
    # Existing datasources are reused. Refresh policy is controlled by -ExistingDatasourceMode.
    $reuseLocalSnapshot = $true
    if ($env:GITHUB_ACTIONS -eq "true") {
        $reuseLocalSnapshot = $false
        Write-Host "[UPLOAD] Ignoring runner-local datasource snapshot in GitHub Actions: $idsOutput" -ForegroundColor DarkYellow
    }

    if ($reuseLocalSnapshot -and (Test-Path -LiteralPath $idsOutput)) {
        try {
            $saved = ((Get-Content -LiteralPath $idsOutput -Raw).TrimStart([char]0xFEFF)) | ConvertFrom-Json
            if ($null -ne $saved) {
                $savedIssues = Get-OptionalPositiveIntProperty -Target $saved -Name "issues"
                if (($IssuesDatasourceId -le 0) -and $savedIssues -gt 0) {
                    $IssuesDatasourceId = $savedIssues
                }
                $savedFiles = Get-OptionalPositiveIntProperty -Target $saved -Name "files"
                if (($FilesDatasourceId -le 0) -and $savedFiles -gt 0) {
                    $FilesDatasourceId = $savedFiles
                }
                $savedDiagnostic = Get-OptionalPositiveIntProperty -Target $saved -Name "diagnostic"
                if (($DiagnosticDatasourceId -le 0) -and $savedDiagnostic -gt 0) {
                    $DiagnosticDatasourceId = $savedDiagnostic
                }
                $savedResolver = Get-OptionalPositiveIntProperty -Target $saved -Name "resolver"
                if (($ResolverDatasourceId -le 0) -and $savedResolver -gt 0) {
                    $ResolverDatasourceId = $savedResolver
                }

                Write-Host "[UPLOAD] Reusing datasource IDs from $idsOutput when available." -ForegroundColor DarkCyan
            }
        } catch {
            Write-Host "[WARN] Could not parse saved datasource IDs from $idsOutput. Proceeding without reuse." -ForegroundColor Yellow
        }
    }

    # Fallback to shared/config/config_all_series.json when no local snapshot IDs are available.
    if ((($IssuesDatasourceId -le 0) -or ($FilesDatasourceId -le 0) -or ($DiagnosticDatasourceId -le 0) -or ($ResolverDatasourceId -le 0)) -and (Test-Path -LiteralPath $globalConfigPath)) {
        try {
            $cfg = ((Get-Content -LiteralPath $globalConfigPath -Raw).TrimStart([char]0xFEFF)) | ConvertFrom-Json
            $seriesEntry = $null
            if ($null -ne $cfg -and $null -ne $cfg.kb_datasource_ids) {
                $prop = $cfg.kb_datasource_ids.PSObject.Properties[$seriesRepo]
                if ($null -ne $prop) {
                    $seriesEntry = $prop.Value
                }
            }

            if ($null -ne $seriesEntry) {
                $cfgIssues = Get-OptionalPositiveIntProperty -Target $seriesEntry -Name "issues"
                if (($IssuesDatasourceId -le 0) -and $cfgIssues -gt 0) {
                    $IssuesDatasourceId = $cfgIssues
                }
                $cfgFiles = Get-OptionalPositiveIntProperty -Target $seriesEntry -Name "files"
                if (($FilesDatasourceId -le 0) -and $cfgFiles -gt 0) {
                    $FilesDatasourceId = $cfgFiles
                }
                $cfgDiagnostic = Get-OptionalPositiveIntProperty -Target $seriesEntry -Name "diagnostic"
                if (($DiagnosticDatasourceId -le 0) -and $cfgDiagnostic -gt 0) {
                    $DiagnosticDatasourceId = $cfgDiagnostic
                }
                $cfgResolver = Get-OptionalPositiveIntProperty -Target $seriesEntry -Name "resolver"
                if (($ResolverDatasourceId -le 0) -and $cfgResolver -gt 0) {
                    $ResolverDatasourceId = $cfgResolver
                }

                Write-Host "[UPLOAD] Reusing datasource IDs from $globalConfigPath for ${seriesRepo} when available." -ForegroundColor DarkCyan
            }
        } catch {
            Write-Host "[WARN] Could not parse datasource IDs from $globalConfigPath. Proceeding without global fallback." -ForegroundColor Yellow
        }
    }

    # Runtime synchronization from KB is the source of truth.
    # This keeps automation aligned even when repo config IDs are stale.
    $synced = Sync-DatasourceIdsFromKbLive `
        -CurrentIssuesId $IssuesDatasourceId `
        -CurrentFilesId $FilesDatasourceId `
        -CurrentDiagnosticId $DiagnosticDatasourceId `
        -CurrentResolverId $ResolverDatasourceId

    $IssuesDatasourceId = [int]$synced.issues
    $FilesDatasourceId = [int]$synced.files
    $DiagnosticDatasourceId = [int]$synced.diagnostic
    $ResolverDatasourceId = [int]$synced.resolver

    $script:EffectiveDatasourceMode = $ExistingDatasourceMode
    if (
        ($script:EffectiveDatasourceMode -eq "Replace") -and
        ($env:GITHUB_ACTIONS -eq "true") -and
        (-not [bool]$synced.live_files_resolved) -and
        (-not [bool]$synced.live_diagnostic_resolved)
    ) {
        Write-Host "[WARN] Live KB resolver did not return files/diagnostic IDs for ${Series} in GitHub Actions." -ForegroundColor Yellow
        Write-Host "[WARN] Auto-switching ExistingDatasourceMode Replace -> Add to avoid replace deadlock on reserved datasource names." -ForegroundColor Yellow
        $script:EffectiveDatasourceMode = "Add"
    }

    $issuesFile = "$deliveryRoot/issues_json/st_ready_issues_with_images_$slug.json"
    $filesFile = "$deliveryRoot/files_json/st_ready_files_${slug}_v3.json"
    $diagnosticFile = "$deliveryRoot/diagnostic_cards_json/st_ready_diagnostic_cards_$slug.json"
    $resolverFile = "$deliveryRoot/resolver_cases_json/st_ready_resolver_cases_$slug.json"

    $driverIssueFiles = @(Get-SubrepoIssueUploadFiles)
    $driverFiles = @(Get-SubrepoDeliveryFiles -SubDirectory "files_json" -Pattern "st_ready_files_*.json")
    $driverDiagnosticFiles = @(Get-SubrepoDeliveryFiles -SubDirectory "diagnostic_cards_json" -Pattern "st_ready_diagnostic_cards_*.json")
    $driverResolverFiles = @(Get-SubrepoDeliveryFiles -SubDirectory "resolver_cases_json" -Pattern "st_ready_resolver_cases_*.json")
    $driverIssueNonEmptyFiles = @(Get-NonEmptyJsonFiles -Files $driverIssueFiles -RootKey "issues")
    $driverDiagnosticNonEmptyFiles = @(Get-NonEmptyJsonFiles -Files $driverDiagnosticFiles -RootKey "diagnostic_cards")
    $driverResolverNonEmptyFiles = @(Get-NonEmptyJsonFiles -Files $driverResolverFiles -RootKey "resolver_cases")

    $issuesParams = New-ProcessorParamsArg `
        -RootTagPath "issues" `
        -LinkUrlTemplate "https://github.com/STMicroelectronics/{{repo}}/issues/{{issue_number}}" `
        -LinkLabelTemplate "{{repo}} issue #{{issue_number}} - {{issue_title}}"
    $filesParams = New-ProcessorParamsArg `
        -RootTagPath "files" `
        -LinkUrlTemplate "https://github.com/STMicroelectronics/{{repo}}/search?q={{path}}&type=code" `
        -LinkLabelTemplate "{{repo}} {{file_type}} - {{path}}"
    $diagnosticParams = New-ProcessorParamsArg `
        -RootTagPath "diagnostic_cards" `
        -LinkUrlTemplate "{{externalURL}}" `
        -LinkLabelTemplate "{{repo}} diagnostic #{{issue_number}} - {{title}}"
    $resolverParams = New-ProcessorParamsArg `
        -RootTagPath "resolver_cases" `
        -LinkUrlTemplate "{{externalURL}}" `
        -LinkLabelTemplate "{{repo}} resolver #{{issue_number}} - {{issue_title}}"

    $ids = [ordered]@{
        series = $Series
        slug = $slug
        kb = $KbId
        issues = $(if ($IssuesDatasourceId -gt 0) { [int]$IssuesDatasourceId } else { $null })
        files = $(if ($FilesDatasourceId -gt 0) { [int]$FilesDatasourceId } else { $null })
        diagnostic = $(if ($DiagnosticDatasourceId -gt 0) { [int]$DiagnosticDatasourceId } else { $null })
        resolver = $(if ($ResolverDatasourceId -gt 0) { [int]$ResolverDatasourceId } else { $null })
        last_successful_stage = $null
        uploaded_at = (Get-Date).ToString("s")
    }

    if ($ComponentIssuesOnly) {
        Write-Host "[SKIP] Monolithic issues datasource upload disabled by -ComponentIssuesOnly" -ForegroundColor Yellow
        Save-DatasourceIdsSnapshot -Ids $ids -Reason "issues_skipped_component_only"
    } else {
        if ($IssuesDatasourceId -gt 0) {
            $ids.issues = Invoke-UploadJsonAdd `
                -Label "${Series} issues" `
                -FilePath $issuesFile `
                -RootKey "issues" `
                -DatasourceId $IssuesDatasourceId `
                -ProcessorParams $issuesParams `
                -DatasourceNameForFallback "DB_STready_${Series}_Issues"
        } elseif ((Test-JsonRootIsEmpty -Path $issuesFile -RootKey "issues") -and ($driverIssueNonEmptyFiles.Count -gt 0)) {
            $firstIssueFile = $driverIssueNonEmptyFiles[0]
            $ids.issues = Invoke-UploadJsonNew `
                -Label "${Series} issues from driver/subrepo $($firstIssueFile.Directory.Parent.Name)" `
                -FilePath $firstIssueFile.FullName `
                -RootKey "issues" `
                -DatasourceName "DB_STready_${Series}_Issues" `
                -ProcessorParams $issuesParams
            $driverIssueFiles = @($driverIssueFiles | Where-Object { $_.FullName -ne $firstIssueFile.FullName })
        } else {
            $ids.issues = Invoke-UploadJsonNew `
                -Label "${Series} issues" `
                -FilePath $issuesFile `
                -RootKey "issues" `
                -DatasourceName "DB_STready_${Series}_Issues" `
                -ProcessorParams $issuesParams `
                -AllowEmpty
        }
        Save-DatasourceIdsSnapshot -Ids $ids -Reason "issues"
    }

    if ($FilesDatasourceId -gt 0) {
        $ids.files = Invoke-UploadJsonAdd `
            -Label "${Series} files" `
            -FilePath $filesFile `
            -RootKey "files" `
            -DatasourceId $FilesDatasourceId `
            -ProcessorParams $filesParams `
            -DatasourceNameForFallback "DB_STready_${Series}_Files"
    } else {
        $ids.files = Invoke-UploadJsonNew `
            -Label "${Series} files" `
            -FilePath $filesFile `
            -RootKey "files" `
            -DatasourceName "DB_STready_${Series}_Files" `
            -ProcessorParams $filesParams
    }
    Save-DatasourceIdsSnapshot -Ids $ids -Reason "files"

    if ($DiagnosticDatasourceId -gt 0) {
        $ids.diagnostic = Invoke-UploadJsonAdd `
            -Label "${Series} diagnostic" `
            -FilePath $diagnosticFile `
            -RootKey "diagnostic_cards" `
            -DatasourceId $DiagnosticDatasourceId `
            -ProcessorParams $diagnosticParams `
            -DatasourceNameForFallback "DB_STready_${Series}_Diagnostic" `
            -AllowEmpty
    } elseif ((Test-JsonRootIsEmpty -Path $diagnosticFile -RootKey "diagnostic_cards") -and ($driverDiagnosticNonEmptyFiles.Count -gt 0)) {
        $firstDiagnosticFile = $driverDiagnosticNonEmptyFiles[0]
        $ids.diagnostic = Invoke-UploadJsonNew `
            -Label "${Series} diagnostic from driver/subrepo $($firstDiagnosticFile.Directory.Parent.Name)" `
            -FilePath $firstDiagnosticFile.FullName `
            -RootKey "diagnostic_cards" `
            -DatasourceName "DB_STready_${Series}_Diagnostic" `
            -ProcessorParams $diagnosticParams
        $driverDiagnosticFiles = @($driverDiagnosticFiles | Where-Object { $_.FullName -ne $firstDiagnosticFile.FullName })
    } else {
        $ids.diagnostic = Invoke-UploadJsonNew `
            -Label "${Series} diagnostic" `
            -FilePath $diagnosticFile `
            -RootKey "diagnostic_cards" `
            -DatasourceName "DB_STready_${Series}_Diagnostic" `
            -ProcessorParams $diagnosticParams `
            -AllowEmpty
    }
    Save-DatasourceIdsSnapshot -Ids $ids -Reason "diagnostic"

    $resolverAllowEmpty = ($driverResolverNonEmptyFiles.Count -eq 0)
    if ($ResolverDatasourceId -gt 0) {
        $ids.resolver = Invoke-UploadJsonAdd `
            -Label "${Series} resolver" `
            -FilePath $resolverFile `
            -RootKey "resolver_cases" `
            -DatasourceId $ResolverDatasourceId `
            -ProcessorParams $resolverParams `
            -DatasourceNameForFallback "DB_STready_${Series}_Resolver" `
            -AllowEmpty
    } elseif ((Test-JsonRootIsEmpty -Path $resolverFile -RootKey "resolver_cases") -and ($driverResolverNonEmptyFiles.Count -gt 0)) {
        $firstResolverFile = $driverResolverNonEmptyFiles[0]
        $ids.resolver = Invoke-UploadJsonNew `
            -Label "${Series} resolver from driver/subrepo $($firstResolverFile.Directory.Parent.Name)" `
            -FilePath $firstResolverFile.FullName `
            -RootKey "resolver_cases" `
            -DatasourceName "DB_STready_${Series}_Resolver" `
            -ProcessorParams $resolverParams
        $driverResolverFiles = @($driverResolverFiles | Where-Object { $_.FullName -ne $firstResolverFile.FullName })
    } else {
        $ids.resolver = Invoke-UploadJsonNew `
            -Label "${Series} resolver" `
            -FilePath $resolverFile `
            -RootKey "resolver_cases" `
            -DatasourceName "DB_STready_${Series}_Resolver" `
            -ProcessorParams $resolverParams `
            -AllowEmpty:$resolverAllowEmpty
    }
            Save-DatasourceIdsSnapshot -Ids $ids -Reason "resolver"

            Write-Host "`nSaved datasource IDs: $idsOutput" -ForegroundColor Green

    Invoke-UploadSubrepoDeliveryAdd -Label "issues" -Files $driverIssueFiles -RootKey "issues" -DatasourceId $ids.issues -ProcessorParams $issuesParams
    Invoke-UploadSubrepoDeliveryAdd -Label "files" -Files $driverFiles -RootKey "files" -DatasourceId $ids.files -ProcessorParams $filesParams
    Invoke-UploadSubrepoDeliveryAdd -Label "diagnostic cards" -Files $driverDiagnosticFiles -RootKey "diagnostic_cards" -DatasourceId $ids.diagnostic -ProcessorParams $diagnosticParams
    Invoke-UploadSubrepoDeliveryAdd -Label "resolver cases" -Files $driverResolverFiles -RootKey "resolver_cases" -DatasourceId $ids.resolver -ProcessorParams $resolverParams

    if ($EnableIssuesByComponentFlow) {
        Invoke-IssuesByComponentSplit
        Invoke-IssuesByComponentUpload
    }

    Write-Host "`n===== $Series upload summary =====" -ForegroundColor Cyan
    $ids | ConvertTo-Json -Depth 4 | Write-Host
}

if ($Mode -in @("Full", "Prepare")) {
    Invoke-PrepareSeries
}

if ($Mode -in @("Full", "Upload")) {
    if ($RunAlfredBeforeUpload) {
        Invoke-PreUploadAlfredFinalize
    }
    Invoke-UploadSeries
}

Write-Host "`nDone for $Series ($Mode)." -ForegroundColor Green