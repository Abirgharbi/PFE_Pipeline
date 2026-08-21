"""Shared path-resolution helpers used across the whole pipeline and automation layer.

Every pipeline/automation script imports `get_config_path()` and/or `get_repos_root()`
from this module instead of hardcoding paths, so that:
  - the active JSON config can be overridden per run via the `STM32CUBE_CONFIG`
    env var (e.g. to point at a per-series config file), without touching code;
  - the project root is always resolved relative to this file, regardless of the
    current working directory the script is launched from.
"""
from pathlib import Path
import os


# This file lives at <project_root>/shared/utils/paths.py, so climbing two
# parent levels (shared/utils -> shared -> project root) gives the repo root.
PROJECT_ROOT = Path(__file__).resolve().parents[2]

SRC_DIR = PROJECT_ROOT / "src"
DATA_DIR = PROJECT_ROOT / "data"
CONFIG_DIR = PROJECT_ROOT / "shared" / "config"
# Legacy location kept only as a fallback for older checkouts/scripts that
# expected the config under src/config instead of shared/config.
LEGACY_CONFIG_DIR = SRC_DIR / "config"


def get_config_path() -> Path:
    """Resolve which JSON config file the pipeline should use for this run.

    Resolution order:
        1. `STM32CUBE_CONFIG` env var, if set and the file exists (relative
           paths are resolved against `PROJECT_ROOT`). This lets CI/automation
           scripts target a specific series config without code changes.
        2. `shared/config/config.json`, if present.
        3. Fallback to the legacy `src/config/config.json` location.

    Returns:
        Path: the resolved config file path (existence of the final fallback
        is not guaranteed; callers should handle a missing file).
    """
    env_cfg = os.environ.get("STM32CUBE_CONFIG")
    if env_cfg:
        p = Path(env_cfg)
        if not p.is_absolute():
            p = PROJECT_ROOT / p
        if p.exists():
            return p
    cfg = CONFIG_DIR / "config.json"
    if cfg.exists():
        return cfg
    return LEGACY_CONFIG_DIR / "config.json"


def get_repos_root(repos_dir_name: str) -> Path:
    """Return the absolute path to a local repos directory (e.g. "GitHub_repos"),
    resolved relative to the project root regardless of the current working directory.
    """
    return PROJECT_ROOT / repos_dir_name
