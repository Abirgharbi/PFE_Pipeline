"""Path-resolution helpers shared by every ST-ready delivery export/split script.

This module is the single source of truth for where delivery artifacts live
under `datasets/07_delivery/st_ready/`. It resolves:

- The per-series output tree (`by_series/<series>/...`), grouping BSP/HAL/CMSIS
  sub-repos (e.g. `stm32h7xx-hal-driver`) under their parent series folder
  (e.g. `by_series/stm32cubeh7/drivers/stm32h7xx-hal-driver/`) instead of
  exporting them as standalone top-level series.
- Per-repo artifact directories/files for each artifact type used by the
  `export_st_ready_*.py` scripts (`issues_json`, `files_json`,
  `resolver_cases_json`, `diagnostic_cards_json`, ...).
- A legacy flat layout (`st_ready/<artifact_dir>/...`) kept as a
  backward-compatible mirror/fallback for consumers that have not migrated
  to the per-series layout yet.

No files are read or written here beyond the config lookups needed to build
the repo -> series mapping; this module only computes `Path` objects.
"""

import os
import json
from pathlib import Path

from shared.utils.paths import PROJECT_ROOT


ST_READY_ROOT = PROJECT_ROOT / "datasets" / "07_delivery" / "st_ready"
ST_READY_BY_SERIES_ROOT = ST_READY_ROOT / "by_series"

# Static repo -> series lookup table, used as a fallback/back-compat baseline
# and then extended/overridden by `_load_config_repo_series_map()` below,
# which treats `shared/config/config_*.json` as the source of truth.
_REPO_TO_SERIES: dict[str, str] = {}

# H7 sub-repos
for _r in [
    "stm32h7xx-hal-driver", "cmsis_device_h7",
    "stm32h735g-dk-bsp", "stm32h743i-eval-bsp", "stm32h745i-disco-bsp",
    "stm32h747i-disco-bsp", "stm32h747i-eval-bsp", "stm32h750b-dk-bsp",
    "stm32h7b3i-dk-bsp", "stm32h7b3i-eval-bsp", "stm32h7xx-nucleo-bsp",
]:
    _REPO_TO_SERIES[_r] = "stm32cubeh7"

# F4 sub-repos
for _r in [
    "stm32f4xx-hal-driver", "cmsis_device_f4",
    "stm32f4xx-nucleo-bsp", "stm32f4xx-nucleo-144-bsp", "stm32f4discovery-bsp",
    "32f401cdiscovery-bsp", "32f411ediscovery-bsp", "32f412gdiscovery-bsp",
    "32f413hdiscovery-bsp", "32f429idiscovery-bsp", "32f469idiscovery-bsp",
    "stm324x9i-eval-bsp", "stm324xg-eval-bsp", "stm32446e-eval-bsp",
    "stm32469i-eval-bsp",
]:
    _REPO_TO_SERIES[_r] = "stm32cubef4"

# H5 sub-repos
for _r in [
    "stm32h5xx-hal-driver", "cmsis_device_h5",
    "stm32h5xx-nucleo-bsp", "stm32h573i-discovery-bsp", "stm32h5f5j-discovery-bsp",
]:
    _REPO_TO_SERIES[_r] = "stm32cubeh5"

# U5 sub-repos
for _r in [
    "stm32u5xx-hal-driver", "cmsis_device_u5",
    "b-u585i-iot02a-bsp", "stm32u575i-ev-bsp", "stm32u5x9j-dk-bsp",
    "stm32u5g9j-dk2-bsp", "stm32u5xx-nucleo-bsp",
]:
    _REPO_TO_SERIES[_r] = "stm32cubeu5"

# WL sub-repos
for _r in [
    "stm32wlxx-hal-driver", "cmsis_device_wl",
    "stm32wlxx-nucleo-bsp", "b-wl5m-subg1-bsp",
]:
    _REPO_TO_SERIES[_r] = "stm32cubewl"

