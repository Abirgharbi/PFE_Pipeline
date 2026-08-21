"""Chunking stage of the STM32Cube preprocessing pipeline.

This package splits enriched documents (issues and files) into smaller
RAG-ready "chunks" with attached metadata, so that each chunk fits within an
embedding/context size budget.

Main modules:
- `chunk_service.py`: shared chunk-building helpers (paragraph splitting,
  doc-to-chunk conversion) used by all the CLI scripts below.
- `docs_to_chunks_issues_v2.py` / `docs_to_chunks_files_v2.py`: current (V2)
  CLI scripts producing `chunks_issues_<repo>_v2.json` /
  `chunks_files_<repo>_v2.json`.
- `docs_to_chunks_issues.py` / `issues_to_chunks.py`: legacy (V1) CLI scripts.

See `pipeline/chunking/README.md` for detailed usage of each script.
"""
