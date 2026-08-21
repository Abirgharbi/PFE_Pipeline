"""CLI script: split enriched V2 file docs into RAG-ready chunks.

Role in the pipeline: chunking stage for the "files" source, run after
`files_to_docs_v2.py` (enrichment). Produces the final chunk-level JSON
consumed by the delivery/export stage.

For each repo in the active config, reads `data/docs_files_<repo>_v2.json`,
skips docs flagged `is_valid=False`, splits each remaining doc's
`clean_text` via `chunk_service.doc_file_to_chunks` (paragraph-aware
splitting bounded by `chunk_max_chars_file`), and writes the flattened list
of chunks to `data/chunks_files_<repo>_v2.json`.

Config: resolved via `shared.utils.paths.get_config_path()`. Uses the
`repos` list and optional `chunk_max_chars_file` key (default 2000).

Run with:
    python -m pipeline.chunking.docs_to_chunks_files_v2
"""

import json

from pipeline.chunking.chunk_service import doc_file_to_chunks
from shared.utils.paths import DATA_DIR, get_config_path


def load_config() -> dict:
    """Load and return the active pipeline config as a dict."""
    cfg_path = get_config_path()
    return json.loads(cfg_path.read_text(encoding="utf-8"))


def main() -> None:
    """Chunk V2 file docs into `chunks_files_<repo>_v2.json` for every repo.

    Skips repos whose `docs_files_<repo>_v2.json` file is missing (with a
    warning) and excludes docs marked invalid before chunking.
    """
    cfg = load_config()
    repos = cfg["repos"]
    max_chars = cfg.get("chunk_max_chars_file", 2000)

    for repo in repos:
        in_file = DATA_DIR / f"docs_files_{repo.lower()}_v2.json"
        out_file = DATA_DIR / f"chunks_files_{repo.lower()}_v2.json"

        if not in_file.exists():
            print(f"[WARN] docs_files_v2 file not found: {in_file}")
            continue

        print(f"[V2] Multi-chunk splitting for files {repo} (max_chars={max_chars})")
        docs = json.loads(in_file.read_text(encoding="utf-8"))

        all_chunks: list[dict] = []
        for doc in docs:
            if not doc.get("is_valid", True):
                continue
            all_chunks.extend(doc_file_to_chunks(doc, max_chars=max_chars))

        out_file.write_text(
            json.dumps(all_chunks, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"[V2] {len(all_chunks)} file chunks written -> {out_file}")

    print("Done V2 chunks_files.")


if __name__ == "__main__":
    main()
