param(
    [Parameter(Mandatory = $true)]
    [string]$RemoteUser,

    [string]$PythonExe = "python",
    [ValidateSet("add", "new")]
    [string]$Operation = "add",
    [ValidateSet("", "add", "new")]
    [string]$FilesOperation = "",
    [int]$KbId = 793,
    [int]$IssuesDatasourceId = 19896,
    [int]$FilesDatasourceId = 21824,
    [int]$DiagnosticDatasourceId = 23768,
    [int]$ResolverDatasourceId = 20403,
    [string]$IssuesDatasourceName = "",
    [string]$FilesDatasourceName = "",
    [string]$DiagnosticDatasourceName = "",
    [string]$ResolverDatasourceName = "",
    [string]$DatasourceClassification = "PUBLIC",
    [string]$DatasourceTags = "",
    [string]$Service = "kb",
    [string]$RequestTypes = "",
    [string]$PayloadModes = "flat",
    [string]$TimestampModes = "s",
    [string]$RequestPartNames = "request,body,payload",
    [int]$JsonSplitSize = 0,
    [double]$JsonSplitMinMb = 2.0,
    [string]$IssuesRootTagPath = "issues",
    [string]$FilesRootTagPath = "files",
    [string]$DiagnosticRootTagPath = "diagnostic_cards",
    [string]$ResolverRootTagPath = "resolver_cases",
    [string]$IssuesLinkUrlTemplate = "{{github_url}}",
    [string]$FilesLinkUrlTemplate = "https://github.com/STMicroelectronics/{{repo}}/search?q={{path}}&type=code",
    [string]$DiagnosticLinkUrlTemplate = "{{externalURL}}",
    [string]$ResolverLinkUrlTemplate = "{{externalURL}}",
    [string]$IssuesLinkLabelTemplate = "{{repo}} issue #{{issue_number}} - {{issue_title}}",
    [string]$FilesLinkLabelTemplate = "{{repo}} {{file_type}} - {{path}}",
    [string]$DiagnosticLinkLabelTemplate = "{{repo}} diagnostic #{{issue_number}} - {{title}}",
    [string]$ResolverLinkLabelTemplate = "{{repo}} resolver #{{issue_number}} - {{issue_title}}",
    [string]$IssuesFiles = "",
    [string]$FilesFiles = "",
    [string]$DiagnosticFiles = "",
    [string]$ResolverFiles = "",
    [switch]$DeleteFilesBeforeAdd,
    [string]$ApiKey = "",
    [string]$ClientAppName = "",
    [string]$RootDir = "datasets/07_delivery/st_ready",
    [switch]$VerifySsl,
    [switch]$UseLegacyProxy,
    [switch]$VerboseUpload
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function New-ProcessorParamsJson {
    param(
        [string]$RootTagPath,
        [string]$LinkUrlTemplate,
        [string]$LinkLabelTemplate
    )

    $processorParams = @{}

    if ($RootTagPath) {
        $processorParams["rootTagPath"] = $RootTagPath
    }
    if ($LinkUrlTemplate) {
        $processorParams["externalURL"] = $LinkUrlTemplate
    }
    if ($LinkLabelTemplate) {
        $processorParams["label"] = $LinkLabelTemplate
    }

    if ($processorParams.Count -eq 0) {
        return ""
    }

    return ($processorParams | ConvertTo-Json -Compress)
}

function Encode-ProcessorParamsArg {
    param(
        [string]$ProcessorParamsJson
    )

    if (-not $ProcessorParamsJson) {
        return ""
    }

    $bytes = [System.Text.Encoding]::UTF8.GetBytes($ProcessorParamsJson)
    $encoded = [System.Convert]::ToBase64String($bytes)
    return "base64:$encoded"
}

function Resolve-JsonFiles {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Directory,
        [Parameter(Mandatory = $true)]
        [string]$DefaultPattern,
        [string]$ExplicitFilesCsv,
        [string]$Label
    )

    $resolved = @()

    if ($ExplicitFilesCsv) {
        $entries = @(
            $ExplicitFilesCsv -split "," |
            ForEach-Object { $_.Trim() } |
            Where-Object { $_ }
        )

        foreach ($entry in $entries) {
            $candidate = if ([System.IO.Path]::IsPathRooted($entry)) {
                $entry
            } else {
                Join-Path $Directory $entry
            }

            if (-not (Test-Path -LiteralPath $candidate)) {
                throw "$Label file not found: $candidate"
            }

            $resolved += Get-Item -LiteralPath $candidate
        }
    } else {
        $resolved = @(Get-ChildItem -LiteralPath $Directory -Filter $DefaultPattern -File)
    }

    $resolved = @($resolved | Sort-Object Name)

    if ($resolved.Count -eq 0) {
        throw "No $DefaultPattern found in $Directory"
    }

    return $resolved
}

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $repoRoot

