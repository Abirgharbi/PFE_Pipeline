# STM32Cube Preprocessing Project – Global Instructions

## Project Overview

This repository implements a preprocessing pipeline for STM32Cube GitHub public data (issues, files, PR/commit links) and ST-ready delivery exports.
The goal is to produce RAG-ready chunks and KB-ready JSON payloads for downstream indexing and troubleshooting.

## Source Of Truth

- Legacy `src/` is not the source of truth.
- Active execution paths are:
  - `pipeline/ingestion`, `pipeline/cleaning`, `pipeline/enrichment`, `pipeline/similarity`, `pipeline/chunking`, `pipeline/evaluation`, `pipeline/delivery`
  - `shared/config`, `shared/utils`, `shared/schemas`
- Main artifacts are under:
  - `data/` for raw/intermediate historical outputs
  - `datasets/01_raw` to `datasets/07_delivery` for staged outputs
  - `datasets/07_delivery/st_ready/*` for KB-ready exports

The main steps are:

1. **Ingestion**
  - `pipeline/ingestion/fetch_issues.py`: fetch GitHub issues for STM32Cube repositories (e.g. STM32CubeH7, STM32CubeH5).
  - `pipeline/ingestion/fetch_prs.py`, `pipeline/ingestion/fetch_commits.py`: fetch PR and commit metadata.
  - `pipeline/ingestion/fetch_issue_pr_commit_links.py`: compute issue/PR/commit linkage.
  - `pipeline/ingestion/repo_sync_service.py`: sync local repositories.
  - `pipeline/ingestion/fetch_files.py`: collect relevant files from cloned STM32Cube repositories (`README`, `Release_Notes`, `Projects/*/README`, docs, etc.).

2. **Cleaning**
  - `pipeline/cleaning/clean_issues.py`: normalize issue texts, merge comments, build a `clean_text` representation → `clean_issues_<repo>.json`.
  - `pipeline/cleaning/clean_files.py`: normalize file contents, classify file types (root_readme, project_readme, release_notes, doc_readme, other) → `clean_files_<repo>.json`.

3. **Enrichment V2**
  - `pipeline/enrichment/issues_to_docs_v2.py` → `docs_issues_<repo>_v2.json`
    - Adds fields such as `layer`, `severity`, `issue_kind`, `board`, `component`, `is_valid`, etc.
  - `pipeline/enrichment/files_to_docs_v2.py` → `docs_files_<repo>_v2.json`
    - Adds fields such as `file_type`, `board`, `component`, `example_name`, `is_valid`, etc.

4. **Similarity & Chunking**
  - `pipeline/similarity/compute_issue_similarity_v2.py` → `docs_issues_<repo>_v2_sim.json` with `related_issue_ids`.
  - `pipeline/chunking/docs_to_chunks_issues_v2.py` → `chunks_issues_<repo>_v2.json`.
  - `pipeline/chunking/docs_to_chunks_files_v2.py` → `chunks_files_<repo>_v2.json`.

5. **Delivery (ST-ready)**
  - `pipeline/delivery/export_st_ready_issues.py` → `datasets/07_delivery/st_ready/issues_json/st_ready_issues_<repo>.json`
  - `pipeline/delivery/export_st_ready_issues_with_images.py` → `st_ready_issues_with_images_<repo>.json` (includes `image_urls` for Alfred)
  - `pipeline/delivery/export_st_ready_files.py` → `datasets/07_delivery/st_ready/files_json/st_ready_files_<repo>.json`
  - `pipeline/delivery/export_st_ready_resolver_cases.py` → `datasets/07_delivery/st_ready/resolver_cases_json/st_ready_resolver_cases_<repo>.json`
  - `pipeline/delivery/export_st_ready_diagnostic_cards.py` → `datasets/07_delivery/st_ready/diagnostic_cards_json/st_ready_diagnostic_cards_<repo>.json`
  - Each export also writes summary files (`summary_*.json`) for traceability.

6. **Alfred Image Enrichment**
  - `pipeline_Automation/alfred/enrich_json_images_with_alfred.py` → replaces `[IMAGE ATTACHED]` with `[IMAGE DESCRIPTION] ...` via Vision API.
  - Output: `*_with_alfred_image_text.json`
  - Known fix: `first_sentence()` strips image markers from `root_cause_hint` to prevent duplication.

