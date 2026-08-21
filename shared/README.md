# Shared Folder

Shared components used across every pipeline stage and automation script — no
pipeline-specific logic lives here, only generic building blocks.

- [config/](config/README.md): global + per-series JSON configuration files
  (`config_all_series.json`, `config_<series>.json`), resolved at runtime via
  `shared/utils/paths.py`.
- [utils/](utils/paths.py): common utilities, currently path resolution
  (`get_config_path()`, `get_repos_root()`) supporting the `STM32CUBE_CONFIG`
  env var override.
- [schemas/](schemas/README.md): JSON Schema contracts validating the docs/chunks
  produced by `pipeline/enrichment` and `pipeline/chunking`, checked by
  `pipeline/evaluation/validate_schemas.py`.