$uploader = Join-Path $repoRoot "pipeline_Automation/upload/Add_Data_Source_Files.py"
if (-not (Test-Path -LiteralPath $uploader)) {
    throw "Uploader script not found: $uploader"
}

$filesDir = Join-Path $repoRoot (Join-Path $RootDir "files_json")
$diagnosticDir = Join-Path $repoRoot (Join-Path $RootDir "diagnostic_cards_json")
$resolverDir = Join-Path $repoRoot (Join-Path $RootDir "resolver_cases_json")
$issuesDir = Join-Path $repoRoot (Join-Path $RootDir "issues_json")

if (-not (Test-Path -LiteralPath $filesDir)) {
    throw "Files directory not found: $filesDir"
}
if (-not (Test-Path -LiteralPath $diagnosticDir)) {
    throw "Diagnostic cards directory not found: $diagnosticDir"
}
if (-not (Test-Path -LiteralPath $resolverDir)) {
    throw "Resolver directory not found: $resolverDir"
}
if (-not (Test-Path -LiteralPath $issuesDir)) {
    throw "Issues directory not found: $issuesDir"
}

$filesJson = @(Resolve-JsonFiles -Directory $filesDir -DefaultPattern "st_ready_files_*.json" -ExplicitFilesCsv $FilesFiles -Label "files")
$diagnosticJson = @(Resolve-JsonFiles -Directory $diagnosticDir -DefaultPattern "st_ready_diagnostic_cards_*.json" -ExplicitFilesCsv $DiagnosticFiles -Label "diagnostic")
$resolverJson = @(Resolve-JsonFiles -Directory $resolverDir -DefaultPattern "st_ready_resolver_cases_*.json" -ExplicitFilesCsv $ResolverFiles -Label "resolver")
$issuesJson = @(Resolve-JsonFiles -Directory $issuesDir -DefaultPattern "st_ready_issues_*.json" -ExplicitFilesCsv $IssuesFiles -Label "issues")

Write-Host "KB: $KbId"
Write-Host "Operation: $Operation"
$issuesOperation = $Operation
$filesOperationRequested = if ($FilesOperation) { $FilesOperation } else { $Operation }
$diagnosticOperation = $Operation
$resolverOperation = $Operation
$filesDatasourceIdForDelete = $FilesDatasourceId
$recreateFilesDatasourceAfterDelete = $DeleteFilesBeforeAdd -and ($filesOperationRequested -eq "add")
$filesOperationResolved = if ($recreateFilesDatasourceAfterDelete) { "new" } else { $filesOperationRequested }

Write-Host "Issues operation: $issuesOperation"
Write-Host "Files operation: $filesOperationResolved"
Write-Host "Diagnostic operation: $diagnosticOperation"
Write-Host "Resolver operation: $resolverOperation"

if ($recreateFilesDatasourceAfterDelete) {
    Write-Warning (
        "Delete API marks datasource as deleted in this backend. " +
        "Files upload will create a new datasource instead of reusing ID $filesDatasourceIdForDelete."
    )
}