# C0 sub-repos
for _r in [
    "stm32c0xx-hal-driver", "cmsis_device_c0",
    "stm32c0xx-nucleo-bsp",
]:
    _REPO_TO_SERIES[_r] = "stm32cubec0"

# F0 sub-repos
for _r in [
    "stm32f0xx-hal-driver", "cmsis_device_f0",
    "stm32f0xx-nucleo-bsp", "stm32f0discovery-bsp",
    "32f072bdiscovery-bsp", "32f0508discovery-bsp",
    "stm32091c-eval-bsp", "stm32072b-eval-bsp",
]:
    _REPO_TO_SERIES[_r] = "stm32cubef0"

# F1 sub-repos
for _r in [
    "stm32f1xx-hal-driver", "cmsis_device_f1",
    "stm32f1xx-nucleo-bsp", "stm32vldiscovery-bsp",
    "stm3210c-eval-bsp", "stm3210e-eval-bsp",
]:
    _REPO_TO_SERIES[_r] = "stm32cubef1"

# F2 sub-repos
for _r in [
    "stm32f2xx-hal-driver", "cmsis_device_f2",
    "stm322xg-eval-bsp",
]:
    _REPO_TO_SERIES[_r] = "stm32cubef2"

# F3 sub-repos
for _r in [
    "stm32f3xx-hal-driver", "cmsis_device_f3",
    "stm32f3xx-nucleo-bsp", "stm32f3xx-nucleo-144-bsp",
    "stm32f3xx-nucleo-32-bsp", "stm32f3discovery-bsp",
    "32f3348discovery-bsp", "stm32303c-eval-bsp", "stm32303e-eval-bsp",
    "stm32373c-eval-bsp",
]:
    _REPO_TO_SERIES[_r] = "stm32cubef3"

# F7 sub-repos
for _r in [
    "stm32f7xx-hal-driver", "cmsis_device_f7",
    "stm32f7xx-nucleo-144-bsp", "stm32746g-discovery-bsp",
    "stm32f769i-disco-bsp", "stm32756g-eval-bsp",
    "stm32f769i-eval-bsp",
]:
    _REPO_TO_SERIES[_r] = "stm32cubef7"

# H7RS sub-repos
for _r in [
    "stm32h7rsxx-hal-driver", "cmsis_device_h7rs",
    "stm32h7s78-dk-bsp",
]:
    _REPO_TO_SERIES[_r] = "stm32cubeh7rs"

# G0 sub-repos
for _r in [
    "stm32g0xx-hal-driver", "cmsis_device_g0",
    "stm32g0xx-nucleo-bsp", "stm32g0c1e-ev-bsp",
]:
    _REPO_TO_SERIES[_r] = "stm32cubeg0"


def repo_slug(repo: str) -> str:
    """Normalize a repo name to its lowercase slug used as a dict/path key."""
    return str(repo).strip().lower()


def _extract_repo_series_mapping(cfg: dict) -> dict[str, str]:
    """Derive a repo-slug -> series-slug mapping from one config's `repos` list.

    Each series config lists the main `stm32cube<series>` repo alongside its
    HAL/CMSIS/BSP sub-repos. The first `stm32cube*`-prefixed entry is taken as
    the series anchor; every other repo in the same list is mapped to it so
    sub-repos are exported under the series folder instead of standalone.
    """
    mapping: dict[str, str] = {}
    repos = cfg.get("repos")
    if not isinstance(repos, list) or not repos:
        return mapping

    series_repo = next((str(repo).strip() for repo in repos if str(repo).lower().startswith("stm32cube")), "")
    if not series_repo:
        return mapping
    series_slug = repo_slug(series_repo)

    for repo in repos:
        repo_slug_value = repo_slug(repo)
        if repo_slug_value and repo_slug_value != series_slug:
            mapping[repo_slug_value] = series_slug

    return mapping


