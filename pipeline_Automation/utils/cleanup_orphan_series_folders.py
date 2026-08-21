"""
Remove orphan sub-repo folders from ``by_series/`` that should live under their
parent series' ``drivers/`` subfolder instead.

Role in the automation layer:
    Earlier delivery layouts created one top-level folder per sub-repo (HAL driver,
    CMSIS, BSP) directly under ``by_series/``. The current layout nests those
    sub-repos under their parent series folder (e.g. ``drivers/`` inside
    ``stm32cubef4/``). This maintenance script detects and deletes any leftover
    top-level folder that is not one of the known valid series folders, cleaning up
    stale structure left behind by older pipeline runs. It should be run after
    ``reexport_delivery.py`` when the delivery grouping logic has changed.

Inputs:
    - ``datasets/07_delivery/st_ready/by_series/`` directory tree (read/deleted).

Outputs:
    - Orphan folders removed in place; console log of removed/remaining folders.

Usage:
    python -m pipeline_Automation.utils.cleanup_orphan_series_folders
"""

import os
import shutil
import stat
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BY_SERIES = PROJECT_ROOT / "datasets" / "07_delivery" / "st_ready" / "by_series"

# Valid top-level series folders
VALID_SERIES = {"stm32cubef4", "stm32cubeh5", "stm32cubeh7", "stm32cubeu5", "stm32cubewl"}


def force_remove_readonly(func, path, exc_info):
    """Handle read-only files on Windows (OneDrive / git)."""
    os.chmod(path, stat.S_IWRITE)
    func(path)


def main():
    """Scan ``by_series/`` and delete any top-level folder not in ``VALID_SERIES``."""
    if not BY_SERIES.exists():
        print("by_series/ not found")
        return

    removed = []
    for entry in sorted(BY_SERIES.iterdir()):
        # Only top-level directories matter here; anything not a recognized series
        # name is considered an orphan left over from an older delivery layout.
        if entry.is_dir() and entry.name not in VALID_SERIES:
            print(f"  Removing: {entry.name}/")
            shutil.rmtree(entry, onexc=force_remove_readonly)
            removed.append(entry.name)

    if removed:
        print(f"\nRemoved {len(removed)} orphan folders.")
    else:
        print("No orphan folders found.")

    print("\nRemaining:")
    for entry in sorted(BY_SERIES.iterdir()):
        if entry.is_dir():
            print(f"  {entry.name}/")


if __name__ == "__main__":
    main()
