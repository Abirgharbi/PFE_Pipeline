# pipeline_Automation/workflow

Orchestration layer that drives the core `pipeline/` package across multiple STM32Cube
series and repos, and automates the end-to-end path from raw ingestion to KB upload.

## Python scripts

### `run_all_series.py`
Runs the full pipeline (`pipeline.run_full_workflow`) once per requested STM32 series
(f4, h5, u5, wl, c0, h7). Since the core pipeline only reads a single
`shared/config/config.json`, this script swaps in each series' own
`config_<series>.json` before running, and always restores the original (H7 default)
config afterward — even on failure.

```powershell
python -m pipeline_Automation.run_all_series --series f4 h5 u5 wl --continue-on-error --export-st-ready
```

### `reexport_delivery.py`
Re-runs only the four ST-ready delivery exporters (issues, files, resolver cases,
diagnostic cards) for every repo in the requested series, without re-running
ingestion/cleaning/enrichment. Useful after changing delivery/export logic only.

```powershell
python -m pipeline_Automation.reexport_delivery --series f4 h5 u5 wl
```

## PowerShell scripts

| Script | Purpose |
|---|---|
| `COMMANDS_Series_Pipeline_And_Upload.md` | French-language cheat sheet listing the full per-series command sequence (sync, pipeline, Alfred enrichment, exports, validation, KB upload). |
| `Fix_Driver_Locations.ps1` | Moves driver/CMSIS/BSP sub-repo folders that were generated directly under `by_series/` back into their correct `by_series/<series>/drivers/` location. |
| `Generate_Diagnostic_Cards_For_All_Repos.ps1` | Runs `pipeline.delivery.export_st_ready_diagnostic_cards` for one or more repos. |
| `Run_Full_Auto_Update_KB.ps1` | End-to-end scheduled job: ingestion → preprocessing → export → validation → KB upload for all (or selected) MCU series. |
| `Run_Full_Workflow_For_Repo_Batch.ps1` | Temporarily overrides `config.json`'s repo list with a given batch of repos and runs the full workflow for them. |
| `Run_Issues_Pipeline_For_All_Repos.ps1` | Runs cleaning + enrichment (and optionally similarity/chunking) for issues only, across repos. |
| `Run_Single_Series_Full_Pipeline_And_Upload.ps1` | Main one-command driver for a single series: sync, full pipeline with Alfred PDF enrichment, ST-ready exports, Alfred image enrichment, schema validation, and KB datasource creation/upload. |
| `Split_Issues_By_Component.ps1` | Splits ST-ready issues-with-images JSON into per-component (peripheral) files under `issues_json/by_component`. |
| `Upload_Issues_By_Component.ps1` | Uploads the per-component issues JSON files into their own KB datasources, reusing saved datasource IDs on re-runs. |
| `Upload_Multi_Series_All_Categories.ps1` | Calls `Upload_Series_All_Categories.ps1` sequentially for a list of series (bulk upload). |
| `Upload_Series_All_Categories.ps1` | Uploads all ST-ready categories (issues, files, diagnostic_cards, resolver_cases) for one series and its drivers/subrepos into KB #793, tracking datasource IDs across re-runs. |
