"""Audit STM32Cube series configs against the GitHub submodules they declare.

Role in the evaluation stage
-----------------------------
Each STM32Cube series repo (e.g. STM32CubeH7) is a GitHub "umbrella" repo that
declares BSP/CMSIS/HAL/Middleware sub-repositories as git submodules (see its
``.gitmodules`` file). The preprocessing pipeline needs every one of those
submodule repos to also be listed in the matching ``shared/config/config_<series>.json``
so ingestion (fetch_*.py scripts) actually pulls their issues/files. This
script is a *drift detector*: it diffs "submodules declared in .gitmodules"
against "repos configured in config_<series>.json" and reports (or fixes)
any missing entries before a full pipeline run, preventing silent coverage
gaps in the knowledge base.

Inputs
------
- ``shared/config/config_<series>.json`` files (all ``config*.json`` except
  ``config_all_series.json``), read for ``repos``, ``repo_clone_urls``,
  ``repos_dir``.
- The local clone of each series repo under ``GitHub_repos/<series>`` (path
  resolved via ``get_repos_root``), specifically its ``.gitmodules`` file and
  git history (via ``git ls-tree HEAD <path>``) to resolve the pinned
  submodule commit SHA.

Outputs
-------
- Console report per config file listing missing submodule repos.
- With ``--fix``, the config file is rewritten in place: missing repos are
  appended to ``repos``, their clone URL to ``repo_clone_urls``, and their
  pinned commit SHA to ``linked_repo_refs``.
- Process exit code 1 when repos are missing and ``--fix``/``--no-fail`` are
  not used, so this can be wired into CI as a gate.

Usage (CLI)
-----------
    python pipeline/evaluation/audit_config_submodules.py
    python pipeline/evaluation/audit_config_submodules.py --fix
    python pipeline/evaluation/audit_config_submodules.py --no-fail

Arguments
---------
--fix       Append missing submodule repos, clone URLs, and local gitlink
            refs to the matching config files instead of only reporting them.
--no-fail   Report missing repos without returning a non-zero exit code
            (useful for advisory/non-blocking CI runs).
"""

import argparse
import configparser
import json
import subprocess
from pathlib import Path
from urllib.parse import urlparse

from shared.utils.paths import PROJECT_ROOT, get_repos_root

CONFIG_DIR = PROJECT_ROOT / "shared" / "config"


def repo_slug(value: str) -> str:
    """Extract the lowercase repo name from a URL/path (strip trailing ``.git``)."""
    return value.strip().removesuffix(".git").split("/")[-1].lower()


def canonical_repo_slug(value: str) -> str:
    """Normalize a repo slug to the config convention (underscores -> hyphens).

    Config files and .gitmodules can spell the same repo with either
    separator (e.g. ``b_u585i_iot02a_bsp`` vs ``b-u585i-iot02a-bsp``); this
    normalization lets the two sources be compared reliably.
    """
    return repo_slug(value).replace("_", "-")


def normalize_clone_url(url: str) -> str:
    """Ensure a git clone URL ends with ``.git`` so it clones consistently."""
    value = url.strip()
    if value and not value.endswith(".git"):
        value = f"{value}.git"
    return value


def load_config_files() -> list[Path]:
    """Return all per-series config files, excluding the shared defaults file.

    ``config_all_series.json`` holds cross-series defaults, not a repo list,
    so it is never a candidate for submodule auditing.
    """
    return sorted(
        path for path in CONFIG_DIR.glob("config*.json")
        if path.name != "config_all_series.json"
    )


def extract_submodules(gitmodules_path: Path) -> dict[str, dict[str, str]]:
    """Parse a ``.gitmodules`` file and return its GitHub submodules.

    Args:
        gitmodules_path: Path to the series repo's ``.gitmodules`` file.

    Returns:
        Mapping of canonical repo slug -> {repo, path, url}, restricted to
        submodules hosted on github.com (other hosts are not part of the
        knowledge base scope and are skipped).
    """
    parser = configparser.ConfigParser()
    parser.read(gitmodules_path, encoding="utf-8")

    submodules: dict[str, dict[str, str]] = {}
    for section in parser.sections():
        if not section.startswith("submodule "):
            continue
        url = parser.get(section, "url", fallback="").strip()
        path = parser.get(section, "path", fallback="").strip()
        if not url or not path:
            continue
        parsed = urlparse(url)
        # Only GitHub-hosted submodules are ingestible by the fetch_*.py scripts.
        if "github.com" not in parsed.netloc.lower():
            continue
        slug = repo_slug(parsed.path)
        if slug:
            submodules[canonical_repo_slug(slug)] = {
                "repo": slug.replace("_", "-"),
                "path": path,
                "url": normalize_clone_url(url),
            }
    return submodules


def configured_repo_keys(cfg: dict) -> set[str]:
    """Collect every repo slug already known to a config file.

    Looks both at the plain ``repos`` list and at ``repo_clone_urls`` (keys
    and URL paths), since a repo can be referenced only via its clone URL
    alias in some configs.

    Args:
        cfg: Parsed config JSON (per-series config dict).

    Returns:
        Set of canonical repo slugs already configured.
    """
    repos = [str(repo).strip() for repo in cfg.get("repos", []) if str(repo).strip()]
    configured = {canonical_repo_slug(repo) for repo in repos}

    clone_urls = cfg.get("repo_clone_urls", {})
    if isinstance(clone_urls, dict):
        for alias, url in clone_urls.items():
            if isinstance(alias, str) and alias.strip():
                configured.add(canonical_repo_slug(alias))
            if isinstance(url, str) and url.strip():
                configured.add(canonical_repo_slug(urlparse(url).path))

    return configured


