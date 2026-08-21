# Upload Runtime Config (Config-First)

This mode lets you run uploads from one JSON config file instead of passing many CLI flags.

## 1) Create your team config

```powershell
Copy-Item pipeline_Automation/upload/upload_runtime_config.example.json pipeline_Automation/upload/upload_runtime_config.json
```

## 2) Edit values in upload_runtime_config.json

Common fields to update:
- remote_user
- kb_id
- datasource IDs
- json_split_size
- sleep_between_uploads_seconds
- operation / files_operation

## 3) Run with config only

```powershell
powershell -ExecutionPolicy Bypass -File pipeline_Automation/upload/Upload_STReady_New_Batch.ps1 -ConfigPath pipeline_Automation/upload/upload_runtime_config.json
```

## Compatibility

- Existing flag-based usage still works.
- If both config and flags are provided, explicit flags win.
- No automation workflow is forced to change.