# ST-Ready KB Upload Onboarding Guide (Team Handover)

This guide is for new team members who need to run the same ST-ready upload workflow safely.
It explains where scripts are, what each script does, and which commands to run.

## 1) Where to find the scripts

Main upload script (API request builder):
- `pipeline_Automation/upload/Add_Data_Source_Files.py`

Batch upload launcher (config-first mode):
- `pipeline_Automation/upload/Upload_STReady_New_Batch.ps1`

Batch upload config template:
- `pipeline_Automation/upload/upload_runtime_config.example.json`

Single-series full automation (prepare + upload):
- `pipeline_Automation/workflow/Run_Single_Series_Full_Pipeline_And_Upload.ps1`

All-series automation entrypoint:
- `pipeline_Automation/workflow/Run_Full_Auto_Update_KB.ps1`

Series + datasource IDs source of truth:
- `shared/config/config_all_series.json`

Main output folder produced by pipeline:
- `datasets/07_delivery/st_ready/by_series/`

## 2) Typical generated files to upload

For one series slug (example: `stm32cubeh7`), files are usually:
- `datasets/07_delivery/st_ready/by_series/stm32cubeh7/issues_json/st_ready_issues_with_images_stm32cubeh7.json`
- `datasets/07_delivery/st_ready/by_series/stm32cubeh7/files_json/st_ready_files_stm32cubeh7_v3.json`
- `datasets/07_delivery/st_ready/by_series/stm32cubeh7/diagnostic_cards_json/st_ready_diagnostic_cards_stm32cubeh7.json`
- `datasets/07_delivery/st_ready/by_series/stm32cubeh7/resolver_cases_json/st_ready_resolver_cases_stm32cubeh7.json`

After upload, datasource IDs are saved in:
- `datasets/07_delivery/st_ready/by_series/stm32cubeh7/upload_datasource_ids_stm32cubeh7.json`

## 3) Prerequisites for each teammate

1. Python environment installed and project dependencies available.
2. Access to ST API key.
3. Valid `--remote-user` email (single `@`, ST email format).
4. Correct `clientAppName` for the persona.

Recommended env vars (PowerShell):

```powershell
$env:ST_GITHUB_ANALYZER_API_KEY = "<REAL_API_KEY>"
$env:ST_CHATGPT_CLIENT_APP = "mdrf_st_github_analyzer"
```

## 4) Fast precheck (auth only)

Run this first to validate auth and persona binding before any upload:

```powershell
python pipeline_Automation/upload/Add_Data_Source_Files.py --kb 793 --remote-user "first.last@st.com" --auth-check-only --verbose
```

If this fails, fix API key / client app / account permissions before continuing.

## 5) Critical rule for processorParams rootTagPath

With this repository upload script, `rootTagPath` must match the JSON array key in the payload.
Do not use JSONPath like `$.items[*]` here.

Use these values:
- issues JSON: `issues`
- files JSON: `files`
- diagnostic cards JSON: `diagnostic_cards`
- resolver cases JSON: `resolver_cases`

## 6) Build processorParams safely in PowerShell (base64)

Use base64 to avoid PowerShell escaping issues with braces and templates.

### 6.1 Issues params

```powershell
$ppIssues = @{
  label = "{{repo}} issue #{{issue_number}} - {{issue_title}}"
  externalURL = "https://github.com/STMicroelectronics/{{repo}}/issues/{{issue_number}}"
  rootTagPath = "issues"
  jobBatchSize = 200
  embeddingsBatchSize = 100
}
$ppIssuesJson = $ppIssues | ConvertTo-Json -Compress
$ppIssuesB64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($ppIssuesJson))
```

### 6.2 Files params

```powershell
$ppFiles = @{
  label = "{{repo}} - {{file_type}} - {{path}}"
  externalURL = "{{github_url}}"
  rootTagPath = "files"
  jobBatchSize = 200
  embeddingsBatchSize = 100
}
$ppFilesJson = $ppFiles | ConvertTo-Json -Compress
$ppFilesB64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($ppFilesJson))
```

### 6.3 Diagnostic params

```powershell
$ppDiag = @{
  label = "{{card_id}} - {{card_title}}"
  externalURL = "{{primary_issue_url}}"
  rootTagPath = "diagnostic_cards"
  jobBatchSize = 200
  embeddingsBatchSize = 100
}
$ppDiagJson = $ppDiag | ConvertTo-Json -Compress
$ppDiagB64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($ppDiagJson))
```

### 6.4 Resolver params

