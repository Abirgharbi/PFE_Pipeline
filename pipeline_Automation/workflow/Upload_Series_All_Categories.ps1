<#
.SYNOPSIS
    Upload all ST-ready categories (issues, files, diagnostic_cards, resolver_cases)
    for a series and its drivers/subrepos into KB #793.

.DESCRIPTION
    - For each category, uploads parent repo JSON then all driver/subrepo JSONs.
    - Saves datasource IDs to upload_ids_<slug>.json after each category.
    - On re-run, reloads saved IDs and uses operation=add (no duplicate datasources).
    - Skips empty JSON payloads (e.g. resolver_cases=[]) silently.
    - Shows full Python traceback on failure.

.EXAMPLES
    # First run (creates new datasources):
    .\Upload_Series_All_Categories.ps1 -Series L1

    # Re-run continues where it left off:
    .\Upload_Series_All_Categories.ps1 -Series L1

    # Override existing IDs (e.g. G4 already in KB):
    .\Upload_Series_All_Categories.ps1 -Series G4 -IssuesDatasourceId 29611 -FilesDatasourceId 29612 -DiagnosticDatasourceId 29614
#>

param(
    [Parameter(Mandatory = $true)]
    [string]$Series,

    [string]$RemoteUser    = "abir.gharbi@st.com",
    [string]$PythonExe     = "",
    [int]   $KbId          = 793,
    [int]   $JsonSplitSize = 1000,

    # Optional: force specific IDs (overrides saved IDs from previous run)
    [int]$IssuesDatasourceId     = 0,
    [int]$FilesDatasourceId      = 0,
    [int]$DiagnosticDatasourceId = 0,
    [int]$ResolverDatasourceId   = 0,

    [switch]$SkipIssues,
    [switch]$SkipFiles,
    [switch]$SkipDiagnostic,
    [switch]$SkipResolver,
    [switch]$EnableIssuesByComponentFlow,
    [switch]$ComponentIssuesOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $repoRoot

$allSeriesConfigPath = "shared/config/config_all_series.json"

if (-not (Test-Path -LiteralPath $allSeriesConfigPath)) {
    throw "Missing config file: $allSeriesConfigPath"
}

$cfgAll = Get-Content -LiteralPath $allSeriesConfigPath -Raw | ConvertFrom-Json

$seriesMap = @{}
foreach ($seriesFull in @($cfgAll.all_series)) {
    $name = [string]$seriesFull
    if (-not $name.StartsWith("STM32Cube")) {
        continue
    }
    $seriesCode = $name.Substring(9).ToUpperInvariant()
    $seriesMap[$seriesCode] = $name.ToLowerInvariant()
}

$seriesInput = [string]$Series
if ($seriesInput.StartsWith("STM32Cube")) {
    $Series = $seriesInput.Substring(9).ToUpperInvariant()
} else {
    $Series = $seriesInput.ToUpperInvariant()
}

if (-not $seriesMap.ContainsKey($Series)) {
    $allowed = ($seriesMap.Keys | Sort-Object) -join ", "
    throw "Unsupported series '$Series'. Allowed (from $allSeriesConfigPath): $allowed"
}

$slug         = $seriesMap[$Series]
$deliveryRoot = "datasets/07_delivery/st_ready/by_series/$slug"
$uploader     = "pipeline_Automation/upload/Add_Data_Source_Files.py"
$idsFile      = "$deliveryRoot/upload_ids_${slug}.json"
$allSeriesKey = "STM32Cube$Series"

Write-Host "`n===== Upload all categories for $Series =====" -ForegroundColor Cyan
Write-Host "Delivery root : $deliveryRoot" -ForegroundColor Gray

if (-not (Test-Path -LiteralPath $deliveryRoot)) {
    throw "Delivery root not found: $deliveryRoot"
}

# Auto-detect venv python if not specified
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

# ---- Load saved IDs from previous run ----------------------------
$savedIds = [ordered]@{
    issues           = 0
    files            = 0
    diagnostic_cards = 0
    resolver_cases   = 0
}

if (Test-Path -LiteralPath $idsFile) {
    $loaded = Get-Content -LiteralPath $idsFile -Raw | ConvertFrom-Json
    foreach ($key in @("issues", "files", "diagnostic_cards", "resolver_cases")) {
        $prop = $loaded.PSObject.Properties[$key]
        if ($null -ne $prop) {
            $v = 0
            if ([int]::TryParse([string]$prop.Value, [ref]$v) -and $v -gt 0) {
                $savedIds[$key] = $v
            }
        }
    }
    Write-Host "Loaded saved IDs: $(($savedIds.GetEnumerator() | ForEach-Object { "$($_.Key)=$($_.Value)" }) -join ', ')" -ForegroundColor DarkCyan
}

# Parameter overrides take priority
if ($IssuesDatasourceId     -gt 0) { $savedIds["issues"]           = $IssuesDatasourceId     }
if ($FilesDatasourceId      -gt 0) { $savedIds["files"]            = $FilesDatasourceId      }
if ($DiagnosticDatasourceId -gt 0) { $savedIds["diagnostic_cards"] = $DiagnosticDatasourceId }
if ($ResolverDatasourceId   -gt 0) { $savedIds["resolver_cases"]   = $ResolverDatasourceId   }

function Save-Ids {
    New-Item -ItemType Directory -Force -Path $deliveryRoot | Out-Null
    $savedIds | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath $idsFile -Encoding UTF8

    if (Test-Path -LiteralPath $allSeriesConfigPath) {
        $allCfg = Get-Content -LiteralPath $allSeriesConfigPath -Raw | ConvertFrom-Json
        $kbIdsProp = $allCfg.PSObject.Properties["kb_datasource_ids"]
        if ($null -ne $kbIdsProp) {
            $kbIds = $kbIdsProp.Value
            $seriesProp = $kbIds.PSObject.Properties[$allSeriesKey]
            if ($null -ne $seriesProp) {
                $seriesObj = $seriesProp.Value
                $seriesObj.issues = if ($savedIds["issues"] -gt 0) { $savedIds["issues"] } else { $null }
                $seriesObj.files = if ($savedIds["files"] -gt 0) { $savedIds["files"] } else { $null }
                $seriesObj.diagnostic = if ($savedIds["diagnostic_cards"] -gt 0) { $savedIds["diagnostic_cards"] } else { $null }

                # Add/update resolver only when available.
                if ($savedIds["resolver_cases"] -gt 0) {
                    $resolverProp = $seriesObj.PSObject.Properties["resolver"]
                    if ($null -eq $resolverProp) {
                        Add-Member -InputObject $seriesObj -NotePropertyName "resolver" -NotePropertyValue $savedIds["resolver_cases"]
                    } else {
                        $seriesObj.resolver = $savedIds["resolver_cases"]
                    }
                }

                $allCfg | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $allSeriesConfigPath -Encoding UTF8
            }
        }
    }
}

# ---- Helper functions --------------------------------------------

function Invoke-Python {
    param([string]$Label, [string[]]$CommandArgs)
    Write-Host "`n[UPLOAD] $Label" -ForegroundColor Green

    $tmpOut = [System.IO.Path]::GetTempFileName()
    $tmpErr = [System.IO.Path]::GetTempFileName()

    try {
        $argLine = ($CommandArgs | ForEach-Object {
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

        $stdoutLines = @()
        if (Test-Path -LiteralPath $tmpOut) {
            $stdoutLines = @(Get-Content -LiteralPath $tmpOut)
        }
        $stderrLines = @()
        if (Test-Path -LiteralPath $tmpErr) {
            $stderrLines = @(Get-Content -LiteralPath $tmpErr)
        }

        $stdoutLines | ForEach-Object { Write-Host $_ }
        $stderrLines | ForEach-Object { Write-Host $_ -ForegroundColor Red }

        if ($proc.ExitCode -ne 0) {
            $details = @($stderrLines + $stdoutLines) -join "`n"
            throw "Python failed ($Label) exit=$($proc.ExitCode)`n$details"
        }

        return @($stdoutLines + $stderrLines)
    } finally {
        Remove-Item -LiteralPath $tmpOut -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $tmpErr -ErrorAction SilentlyContinue
    }
}

function Get-DatasourceId {
    param([string[]]$Lines)
    foreach ($line in $Lines) {
        if ($line -match "Datasource ID returned:\s*(\d+)") { return [int]$Matches[1] }
    }
    return $null
}

function Resolve-ExistingDatasourceIdByName {
    param([string]$DatasourceName)

    $args = @(
        $uploader,
        "--kb", "$KbId",
        "--operation", "new",
        "--datasource-name", $DatasourceName,
        "--datasource-classification", "PUBLIC",
        "--remote-user", $RemoteUser,
        "--processor", "JSON",
        "--processor-params", "{}",
        "--json-root-mode", "auto",
        "--empty-json-policy", "skip",
        "--json-split-size", "1",
        "--max-retries", "1",
        "--timeout", "30",
        "--auth-check-only"
    )

    $out = Invoke-Python "resolve existing datasource id for $DatasourceName" $args
    foreach ($line in $out) {
        if ($line -match "datasource_id\D+(\d+)") {
            return [int]$Matches[1]
        }
        if ($line -match "datasource\D+(\d+)") {
            return [int]$Matches[1]
        }
    }
    return $null
}

function Resolve-DatasourceIdFromConfig {
    param([string]$Category)

    if (-not (Test-Path -LiteralPath $allSeriesConfigPath)) {
        return $null
    }
    $cfg = Get-Content -LiteralPath $allSeriesConfigPath -Raw | ConvertFrom-Json
    $kbIdsProp = $cfg.PSObject.Properties["kb_datasource_ids"]
    if ($null -eq $kbIdsProp) {
        return $null
    }
    $seriesProp = $kbIdsProp.Value.PSObject.Properties[$allSeriesKey]
    if ($null -eq $seriesProp) {
        return $null
    }

    $seriesObj = $seriesProp.Value
    $cfgKey = if ($Category -eq "diagnostic_cards") { "diagnostic" } elseif ($Category -eq "resolver_cases") { "resolver" } else { $Category }
    $catProp = $seriesObj.PSObject.Properties[$cfgKey]
    if ($null -eq $catProp -or $null -eq $catProp.Value) {
        return $null
    }

    $v = 0
    if ([int]::TryParse([string]$catProp.Value, [ref]$v) -and $v -gt 0) {
        return $v
    }
    return $null
}

function New-ProcessorParams {
    param([string]$RootTagPath, [string]$LinkUrl, [string]$LinkLabel)
    $j = (@{ rootTagPath = $RootTagPath; externalURL = $LinkUrl; label = $LinkLabel } | ConvertTo-Json -Compress)
    return "base64:$([Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($j)))"
}

function Test-JsonRootIsEmpty {
    param([string]$Path, [string]$RootKey)
    if (-not (Test-Path -LiteralPath $Path)) { return $true }
    $json = Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
    if ($null -eq $json) { return $true }
    if ($json -is [System.Array]) { return @($json).Count -eq 0 }
    $prop = $json.PSObject.Properties[$RootKey]
    if ($null -eq $prop -or $null -eq $prop.Value) { return $true }
    return @($prop.Value).Count -eq 0
}

function Get-UploadFiles {
    param([string]$Category)
    $categoryDir = "$deliveryRoot/${Category}_json"
    $parentFiles = @()
    $driverFiles = @()
    $extraSubrepoFiles = @()

    if ($Category -eq "issues") {
        if (Test-Path -LiteralPath $categoryDir) {
            $wi = @(Get-ChildItem $categoryDir -Filter "st_ready_issues_with_images_*.json" -ErrorAction SilentlyContinue | Where-Object { $_.Name -notmatch "summary" } | Sort-Object FullName)
            if ($wi.Count -gt 0) { $parentFiles += $wi }
            else { $parentFiles += @(Get-ChildItem $categoryDir -Filter "st_ready_issues_*.json" -ErrorAction SilentlyContinue | Where-Object { $_.Name -notmatch "summary|with_images" } | Sort-Object FullName) }
        }
        foreach ($d in @(Get-ChildItem "$deliveryRoot/drivers/*/issues_json" -Directory -ErrorAction SilentlyContinue)) {
            $wi = @(Get-ChildItem $d.FullName -Filter "st_ready_issues_with_images_*.json" -ErrorAction SilentlyContinue | Where-Object { $_.Name -notmatch "summary" } | Sort-Object FullName)
            if ($wi.Count -gt 0) { $driverFiles += $wi; continue }
            $driverFiles += @(Get-ChildItem $d.FullName -Filter "st_ready_issues_*.json" -ErrorAction SilentlyContinue | Where-Object { $_.Name -notmatch "summary|with_images" } | Sort-Object FullName)
        }
    } else {
        if (Test-Path -LiteralPath $categoryDir) {
            $parentFiles += @(Get-ChildItem $categoryDir -Filter "st_ready_${Category}_*.json" -ErrorAction SilentlyContinue | Where-Object { $_.Name -notmatch "summary" } | Sort-Object FullName)
        }
        foreach ($driver in @(Get-ChildItem "$deliveryRoot/drivers" -Directory -ErrorAction SilentlyContinue)) {
            $catDir = Join-Path $driver.FullName "${Category}_json"
            if (-not (Test-Path -LiteralPath $catDir)) {
                continue
            }
            $driverFiles += @(Get-ChildItem $catDir -Filter "st_ready_${Category}_*.json" -ErrorAction SilentlyContinue | Where-Object { $_.Name -notmatch "summary" } | Sort-Object FullName)
        }
    }

    # Also include subrepo folders that are not under /drivers (future-proof layout).
    $standardRootDirs = @("drivers", "issues_json", "files_json", "diagnostic_cards_json", "resolver_cases_json")
    foreach ($subdir in @(Get-ChildItem -Path $deliveryRoot -Directory -ErrorAction SilentlyContinue | Where-Object { $standardRootDirs -notcontains $_.Name })) {
        $catPath = Join-Path $subdir.FullName "${Category}_json"
        if (-not (Test-Path -LiteralPath $catPath)) {
            continue
        }

        if ($Category -eq "issues") {
            $wi = @(Get-ChildItem $catPath -Filter "st_ready_issues_with_images_*.json" -ErrorAction SilentlyContinue | Where-Object { $_.Name -notmatch "summary" } | Sort-Object FullName)
            if ($wi.Count -gt 0) {
                $extraSubrepoFiles += $wi
            } else {
                $extraSubrepoFiles += @(Get-ChildItem $catPath -Filter "st_ready_issues_*.json" -ErrorAction SilentlyContinue | Where-Object { $_.Name -notmatch "summary|with_images" } | Sort-Object FullName)
            }
        } else {
            $extraSubrepoFiles += @(Get-ChildItem $catPath -Filter "st_ready_${Category}_*.json" -ErrorAction SilentlyContinue | Where-Object { $_.Name -notmatch "summary" } | Sort-Object FullName)
        }
    }

    $all = @($parentFiles + $driverFiles + $extraSubrepoFiles)
    return @($all | Where-Object {
        $empty = Test-JsonRootIsEmpty -Path $_.FullName -RootKey $Category
        if ($empty) { Write-Host "[SKIP] Empty payload: $($_.Name)" -ForegroundColor Yellow }
        -not $empty
    })
}

function Upload-Category {
    param([string]$Category, [string]$RootTagPath, [string]$LinkUrl, [string]$LinkLabel)

    $existingId = $savedIds[$Category]
    $files      = @(Get-UploadFiles -Category $Category)

    if ($files.Count -eq 0) {
        Write-Host "[SKIP] No non-empty $Category files for $Series." -ForegroundColor Yellow
        return
    }

    $pp         = New-ProcessorParams -RootTagPath $RootTagPath -LinkUrl $LinkUrl -LinkLabel $LinkLabel
    $commonArgs = @(
        $uploader,
        "--kb", "$KbId",
        "--remote-user", $RemoteUser,
        "--processor", "JSON",
        "--processor-params", $pp,
        "--json-root-mode", "auto",
        "--empty-json-policy", "skip",
        "--json-split-size", "$JsonSplitSize",
        "--skip-auth-precheck",
        "--max-retries", "3",
        "--timeout", "120"
    )

    $effectiveId = $existingId
    $startIdx    = 0

    if ($effectiveId -le 0) {
        # Create datasource from first (parent) file
        $first   = $files[0]
        $datasourceName = "DB_STready_${Series}_${Category}"
        Write-Host "`nCreating $Category datasource from: $($first.Name)" -ForegroundColor Cyan
        try {
            $out     = Invoke-Python "$Category new DS" @($commonArgs + @("--operation", "new", "--datasource-name", $datasourceName, "--datasource-classification", "PUBLIC", "--files", $first.FullName))
            $parsed  = Get-DatasourceId $out
            if ($null -eq $parsed) { throw "Could not parse datasource ID for $Category" }
            $effectiveId = $parsed
            $startIdx    = 1
            $savedIds[$Category] = $effectiveId
            Save-Ids
        }
        catch {
            $msg = [string]$_.Exception.Message
            if ($msg -match "already exists") {
                Write-Host "Datasource already exists for $Category ($datasourceName), resolving ID..." -ForegroundColor Yellow
                $existingId = Resolve-ExistingDatasourceIdByName -DatasourceName $datasourceName
                if ($null -eq $existingId -or $existingId -le 0) {
                    $existingId = Resolve-DatasourceIdFromConfig -Category $Category
                }
                if ($null -eq $existingId -or $existingId -le 0) {
                    throw "Could not resolve existing datasource ID for $datasourceName"
                }
                $effectiveId = [int]$existingId
                $startIdx = 0
                $savedIds[$Category] = $effectiveId
                Save-Ids
            } else {
                throw
            }
        }
    }

    Write-Host "Uploading $($files.Count - $startIdx) remaining $Category file(s) into DS#$effectiveId..." -ForegroundColor Cyan
    for ($i = $startIdx; $i -lt $files.Count; $i++) {
        $f = $files[$i]
        Invoke-Python "$Category add $($f.Name) -> DS#$effectiveId" @($commonArgs + @("--operation", "add", "--datasource-id", "$effectiveId", "--files", $f.FullName)) | Out-Null
    }

    $savedIds[$Category] = $effectiveId
    Save-Ids
    Write-Host "[DONE] $Category -> DS#$effectiveId ($($files.Count) file(s))" -ForegroundColor Green
}

# ---- Main --------------------------------------------------------
if ($ComponentIssuesOnly) {
    Write-Host "[SKIP] Monolithic issues upload disabled by -ComponentIssuesOnly" -ForegroundColor Yellow
} elseif (-not $SkipIssues) {
    Upload-Category "issues" "issues" "https://github.com/STMicroelectronics/{{repo}}/issues/{{issue_number}}" "{{repo}} issue #{{issue_number}} - {{issue_title}}"
}
if (-not $SkipFiles)     { Upload-Category "files"           "files"           "{{github_url}}" "{{repo}} {{file_type}} - {{path}}" }
if (-not $SkipDiagnostic){ Upload-Category "diagnostic_cards" "diagnostic_cards" "{{externalURL}}" "{{repo}} diagnostic #{{issue_number}} - {{title}}" }
if (-not $SkipResolver)  { Upload-Category "resolver_cases"  "resolver_cases"  "{{externalURL}}" "{{repo}} resolver #{{issue_number}} - {{issue_title}}" }

if ($EnableIssuesByComponentFlow) {
    $splitScript = Join-Path $repoRoot "pipeline_Automation/workflow/Split_Issues_By_Component.ps1"
    $uploadScript = Join-Path $repoRoot "pipeline_Automation/workflow/Upload_Issues_By_Component.ps1"

    if (-not (Test-Path -LiteralPath $splitScript)) {
        throw "Issues-by-component split script not found: $splitScript"
    }
    if (-not (Test-Path -LiteralPath $uploadScript)) {
        throw "Issues-by-component upload script not found: $uploadScript"
    }

    Write-Host "`n===== Issues by component: split ($Series) =====" -ForegroundColor Cyan
    & powershell -ExecutionPolicy Bypass -File $splitScript -Series $Series -PythonExe $PythonExe
    if ($LASTEXITCODE -ne 0) {
        throw "Issues-by-component split failed for $Series"
    }

    Write-Host "`n===== Issues by component: upload ($Series) =====" -ForegroundColor Cyan
    & powershell -ExecutionPolicy Bypass -File $uploadScript -Series $Series -PythonExe $PythonExe -RemoteUser $RemoteUser -KbId $KbId -JsonSplitSize $JsonSplitSize
    if ($LASTEXITCODE -ne 0) {
        throw "Issues-by-component upload failed for $Series"
    }
}

Write-Host "`n===== $Series upload complete =====" -ForegroundColor Green
Write-Host "Final IDs:" -ForegroundColor Gray
$savedIds.GetEnumerator() | ForEach-Object { Write-Host "  $($_.Key) = $($_.Value)" -ForegroundColor Gray }