def _load_config_repo_series_map() -> dict[str, str]:
    """Build repo -> parent series mapping from shared/config/config_*.json.

    The static lists above are kept for backward compatibility, but configs are
    the source of truth. This prevents newly added BSP sub-repos from being
    exported as standalone series folders.
    """
    config_dir = PROJECT_ROOT / "shared" / "config"
    mapping: dict[str, str] = {}

    # If an active series config is selected for this run, use it first so
    # shared repos (e.g., middleware/component repos) map to the current series.
    active_cfg_env = os.getenv("STM32CUBE_CONFIG")
    if active_cfg_env:
        active_cfg_path = Path(active_cfg_env)
        if not active_cfg_path.is_absolute():
            active_cfg_path = (PROJECT_ROOT / active_cfg_path).resolve()
        try:
            active_cfg = json.loads(active_cfg_path.read_text(encoding="utf-8-sig"))
            mapping.update(_extract_repo_series_mapping(active_cfg))
        except (OSError, json.JSONDecodeError):
            pass

    for cfg_file in sorted(config_dir.glob("config*.json")):
        if cfg_file.name == "config_all_series.json":
            continue
        try:
            cfg = json.loads(cfg_file.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            continue

        # Do not override active-series mapping with mappings from other series.
        for repo_slug_value, series_slug in _extract_repo_series_mapping(cfg).items():
            mapping.setdefault(repo_slug_value, series_slug)

    return mapping


_REPO_TO_SERIES.update(_load_config_repo_series_map())


def get_repo_series_root(repo: str) -> Path:
    """Return the by-series output root directory for a given repo.

    If the repo is a known sub-repo (HAL/CMSIS/BSP), its artifacts are nested
    under its parent series' `drivers/<sub-repo>/` folder so all delivery
    artifacts for one MCU series stay together. Otherwise the repo is assumed
    to be a main series repo and gets its own top-level folder.
    """
    slug = repo_slug(repo)
    parent_series = _REPO_TO_SERIES.get(slug)
    if parent_series:
        # Sub-repo goes under parent_series/drivers/<sub-repo>/
        return ST_READY_BY_SERIES_ROOT / parent_series / "drivers" / slug
    return ST_READY_BY_SERIES_ROOT / slug


def get_repo_artifact_dir(repo: str, artifact_dir: str) -> Path:
    """Return the directory for one artifact type (e.g. `issues_json`) of a repo."""
    return get_repo_series_root(repo) / artifact_dir


def get_repo_artifact_file(repo: str, artifact_dir: str, file_name: str) -> Path:
    """Return the full path to a specific artifact file for a repo."""
    return get_repo_artifact_dir(repo, artifact_dir) / file_name


def get_legacy_artifact_dir(artifact_dir: str) -> Path:
    """Return the flat (pre-by-series) directory for one artifact type.

    Kept so older consumers/scripts that still read from the flat
    `st_ready/<artifact_dir>/` layout keep working; export scripts write a
    mirror copy here in addition to the by-series path.
    """
    return ST_READY_ROOT / artifact_dir


def get_legacy_artifact_file(artifact_dir: str, file_name: str) -> Path:
    """Return the full path to an artifact file in the legacy flat layout."""
    return get_legacy_artifact_dir(artifact_dir) / file_name


def get_existing_repo_artifact_file(repo: str, artifact_dir: str, file_name: str) -> Path:
    """Resolve an artifact file, preferring the by-series path but falling
    back to the legacy flat path if that is the only one that exists.

    Used by downstream export scripts (e.g. resolver cases, diagnostic cards)
    that need to read an upstream artifact (like `st_ready_files_<repo>.json`)
    without knowing in advance which layout produced it.
    """
    repo_file = get_repo_artifact_file(repo, artifact_dir, file_name)
    if repo_file.exists():
        return repo_file

    legacy_file = get_legacy_artifact_file(artifact_dir, file_name)
    if legacy_file.exists():
        return legacy_file

    return repo_file
