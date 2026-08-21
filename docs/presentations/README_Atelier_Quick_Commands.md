# Practical Workshop - Quick Commands

This is a short, copy-paste friendly command guide for demos and handover.

Full references:
- docs/pipeline_commands_reference.md
- docs/Atelier_Pratique_Pipeline_STM32Cube.md

## 1) Quick setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 2) Select a series config

```powershell
$env:STM32CUBE_CONFIG = "shared/config/config_h7.json"
```

Examples:
- shared/config/config_f4.json
- shared/config/config_h5.json
- shared/config/config_wl.json

## 3) Full local pipeline

```powershell
python -m pipeline.run_full_workflow --export-st-ready --skip-chunking --continue-on-error
```

## 4) Split mode (prepare and upload separately)

### 4.1 Prepare only

```powershell
powershell -ExecutionPolicy Bypass -File pipeline_Automation/workflow/Run_Single_Series_Full_Pipeline_And_Upload.ps1 -Series H7 -Mode Prepare -SkipSchemaValidation
```

### 4.2 Upload only

```powershell
powershell -ExecutionPolicy Bypass -File pipeline_Automation/workflow/Run_Single_Series_Full_Pipeline_And_Upload.ps1 -Series H7 -Mode Upload -ExistingDatasourceMode Replace -KbId 793 -RemoteUser "first.last@st.com"
```

### 4.3 Full (prepare + upload)

```powershell
powershell -ExecutionPolicy Bypass -File pipeline_Automation/workflow/Run_Single_Series_Full_Pipeline_And_Upload.ps1 -Series H7 -Mode Full -ExistingDatasourceMode Replace -KbId 793 -RemoteUser "first.last@st.com"
```

## 5) Config-driven upload (recommended for post-internship)

This lets future users change values like remote user, split size, and delay between uploads without editing scripts.

### 5.1 Create your config file

```powershell
Copy-Item pipeline_Automation/upload/upload_runtime_config.example.json pipeline_Automation/upload/upload_runtime_config.json
```

Then edit:
- remote_user
- json_split_size
- sleep_between_uploads_seconds
- datasource IDs
- operation / files_operation

### 5.2 Run upload from config

```powershell
powershell -ExecutionPolicy Bypass -File pipeline_Automation/upload/Run_Upload_STReady_From_Config.ps1 -ConfigPath pipeline_Automation/upload/upload_runtime_config.json
```

## 6) Quick validation before demo

```powershell
python -m pipeline.evaluation.validate_schemas
python -m pipeline.evaluation.test_stats_issues_v2
python -m pipeline.evaluation.test_stats_files_v2
```

## 7) Main output folders to show

- Per-series ST-ready output:
  datasets/07_delivery/st_ready/by_series/
- Issues JSON:
  datasets/07_delivery/st_ready/by_series/stm32cubeh7/issues_json/
- Files JSON:
  datasets/07_delivery/st_ready/by_series/stm32cubeh7/files_json/
- Diagnostic cards JSON:
  datasets/07_delivery/st_ready/by_series/stm32cubeh7/diagnostic_cards_json/

## 8) Regenerate workshop presentation (if needed)

```powershell
python docs/scripts/generate_atelier_pratique_pptx.py --output docs/Atelier_Pratique_Pipeline_STM32Cube.pptx
```

## 9) Common issues

### Missing GitHub token

```powershell
$env:GITHUB_TOKEN = "ghp_your_token"
```

### Low API quota / runner contention

Retry later or reduce parallelism.

### ST upload rollback

Try a smaller split size (for example 200) and confirm JSON records contain usable text in st_ready_text.
