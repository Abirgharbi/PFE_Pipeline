"""
Orchestrate the STM32Cube preprocessing pipeline across several STM32 series.

Role in the automation layer:
    Each STM32 series (F4, H5, U5, WL, C0, H7) has its own
    ``shared/config/config_<series>.json`` describing the HAL driver + CMSIS + BSP
    sub-repos to process for that series. The core pipeline entry point
    (``pipeline.run_full_workflow``) only reads a single main config file
    (``shared/config/config.json``), so this script temporarily swaps that main
    config for each requested series' config, runs the full workflow
    (ingestion -> cleaning -> enrichment -> similarity -> chunking -> optional
    ST-ready delivery export), then restores the original (H7 default) config,
    even if the run fails.

Inputs:
    - ``shared/config/config_<series>.json`` for each requested series.
    - CLI flags selecting which pipeline stages to skip/run.

Outputs:
    - Standard pipeline artifacts under ``datasets/`` for each processed series.
    - A console summary (OK/FAILED) per series printed at the end of the run.

Usage:
    python -m pipeline_Automation.run_all_series --series f4 h5 u5 wl --continue-on-error --export-st-ready
    python -m pipeline_Automation.run_all_series --series h5 --skip-ingestion --export-st-ready
"""

import argparse
import json
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = PROJECT_ROOT / "shared" / "config"
MAIN_CONFIG = CONFIG_DIR / "config.json"

SERIES_CONFIGS = {
    "h7": CONFIG_DIR / "config.json",  # H7 is the default
    "f4": CONFIG_DIR / "config_f4.json",
    "h5": CONFIG_DIR / "config_h5.json",
    "u5": CONFIG_DIR / "config_u5.json",
    "wl": CONFIG_DIR / "config_wl.json",
    "c0": CONFIG_DIR / "config_c0.json",
}


def run_pipeline_for_series(
    series: str,
    skip_ingestion: bool = False,
    skip_chunking: bool = False,
    continue_on_error: bool = False,
    export_st_ready: bool = False,
) -> bool:
    """Swap config.json with series-specific config, run pipeline, restore."""
    series_config = SERIES_CONFIGS.get(series)
    if not series_config or not series_config.exists():
        print(f"[ERROR] Config not found for series '{series}': {series_config}")
        return False

    # Read original config to restore later
    original_config = MAIN_CONFIG.read_text(encoding="utf-8")

    # Read series config
    series_config_text = series_config.read_text(encoding="utf-8")
    series_cfg = json.loads(series_config_text)

    print(f"\n{'='*60}")
    print(f" SERIES: {series.upper()} — {len(series_cfg['repos'])} repos")
    print(f"{'='*60}")
    for repo in series_cfg["repos"]:
        print(f"  - {repo}")
    print()

    try:
        # Write series config as main config
        if series != "h7":
            MAIN_CONFIG.write_text(series_config_text, encoding="utf-8")

        # Import and run workflow
        from pipeline.run_full_workflow import main as run_workflow

        run_workflow(
            skip_ingestion=skip_ingestion,
            skip_chunking=skip_chunking,
            continue_on_error=continue_on_error,
            export_st_ready=export_st_ready,
        )
        return True

    except Exception as exc:
        print(f"[ERROR] Pipeline failed for series {series.upper()}: {exc}")
        if not continue_on_error:
            raise
        return False

    finally:
        # Always restore original config
        if series != "h7":
            MAIN_CONFIG.write_text(original_config, encoding="utf-8")
            print(f"[RESTORE] config.json restored to H7 default.")


def main():
    """CLI entry point: parse arguments and run the pipeline sequentially for each requested series."""
    parser = argparse.ArgumentParser(description="Run pipeline for multiple STM32 series.")
    parser.add_argument(
        "--series",
        nargs="+",
        choices=list(SERIES_CONFIGS.keys()),
        required=True,
        help="Series to process (e.g. --series f4 h5 u5 wl c0)",
    )
    parser.add_argument("--skip-ingestion", action="store_true")
    parser.add_argument("--skip-chunking", action="store_true", help="Skip local chunking (platform handles it).")
    parser.add_argument("--continue-on-error", action="store_true")
    parser.add_argument("--export-st-ready", action="store_true")
    args = parser.parse_args()

    results = {}
    for series in args.series:
        success = run_pipeline_for_series(
            series=series,
            skip_ingestion=args.skip_ingestion,
            skip_chunking=args.skip_chunking,
            continue_on_error=args.continue_on_error,
            export_st_ready=args.export_st_ready,
        )
        results[series] = success

    print(f"\n{'='*60}")
    print(" SUMMARY")
    print(f"{'='*60}")
    for series, ok in results.items():
        status = "OK" if ok else "FAILED"
        print(f"  {series.upper()}: {status}")


if __name__ == "__main__":
    main()
