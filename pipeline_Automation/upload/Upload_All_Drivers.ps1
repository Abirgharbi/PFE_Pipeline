<#
.SYNOPSIS
    Upload all driver sub-repo artifacts (issues, files, diagnostic_cards, resolver_cases)
    to the correct series datasources in KB #793.

.DESCRIPTION
    Reads datasource IDs from shared/config/config_all_series.json and scans
    by_series/<series>/drivers/<driver>/ for JSON artifacts, then uploads them
    with --operation add into the corresponding series-level datasource.

    Skips series with null IDs. Skips empty JSON payloads.
    For issues: prefers st_ready_issues_with_images_* (Alfred-enriched) over plain.
    Auto-detects .venv\Scripts\python.exe if PythonExe not specified.
#>

param(
    [Parameter(Mandatory = $true)]
    [string]$RemoteUser,

    # Limit to specific series short names (e.g. "G4", "L0", "H7"). Default = all series with IDs.
    [string[]]$SeriesFilter = @(),

    [switch]$SkipIssues,
    [switch]$SkipFiles,
    [switch]$SkipDiagnostic,
    [switch]$SkipResolver,

    [int]$KbId = 793,
    [int]$JsonSplitSize = 1000,

    # Auto-detected from .venv\Scripts\python.exe if left empty
    [string]$PythonExe = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ScriptDir    = $PSScriptRoot
$RepoRoot     = (Resolve-Path (Join-Path $ScriptDir "..\..\")).Path
Set-Location $RepoRoot

# ---- Auto-detect Python venv ----
if (-not $PythonExe) {
    $venvPy    = Join-Path $RepoRoot ".venv\Scripts\python.exe"
    $PythonExe = if (Test-Path $venvPy) { $venvPy } else { "python" }
}
Write-Host "Python  : $PythonExe"
Write-Host "KB      : #$KbId"
Write-Host "Remote  : $RemoteUser"
Write-Host ""

$Uploader    = Join-Path $RepoRoot "pipeline_Automation\upload\Add_Data_Source_Files.py"
$ConfigFile  = Join-Path $RepoRoot "shared\config\config_all_series.json"
$BySeriesRoot= Join-Path $RepoRoot "datasets\07_delivery\st_ready\by_series"

if (-not (Test-Path $Uploader))   { throw "Uploader not found: $Uploader" }
if (-not (Test-Path $ConfigFile)) { throw "Config not found: $ConfigFile" }

# ---- Read IDs from config ----
$Config = Get-Content $ConfigFile -Raw | ConvertFrom-Json

# ---- Processor params (base64) per category ----
function Get-ProcessorParams {
    param([string]$Category)
    $jsonStr = switch ($Category) {
        "issues"           { '{"rootTagPath":"issues","externalURL":"{{github_url}}","label":"{{repo}} issue #{{issue_number}} - {{issue_title}}"}' }
        "files"            { '{"rootTagPath":"files","externalURL":"{{github_url}}","label":"{{repo}} {{file_type}} - {{path}}"}' }
        "diagnostic_cards" { '{"rootTagPath":"diagnostic_cards","externalURL":"{{externalURL}}","label":"{{repo}} diagnostic #{{issue_number}} - {{title}}"}' }
        "resolver_cases"   { '{"rootTagPath":"resolver_cases","externalURL":"{{externalURL}}","label":"{{repo}} resolver #{{issue_number}} - {{issue_title}}"}' }
        default { '{}' }
    }
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($jsonStr)
    return "base64:" + [System.Convert]::ToBase64String($bytes)
}

# ---- Empty payload check ----
function Test-JsonPayloadEmpty {
    param([string]$Path, [string]$RootKey)
    try {
        $obj  = Get-Content $Path -Raw | ConvertFrom-Json
        $prop = $obj.PSObject.Properties[$RootKey]
        if ($null -eq $prop) { return $true }
        $val  = $prop.Value
        if ($null -eq $val)  { return $true }
        if ($val -is [System.Collections.IEnumerable] -and -not ($val -is [string])) {
            return @($val).Count -eq 0
        }
        return $false
    } catch { return $true }
}

# ---- Upload one file ----
function Invoke-Upload {
    param([int]$DatasourceId, [string]$FilePath, [string]$ProcessorParams)
    $cmdArgs = @(
        $Uploader,
        "--kb",               "$KbId",
        "--remote-user",      $RemoteUser,
        "--operation",        "add",
        "--datasource-id",    "$DatasourceId",
        "--processor",        "JSON",
        "--processor-params", $ProcessorParams,
        "--json-root-mode",   "auto",
        "--empty-json-policy","skip",
        "--json-split-size",  "$JsonSplitSize",
        "--files",            $FilePath
    )
    Write-Host "  -> DS#$DatasourceId  $(Split-Path $FilePath -Leaf)" -ForegroundColor Cyan
    & $PythonExe @cmdArgs
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "  Upload returned exit code $LASTEXITCODE for: $(Split-Path $FilePath -Leaf)"
    }
}

# ---- Category definitions ----
# Name = category key, Dir = subfolder under driver repo, Root = JSON root key, IdKey = key in config
$Categories = @(
    [PSCustomObject]@{ Name="issues";           Dir="issues_json";           Root="issues";           IdKey="issues"     }
    [PSCustomObject]@{ Name="files";            Dir="files_json";            Root="files";            IdKey="files"      }
    [PSCustomObject]@{ Name="diagnostic_cards"; Dir="diagnostic_cards_json"; Root="diagnostic_cards"; IdKey="diagnostic" }
    [PSCustomObject]@{ Name="resolver_cases";   Dir="resolver_cases_json";   Root="resolver_cases";   IdKey="resolver"   }
)

# ---- Series filter set ----
$filterSet = @{}
foreach ($s in $SeriesFilter) { $filterSet[$s.ToUpper()] = $true }

$totalUploaded = 0
$totalSkipped  = 0
$totalFailed   = 0

# ---- Main loop: iterate series ----
foreach ($prop in $Config.kb_datasource_ids.PSObject.Properties) {
    $SeriesName = $prop.Name        # e.g. "STM32CubeG4"
    $Ids        = $prop.Value
    $SeriesKey  = $SeriesName.ToUpper()
    $shortKey   = $SeriesKey -replace "STM32CUBE", ""    # "G4", "L0", etc.

    # Apply series filter
    if ($filterSet.Count -gt 0) {
        if (-not ($filterSet.ContainsKey($SeriesKey) -or $filterSet.ContainsKey($shortKey))) {
            continue
        }
    }

    $SeriesSlug = $SeriesName.ToLower()                   # "stm32cubeg4"
    $DriversDir = Join-Path $BySeriesRoot "$SeriesSlug\drivers"

    if (-not (Test-Path $DriversDir)) { continue }

    $DriverRepos = @(Get-ChildItem $DriversDir -Directory -ErrorAction SilentlyContinue)
    if ($DriverRepos.Count -eq 0) { continue }

    Write-Host "=== $SeriesName  ($($DriverRepos.Count) driver(s)) ===" -ForegroundColor Magenta

    foreach ($Cat in $Categories) {
        # Skip flags
        if ($SkipIssues    -and $Cat.Name -eq "issues")            { continue }
        if ($SkipFiles     -and $Cat.Name -eq "files")             { continue }
        if ($SkipDiagnostic -and $Cat.Name -eq "diagnostic_cards") { continue }
        if ($SkipResolver  -and $Cat.Name -eq "resolver_cases")    { continue }

        # Resolve datasource ID from config
        $idProp = $Ids.PSObject.Properties[$Cat.IdKey]
        if ($null -eq $idProp -or $null -eq $idProp.Value) {
            Write-Host "  [NO ID ] $($Cat.Name) for $SeriesName - add to config_all_series.json first" -ForegroundColor DarkGray
            continue
        }
        $DsId = [int]$idProp.Value
        $pp   = Get-ProcessorParams -Category $Cat.Name

        foreach ($DriverRepo in $DriverRepos) {
            $catDir = Join-Path $DriverRepo.FullName $Cat.Dir
            if (-not (Test-Path $catDir)) { continue }

            # For issues: prefer with_images (Alfred-enriched), fallback to plain
            if ($Cat.Name -eq "issues") {
                $wiFiles = @(Get-ChildItem $catDir -Filter "st_ready_issues_with_images_*.json" -ErrorAction SilentlyContinue |
                             Where-Object { $_.Name -notmatch "summary|alfred_summary" } | Sort-Object Name)
                $files = if ($wiFiles.Count -gt 0) {
                    $wiFiles
                } else {
                    @(Get-ChildItem $catDir -Filter "st_ready_issues_*.json" -ErrorAction SilentlyContinue |
                      Where-Object { $_.Name -notmatch "summary|with_images" } | Sort-Object Name)
                }
            } else {
                $glob  = "st_ready_$($Cat.Name)_*.json"
                $files = @(Get-ChildItem $catDir -Filter $glob -ErrorAction SilentlyContinue |
                           Where-Object { $_.Name -notmatch "summary" } | Sort-Object Name)
            }

            foreach ($f in $files) {
                if (Test-JsonPayloadEmpty -Path $f.FullName -RootKey $Cat.Root) {
                    Write-Host "  [EMPTY ] $($DriverRepo.Name)/$($Cat.Dir)/$($f.Name)" -ForegroundColor DarkYellow
                    $totalSkipped++
                    continue
                }
                try {
                    Invoke-Upload -DatasourceId $DsId -FilePath $f.FullName -ProcessorParams $pp
                    $totalUploaded++
                } catch {
                    Write-Warning "  [FAIL] $($f.Name): $_"
                    $totalFailed++
                }
            }
        }
    }
    Write-Host ""
}

Write-Host "====== SUMMARY ======" -ForegroundColor Cyan
Write-Host "Uploaded : $totalUploaded" -ForegroundColor Green
Write-Host "Skipped  : $totalSkipped"  -ForegroundColor Yellow
if ($totalFailed -gt 0) {
    Write-Host "Failed   : $totalFailed" -ForegroundColor Red
}
