"""Ingestion stage: fetch raw GitHub issues (with comments) for STM32Cube repos.

Role in the pipeline
---------------------
First step of the issues track in `pipeline/ingestion`. Its output feeds
`pipeline/cleaning/clean_issues.py`, which in turn feeds enrichment
(`issues_to_docs_v2.py`) and downstream similarity/chunking/delivery stages.

Inputs
------
- Config: resolved via `shared.utils.paths.get_config_path()` (default
  `shared/config/config_all_series.json`, overridable with `STM32CUBE_CONFIG`).
  Uses `owner`, `repos`, `github_token_env` and `rate_limits`.
- GitHub REST API (issues + comments endpoints), via `GitHubService`.

Outputs
-------
- `data/raw_issues_<repo>.json`: list of raw issue records (title, body,
  labels, state, timestamps, comments, github_url) for each configured repo.

How to run
----------
No CLI arguments; run as a module: `python -m pipeline.ingestion.fetch_issues`.
Requires a GitHub token (env var named by `github_token_env`, default
`GITHUB_TOKEN`) to avoid unauthenticated rate limits.
"""

import json

from pipeline.ingestion.github_service import GitHubService
from shared.utils.paths import DATA_DIR, get_config_path


def load_config() -> dict:
    """Load and parse the active pipeline configuration JSON file.

    Returns:
        The parsed configuration as a dict.
    """
    cfg_path = get_config_path()
    return json.loads(cfg_path.read_text(encoding="utf-8"))


def main() -> None:
    """Entry point: fetch all issues (with comments) for each configured repo.

    Writes one `raw_issues_<repo>.json` file per repo under `DATA_DIR`.
    """
    cfg = load_config()
    owner = cfg["owner"]
    repos = cfg["repos"]
    data_dir = DATA_DIR
    data_dir.mkdir(parents=True, exist_ok=True)

    gh = GitHubService(
        owner=owner,
        token_env=cfg.get("github_token_env", "GITHUB_TOKEN"),
        issues_sleep=cfg.get("rate_limits", {}).get("issues_sleep", 0.2),
        comments_sleep=cfg.get("rate_limits", {}).get("comments_sleep", 0.1),
    )

    for repo in repos:
        print(f"Processing repo {repo}")
        issues = gh.fetch_all_issues(repo)

        out_file = data_dir / f"raw_issues_{repo.lower()}.json"
        out_file.write_text(
            json.dumps(issues, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"[{repo}] {len(issues)} issues fetched -> {out_file}")


if __name__ == "__main__":
    main()
