"""Ingestion stage: fetch commit details for STM32Cube pull requests.

Role in the pipeline
---------------------
This script is part of `pipeline/ingestion`. It complements `fetch_prs.py` by
resolving the actual commits attached to pull requests, which is required by
`fetch_issue_pr_commit_links.py` to build issue <-> PR <-> commit linkage used
downstream for resolution-status heuristics (e.g. "merged_fix").

Inputs
------
- Config: resolved via `shared.utils.paths.get_config_path()` (default
  `shared/config/config_all_series.json`, overridable with the
  `STM32CUBE_CONFIG` env var). Uses `owner`, `repos`, `github_token_env`,
  `rate_limits` and `commit_pr_scope`.
- `data/raw_prs_<repo>.json`: pull requests previously fetched by
  `fetch_prs.py`. If missing, this script fetches them itself via
  `GitHubService.fetch_all_pull_requests` before continuing.

Outputs
-------
- `data/raw_commits_<repo>.json`: list of commit detail records (one per
  distinct commit SHA referenced by the selected pull requests).
- `data/raw_prs_<repo>.json`: written as a side effect only when the PR file
  did not already exist (fallback fetch path).

How to run
----------
No CLI arguments; run as a module: `python -m pipeline.ingestion.fetch_commits`.
Uses the GitHub REST API (via `GitHubService`), so `GITHUB_TOKEN` (or the env
var named by `github_token_env`) should be set to avoid low rate limits.
"""

import json
from typing import Any

from pipeline.ingestion.github_service import GitHubService
from shared.utils.paths import DATA_DIR, get_config_path


def load_config() -> dict:
    """Load and parse the active pipeline configuration JSON file.

    Returns:
        The parsed configuration as a dict (see `get_config_path` for how the
        file path is resolved).
    """
    cfg_path = get_config_path()
    return json.loads(cfg_path.read_text(encoding="utf-8"))


def load_pull_requests(data_dir, repo: str) -> list[dict[str, Any]]:
    """Load previously fetched pull requests for a repo, if present.

    Args:
        data_dir: Directory containing raw ingestion JSON artifacts.
        repo: Repository name (case-insensitive; matched via lowercase file name).

    Returns:
        The list of PR records from `raw_prs_<repo>.json`, or an empty list if
        the file does not exist yet (caller is expected to fetch it in that case).
    """
    prs_path = data_dir / f"raw_prs_{repo.lower()}.json"
    if prs_path.exists():
        return json.loads(prs_path.read_text(encoding="utf-8"))
    return []


def select_pull_requests_for_commit_ingestion(
    pull_requests: list[dict[str, Any]],
    scope: str,
) -> list[dict[str, Any]]:
    """Filter which pull requests should have their commits fetched.

    Fetching commit details for every PR (including drafts/unrelated ones) is
    expensive against the GitHub API, so `commit_pr_scope` in the config lets
    us narrow the set of PRs that actually matter for issue resolution.

    Args:
        pull_requests: Full list of PR records for a repo.
        scope: One of "all", "linked_only", "merged_only", or any other value
            which falls back to the default resolver-friendly mode.

    Returns:
        The filtered list of PR records to fetch commits for.
    """
    if scope == "all":
        return pull_requests

    if scope == "linked_only":
        return [pr for pr in pull_requests if pr.get("linked_issue_numbers")]

    if scope == "merged_only":
        return [pr for pr in pull_requests if pr.get("merged")]

    # Default resolver-friendly mode: keep merged PRs + PRs explicitly linked to issues.
    return [
        pr for pr in pull_requests
        if pr.get("merged") or pr.get("linked_issue_numbers")
    ]


def main() -> None:
    """Entry point: fetch commits for each configured repo's selected PRs.

    For every repo in the config, ensures pull requests are available (fetching
    them if the raw PR file is missing), narrows them down using
    `commit_pr_scope`, then fetches the associated commit details and writes
    them to `data/raw_commits_<repo>.json`.
    """
    cfg = load_config()
    owner = cfg["owner"]
    repos = cfg["repos"]
    data_dir = DATA_DIR
    data_dir.mkdir(parents=True, exist_ok=True)

    rate_limits = cfg.get("rate_limits", {})
    commit_pr_scope = cfg.get("commit_pr_scope", "linked_or_merged")
    gh = GitHubService(
        owner=owner,
        token_env=cfg.get("github_token_env", "GITHUB_TOKEN"),
        prs_sleep=rate_limits.get("prs_sleep", 0.2),
        pr_details_sleep=rate_limits.get("pr_details_sleep", 0.1),
        commits_sleep=rate_limits.get("commits_sleep", 0.1),
    )

    for repo in repos:
        print(f"Processing repo {repo}")
        pull_requests = load_pull_requests(data_dir, repo)
        if not pull_requests:
            # Commits are fetched per-PR, so we need PR data first; self-heal by
            # fetching PRs here instead of forcing the operator to run fetch_prs.py.
            print(f"[{repo}] raw PR file missing or empty, fetching pull requests first")
            pull_requests = gh.fetch_all_pull_requests(repo)
            prs_out_file = data_dir / f"raw_prs_{repo.lower()}.json"
            prs_out_file.write_text(
                json.dumps(pull_requests, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

        selected_pull_requests = select_pull_requests_for_commit_ingestion(
            pull_requests,
            scope=commit_pr_scope,
        )
        commits = gh.fetch_commits_for_pull_requests(repo, selected_pull_requests)

        out_file = data_dir / f"raw_commits_{repo.lower()}.json"
        out_file.write_text(
            json.dumps(commits, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        linked_selected_count = len(
            [pr for pr in selected_pull_requests if pr.get("linked_issue_numbers")]
        )
        merged_selected_count = len([pr for pr in selected_pull_requests if pr.get("merged")])
        print(
            f"[{repo}] {len(commits)} commits fetched from {len(selected_pull_requests)} PRs "
            f"(scope={commit_pr_scope}, merged={merged_selected_count}, linked={linked_selected_count}) -> {out_file}"
        )


if __name__ == "__main__":
    main()