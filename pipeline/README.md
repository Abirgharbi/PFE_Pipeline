# Pipeline Folder

This folder organizes code by pipeline stages. It implements the CRISP-DM-aligned
preprocessing pipeline that turns STM32Cube GitHub repos (issues, PRs, commits,
files, PDFs) into a clean, enriched, chunked knowledge base ready for a RAG
chatbot / ST AI Bridge knowledge base upload. Each stage reads the previous
stage's output and writes into `datasets/<NN_stage>/` (see
[datasets/README.md](../datasets/README.md)).

| Stage | Folder | Role |
|---|---|---|
| 1. Ingestion | [ingestion/](ingestion/README.md) | Fetch raw data from the GitHub API and local repo clones (issues, PRs, commits, files, PDFs). |
| 2. Cleaning | [cleaning/](cleaning/README.md) | Normalize and sanitize raw text (issues, files). |
| 3. Enrichment | [enrichment/](enrichment/README.md) | Extract metadata and build structured "docs_v2" documents with heuristics. |
| 4. Similarity | [similarity/](similarity/README.md) | Link related issues via TF-IDF similarity. |
| 5. Chunking | [chunking/](chunking/README.md) | Split enriched docs into RAG-ready chunks. |
| 6. Evaluation | [evaluation/](evaluation/README.md) | Stats, TF-IDF retrieval simulation, schema and Alfred coherence checks. |
| 7. Delivery | [delivery/](delivery/README.md) | Export "ST-ready" JSON for KB upload (see [pipeline_Automation/upload](../pipeline_Automation/upload/README.md)). |

[run_full_workflow.py](run_full_workflow.py) orchestrates stages 2–7 for a
single repo/series (ingestion is run separately, upstream). For running the
full pipeline across *all* STM32Cube series, see
[pipeline_Automation/workflow](../pipeline_Automation/workflow/README.md).

Configuration is resolved via [shared/utils/paths.py](../shared/utils/paths.py)
(`get_config_path()`), see [shared/config](../shared/config/README.md).
