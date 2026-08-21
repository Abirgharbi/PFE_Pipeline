"""Ingestion stage: collect raw file artifacts (README, release notes, source,
documentation PDFs) from local STM32Cube repo clones.

Role in the pipeline
---------------------
Unlike `fetch_issues.py`/`fetch_prs.py` (which call the GitHub REST API), this
script scans repositories already cloned on disk under `GitHub_repos/` (see
`repo_sync_service.ensure_local_repos`) and extracts file content using
`file_collect_service.collect_repo_docs`. Its output feeds
`pipeline/cleaning/clean_files.py`.

Inputs
------
- Config: resolved via `shared.utils.paths.get_config_path()` (default
  `shared/config/config_all_series.json`, overridable with `STM32CUBE_CONFIG`).
  Uses `owner`, `repos`, `repos_dir` and `auto_clone_missing_repos`.
- Local git clones under `GitHub_repos/<repo>` (auto-synced unless
  `--skip-repo-sync` is passed or `auto_clone_missing_repos` is false).

Outputs
-------
- `data/raw_files_<repo>.json`: list of raw file records (path, content,
  github_url, PDF figure/image metadata) for each configured repo.

How to run
----------
`python -m pipeline.ingestion.fetch_files [--skip-repo-sync] [--repo NAME ...]`

- `--skip-repo-sync`: skip cloning/fetching/pinning repos; only scan existing
  local clones.
- `--repo NAME`: limit processing to one repo from the active config; can be
  repeated to select multiple repos.
"""

import argparse
import json

from pipeline.ingestion.file_collect_service import collect_repo_docs, write_raw_files_json
from pipeline.ingestion.repo_sync_service import ensure_local_repos
from shared.utils.paths import DATA_DIR, get_config_path, get_repos_root


def load_config() -> dict:
    """Load and parse the active pipeline configuration JSON file.

    Returns:
        The parsed configuration as a dict.
    """
    cfg_path = get_config_path()
    return json.loads(cfg_path.read_text(encoding="utf-8"))


def main(skip_repo_sync: bool = False, only_repos: list[str] | None = None) -> None:
    """Entry point: scan local repo clones and write raw file JSON per repo.

    Args:
        skip_repo_sync: If True, do not clone/fetch/pin repos beforehand;
            only scan whatever is already present under `GitHub_repos/`.
        only_repos: Optional list of repo names (case-insensitive) to restrict
            processing to a subset of the configured repos.
    """
    cfg = load_config()
    owner = cfg.get("owner", "STMicroelectronics")
    repos = cfg["repos"]
    if only_repos:
        wanted = {repo.lower() for repo in only_repos}
        repos = [repo for repo in repos if repo.lower() in wanted]
    data_dir = DATA_DIR
    data_dir.mkdir(parents=True, exist_ok=True)

    if cfg.get("auto_clone_missing_repos", True) and not skip_repo_sync:
        ensure_local_repos(cfg)
    elif skip_repo_sync:
        print("[SYNC] Skipped repo sync; scanning existing local clones only.")

    repos_root = get_repos_root(cfg.get("repos_dir", "GitHub_repos"))

    for repo_name in repos:
        repo_root = repos_root / repo_name

        if not repo_root.exists():
            print(f"[ERROR] Repo folder does not exist: {repo_root}")
            print("        Make sure repository is cloned under GitHub_repos/")
            continue

        try:
            raw_files = collect_repo_docs(repo_name, repo_root, owner=owner)
        except Exception as exc:
            print(f"[ERROR] Scan failed for {repo_name}: {exc}")
            continue

        output_file = data_dir / f"raw_files_{repo_name.lower()}.json"
        write_raw_files_json(raw_files, output_file)

    print("Done.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Collect raw file artifacts from local STM32Cube repos.")
    parser.add_argument(
        "--skip-repo-sync",
        action="store_true",
        help="Do not clone/fetch/pin repos before scanning; use existing local clones only.",
    )
    parser.add_argument(
        "--repo",
        action="append",
        help="Limit scanning to one repo from the active config. Can be repeated.",
    )
    args = parser.parse_args()
    main(skip_repo_sync=args.skip_repo_sync, only_repos=args.repo)
