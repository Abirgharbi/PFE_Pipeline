# Config — Pipeline Configuration Files

Global and per-series JSON configuration consumed by every stage of `pipeline/`
and by the `pipeline_Automation/` orchestration scripts, via
[shared/utils/paths.py](../utils/paths.py) (`get_config_path()`).

## Files

- **config_all_series.json** — master config: GitHub `owner`, the full list of
  STM32Cube series (`all_series`), and the mapping from series name to its
  dedicated config file (`series_config_files`).
- **config.json** — the "active" config used by default when no override is
  set (typically a copy/symlink-equivalent of one series config, or a generic
  default depending on how the environment is set up).
- **config_<series>.json** (e.g. `config_f4.json`, `config_h7rs.json`, ...) —
  one file per STM32Cube series (C0, F0, F1, F2, F3, F4, F7, G0, G4, H5, H7RS,
  L0, L1, L4, L5, N6, U0, U3, U5, WB, WB0, WBA, WL, WL3). Each defines the
  `repos` list (main repo + BSP/HAL/driver sub-repos) and any series-specific
  options consumed by the pipeline stages (ingestion, cleaning, enrichment,
  chunking, delivery).

## How the active config is selected

By default, scripts resolve `shared/config/config.json`. To target a specific
series without editing files, set the `STM32CUBE_CONFIG` environment variable
before running a pipeline script:

```powershell
$env:STM32CUBE_CONFIG = "shared/config/config_h7rs.json"
python -m pipeline.run_full_workflow
```

See [pipeline/README.md](../../pipeline/README.md) and
[pipeline_Automation/workflow/README.md](../../pipeline_Automation/workflow/README.md)
for how these configs drive the full pipeline across all series.