if ($issuesOperation -eq "add") {
    Write-Host "Issues datasource: $IssuesDatasourceId"
}
if ($filesOperationResolved -eq "add") {
    Write-Host "Files datasource: $FilesDatasourceId"
}
if ($DeleteFilesBeforeAdd) {
    Write-Host "Files datasource to delete: $filesDatasourceIdForDelete"
}
if ($diagnosticOperation -eq "add") {
    Write-Host "Diagnostic datasource: $DiagnosticDatasourceId"
}
if ($resolverOperation -eq "add") {
    Write-Host "Resolver datasource: $ResolverDatasourceId"
}
if ($DeleteFilesBeforeAdd) {
    Write-Host "Delete files before files upload: enabled"
}
Write-Host "Service: $Service"
if ($RequestTypes) {
    Write-Host "Request types: $RequestTypes"
}
Write-Host "Payload modes: $PayloadModes"
Write-Host "Timestamp modes: $TimestampModes"
Write-Host "Request part names: $RequestPartNames"
if ($JsonSplitSize -gt 0) {
    Write-Host "JSON split size: $JsonSplitSize"
    if ($JsonSplitMinMb -gt 0) {
        Write-Host "JSON split min size (MB): $JsonSplitMinMb"
    }
}
if ($ClientAppName) {
    Write-Host "Client app name: $ClientAppName"
}
if ($ApiKey) {
    Write-Host "API key: provided via parameter"
}
if ($ApiKey -and @("TA_VRAIE_API_KEY", "TA_CLE_REELLE", "MA_CLE_API", "VRAIE_CLE_API", "YOUR_API_KEY", "REPLACE_ME", "API_KEY_HERE") -contains $ApiKey.ToUpperInvariant()) {
    throw "ApiKey parameter looks like a placeholder. Replace it with your real ST API key."
}
if ($ClientAppName -eq "stm32-cube-kb-client-app") {
    Write-Warning "ClientAppName 'stm32-cube-kb-client-app' is often rejected. Use your persona app name or omit -ClientAppName to use script auto-resolution."
}
if ($RemoteUser -notmatch '^[^@\s]+@[^@\s]+\.[^@\s]+$') {
    throw "RemoteUser must be a valid email with a single '@' (example: first.last@st.com)."
}
if ($DeleteFilesBeforeAdd -and $filesDatasourceIdForDelete -le 0) {
    throw "-DeleteFilesBeforeAdd requires -FilesDatasourceId > 0."
}
Write-Host "Remote user: $RemoteUser"
Write-Host "Found issues_json: $($issuesJson.Count)"
Write-Host "Found files_json: $($filesJson.Count)"
Write-Host "Found diagnostic_cards_json: $($diagnosticJson.Count)"
Write-Host "Found resolver_cases_json: $($resolverJson.Count)"

if (($issuesOperation -eq "new") -or ($filesOperationResolved -eq "new") -or ($diagnosticOperation -eq "new") -or ($resolverOperation -eq "new")) {
    $stamp = Get-Date -Format "yyyyMMdd_HHmmss"
    if (($issuesOperation -eq "new") -and (-not $IssuesDatasourceName)) {
        $IssuesDatasourceName = "DB_STready_Issues_$stamp"
    }
    if (($filesOperationResolved -eq "new") -and (-not $FilesDatasourceName)) {
        $FilesDatasourceName = "DB_STready_Files_$stamp"
    }
    if (($diagnosticOperation -eq "new") -and (-not $DiagnosticDatasourceName)) {
        $DiagnosticDatasourceName = "DB_STready_Diagnostic_$stamp"
    }
    if (($resolverOperation -eq "new") -and (-not $ResolverDatasourceName)) {
        $ResolverDatasourceName = "DB_STready_Resolver_$stamp"
    }

    if ($issuesOperation -eq "new") {
        Write-Host "Issues datasource name: $IssuesDatasourceName"
    }
    if ($filesOperationResolved -eq "new") {
        Write-Host "Files datasource name: $FilesDatasourceName"
    }
    if ($diagnosticOperation -eq "new") {
        Write-Host "Diagnostic datasource name: $DiagnosticDatasourceName"
    }
    if ($resolverOperation -eq "new") {
        Write-Host "Resolver datasource name: $ResolverDatasourceName"
    }
    Write-Host "Datasource classification: $DatasourceClassification"
    if ($DatasourceTags) {
        Write-Host "Datasource tags: $DatasourceTags"
    }
}