def get_submodule_ref(series_root: Path, submodule_path: str) -> str | None:
    """Resolve the git commit SHA a submodule gitlink is pinned to.

    Uses ``git ls-tree HEAD <path>`` on the local series clone to read the
    submodule's gitlink entry, so the config's ``linked_repo_refs`` can track
    exactly which commit was ingested (useful for reproducibility).

    Args:
        series_root: Local clone path of the series repo (e.g. STM32CubeH7).
        submodule_path: Submodule path as declared in ``.gitmodules``.

    Returns:
        The pinned commit SHA, or ``None`` if it cannot be resolved (e.g. not
        a git repo, path not tracked, or git not available).
    """
    proc = subprocess.run(
        ["git", "ls-tree", "HEAD", submodule_path],
        cwd=str(series_root),
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return None
    parts = (proc.stdout or "").strip().split()
    # `git ls-tree` output for a submodule gitlink is: "<mode> commit <sha>\t<path>".
    if len(parts) >= 3 and parts[1] == "commit":
        return parts[2]
    return None


def audit_config(cfg_file: Path) -> tuple[str, Path | None, list[dict[str, str]]]:
    """Compare one config file's repos against its series' declared submodules.

    Args:
        cfg_file: Path to a ``config_<series>.json`` file.

    Returns:
        Tuple of (series_repo_name, local_series_clone_path_or_None,
        list_of_missing_submodule_dicts). The clone path is ``None`` when the
        series repo has no local clone yet (nothing to audit against).
    """
    cfg = json.loads(cfg_file.read_text(encoding="utf-8-sig"))
    repos = [str(repo).strip() for repo in cfg.get("repos", []) if str(repo).strip()]
    configured = configured_repo_keys(cfg)
    series_repo = next((repo for repo in repos if repo.lower().startswith("stm32cube")), cfg_file.stem)

    repos_root = get_repos_root(cfg.get("repos_dir", "GitHub_repos"))
    series_root = repos_root / series_repo
    gitmodules_path = series_root / ".gitmodules"
    if not gitmodules_path.exists():
        return series_repo, None, []

    missing: list[dict[str, str]] = []
    for submodule_repo, submodule in sorted(extract_submodules(gitmodules_path).items()):
        if submodule_repo not in configured:
            missing.append(submodule)
    return series_repo, series_root, missing


def update_config(cfg_file: Path, series_root: Path, missing: list[dict[str, str]]) -> None:
    """Append missing submodule repos to a config file in place (``--fix`` mode).

    Mutates ``repos``, ``repo_clone_urls``, and ``linked_repo_refs`` in the
    JSON config and rewrites the file. Existing entries are never removed or
    overwritten, only missing ones are added, to keep the fix idempotent and
    safe to re-run.

    Args:
        cfg_file: Config file to update.
        series_root: Local clone path used to resolve pinned commit SHAs.
        missing: Submodule dicts (repo/path/url) to add.
    """
    cfg = json.loads(cfg_file.read_text(encoding="utf-8-sig"))
    repos = cfg.setdefault("repos", [])
    clone_urls = cfg.setdefault("repo_clone_urls", {})
    linked_refs = cfg.setdefault("linked_repo_refs", {})

    existing = configured_repo_keys(cfg)
    for submodule in missing:
        repo = submodule["repo"]
        key = canonical_repo_slug(repo)
        if key in existing:
            continue
        repos.append(repo)
        clone_urls[repo] = submodule["url"]
        ref = get_submodule_ref(series_root, submodule["path"])
        if ref:
            linked_refs[repo] = ref
        existing.add(key)

    cfg_file.write_text(
        json.dumps(cfg, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    """CLI entry point: audit (and optionally fix) all per-series configs."""
    parser = argparse.ArgumentParser(
        description="Audit config repos against GitHub submodules declared by STM32Cube series."
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Append missing submodule repos, clone URLs, and local gitlink refs to config files.",
    )
    parser.add_argument(
        "--no-fail",
        action="store_true",
        help="Report missing repos without returning a non-zero exit code.",
    )
    args = parser.parse_args()

    total_missing = 0
    for cfg_file in load_config_files():
        series_repo, series_root, missing = audit_config(cfg_file)
        if not missing:
            continue
        total_missing += len(missing)
        print(f"\n[{series_repo}] missing submodule repos in {cfg_file.name}:")
        for submodule in missing:
            print(f"  - {submodule['repo']} ({submodule['path']})")

        if args.fix and series_root is not None:
            update_config(cfg_file, series_root, missing)
            print(f"  -> updated {cfg_file.name}")

    if total_missing == 0:
        print("OK: no missing GitHub submodule repos detected in configs.")
    elif args.fix:
        print(f"\nUpdated configs with {total_missing} missing repos. Run the audit again to verify.")
    else:
        print(f"\nTOTAL missing repos: {total_missing}")
        print("Run with --fix to append missing repos to the matching config files.")
        if not args.no_fail:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
