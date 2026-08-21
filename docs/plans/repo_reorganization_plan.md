# STM32Cube Repo Reorganization Plan

## Goal
Reorganize the repository around pipeline stages, so the structure reflects the real data flow from ingestion to delivery.

## Current Status

Migration status: completed.

- The stage-based code layout is active under `pipeline/`.
- Shared components are active under `shared/`.
- Legacy `src/` code wrappers were removed.
- JSON schemas were added under `shared/schemas/`.

## Target Structure

- pipeline/
  - ingestion/
  - cleaning/
  - enrichment/
  - similarity/
  - chunking/
  - evaluation/
  - delivery/
- datasets/
  - 01_raw/
  - 02_clean/
  - 03_docs_v2/
  - 04_docs_sim/
  - 05_chunks/
  - 06_eval_outputs/
  - 07_delivery/
- shared/
  - config/
  - utils/
  - schemas/
- docs/

## Why This Organization
- It matches the pipeline lifecycle.
- It makes dependencies between stages explicit.
- It isolates data outputs by maturity level.
- It simplifies onboarding and maintenance.

## Migration Mapping (Completed)

### Scripts
- pipeline/ingestion/fetch_issues.py
- pipeline/ingestion/fetch_files.py
- pipeline/cleaning/clean_issues.py
- pipeline/cleaning/clean_files.py
- pipeline/enrichment/issues_to_docs_v2.py
- pipeline/enrichment/files_to_docs_v2.py
- pipeline/similarity/compute_issue_similarity_v2.py
- pipeline/chunking/docs_to_chunks_issues_v2.py
- pipeline/chunking/docs_to_chunks_files_v2.py

### Services
- pipeline/ingestion/github_service.py
- pipeline/ingestion/file_collect_service.py
- pipeline/cleaning/cleaning_service.py
- pipeline/enrichment/preprocessing_model.py
- pipeline/enrichment/stm32cube_preprocessing_heuristics.py
- pipeline/chunking/chunk_service.py

### Tests
- pipeline/evaluation/test_stats_issues_v2.py
- pipeline/evaluation/test_stats_files_v2.py
- pipeline/evaluation/test_tfidf_search_issues_v2.py
- pipeline/evaluation/test_tfidf_search_files_v2.py

### Shared
- shared/config/config.json
- shared/utils/paths.py
- shared/schemas/docs_issues_v2.schema.json
- shared/schemas/docs_files_v2.schema.json
- shared/schemas/chunks_issues_v2.schema.json
- shared/schemas/chunks_files_v2.schema.json

### Data Outputs
Current runtime still reads/writes `data/` by default. The stage folders under `datasets/` are prepared and available for activation.

- data/raw_*.json -> datasets/01_raw/
- data/clean_*.json -> datasets/02_clean/
- data/docs_*_v2.json -> datasets/03_docs_v2/
- data/docs_*_v2_sim.json -> datasets/04_docs_sim/
- data/chunks_*_v2.json -> datasets/05_chunks/
- evaluation outputs -> datasets/06_eval_outputs/
- ST RAG export files -> datasets/07_delivery/

## What Was Executed

1. Created stage-based source layout in `pipeline/`.
2. Created shared layer in `shared/`.
3. Added schema contracts in `shared/schemas/`.
4. Removed legacy `src/` wrappers after migration.
5. Kept dataset stage folders in place for controlled path switch.

## Remaining Actions

### A. Optional path switch to datasets/
1. Update `shared/utils/paths.py` to route output files to `datasets/*`.
2. Introduce config-based routing (for example `output_root: datasets`).
3. Validate all stages and evaluation scripts after switching paths.

### B. Operational hardening
1. Add a dedicated validation script for schemas in `pipeline/evaluation/`.
2. Add CI checks: schema validation + smoke run of core pipeline scripts.
3. Add a short runbook in `docs/` for daily execution.

## Minimal Config Extension (Recommended)

- output_root: datasets
- use_stage_layout: true
- st_rag_input_mode: docs_v2_only

## Validation Checklist

### Code layout
- Pipeline code is only under `pipeline/`.
- Shared code is only under `shared/`.
- No imports from legacy `src.*` remain.

### Data and contracts
- Outputs respect the schemas in `shared/schemas/`.
- `docs_*_v2` and `chunks_*_v2` pass schema validation.
- Delivery artifacts match ST ingestion expectations.

### Execution
- Evaluation scripts run without path errors.
- TF-IDF scripts return relevant results for STM32 queries.

## Recommendation for ST RAG
If ST does internal chunking, deliver docs from:
- datasets/03_docs_v2
Optionally include:
- datasets/04_docs_sim
Do not deliver pre-chunked files from datasets/05_chunks unless explicitly required.
