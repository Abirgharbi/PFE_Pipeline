"""CLI script (legacy V1): split enriched issue docs into chunks.

Role in the pipeline: superseded by `docs_to_chunks_issues_v2.py`, which
reads the similarity-enriched V2 docs and filters out invalid issues before
chunking. This V1 script chunks every doc from `issues_to_docs.py` output
unconditionally (no validity filter).

For each repo in the active config, reads `data/docs_issues_<repo>.json`,
splits each doc's `clean_text` via `chunk_service.doc_issue_to_chunks`, and
writes the flattened list of chunks to `data/chunks_issues_<repo>.json`.

Config: resolved via `shared.utils.paths.get_config_path()`. Uses the
`repos` list and optional `chunk_max_chars_issue` key (default 1200).

Run with:
    python -m pipeline.chunking.docs_to_chunks_issues
"""

import json

from pipeline.chunking.chunk_service import doc_issue_to_chunks
from shared.utils.paths import DATA_DIR, get_config_path


def load_config() -> dict:
    """Load and return the active pipeline config as a dict."""
    cfg_path = get_config_path()
    return json.loads(cfg_path.read_text(encoding="utf-8"))


def main() -> None:
    """Chunk legacy V1 issue docs into `chunks_issues_<repo>.json`.

    Skips repos whose `docs_issues_<repo>.json` file is missing (with a
    warning). Does not filter out invalid issues (no `is_valid` check).
    """
    cfg = load_config()
    repos = cfg["repos"]
    max_chars = cfg.get("chunk_max_chars_issue", 1200)

    for repo in repos:
        in_file = DATA_DIR / f"docs_issues_{repo.lower()}.json"
        out_file = DATA_DIR / f"chunks_issues_{repo.lower()}.json"

        if not in_file.exists():
            print(f"[WARN] docs file not found: {in_file}")
            continue

        print(f"Chunking issue documents for {repo}")
        docs = json.loads(in_file.read_text(encoding="utf-8"))

        all_chunks: list[dict] = []
        for doc in docs:
            all_chunks.extend(doc_issue_to_chunks(doc, max_chars=max_chars))

        out_file.write_text(
            json.dumps(all_chunks, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"{len(all_chunks)} chunks written -> {out_file}")

    print("Done.")


if __name__ == "__main__":
    main()