7. **Upload to KB**
  - `pipeline_Automation/upload/Add_Data_Source_Files.py` → uploads JSON to ST ChatGPT KB datasource.
  - Requires base64-encoded `--processor-params` in PowerShell.
  - KB #793, H7 Issues datasource #24406.

## Active Repository Layout

- `pipeline/`: executable pipeline stages.
- `shared/config`: project configuration.
- `shared/utils`: shared utilities (paths, helpers).
- `shared/schemas`: JSON schema contracts for docs/chunks outputs.
- `data/`: current working outputs.
- `datasets/`: staged/finalized output structure for release/delivery.
- `docs/`: technical documentation and reporting assets.

## JSON Outputs

Main preprocessing outputs:

- `docs_issues_<repo>_v2.json`         – enriched issues.
- `docs_issues_<repo>_v2_sim.json`     – enriched issues + `related_issue_ids`.
- `docs_files_<repo>_v2.json`          – enriched files (README, Projects, Release Notes).
- `chunks_issues_<repo>_v2.json`       – chunked issues (RAG-ready).
- `chunks_files_<repo>_v2.json`        – chunked files (RAG-ready).

Main ST-ready delivery outputs:

- `datasets/07_delivery/st_ready/issues_json/st_ready_issues_<repo>.json`
- `datasets/07_delivery/st_ready/files_json/st_ready_files_<repo>.json`
- `datasets/07_delivery/st_ready/resolver_cases_json/st_ready_resolver_cases_<repo>.json`
- `datasets/07_delivery/st_ready/diagnostic_cards_json/st_ready_diagnostic_cards_<repo>.json`

Agents and skills should assume these structures when answering questions or generating documentation.

## Evaluation & Tests

The evaluation is mainly based on:

- **Stats scripts**:
  - `pipeline/evaluation/test_stats_issues_v2.py`
  - `pipeline/evaluation/test_stats_files_v2.py`
- **TF-IDF search scripts**:
  - `pipeline/evaluation/test_tfidf_search_issues_v2.py`
  - `pipeline/evaluation/test_tfidf_search_files_v2.py`

Validation utility:

- `pipeline/evaluation/validate_schemas.py`

Execution entry points:

- `python -m pipeline.run_full_workflow`
- `python -m pipeline.run_full_workflow --export-st-ready`
- `python -m pipeline.run_full_workflow --skip-ingestion`
- `python -m pipeline.run_full_workflow --continue-on-error`
- `python -m pipeline.delivery.export_st_ready_issues_with_images --repo STM32CubeH7`
- `python pipeline_Automation/alfred/enrich_json_images_with_alfred.py --input <file> --inplace`
- `python pipeline_Automation/upload/Add_Data_Source_Files.py --kb 793 --operation add --datasource-id <ID> ...`

Full command reference: `docs/pipeline_commands_reference.md`

Targeted delivery exports:

- `python -m pipeline.delivery.export_st_ready_issues --repo STM32CubeH7`
- `python -m pipeline.delivery.export_st_ready_files --repo STM32CubeH7`
- `python -m pipeline.delivery.export_st_ready_resolver_cases --repo STM32CubeH7`
- `python -m pipeline.delivery.export_st_ready_diagnostic_cards --repo STM32CubeH7`

Automation scripts:

- `pipeline_Automation/Run_Issues_Pipeline_For_All_Repos.ps1`
- `pipeline_Automation/Generate_Diagnostic_Cards_For_All_Repos.ps1`
- `pipeline_Automation/Upload_STReady_New_Batch.ps1`
- `pipeline_Automation/Add_Data_Source_Files.py`

## Quality Checklist

When reviewing generated outputs:

- Verify JSON root format is compatible with target consumer.
- Verify `summary_*.json` counts are coherent with exported payload size.
- Verify diagnostic cards contain useful `query_aliases`, `keywords`, and `evidence_refs`.
- Verify high-value issues include technical anchors used by user queries (API names, error states, transfer sizes).
- Verify delivery outputs remain aligned with `shared/schemas` and `validate_schemas.py`.

Agents should use these scripts and outputs to reason about data quality, detect biases, and guide durable generator improvements.