"""
Re-export ST-ready delivery outputs only, skipping ingestion/cleaning/enrichment.

Role in the automation layer:
    The full pipeline (ingestion -> ... -> delivery) can take a long time to run.
    When only the delivery/export logic changes (for example the ST-ready grouping
    or field mapping), re-running everything is wasteful. This script re-runs just
    the four delivery exporters (issues, files, resolver cases, diagnostic cards)
    for each repo of the requested series, reusing already-computed intermediate
    JSON artifacts (chunks/docs) as input.

Inputs:
    - ``shared/config/config_<series>.json`` (list of repos) for each requested series.
    - Existing intermediate pipeline artifacts consumed by the delivery exporters.

Outputs:
    - Refreshed ``datasets/07_delivery/st_ready/...`` JSON files (issues, files,
      resolver cases, diagnostic cards) and their ``summary_*.json`` counterparts.

Usage:
    python -m pipeline_Automation.reexport_delivery --series f4 h5 u5 wl
    python -m pipeline_Automation.reexport_delivery --series f4
"""

import argparse
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = PROJECT_ROOT / "shared" / "config"

SERIES_CONFIGS = {
    "h7": CONFIG_DIR / "config.json",
    "f4": CONFIG_DIR / "config_f4.json",
    "h5": CONFIG_DIR / "config_h5.json",
    "u5": CONFIG_DIR / "config_u5.json",
    "wl": CONFIG_DIR / "config_wl.json",
}


def reexport_series(series: str, continue_on_error: bool = False):
    """Re-run the four ST-ready delivery exporters for every repo of one series.

    Args:
        series: Series key (e.g. "f4", "h5") used to look up its config file.
        continue_on_error: If True, log and skip exporter failures instead of
            raising, so remaining repos/exporters still run.
    """
    cfg_path = SERIES_CONFIGS.get(series)
    if not cfg_path or not cfg_path.exists():
        print(f"[ERROR] Config not found for '{series}'")
        return

    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    repos = cfg["repos"]

    print(f"\n{'='*50}")
    print(f" RE-EXPORT DELIVERY: {series.upper()} ({len(repos)} repos)")
    print(f"{'='*50}")

    from pipeline.delivery.export_st_ready_issues import export_repo_json as export_issues
    from pipeline.delivery.export_st_ready_files import export_repo_json as export_files
    from pipeline.delivery.export_st_ready_resolver_cases import export_repo_json as export_resolver
    from pipeline.delivery.export_st_ready_diagnostic_cards import export_repo_json as export_diag

    for repo in repos:
        print(f"\n--- {repo} ---")

        # Issues
        try:
            total, exported, out = export_issues(repo=repo, include_invalid=False, comments_chars=1200)
            print(f"  [issues] {exported}/{total} -> {out}")
        except FileNotFoundError:
            print(f"  [issues] skipped (no input)")
        except Exception as e:
            print(f"  [issues] ERROR: {e}")
            if not continue_on_error:
                raise

        # Files
        try:
            total, exported, out = export_files(
                repo=repo, include_invalid=False, summary_max_chars=240, technical_max_chars=4000
            )
            print(f"  [files] {exported}/{total} -> {out}")
        except FileNotFoundError:
            print(f"  [files] skipped (no input)")
        except Exception as e:
            print(f"  [files] ERROR: {e}")
            if not continue_on_error:
                raise

        # Resolver cases
        try:
            total, exported, out = export_resolver(repo=repo, include_reference_only=False)
            print(f"  [resolver] {exported}/{total} -> {out}")
        except FileNotFoundError:
            print(f"  [resolver] skipped (no input)")
        except Exception as e:
            print(f"  [resolver] ERROR: {e}")
            if not continue_on_error:
                raise

        # Diagnostic cards
        try:
            total, exported, out = export_diag(repo=repo, include_all_issues=False)
            print(f"  [diagnostic] {exported}/{total} -> {out}")
        except FileNotFoundError:
            print(f"  [diagnostic] skipped (no input)")
        except Exception as e:
            print(f"  [diagnostic] ERROR: {e}")
            if not continue_on_error:
                raise


def main():
    """CLI entry point: parse arguments and re-export delivery outputs for each requested series."""
    parser = argparse.ArgumentParser(description="Re-export ST-ready delivery for series.")
    parser.add_argument(
        "--series",
        nargs="+",
        choices=["f4", "h5", "u5", "wl", "h7"],
        required=True,
    )
    parser.add_argument("--continue-on-error", action="store_true")
    args = parser.parse_args()

    for series in args.series:
        reexport_series(series, continue_on_error=args.continue_on_error)

    print("\nDone.")


if __name__ == "__main__":
    main()
