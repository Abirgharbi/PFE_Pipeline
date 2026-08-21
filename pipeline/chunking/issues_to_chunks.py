"""CLI script (legacy V1): chunk clean issues directly, skipping enrichment.

Role in the pipeline: earliest/legacy shortcut that bypasses the enrichment
stage entirely, converting `clean_issues_<repo>.json` straight into chunks
via `chunk_service.clean_issue_to_chunk` (always exactly one chunk per
issue, no `clean_text` splitting, no layer/severity/board/component
heuristics). Superseded by the `docs_to_chunks_issues*.py` scripts.

For each repo in the active config, reads `data/clean_issues_<repo>.json`
and writes `data/chunks_issues_<repo>.json` (note: this overwrites the same
output file produced by `docs_to_chunks_issues.py` if run for the same
repo).

Config: resolved via `shared.utils.paths.get_config_path()`. Uses the
`repos` list and optional `ingest_version` key.

Run with:
    python -m pipeline.chunking.issues_to_chunks
"""

import json

from pipeline.chunking.chunk_service import clean_issue_to_chunk
from shared.utils.paths import DATA_DIR, get_config_path


def load_config() -> dict:
    """Load and return the active pipeline config as a dict."""
    cfg_path = get_config_path()
    return json.loads(cfg_path.read_text(encoding="utf-8"))


def main() -> None:
    """Convert clean issues directly into chunks for every repo in the config.

    Note: unlike other chunking scripts, this does not check whether the
    input file exists before reading it, so a missing `clean_issues_<repo>.json`
    will raise instead of being skipped with a warning.
    """
    cfg = load_config()
    repos = cfg["repos"]
    ingest_version = cfg.get("ingest_version", "v1.0")

    for repo in repos:
        in_file = DATA_DIR / f"clean_issues_{repo.lower()}.json"
        out_file = DATA_DIR / f"chunks_issues_{repo.lower()}.json"

        if not in_file.exists():
            print(f"[WARN] clean issues file not found: {in_file}")
            continue

        print(f"Converting issues into chunks for {repo}")
        clean_issues = json.loads(in_file.read_text(encoding="utf-8"))
        chunks = [clean_issue_to_chunk(issue, ingest_version=ingest_version) for issue in clean_issues]

        out_file.write_text(
            json.dumps(chunks, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"{len(chunks)} chunks written -> {out_file}")


if __name__ == "__main__":
    main()
