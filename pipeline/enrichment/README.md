# pipeline/enrichment

## Purpose

The enrichment stage turns **cleaned** issues/files (output of `pipeline/cleaning`)
into structured **doc** records enriched with metadata and heuristics: `layer`,
`severity`, `issue_kind`, `board`, `component`, `is_valid` (validity filter with
rescue mechanism), `evidence_strength`, `mcu_series`, `github_url`, etc.

It runs after `pipeline/cleaning` and before `pipeline/similarity` (issues) /
`pipeline/chunking` (files).

## Scripts

| Script | Description | Run |
| --- | --- | --- |
| `issues_to_docs_v2.py` | **Current** issue enrichment: applies `PreprocessingModelIssuesV2` (layer/severity/issue_kind/board/component detection, validity filtering with rescue). | `python -m pipeline.enrichment.issues_to_docs_v2` |
| `files_to_docs_v2.py` | **Current** file enrichment: applies `PreprocessingModelFilesV2` (board/component/example_name detection, validity flag). Prefers V3 cleaned input if present. | `python -m pipeline.enrichment.files_to_docs_v2` |
| `issues_to_docs.py` | Legacy V1 issue enrichment (no heuristics, just schema shaping via `docs_issue_service.clean_issue_to_doc`). Superseded by `issues_to_docs_v2.py`. | `python -m pipeline.enrichment.issues_to_docs` |
| `preprocessing_model.py` | Core module: `PreprocessingConfig`, `PreprocessingModelIssuesV2`, `PreprocessingModelFilesV2`, and helper functions (`classify_issue_kind`, `detect_board`, `detect_component`, `detect_rescue_signals`, `compute_issue_evidence_strength`, `build_file_github_url`). Not a CLI script; imported by the scripts above. | n/a (library module) |
| `stm32cube_preprocessing_heuristics.py` | Standalone keyword/regex heuristics: `detect_layer`, `detect_severity`. Imported by `preprocessing_model.py`. | n/a (library module) |
| `docs_issue_service.py` | Legacy V1 helper: `clean_issue_to_doc`. Imported by `issues_to_docs.py`. | n/a (library module) |
| `debug_preprocessing_issues_v2.py` | Developer debug utility: prints enriched fields for a sample of issues without writing output. Useful when tuning heuristics. | `python -m pipeline.enrichment.debug_preprocessing_issues_v2` |

## Typical inputs / outputs

- **Inputs**: `data/clean_issues_<repo>.json`, `data/clean_files_<repo>[_v3].json`
  (from `pipeline/cleaning`).
- **Outputs**:
  - `data/docs_issues_<repo>_v2.json` (current issues)
  - `data/docs_issues_<repo>.json` (legacy issues)
  - `data/docs_files_<repo>_v2.json` / `data/docs_files_<repo>_v3.json` (files)

## Role in the pipeline

```
cleaning -> enrichment (this folder) -> similarity (issues) -> chunking -> evaluation -> delivery
```

Config (repo list, `preprocess_version`, `ingest_version`) is resolved via
`shared.utils.paths.get_config_path()` (default
`shared/config/config_all_series.json`, overridable with `STM32CUBE_CONFIG`).
