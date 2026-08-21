<#
.SYNOPSIS
    Upload per-component ST-ready issues JSON into KB datasources.

.DESCRIPTION
    - Reads issues_json/by_component/summary_by_component_<series>.json.
    - Creates datasource when missing (issues_H7_ADC, issues_H7_ETH, ...).
    - Reuses saved datasource IDs on next runs and performs add automatically.
    - Keeps existing workflows untouched.

.EXAMPLES
    .\Upload_Issues_By_Component.ps1 -Series H7
    .\Upload_Issues_By_Component.ps1 -Series H7 -DryRun
    .\Upload_Issues_By_Component.ps1 -AllSeries
#>

param(
    [string]$Series,

    [switch]$AllSeries,
    [string]$RemoteUser = "abir.gharbi@st.com",
    [string]$ApiKey = "",
    [string]$ClientAppName = "",
    [int]$KbId = 793,
    [int]$JsonSplitSize = 1000,
    [string]$PythonExe = "",
    [ValidateSet("add", "replace")]
    [string]$ExistingDatasourcePolicy = "add",
    [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $repoRoot

$cfgAllPath = "shared/config/config_all_series.json"
$cfgAll = Get-Content -LiteralPath $cfgAllPath -Raw | ConvertFrom-Json
$seriesMap = @{}
foreach ($seriesFull in @($cfgAll.all_series)) {
    $name = [string]$seriesFull
    if (-not $name.StartsWith("STM32Cube")) {
        continue
    }
    $seriesCode = $name.Substring(9).ToUpperInvariant()
    $seriesMap[$seriesCode] = $name.ToLowerInvariant()
}

if (-not $AllSeries -and -not $Series) {
    throw "Use -Series <name> or -AllSeries."
}

if (-not $AllSeries) {
    $Series = $Series.ToUpperInvariant()
    if (-not $seriesMap.ContainsKey($Series)) {
        $allowed = ($seriesMap.Keys | Sort-Object) -join ", "
        throw "Unsupported series '$Series'. Allowed (from $cfgAllPath): $allowed"
    }
}

if (-not $PythonExe) {
    $venvPy = Join-Path $repoRoot ".venv\Scripts\python.exe"
    if (Test-Path -LiteralPath $venvPy) {
        $PythonExe = $venvPy
    } else {
        $PythonExe = "python"
    }
}

$uploader = "pipeline_Automation/upload/Add_Data_Source_Files.py"
if (-not (Test-Path -LiteralPath $uploader)) {
    throw "Missing uploader script: $uploader"
}

function New-ProcessorParamsBase64 {
    param([string]$RootTagPath, [string]$LinkUrl, [string]$LinkLabel)
    $json = (@{
        rootTagPath = $RootTagPath
        externalURL = $LinkUrl
        label = $LinkLabel
    } | ConvertTo-Json -Compress)

    $bytes = [System.Text.Encoding]::UTF8.GetBytes($json)
    return "base64:$([Convert]::ToBase64String($bytes))"
}

function Invoke-Uploader {
    param([string]$Label, [string[]]$CommandArgs)

    if ($DryRun) {
        Write-Host "[dry-run] $Label" -ForegroundColor DarkYellow
        Write-Host ("  " + (($CommandArgs | ForEach-Object {
            if ($_ -match '[\s"]') { '"' + ($_ -replace '"', '\\"') + '"' } else { $_ }
        }) -join " "))
        return @()
    }

    Write-Host "[upload] $Label" -ForegroundColor Green

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

        if ($proc.ExitCode -ne 0) {
            $details = @($stderr + $stdout) -join "`n"
            throw "Uploader failed ($Label) exit=$($proc.ExitCode)`n$details"
        }

        return @($stdout + $stderr)
    } finally {
        Remove-Item -LiteralPath $tmpOut -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $tmpErr -ErrorAction SilentlyContinue
    }
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

function Parse-DatasourceId {
    param([string[]]$Lines)
    foreach ($line in $Lines) {
        if ($line -match "Datasource ID returned:\s*(\d+)") {
            return [int]$Matches[1]
        }
    }
    return $null
}

function Load-IdCache {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        return @{}
    }

    try {
        $rawText = Get-Content -LiteralPath $Path -Raw
        if ($rawText -match "^version\s+https://git-lfs.github.com/spec/v1") {
            Write-Host "[warn] Component ID cache is a Git LFS pointer (not materialized): $Path" -ForegroundColor Yellow
            Write-Host "[warn] This run has no concrete component IDs from cache; enable LFS checkout or provide IDs by another source." -ForegroundColor DarkYellow
            return @{}
        }
        $raw = $rawText | ConvertFrom-Json
    } catch {
        Write-Host "[warn] Invalid JSON in component ID cache, ignoring file: $Path" -ForegroundColor Yellow
        $backupPath = "$Path.invalid"
        try {
            $rawText | Set-Content -LiteralPath $backupPath -Encoding UTF8
            Write-Host "[warn] Corrupted cache content saved to: $backupPath" -ForegroundColor DarkYellow
        } catch {
            Write-Host "[warn] Failed to persist corrupted cache backup: $($_.Exception.Message)" -ForegroundColor DarkYellow
        }
        return @{}
    }

    if ($null -eq $raw) {
        return @{}
    }

    $cache = @{}
    foreach ($p in $raw.PSObject.Properties) {
        $v = 0
        if ([int]::TryParse([string]$p.Value, [ref]$v) -and $v -gt 0) {
            $cache[$p.Name] = $v
        }
    }
    return $cache
}

function Save-IdCache {
    param([hashtable]$Cache, [string]$Path)
    $dir = Split-Path -Parent $Path
    if (-not (Test-Path -LiteralPath $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
    $Cache | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $Path -Encoding UTF8
}

function Upload-SeriesByComponent {
    param([string]$Slug)

    $seriesRoot = "datasets/07_delivery/st_ready/by_series/$Slug"
    $byComponentDir = "$seriesRoot/issues_json/by_component"
    $seriesCode = ($Slug -replace "^stm32cube", "").ToUpper()
    $summaryName = "summary_by_component_$($seriesCode.ToLower()).json"
    $idCachePath = Join-Path $byComponentDir "upload_ids_by_component_$($seriesCode.ToLower()).json"

    $summaryFiles = @(
        Get-ChildItem -Path $seriesRoot -Recurse -File -Filter $summaryName -ErrorAction SilentlyContinue |
            Where-Object { $_.DirectoryName -match "issues_json[\\/]by_component$" } |
            Sort-Object FullName
    )

    if ($summaryFiles.Count -eq 0) {
        Write-Host "[skip] no by-component summaries found for ${Slug}" -ForegroundColor Yellow
        return
    }

    $idCache = Load-IdCache -Path $idCachePath
    $items = @()
    foreach ($summaryFile in $summaryFiles) {
        try {
            $summary = Get-Content -LiteralPath $summaryFile.FullName -Raw | ConvertFrom-Json
        } catch {
            Write-Host "[skip] invalid summary JSON for ${Slug}: $($summaryFile.FullName)" -ForegroundColor Yellow
            Write-Host "[skip] parse error: $($_.Exception.Message)" -ForegroundColor DarkYellow
            continue
        }

        if ($null -eq $summary -or $null -eq $summary.datasources) {
            Write-Host "[skip] no datasources in summary: $($summaryFile.FullName)" -ForegroundColor Yellow
            continue
        }

        $items += @($summary.datasources)
    }

    if ($items.Count -eq 0) {
        Write-Host "[skip] no datasource rows found in by-component summaries for $Slug" -ForegroundColor Yellow
        return
    }

    # Group files by datasource to avoid repeated replace/new on the same datasource.
    # Pattern: one "new" (with selected policy) for first file, then "add" for remaining.
    $grouped = @{}
    foreach ($item in $items) {
        $datasourceName = [string]$item.datasource_name
        $filePath = [string]$item.output_file
        $issuesCount = [int]$item.issues_count

        if (-not $datasourceName) {
            Write-Host "[skip] datasource_name missing in summary row" -ForegroundColor Yellow
            continue
        }
        if (-not $filePath -or -not (Test-Path -LiteralPath $filePath)) {
            Write-Host "[skip] file missing for $datasourceName" -ForegroundColor Yellow
            continue
        }
        if ($issuesCount -le 0) {
            Write-Host "[skip] empty payload for $datasourceName" -ForegroundColor Yellow
            continue
        }

        if (-not $grouped.ContainsKey($datasourceName)) {
            $grouped[$datasourceName] = @()
        }
        $grouped[$datasourceName] += $filePath
    }

    $processorParams = New-ProcessorParamsBase64 `
        -RootTagPath "issues" `
        -LinkUrl "https://github.com/STMicroelectronics/{{repo}}/issues/{{issue_number}}" `
        -LinkLabel "{{repo}} issue #{{issue_number}} - {{issue_title}}"

    foreach ($datasourceName in ($grouped.Keys | Sort-Object)) {
        $filePaths = @($grouped[$datasourceName] | Sort-Object -Unique)
        if ($filePaths.Count -eq 0) {
            continue
        }

        $existingIdHint = 0
        if ($idCache.ContainsKey($datasourceName)) {
            $existingIdHint = [int]$idCache[$datasourceName]
        }

        # First file: create/reuse datasource according to selected policy.
        $firstFile = $filePaths[0]
        $newArgs = @(
            $uploader,
            "--kb", "$KbId",
            "--operation", "new",
            "--datasource-name", $datasourceName,
            "--datasource-classification", "PUBLIC",
            "--existing-datasource-policy", $ExistingDatasourcePolicy,
            "--name-conflict-unresolved-policy", "skip",
            "--remote-user", $RemoteUser,
            "--processor", "JSON",
            "--processor-params", $processorParams,
            "--json-root-mode", "auto",
            "--empty-json-policy", "skip",
            "--json-split-size", "$JsonSplitSize",
            "--timeout", "60",
            "--files", $firstFile
        )
        if ($existingIdHint -gt 0) {
            $newArgs += @("--existing-datasource-id-hint", "$existingIdHint")
        }
        $newArgs += @(Get-UploadAuthArgs)

        $newOutLines = Invoke-Uploader -Label "$datasourceName ($ExistingDatasourcePolicy/new)" -CommandArgs $newArgs

        $activeDatasourceId = 0
        if (-not $DryRun) {
            $parsedId = Parse-DatasourceId -Lines $newOutLines
            if ($parsedId) {
                $activeDatasourceId = [int]$parsedId
                $idCache[$datasourceName] = $activeDatasourceId
                Save-IdCache -Cache $idCache -Path $idCachePath
                Write-Host "[saved] $datasourceName -> $activeDatasourceId" -ForegroundColor DarkCyan
            } elseif ($existingIdHint -gt 0) {
                $activeDatasourceId = $existingIdHint
                Write-Host "[warn] datasource ID not found in output for $datasourceName; fallback to cached ID $activeDatasourceId for add uploads." -ForegroundColor Yellow
            }
        }

        # Remaining files: append into the resolved datasource ID.
        if ($filePaths.Count -le 1) {
            continue
        }

        if ($DryRun) {
            foreach ($extraFile in $filePaths[1..($filePaths.Count - 1)]) {
                $addArgsDry = @(
                    $uploader,
                    "--kb", "$KbId",
                    "--operation", "add",
                    "--datasource-id", "<resolved-at-runtime>",
                    "--remote-user", $RemoteUser,
                    "--processor", "JSON",
                    "--processor-params", $processorParams,
                    "--json-root-mode", "auto",
                    "--empty-json-policy", "skip",
                    "--json-split-size", "$JsonSplitSize",
                    "--timeout", "60",
                    "--files", $extraFile
                )
                $addArgsDry += @(Get-UploadAuthArgs)
                Invoke-Uploader -Label "$datasourceName (add)" -CommandArgs $addArgsDry | Out-Null
            }
            continue
        }

        if ($activeDatasourceId -le 0) {
            Write-Host "[warn] could not resolve datasource ID for $datasourceName; skipping add uploads for remaining files." -ForegroundColor Yellow
            continue
        }

        foreach ($extraFile in $filePaths[1..($filePaths.Count - 1)]) {
            $addArgs = @(
                $uploader,
                "--kb", "$KbId",
                "--operation", "add",
                "--datasource-id", "$activeDatasourceId",
                "--remote-user", $RemoteUser,
                "--processor", "JSON",
                "--processor-params", $processorParams,
                "--json-root-mode", "auto",
                "--empty-json-policy", "skip",
                "--json-split-size", "$JsonSplitSize",
                "--timeout", "60",
                "--files", $extraFile
            )
            $addArgs += @(Get-UploadAuthArgs)
            Invoke-Uploader -Label "$datasourceName (add)" -CommandArgs $addArgs | Out-Null
        }
    }

    if (-not $DryRun) {
        Save-IdCache -Cache $idCache -Path $idCachePath
    }

    Write-Host "[done] upload by component completed for $Slug" -ForegroundColor Cyan
}

$targets = @()
if ($AllSeries) {
    $targets = $seriesMap.Values | Sort-Object -Unique
} else {
    $targets = @($seriesMap[$Series])
}

foreach ($slug in $targets) {
    Upload-SeriesByComponent -Slug $slug
}

Write-Host "All requested series processed." -ForegroundColor Green
