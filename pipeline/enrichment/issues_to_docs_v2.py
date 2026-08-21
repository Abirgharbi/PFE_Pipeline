"""CLI script: enrich cleaned issues into V2 doc records.

Role in the pipeline: main enrichment step for the "issues" source, run
after the cleaning stage and before the similarity stage
(`compute_issue_similarity_v2.py`) and chunking stage
(`docs_to_chunks_issues_v2.py`).

For each repo listed in the active config, reads
`data/clean_issues_<repo>.json`, runs each issue through
`PreprocessingModelIssuesV2.process_clean_issue` (layer/severity/issue_kind/
board/component detection, validity filtering with rescue logic), and writes
`data/docs_issues_<repo>_v2.json`.

Config: resolved via `shared.utils.paths.get_config_path()`. Uses the
`repos` list and optional `preprocess_version` key.

Run with:
    python -m pipeline.enrichment.issues_to_docs_v2
"""

import json

from pipeline.enrichment.preprocessing_model import PreprocessingConfig, PreprocessingModelIssuesV2
from shared.utils.paths import DATA_DIR, get_config_path


def load_config() -> dict:
    """Load and return the active pipeline config as a dict."""
    cfg_path = get_config_path()
    return json.loads(cfg_path.read_text(encoding="utf-8"))


def main() -> None:
    """Build V2 enriched issue docs for every repo in the active config.

    Skips repos whose `clean_issues_<repo>.json` file is missing (with a
    warning) and writes the enriched docs list to `docs_issues_<repo>_v2.json`.
    """
    cfg = load_config()
    repos = cfg["repos"]
    preprocess_version = cfg.get("preprocess_version", "v2.0")

    pp_config = PreprocessingConfig(version=preprocess_version)
    pp_model = PreprocessingModelIssuesV2(pp_config)

    for repo in repos:
        in_file = DATA_DIR / f"clean_issues_{repo.lower()}.json"
        out_file = DATA_DIR / f"docs_issues_{repo.lower()}_v2.json"

        if not in_file.exists():
            print(f"[WARN] clean_issues file not found: {in_file}")
            continue

        print(f"[V2] Generating docs_issues for {repo}")
        clean_issues = json.loads(in_file.read_text(encoding="utf-8"))

        docs: list[dict] = []
        for issue in clean_issues:
            docs.append(pp_model.process_clean_issue(issue))

        out_file.write_text(
            json.dumps(docs, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"[V2] {len(docs)} docs written -> {out_file}")

    print("Done V2 docs_issues.")


if __name__ == "__main__":
    main()
