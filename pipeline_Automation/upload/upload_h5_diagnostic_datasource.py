"""
Upload all H5 diagnostic cards JSON (main repo + drivers) to datasource #28165.

Series-specific batch uploader: appends every st_ready_diagnostic_cards_*.json file
for STM32CubeH5 (main repo plus per-driver sub-repos under by_series/stm32cubeh5/drivers/*)
to existing KB #793 (ST GitHub Analyzer) datasource #28165
(STready_H5_Diagnostic_Datasource), splitting payloads at 1000 docs/part, via
Add_Data_Source_Files.py (--operation add --json-split-size 1000).

NOTE: --remote-user is hardcoded below ("abir.gharbi@st.com"); update it if you run
this script under a different ST account.

Required env vars: same as Add_Data_Source_Files.py (PERSONA_API_KEY /
ST_GITHUB_ANALYZER_API_KEY / ST_CHATGPT_API_KEY / ST_AI_BRIDGE_API_KEY / ST_API_KEY).

Required input files: datasets/07_delivery/st_ready/by_series/stm32cubeh5/
diagnostic_cards_json/st_ready_diagnostic_cards_stm32cubeh5.json (and
drivers/*/diagnostic_cards_json/*.json).

Usage:
    python pipeline_Automation/upload_h5_diagnostic_datasource.py [--dry-run] [--verbose]
"""

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BY_SERIES = PROJECT_ROOT / "datasets" / "07_delivery" / "st_ready" / "by_series"
ADD_SCRIPT = PROJECT_ROOT / "pipeline_Automation" / "Add_Data_Source_Files.py"

KB_ID = 793
DATASOURCE_ID = 28165  # STready_H5_Diagnostic_Datasource

PROCESSOR_PARAMS = '{"label": "{{label}}", "externalURL": "{{externalURL}}", "rootTagPath": "diagnostic_cards"}'


def find_all_h5_diagnostic_json() -> list[Path]:
    """Collect all st_ready_diagnostic_cards_*.json for H5 (main + drivers)."""
    files: list[Path] = []
    main = BY_SERIES / "stm32cubeh5" / "diagnostic_cards_json" / "st_ready_diagnostic_cards_stm32cubeh5.json"
    if main.exists():
        files.append(main)
    drivers_dir = BY_SERIES / "stm32cubeh5" / "drivers"
    if drivers_dir.exists():
        for driver_dir in sorted(drivers_dir.iterdir()):
            if driver_dir.is_dir():
                fdir = driver_dir / "diagnostic_cards_json"
                if fdir.exists():
                    for f in sorted(fdir.glob("st_ready_diagnostic_cards_*.json")):
                        files.append(f)
    return files


def main():
    """CLI entry point: find H5 diagnostic cards JSON files, optionally list them
    (--dry-run), then upload each one via Add_Data_Source_Files.py --operation add.
    """
    import argparse
    parser = argparse.ArgumentParser(description="Upload H5 diagnostic cards to datasource #28165")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    files = find_all_h5_diagnostic_json()
    if not files:
        print("No H5 diagnostic cards JSON found!")
        sys.exit(1)

    print(f"Found {len(files)} H5 diagnostic cards JSON to upload to datasource #{DATASOURCE_ID}:")
    for f in files:
        print(f"  {f.relative_to(PROJECT_ROOT)}")

    if args.dry_run:
        print("\n[DRY-RUN] No upload performed.")
        return

    for f in files:
        print(f"\n--- Uploading: {f.name} ---")
        cmd = [
            sys.executable, str(ADD_SCRIPT),
            "--kb", str(KB_ID),
            "--operation", "add",
            "--datasource-id", str(DATASOURCE_ID),
            "--remote-user", "abir.gharbi@st.com",
            "--processor", "JSON",
            "--processor-params", PROCESSOR_PARAMS,
            "--json-split-size", "1000",
            "--files", str(f),
        ]
        if args.verbose:
            cmd.append("--verbose")
        result = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
        if result.returncode != 0:
            print(f"[WARN] Upload failed for {f.name} (exit code {result.returncode})")
        else:
            print(f"[OK] {f.name}")

    print("\nDone.")


if __name__ == "__main__":
    main()