$issuesProcessorParams = New-ProcessorParamsJson -RootTagPath $IssuesRootTagPath -LinkUrlTemplate $IssuesLinkUrlTemplate -LinkLabelTemplate $IssuesLinkLabelTemplate
$filesProcessorParams = New-ProcessorParamsJson -RootTagPath $FilesRootTagPath -LinkUrlTemplate $FilesLinkUrlTemplate -LinkLabelTemplate $FilesLinkLabelTemplate
$diagnosticProcessorParams = New-ProcessorParamsJson -RootTagPath $DiagnosticRootTagPath -LinkUrlTemplate $DiagnosticLinkUrlTemplate -LinkLabelTemplate $DiagnosticLinkLabelTemplate
$resolverProcessorParams = New-ProcessorParamsJson -RootTagPath $ResolverRootTagPath -LinkUrlTemplate $ResolverLinkUrlTemplate -LinkLabelTemplate $ResolverLinkLabelTemplate

$issuesProcessorParamsArg = Encode-ProcessorParamsArg -ProcessorParamsJson $issuesProcessorParams
$filesProcessorParamsArg = Encode-ProcessorParamsArg -ProcessorParamsJson $filesProcessorParams
$diagnosticProcessorParamsArg = Encode-ProcessorParamsArg -ProcessorParamsJson $diagnosticProcessorParams
$resolverProcessorParamsArg = Encode-ProcessorParamsArg -ProcessorParamsJson $resolverProcessorParams

if ($issuesProcessorParams) {
    Write-Host "Issues processor params: $issuesProcessorParams"
}
if ($filesProcessorParams) {
    Write-Host "Files processor params: $filesProcessorParams"
}
if ($diagnosticProcessorParams) {
    Write-Host "Diagnostic processor params: $diagnosticProcessorParams"
}
if ($resolverProcessorParams) {
    Write-Host "Resolver processor params: $resolverProcessorParams"
}

$commonArgs = @(
    $uploader,
    "--kb", $KbId,
    "--remote-user", $RemoteUser,
    "--service", $Service,
    "--payload-modes", $PayloadModes,
    "--timestamp-modes", $TimestampModes,
    "--request-part-names", $RequestPartNames,
    "--processor", "JSON",
    "--json-root-mode", "auto",
    "--empty-json-policy", "skip",
    "--skip-auth-precheck",
    "--max-retries", 3,
    "--timeout", 120
)

if ($RequestTypes) {
    $commonArgs += @("--request-types", $RequestTypes)
}
if ($ApiKey) {
    $commonArgs += @("--api-key", $ApiKey)
}
if ($ClientAppName) {
    $commonArgs += @("--client-app-name", $ClientAppName)
}

if ($VerifySsl) {
    $commonArgs += "--verify-ssl"
}
if ($UseLegacyProxy) {
    $commonArgs += "--use-legacy-proxy"
}
if ($VerboseUpload) {
    $commonArgs += "--verbose"
}

$issuesCommonArgs = $commonArgs + @("--operation", $issuesOperation)
$filesCommonArgs = $commonArgs + @("--operation", $filesOperationResolved)
$diagnosticCommonArgs = $commonArgs + @("--operation", $diagnosticOperation)
$resolverCommonArgs = $commonArgs + @("--operation", $resolverOperation)

