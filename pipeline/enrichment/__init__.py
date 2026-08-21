"""Enrichment stage of the STM32Cube preprocessing pipeline.

This package turns cleaned issues/files (output of the `cleaning` stage) into
structured "docs_v2" documents enriched with metadata and heuristics such as
`layer`, `severity`, `issue_kind`, `board`, `component`, and `is_valid`.

Main modules:
- `preprocessing_model.py`: core `PreprocessingModelIssuesV2` /
  `PreprocessingModelFilesV2` classes that build enriched docs.
- `stm32cube_preprocessing_heuristics.py`: standalone heuristics (layer,
  severity detection) reused by the preprocessing models.
- `issues_to_docs.py` / `issues_to_docs_v2.py`: CLI scripts to generate
  `docs_issues_<repo>[_v2].json` from `clean_issues_<repo>.json`.
- `files_to_docs_v2.py`: CLI script to generate `docs_files_<repo>_v2.json`
  (or `_v3.json`) from `clean_files_<repo>[_v3].json`.
- `docs_issue_service.py`: legacy V1 helper to convert a clean issue into a
  doc dict (used by `issues_to_docs.py`).
- `debug_preprocessing_issues_v2.py`: manual debug script to print enriched
  fields for a sample of issues.

See `pipeline/enrichment/README.md` for detailed usage of each script.
"""
