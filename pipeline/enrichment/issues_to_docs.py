"""CLI script (legacy V1): enrich cleaned issues into doc records.

Role in the pipeline: superseded by `issues_to_docs_v2.py`, which applies
additional heuristics (layer, severity, issue_kind, board, component,
validity filtering). This V1 script only shapes clean issues into the common
doc schema via `docs_issue_service.clean_issue_to_doc`.

For each repo in the active config, reads `data/clean_issues_<repo>.json`
and writes `data/docs_issues_<repo>.json`.

Config: resolved via `shared.utils.paths.get_config_path()`. Uses the
`repos` list and optional `ingest_version` key.

Run with:
    python -m pipeline.enrichment.issues_to_docs
"""

import json

from pipeline.enrichment.docs_issue_service import clean_issue_to_doc
from shared.utils.paths import DATA_DIR, get_config_path


def load_config() -> dict:
    """Load and return the active pipeline config as a dict."""
    cfg_path = get_config_path()
    return json.loads(cfg_path.read_text(encoding="utf-8"))


def main() -> None:
    """Build legacy V1 enriched issue docs for every repo in the config.

    Skips repos whose `clean_issues_<repo>.json` file is missing (with a
    warning) and writes the enriched docs list to `docs_issues_<repo>.json`.
    """
    cfg = load_config()
    repos = cfg["repos"]
    ingest_version = cfg.get("ingest_version", "v1.0")

    for repo in repos:
        in_file = DATA_DIR / f"clean_issues_{repo.lower()}.json"
        out_file = DATA_DIR / f"docs_issues_{repo.lower()}.json"

        if not in_file.exists():
            print(f"[WARN] File not found: {in_file}")
            continue

        print(f"Building enriched documents for {repo}")
        clean_issues = json.loads(in_file.read_text(encoding="utf-8"))
        docs = [clean_issue_to_doc(issue, ingest_version=ingest_version) for issue in clean_issues]

        out_file.write_text(
            json.dumps(docs, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"{len(docs)} enriched documents -> {out_file}")

    print("Done.")


if __name__ == "__main__":
    main()
