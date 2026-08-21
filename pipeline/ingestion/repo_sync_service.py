"""Ingestion stage: ensure STM32Cube repos are cloned locally and pinned to the configured ref.

Role in the pipeline
---------------------
Called by `fetch_files.py` (unless `--skip-repo-sync` is passed) before
scanning local file content, and also runnable standalone. It guarantees
every repo listed in the config exists under `GitHub_repos/<repo>` (cloning
via `git` if missing) and, if the config pins a specific ref for that repo,
fetches and checks it out so file content matches a reproducible snapshot.

Inputs
------
- Config: resolved via `shared.utils.paths.get_config_path()` (default
  `shared/config/config_all_series.json`, overridable with `STM32CUBE_CONFIG`).
  Uses `owner`, `repos`, `repos_dir`, `repo_clone_urls` and `linked_repo_refs`.
- The local `git` executable (invoked via `subprocess`).

Outputs
-------
- Local git clones under `GitHub_repos/<repo>/` (created/updated in place).
  This module does not write any JSON artifacts.

How to run
----------
No CLI arguments; run as a module: `python -m pipeline.ingestion.repo_sync_service`.
Requires `git` to be installed and available on PATH.
"""

import json
import subprocess
from pathlib import Path

from shared.utils.paths import get_config_path, get_repos_root


def load_config() -> dict:
    """Load and parse the active pipeline configuration JSON file.

    Returns:
        The parsed configuration as a dict.
    """
    cfg_path = get_config_path()
    return json.loads(cfg_path.read_text(encoding="utf-8"))


def run_git_command(args: list[str], cwd: Path | None = None) -> tuple[int, str]:
    """Run a `git` subcommand and capture its combined status/output.

    Args:
        args: Arguments passed after `git` (e.g. ["clone", url, dest]).
        cwd: Working directory to run the command in (e.g. the repo clone).

    Returns:
        A tuple of (return code, stdout if non-empty else stderr, stripped).
    """
    proc = subprocess.run(
        ["git", *args],
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        check=False,
    )
    message = (proc.stdout or "").strip() or (proc.stderr or "").strip()
    return proc.returncode, message


def resolve_clone_url(owner: str, repo: str, cfg: dict) -> str:
    """Resolve the clone URL for a repo, honoring config overrides.

    Args:
        owner: Default GitHub owner/organization.
        repo: Repository name.
        cfg: Active configuration dict (may contain a `repo_clone_urls` map
            for repos that need a non-standard URL, e.g. private mirrors).

    Returns:
        The HTTPS clone URL to use for this repo.
    """
    custom_urls = cfg.get("repo_clone_urls")
    if isinstance(custom_urls, dict):
        value = custom_urls.get(repo)
        if isinstance(value, str) and value.strip():
            return value.strip()

    return f"https://github.com/{owner}/{repo}.git"


def ensure_single_repo(repo: str, owner: str, repos_root: Path, cfg: dict) -> None:
    """Ensure one repo is cloned locally and, if configured, pinned to a specific ref.

    Clones the repo if its local folder doesn't exist yet. If the config's
    `linked_repo_refs` specifies a target ref for this repo, fetches and
    checks it out (skipping the fetch/checkout if HEAD already matches, to
    avoid unnecessary network calls on repeated runs).

    Args:
        repo: Repository name.
        owner: Default GitHub owner/organization.
        repos_root: Local directory under which repos are cloned.
        cfg: Active configuration dict.
    """
    repo_root = repos_root / repo

    if not repo_root.exists():
        clone_url = resolve_clone_url(owner=owner, repo=repo, cfg=cfg)
        print(f"[SYNC] Cloning {repo} from {clone_url}")
        clone_code, clone_msg = run_git_command(["clone", clone_url, str(repo_root)])
        if clone_code != 0:
            print(f"[ERROR] Clone failed for {repo}: {clone_msg}")
            return
    else:
        print(f"[SYNC] Using existing local repo: {repo_root}")

    if not (repo_root / ".git").exists():
        print(f"[WARN] Not a git repository: {repo_root}")
        return

    refs = cfg.get("linked_repo_refs")
    if not isinstance(refs, dict):
        return

    target_ref = refs.get(repo)
    if not isinstance(target_ref, str) or not target_ref.strip():
        return

    target_ref = target_ref.strip()

    rev_code, rev_msg = run_git_command(["rev-parse", "--short", "HEAD"], cwd=repo_root)
    if rev_code == 0 and rev_msg.startswith(target_ref):
        # Already at the pinned ref; skip network calls on repeated runs.
        print(f"[SYNC] {repo} already pinned at {rev_msg}")
        return

    print(f"[SYNC] Pinning {repo} to {target_ref}")
    fetch_code, fetch_msg = run_git_command(["fetch", "origin", target_ref], cwd=repo_root)
    if fetch_code != 0:
        print(f"[WARN] git fetch origin {target_ref} failed for {repo}: {fetch_msg}")
        # Targeted fetch of the ref failed (e.g. shallow clone or unknown ref);
        # fall back to a full fetch before giving up.
        full_fetch_code, full_fetch_msg = run_git_command(["fetch", "origin"], cwd=repo_root)
        if full_fetch_code != 0:
            print(f"[ERROR] git fetch origin failed for {repo}: {full_fetch_msg}")
            return

    checkout_code, checkout_msg = run_git_command(["checkout", target_ref], cwd=repo_root)
    if checkout_code != 0:
        print(f"[ERROR] git checkout {target_ref} failed for {repo}: {checkout_msg}")
        return

    print(f"[SYNC] {repo} pinned to {target_ref}")


def ensure_local_repos(cfg: dict | None = None) -> None:
    """Ensure every configured repo is cloned locally (and pinned, if configured).

    Args:
        cfg: Optional pre-loaded configuration dict; loaded via `load_config`
            if not provided.

    Raises:
        ValueError: If the config's `repos` field is missing or not a list.
    """
    cfg = cfg or load_config()
    owner = cfg.get("owner", "STMicroelectronics")
    repos = cfg.get("repos")

    if not isinstance(repos, list):
        raise ValueError("config field 'repos' must be a list")

    repos_root = get_repos_root(cfg.get("repos_dir", "GitHub_repos"))
    repos_root.mkdir(parents=True, exist_ok=True)

    for repo in repos:
        if not isinstance(repo, str) or not repo.strip():
            print(f"[WARN] Skipping invalid repo entry: {repo}")
            continue
        ensure_single_repo(repo=repo.strip(), owner=owner, repos_root=repos_root, cfg=cfg)


def main() -> None:
    """Entry point: load the active config and sync all configured repos locally."""
    cfg = load_config()
    ensure_local_repos(cfg)
    print("Done sync local repos.")


if __name__ == "__main__":
    main()
