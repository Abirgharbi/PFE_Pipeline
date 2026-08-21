---
name: stm32cube_preprocessing_contract
description: "Contract describing how the STM32Cube Preprocessing Agent collaborates with its skills for preprocessing, Alfred image enrichment, and ST-ready delivery outputs."
agents: ["STM32Cube Preprocessing Agent"]
skills: ["analyze-stats", "document-json-schema", "chunking-strategies"]
---

# STM32Cube Preprocessing Contract

## Purpose

This contract defines how the STM32Cube Preprocessing Agent should use its skills to support the STM32Cube preprocessing, Alfred image enrichment, and ST-ready delivery/upload workflow.

## Agent

- **STM32Cube Preprocessing Agent**
  - Main role: analyze, validate, and document the STM32Cube pipeline from ingestion to KB-ready delivery exports.
  - Uses workspace files under `pipeline/`, `shared/`, `data/`, `datasets/`, `docs/`.
  - Prioritizes durable fixes in generators and quality gates over manual one-off patches.
  - Manages Alfred Vision API enrichment for image descriptions in issues.
  - Handles upload to ST ChatGPT KB via `Add_Data_Source_Files.py`.

## Active execution paths

- Ingestion: `pipeline/ingestion/*`
- Cleaning: `pipeline/cleaning/*`
- Enrichment: `pipeline/enrichment/*`
- Similarity: `pipeline/similarity/*`
- Chunking: `pipeline/chunking/*`
- Evaluation: `pipeline/evaluation/*`
- Delivery: `pipeline/delivery/*`
- Alfred enrichment: `pipeline_Automation/alfred/*`
- Upload: `pipeline_Automation/upload/*`
- Workflow automation: `pipeline_Automation/workflow/*`

Utility entry points:

- Full workflow: `python -m pipeline.run_full_workflow`
- Full workflow with delivery exports: `python -m pipeline.run_full_workflow --export-st-ready`
- Common options: `--skip-ingestion`, `--continue-on-error`
- Schema checks: `python -m pipeline.evaluation.validate_schemas`

Targeted delivery exports:

- `python -m pipeline.delivery.export_st_ready_issues --repo STM32CubeH7`
- `python -m pipeline.delivery.export_st_ready_issues_with_images --repo STM32CubeH7`
- `python -m pipeline.delivery.export_st_ready_files --repo STM32CubeH7`
- `python -m pipeline.delivery.export_st_ready_resolver_cases --repo STM32CubeH7`
- `python -m pipeline.delivery.export_st_ready_diagnostic_cards --repo STM32CubeH7`

Alfred image enrichment:

- `python pipeline_Automation/alfred/enrich_json_images_with_alfred.py --input <file> --inplace`
- Options: `--use-proxy`, `--no-replace-text`, `--max-records N`, `--strip-analyses`
- Alfred replaces `[IMAGE ATTACHED]` markers with `[IMAGE DESCRIPTION] ...` using Vision API.

Upload to KB:

- `python pipeline_Automation/upload/Add_Data_Source_Files.py --kb 793 --operation add --datasource-id <ID> --remote-user "abir.gharbi@st.com" --processor JSON --processor-params "base64:<b64>" --json-split-size 1000 --files <file>`
- PowerShell base64 encoding required for `--processor-params` containing `{}`.

## Skills

- **analyze-stats**
  - Used when the user provides outputs from:
    - `test_stats_issues_v2.py`
    - `test_stats_files_v2.py`
  - Expected behavior:
    - summarize key distributions (layer, severity, file_type, board, component, etc.),
    - highlight potential biases or anomalies,
    - check consistency against delivery summaries when relevant,
    - suggest bullet points for the Evaluation section.

- **document-json-schema**
  - Used when the user provides one or more JSON examples from:
    - `docs_issues_*_v2.json`
    - `docs_issues_*_v2_sim.json`
    - `docs_files_*_v2.json`
    - `chunks_issues_*_v2.json`
    - `chunks_files_*_v2.json`
    - `st_ready_issues_*.json`
    - `st_ready_files_*.json`
    - `st_ready_resolver_cases_*.json`
    - `st_ready_diagnostic_cards_*.json`
  - Expected behavior:
    - infer field names, types, and meaning,
    - document root format expectations (array vs object key),
    - generate Markdown JSON schema documentation for `docs/json_schemas.md`.

- **chunking-strategies**
  - Used when the user describes or evaluates different chunking configurations (V1_full, V2_paragraph, V2_small, etc.).
  - Expected behavior:
    - compare configurations,
    - explain trade-offs (noise vs context length) in a RAG setting,
    - propose written guidelines for `docs/chunking_strategies.md` and the Evaluation section.

## Workflow (high-level)

1. When the user shares stats outputs, the agent should invoke/align with:
  - `analyze-stats`.

2. When the user shares JSON examples of pipeline outputs, the agent should invoke/align with:
  - `document-json-schema`.

3. When the user discusses chunking configurations and evaluation, the agent should invoke/align with:
  - `chunking-strategies`.

4. When the user reports KB retrieval failures, the agent should first improve generator quality (query aliases, technical anchors, signal filtering, evidence refs) before manual file-specific overrides.

5. When the user wants to enrich issues with image descriptions:
  - Export with `export_st_ready_issues_with_images` (generates `[IMAGE ATTACHED]` markers + `image_urls`).
  - Run Alfred enrichment (`enrich_json_images_with_alfred.py --inplace`).
  - Upload the enriched `*_with_alfred_image_text.json` to the target datasource.

6. When the user wants to upload to KB:
  - Use base64 encoding for processor-params in PowerShell.
  - Validate record count matches expected (264 valid for H7).
  - Reference `docs/pipeline_commands_reference.md` for full command syntax.

## Known fixes and design decisions

- **Image marker duplication fix**: `first_sentence()` in `export_st_ready_issues.py` and `export_st_ready_issues_with_images.py` strips `[IMAGE ATTACHED]` markers from `root_cause_hint`. This prevents duplication when comment images are repeated in the hint AND in Key comments, which caused Alfred to exhaust URLs on the copy and mark the originals as UNAVAILABLE.

- **Invalid issues excluded by default**: Issues with `is_valid: false` (short text < 100 chars, or labels invalid/duplicate/wontfix) are excluded from delivery. The `rescue` mechanism recovers false negatives (mislabeled but technically rich issues).

- **ST ChatGPT Tool fallback**: The persona "ST GitHub Analyzer" uses Alfred as a fallback tool when the KB does not contain a relevant answer. Tool description should enforce KB-first priority.

## Output quality checks

- Root JSON format matches consumer expectations.
- Summary counts are coherent with exported payload size.
- Diagnostic cards contain useful `query_aliases`, `keywords`, and `evidence_refs`.
- High-value troubleshooting cases include lexical anchors used in real queries.
- After Alfred enrichment: 0 `[IMAGE DESCRIPTION UNAVAILABLE]` for issues where all image URLs were captured.
- Upload datasource IDs: H7 Issues = #24406, KB = #793.




  