```powershell
$ppResolver = @{
  label = "{{repo}} resolver #{{issue_number}} - {{issue_title}}"
  externalURL = "https://github.com/STMicroelectronics/{{repo}}/issues/{{issue_number}}"
  rootTagPath = "resolver_cases"
  jobBatchSize = 200
  embeddingsBatchSize = 100
}
$ppResolverJson = $ppResolver | ConvertTo-Json -Compress
$ppResolverB64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($ppResolverJson))
```

## 7) Standard upload flows

## Flow A (recommended for beginners): config-first batch upload

1. Copy template:

```powershell
Copy-Item pipeline_Automation/upload/upload_runtime_config.example.json pipeline_Automation/upload/upload_runtime_config.json
```

2. Edit `upload_runtime_config.json` (remote_user, kb_id, datasource IDs, split settings, operation mode).
3. Run:

```powershell
powershell -ExecutionPolicy Bypass -File pipeline_Automation/upload/Upload_STReady_New_Batch.ps1 -ConfigPath pipeline_Automation/upload/upload_runtime_config.json
```

## Flow B (manual precise control): create datasource then add files

### Step B1 - Create a datasource (`operation new`)

```powershell
python pipeline_Automation/upload/Add_Data_Source_Files.py `
  --kb 793 `
  --operation new `
  --datasource-name "DB_STready_H7_Issues" `
  --datasource-classification PUBLIC `
  --remote-user "first.last@st.com" `
  --processor JSON `
  --processor-params "base64:$ppIssuesB64" `
  --json-root-mode auto `
  --empty-json-policy skip `
  --json-split-size 1000 `
  --files "datasets/07_delivery/st_ready/by_series/stm32cubeh7/issues_json/st_ready_issues_with_images_stm32cubeh7.json" `
  --existing-datasource-policy replace `
  --verbose
```

### Step B2 - Add more files to existing datasource (`operation add`)

```powershell
python pipeline_Automation/upload/Add_Data_Source_Files.py `
  --kb 793 `
  --operation add `
  --datasource-id <DATASOURCE_ID> `
  --remote-user "first.last@st.com" `
  --processor JSON `
  --processor-params "base64:$ppIssuesB64" `
  --json-root-mode auto `
  --empty-json-policy skip `
  --json-split-size 1000 `
  --files "<ANOTHER_JSON_FILE>.json" `
  --verbose
```

## Step B3 - Delete datasource content (`operation delete`)

```powershell
python pipeline_Automation/upload/Add_Data_Source_Files.py `
  --kb 793 `
  --operation delete `
  --datasource-id <DATASOURCE_ID> `
  --remote-user "first.last@st.com" `
  --delete-not-found-policy ignore `
  --verbose
```

## 8) Team execution model (2 new people)

Suggested split:

- Operator A (generation owner)
1. Runs pipeline/export.
2. Verifies produced JSON files exist and are non-empty.
3. Confirms no unresolved placeholders remain.

- Operator B (upload owner)
1. Runs auth precheck.
2. Executes upload with config-first or manual flow.
3. Saves returned datasource IDs and updates tracking file.

Shared validation before sign-off:
1. `Datasource response` has no API errorCode.
2. `uploaded_files` is not empty (unless expected skip).
3. `upload_datasource_ids_<series>.json` exists and is archived.

## 9) Common errors and fixes

1. Error: `Invalid JSON in --processor-params`
- Fix: use base64 mode exactly as shown.

2. Error: `rootTagPath does not match payload keys`
- Fix: use `issues`, `files`, `diagnostic_cards`, or `resolver_cases` based on the JSON file.

3. Error: `cannot upload existing file`
- Fix: default behavior skips existing files in add mode.
- If you want strict mode, use `--fail-on-existing-files`.

4. Error: datasource already exists (name conflict)
- Fix: keep `--existing-datasource-policy replace` for refresh, or set `add` for append.

5. Error: datasource deleted or missing
- Fix: rerun in `operation new` or resolve datasource ID from saved snapshot/config.

## 10) Useful references in repo

- Upload runtime config notes:
  - `pipeline_Automation/upload/README_upload_runtime_config.md`
- Workflow commands by series:
  - `pipeline_Automation/workflow/COMMANDS_Series_Pipeline_And_Upload.md`
- Global pipeline command catalog:
  - `docs/pipeline_commands_reference.md`

---

If your team follows this sequence (auth precheck -> correct processorParams -> controlled new/add), uploads are repeatable and much safer for handover.