if (($issuesOperation -in @("add", "new")) -and $issuesProcessorParamsArg) {
    $issuesCommonArgs += @("--processor-params", $issuesProcessorParamsArg)
}
if (($filesOperationResolved -in @("add", "new")) -and $filesProcessorParamsArg) {
    $filesCommonArgs += @("--processor-params", $filesProcessorParamsArg)
}
if (($diagnosticOperation -in @("add", "new")) -and $diagnosticProcessorParamsArg) {
    $diagnosticCommonArgs += @("--processor-params", $diagnosticProcessorParamsArg)
}
if (($resolverOperation -in @("add", "new")) -and $resolverProcessorParamsArg) {
    $resolverCommonArgs += @("--processor-params", $resolverProcessorParamsArg)
}

$filesDeleteArgs = @(
    $uploader,
    "--kb", $KbId,
    "--operation", "delete",
    "--datasource-id", $filesDatasourceIdForDelete,
    "--delete-not-found-policy", "ignore",
    "--remote-user", $RemoteUser,
    "--service", $Service,
    "--payload-modes", $PayloadModes,
    "--timestamp-modes", $TimestampModes,
    "--request-part-names", $RequestPartNames,
    "--skip-auth-precheck",
    "--max-retries", 3,
    "--timeout", 120
)

if ($ApiKey) {
    $filesDeleteArgs += @("--api-key", $ApiKey)
}
if ($ClientAppName) {
    $filesDeleteArgs += @("--client-app-name", $ClientAppName)
}
if ($VerifySsl) {
    $filesDeleteArgs += "--verify-ssl"
}
if ($UseLegacyProxy) {
    $filesDeleteArgs += "--use-legacy-proxy"
}
if ($VerboseUpload) {
    $filesDeleteArgs += "--verbose"
}

$filesSplitArgs = @()
if ($JsonSplitSize -gt 0) {
    $filesSplitArgs += @("--json-split-size", $JsonSplitSize)
    if ($JsonSplitMinMb -gt 0) {
        $filesSplitArgs += @("--json-split-min-mb", $JsonSplitMinMb)
    }
}

if ($issuesOperation -eq "add") {
    $issuesTargetArgs = @("--datasource-id", $IssuesDatasourceId)
} else {
    $issuesTargetArgs = @(
        "--datasource-name", $IssuesDatasourceName,
        "--datasource-classification", $DatasourceClassification
    )
    if ($DatasourceTags) {
        $issuesTargetArgs += @("--datasource-tags", $DatasourceTags)
    }
}

if ($filesOperationResolved -eq "add") {
    $filesTargetArgs = @("--datasource-id", $FilesDatasourceId)
} else {
    $filesTargetArgs = @(
        "--datasource-name", $FilesDatasourceName,
        "--datasource-classification", $DatasourceClassification
    )
    if ($DatasourceTags) {
        $filesTargetArgs += @("--datasource-tags", $DatasourceTags)
    }
}

if ($diagnosticOperation -eq "add") {
    $diagnosticTargetArgs = @("--datasource-id", $DiagnosticDatasourceId)
} else {
    $diagnosticTargetArgs = @(
        "--datasource-name", $DiagnosticDatasourceName,
        "--datasource-classification", $DatasourceClassification
    )
    if ($DatasourceTags) {
        $diagnosticTargetArgs += @("--datasource-tags", $DatasourceTags)
    }
}

if ($resolverOperation -eq "add") {
    $resolverTargetArgs = @("--datasource-id", $ResolverDatasourceId)
} else {
    $resolverTargetArgs = @(
        "--datasource-name", $ResolverDatasourceName,
        "--datasource-classification", $DatasourceClassification
    )
    if ($DatasourceTags) {
        $resolverTargetArgs += @("--datasource-tags", $DatasourceTags)
    }
}

