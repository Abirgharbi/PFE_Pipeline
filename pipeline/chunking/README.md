# pipeline/chunking

## Purpose

The chunking stage splits enriched documents (issues and files) into smaller
RAG-ready **chunks** (`id`, `text`, `metadata`), so each chunk fits within an
embedding/context size budget. Chunk metadata mirrors the source doc's fields
(minus the full `clean_text`) plus `chunk_index`/`chunk_count`.

It runs after `pipeline/enrichment` / `pipeline/similarity` and before
`pipeline/evaluation` and `pipeline/delivery`.

## Scripts

| Script | Description | Run |
| --- | --- | --- |
| `docs_to_chunks_issues_v2.py` | **Current** issue chunking: reads `docs_issues_<repo>_v2_sim.json` (fallback `_v2.json`), excludes invalid docs, splits `clean_text` into paragraph-aware chunks. | `python -m pipeline.chunking.docs_to_chunks_issues_v2` |
| `docs_to_chunks_files_v2.py` | **Current** file chunking: reads `docs_files_<repo>_v2.json`, excludes invalid docs, splits `clean_text` into paragraph-aware chunks. | `python -m pipeline.chunking.docs_to_chunks_files_v2` |
| `chunk_service.py` | Shared helpers used by all scripts here: `mcu_series_from_repo`, `split_by_paragraphs`, `doc_issue_to_chunks`, `doc_file_to_chunks`, and the legacy `clean_issue_to_chunk`. Not a CLI script. | n/a (library module) |
| `docs_to_chunks_issues.py` | Legacy V1 issue chunking: reads `docs_issues_<repo>.json` (no validity filter). Superseded by `docs_to_chunks_issues_v2.py`. | `python -m pipeline.chunking.docs_to_chunks_issues` |
| `issues_to_chunks.py` | Earliest/legacy shortcut: chunks `clean_issues_<repo>.json` directly (skips the enrichment stage entirely), one chunk per issue. Writes to the same output filename as `docs_to_chunks_issues.py`. | `python -m pipeline.chunking.issues_to_chunks` |

## Typical inputs / outputs

- **Inputs**:
  - `data/docs_issues_<repo>_v2_sim.json` / `_v2.json` (issues, current)
  - `data/docs_files_<repo>_v2.json` (files, current)
  - `data/docs_issues_<repo>.json` / `data/clean_issues_<repo>.json` (legacy)
- **Outputs**:
  - `data/chunks_issues_<repo>_v2.json` (current issues)
  - `data/chunks_files_<repo>_v2.json` (current files)
  - `data/chunks_issues_<repo>.json` (legacy, shared by both legacy scripts)

## Role in the pipeline

```
enrichment / similarity -> chunking (this folder) -> evaluation -> delivery
```

Config (repo list, `chunk_max_chars_issue` default 1200, `chunk_max_chars_file`
default 2000, `ingest_version`) is resolved via
`shared.utils.paths.get_config_path()` (default
`shared/config/config_all_series.json`, overridable with `STM32CUBE_CONFIG`).
