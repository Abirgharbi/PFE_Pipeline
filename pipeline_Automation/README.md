# pipeline_Automation — Orchestration, Upload & CI Layer

This folder wraps the core `pipeline/` package (ingestion → cleaning →
enrichment → similarity → chunking → evaluation → delivery) with the
automation needed to run it at scale across every STM32Cube series, enrich
content with an internal LLM, upload results to the ST AI Bridge knowledge
base, and grade output quality.

## Subfolders

| Folder | Purpose |
|---|---|
| [workflow/](workflow/README.md) | Drives the full pipeline across all/selected STM32Cube series (`run_all_series.py`, `reexport_delivery.py`) plus PowerShell wrappers for batch runs. |
| [upload/](upload/README.md) | Uploads "ST-ready" JSON (from `pipeline/delivery`) to the ST AI Bridge persona Knowledge Base (KB #793) via REST API. |
| [alfred/](alfred/README.md) | Calls the internal "Alfred" LLM service to enrich PDF/image content and to chat/verify answers. |
| [test_suites/](test_suites/README.md) | Builds Excel-based QA test suites and compares Alfred vs. persona KB answers for quality grading. |
| [utils/](utils/README.md) | Misc maintenance scripts (orphan folder cleanup, manual upload file splitting). |
| [jenkins/](jenkins/README.md) | Jenkins pipeline definition to run the full workflow + upload on a schedule/trigger. |
| bridge/ | Reserved for future ST AI Bridge integration code; currently empty. |

## Root-level scripts

| Script | Purpose |
|---|---|
| [fix_corrupted_json_deep.py](fix_corrupted_json_deep.py) | Deep-repairs malformed/truncated JSON files (rebuilds broken top-level blocks). |
| [fix_corrupted_json_files.py](fix_corrupted_json_files.py) | Lighter-weight JSON corruption repair pass. |
| [patch_pdf_descriptions_in_delivery.py](patch_pdf_descriptions_in_delivery.py) | Patches `[IMAGE ATTACHED]` placeholders in already-exported delivery JSON with Alfred-generated image descriptions. |

## Typical end-to-end flow

1. `workflow/run_all_series.py` (or the PowerShell wrappers) runs ingestion →
   cleaning → enrichment → similarity → chunking → evaluation → delivery for
   each series, using configs from [shared/config](../shared/config/README.md).
2. `alfred/enrich_pdf_figures_with_alfred.py` / `enrich_json_images_with_alfred.py`
   enrich PDF figures and issue images with AI-generated descriptions.
3. `upload/*.py` push the resulting ST-ready JSON to the target KB datasources.
4. `test_suites/*.py` generate/grade QA test suites against the live KB.
5. `jenkins/Jenkinsfile_GitHubArtifactsToKB.groovy` automates steps 1–3 on a
   schedule for CI.