Write-Host "`n[0/4] Authentication precheck (kb-list)"
$precheckArgs = @(
    $uploader,
    "--kb", $KbId,
    "--operation", $Operation,
    "--remote-user", $RemoteUser,
    "--service", $Service,
    "--auth-check-only",
    "--timeout", 120
)

if ($ApiKey) {
    $precheckArgs += @("--api-key", $ApiKey)
}
if ($ClientAppName) {
    $precheckArgs += @("--client-app-name", $ClientAppName)
}
if ($VerifySsl) {
    $precheckArgs += "--verify-ssl"
}
if ($UseLegacyProxy) {
    $precheckArgs += "--use-legacy-proxy"
}
if ($VerboseUpload) {
    $precheckArgs += "--verbose"
}

& $PythonExe @precheckArgs
if ($LASTEXITCODE -ne 0) {
    throw "Authentication precheck failed with exit code $LASTEXITCODE"
}

$issuesArgs = @("--files") + ($issuesJson | ForEach-Object { $_.FullName }) + $issuesTargetArgs

if ($issuesOperation -eq "add") {
    Write-Host "\n[1/4] Upload issues_json -> datasource $IssuesDatasourceId"
} else {
    Write-Host "\n[1/4] Create datasource + upload issues_json -> $IssuesDatasourceName"
}
& $PythonExe @issuesCommonArgs @issuesArgs
if ($LASTEXITCODE -ne 0) {
    throw "Upload to issues datasource failed with exit code $LASTEXITCODE"
}

if ($DeleteFilesBeforeAdd) {
    Write-Host "\n[1.5/3] Delete existing files in files datasource $filesDatasourceIdForDelete"
    & $PythonExe @filesDeleteArgs
    if ($LASTEXITCODE -ne 0) {
        if ($recreateFilesDatasourceAfterDelete) {
            Write-Warning (
                "Delete step failed, continuing because files upload is configured in create mode. " +
                "The old files datasource may already be deleted or inaccessible."
            )
        } else {
            throw "Delete files in files datasource failed with exit code $LASTEXITCODE"
        }
    }
}

if ($filesOperationResolved -eq "add") {
    Write-Host "\n[2/4] Upload files_json -> datasource $FilesDatasourceId"
} else {
    Write-Host "\n[2/4] Create datasource + upload files_json -> $FilesDatasourceName"
}
$filesArgs = @("--files") + ($filesJson | ForEach-Object { $_.FullName }) + $filesSplitArgs + $filesTargetArgs

& $PythonExe @filesCommonArgs @filesArgs
if ($LASTEXITCODE -ne 0) {
    throw "Upload to files datasource failed with exit code $LASTEXITCODE"
}

if ($diagnosticOperation -eq "add") {
    Write-Host "\n[3/4] Upload diagnostic_cards_json -> datasource $DiagnosticDatasourceId"
} else {
    Write-Host "\n[3/4] Create datasource + upload diagnostic_cards_json -> $DiagnosticDatasourceName"
}
$diagnosticArgs = @("--files") + ($diagnosticJson | ForEach-Object { $_.FullName }) + $diagnosticTargetArgs

& $PythonExe @diagnosticCommonArgs @diagnosticArgs
if ($LASTEXITCODE -ne 0) {
    throw "Upload to diagnostic datasource failed with exit code $LASTEXITCODE"
}

if ($resolverOperation -eq "add") {
    Write-Host "\n[4/4] Upload resolver_cases_json -> datasource $ResolverDatasourceId"
} else {
    Write-Host "\n[4/4] Create datasource + upload resolver_cases_json -> $ResolverDatasourceName"
}
$resolverArgs = @("--files") + ($resolverJson | ForEach-Object { $_.FullName }) + $resolverTargetArgs

& $PythonExe @resolverCommonArgs @resolverArgs
if ($LASTEXITCODE -ne 0) {
    throw "Upload to resolver datasource failed with exit code $LASTEXITCODE"
}

Write-Host "\nDone: batch upload completed successfully."
