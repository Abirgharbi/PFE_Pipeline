"""
Upload Alfred-enriched issues JSON to existing issues datasources.

These files contain image text descriptions from Alfred vision AI,
providing richer context for KB retrieval.

Multi-series batch uploader: appends the Alfred-enriched issues JSON (produced by
pipeline_Automation/alfred/enrich_json_images_with_alfred.py, where
[IMAGE ATTACHED] markers are replaced with [IMAGE DESCRIPTION] text) for every
STM32Cube series to KB #793 (ST GitHub Analyzer), reusing the existing per-series
issues datasource IDs listed in SERIES_DATASOURCES below. For each series, tries
three candidate filenames (with-images+alfred, alfred-only, with-images-only) and
skips the series if none is found.

NOTE: --remote-user is hardcoded below ("abir.gharbi@st.com"); update it if you run
this script under a different ST account.

Required env vars: same as Add_Data_Source_Files.py (PERSONA_API_KEY /
ST_GITHUB_ANALYZER_API_KEY / ST_CHATGPT_API_KEY / ST_AI_BRIDGE_API_KEY / ST_API_KEY).

Required input files: datasets/07_delivery/st_ready/by_series/<series>/issues_json/
st_ready_issues_with_images_<series>_with_alfred_image_text.json (or one of the
fallback filenames tried in main()).

Usage:
    python pipeline_Automation/upload_alfred_issues_all_series.py --dry-run
    python pipeline_Automation/upload_alfred_issues_all_series.py --verbose
"""

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BY_SERIES = PROJECT_ROOT / "datasets" / "07_delivery" / "st_ready" / "by_series"
ADD_SCRIPT = PROJECT_ROOT / "pipeline_Automation" / "upload" / "Add_Data_Source_Files.py"

KB_ID = 793

PROCESSOR_PARAMS = '{"label": "{{repo}} issue #{{issue_number}} - {{issue_title}}", "externalURL": "https://github.com/STMicroelectronics/{{repo}}/issues/{{issue_number}}", "rootTagPath": "issues"}'

# Datasource IDs for issues per series
SERIES_DATASOURCES = {
    "stm32cubec0": 29193,
    "stm32cubef0": 29195,
    "stm32cubef1": 29197,
    "stm32cubef2": 29199,
    "stm32cubef3": 29282,
    "stm32cubef4": 28099,
    "stm32cubef7": 29276,
    "stm32cubeg0": 29273,
    "stm32cubeh5": 28158,
    "stm32cubeh7": 24406,
    "stm32cubeh7rs": 29270,
    "stm32cubeu5": 28167,
    "stm32cubewl": 28171,
}


def main():
    """CLI entry point: for each configured series, locate the Alfred-enriched issues
    JSON (trying multiple known filenames) and upload/append it to the series'
    existing issues datasource via Add_Data_Source_Files.py --operation add.
    """
    import argparse
    parser = argparse.ArgumentParser(description="Upload Alfred issues to existing datasources")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--f4-id", type=int, help="F4 issues datasource ID (if available)")
    args = parser.parse_args()

    if args.f4_id:
        SERIES_DATASOURCES["stm32cubef4"] = args.f4_id

    print(f"Uploading Alfred-enriched issues to KB #{KB_ID}")
    print()

    for series, ds_id in SERIES_DATASOURCES.items():
        # Try both naming conventions
        alfred_file = BY_SERIES / series / "issues_json" / f"st_ready_issues_with_images_{series}_with_alfred_image_text.json"
        if not alfred_file.exists():
            alfred_file = BY_SERIES / series / "issues_json" / f"st_ready_issues_{series}_with_alfred_image_text.json"
        if not alfred_file.exists():
            alfred_file = BY_SERIES / series / "issues_json" / f"st_ready_issues_with_images_{series}.json"

        if not alfred_file.exists():
            print(f"[SKIP] {series}: Alfred file not found")
            continue

        if ds_id is None:
            print(f"[SKIP] {series}: No datasource ID configured (use --f4-id for F4)")
            continue

        size_mb = alfred_file.stat().st_size / (1024 * 1024)
        print(f"[{series}] {alfred_file.name} ({size_mb:.1f} MB) -> datasource #{ds_id}")

        if args.dry_run:
            continue

        print(f"  Uploading...")
        cmd = [
            sys.executable, str(ADD_SCRIPT),
            "--kb", str(KB_ID),
            "--operation", "add",
            "--datasource-id", str(ds_id),
            "--remote-user", "abir.gharbi@st.com",
            "--processor", "JSON",
            "--processor-params", PROCESSOR_PARAMS,
            "--json-split-size", "1000",
            "--empty-json-policy", "skip",
            "--files", str(alfred_file),
        ]
        if args.verbose:
            cmd.append("--verbose")

        result = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
        if result.returncode != 0:
            print(f"  [WARN] Upload failed (exit code {result.returncode})")
        else:
            print(f"  [OK] Uploaded")

    print("\nDone.")


if __name__ == "__main__":
    main()
