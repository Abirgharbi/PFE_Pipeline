# pipeline_Automation/utils

Miscellaneous maintenance scripts that are not part of the main per-series
workflow orchestration but support cleanup and manual-upload preparation tasks.

## Python scripts

### `cleanup_orphan_series_folders.py`
Deletes leftover top-level folders under
`datasets/07_delivery/st_ready/by_series/` that are not one of the known valid
series folders (e.g. old sub-repo exports that predate the current
`by_series/<series>/drivers/...` nesting). Run after `reexport_delivery.py` when
the delivery grouping logic has changed.

```powershell
python -m pipeline_Automation.utils.cleanup_orphan_series_folders
```

## PowerShell scripts

| Script | Purpose |
|---|---|
| `Prepare_Manual_Files_Splits.ps1` | Splits large `st_ready_files_*.json` delivery files into smaller parts (via `pipeline.delivery.split_st_ready_files_for_manual_upload`) sized for manual KB upload. |
| `Prepare_Manual_Files_Splits_STM32CubeH7_50Parts.ps1` | Convenience wrapper around `Prepare_Manual_Files_Splits.ps1` pre-configured to split the STM32CubeH7 files export into exactly 50 parts. |
