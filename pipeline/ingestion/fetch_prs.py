"""Ingestion stage: fetch raw GitHub pull requests (with files changed) for STM32Cube repos.

Role in the pipeline
---------------------
Part of `pipeline/ingestion`. Its output is consumed by `fetch_commits.py`
(to resolve commits per PR) and by `fetch_issue_pr_commit_links.py` (to link
issues to the PRs that reference/fix them).

Inputs
------
- Config: resolved via `shared.utils.paths.get_config_path()` (default
  `shared/config/config_all_series.json`, overridable with `STM32CUBE_CONFIG`).
  Uses `owner`, `repos`, `github_token_env` and `rate_limits`.
- GitHub REST API (pulls, pull files endpoints), via `GitHubService`.

Outputs
-------
- `data/raw_prs_<repo>.json`: list of raw PR detail records (title, body,
  state, merge info, linked issue numbers, changed files) for each repo.

How to run
----------
No CLI arguments; run as a module: `python -m pipeline.ingestion.fetch_prs`.
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
    """Entry point: fetch all pull requests (with detail/files) for each configured repo.

    Writes one `raw_prs_<repo>.json` file per repo under `DATA_DIR`.
    """
    cfg = load_config()
    owner = cfg["owner"]
    repos = cfg["repos"]
    data_dir = DATA_DIR
    data_dir.mkdir(parents=True, exist_ok=True)

    rate_limits = cfg.get("rate_limits", {})
    gh = GitHubService(
        owner=owner,
        token_env=cfg.get("github_token_env", "GITHUB_TOKEN"),
        prs_sleep=rate_limits.get("prs_sleep", 0.2),
        pr_details_sleep=rate_limits.get("pr_details_sleep", 0.1),
        commits_sleep=rate_limits.get("commits_sleep", 0.1),
    )

    for repo in repos:
        print(f"Processing repo {repo}")
        pull_requests = gh.fetch_all_pull_requests(repo)

        out_file = data_dir / f"raw_prs_{repo.lower()}.json"
        out_file.write_text(
            json.dumps(pull_requests, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"[{repo}] {len(pull_requests)} pull requests fetched -> {out_file}")


if __name__ == "__main__":
    main()