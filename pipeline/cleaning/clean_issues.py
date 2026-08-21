"""Cleaning stage: sanitize raw GitHub issues into RAG-friendly clean text.

Role in the pipeline
---------------------
Consumes `data/raw_issues_<repo>.json` (from `pipeline/ingestion/fetch_issues.py`)
and produces `data/clean_issues_<repo>.json` using `build_clean_issue` from
`pipeline/cleaning/cleaning_service.py`. Its output feeds enrichment
(`issues_to_docs_v2.py`), similarity computation, and chunking for the issues
track of the pipeline.

Inputs
------
- Config: resolved via `shared.utils.paths.get_config_path()` (default
  `shared/config/config_all_series.json`, overridable with `STM32CUBE_CONFIG`).
  Uses `repos`.
- `data/raw_issues_<repo>.json` for each configured repo.

Outputs
-------
- `data/clean_issues_<repo>.json`: list of clean issue records with
  `clean_text`, `image_urls`, `images_count`, and passthrough metadata.

How to run
----------
No CLI arguments; run as a module: `python -m pipeline.cleaning.clean_issues`.
"""

import json

from pipeline.cleaning.cleaning_service import build_clean_issue
from shared.utils.paths import DATA_DIR, get_config_path


def load_config() -> dict:
    """Load and parse the active pipeline configuration JSON file.

    Returns:
        The parsed configuration as a dict.
    """
    cfg_path = get_config_path()
    return json.loads(cfg_path.read_text(encoding="utf-8"))


def main() -> None:
    """Entry point: clean raw issues into `clean_text` records for every configured repo."""
    cfg = load_config()
    repos = cfg["repos"]

    for repo in repos:
        raw_file = DATA_DIR / f"raw_issues_{repo.lower()}.json"
        out_file = DATA_DIR / f"clean_issues_{repo.lower()}.json"

        print(f"Cleaning issues for {repo}")
        if not raw_file.exists():
            print(f"[WARN] raw_issues file not found: {raw_file}")
            continue

        raw_issues = json.loads(raw_file.read_text(encoding="utf-8"))
        clean_issues = [build_clean_issue(issue) for issue in raw_issues]

        out_file.write_text(
            json.dumps(clean_issues, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"{len(clean_issues)} cleaned issues -> {out_file}")


if __name__ == "__main__":
    main()
