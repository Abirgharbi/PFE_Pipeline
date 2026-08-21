"""
Upload all F4 diagnostic cards JSON to datasource #28122.

Series-specific batch uploader: appends every st_ready_diagnostic_cards_*.json file
for STM32CubeF4 (main repo plus per-driver sub-repos under by_series/stm32cubef4/drivers/*)
to existing KB #793 (ST GitHub Analyzer) datasource #28122
(STready_F4_Diagnostic_Datasource), one file per API call via Add_Data_Source_Files.py
(--operation add).

Required env vars: same as Add_Data_Source_Files.py (PERSONA_API_KEY /
ST_GITHUB_ANALYZER_API_KEY / ST_CHATGPT_API_KEY / ST_AI_BRIDGE_API_KEY / ST_API_KEY).

Required input files: datasets/07_delivery/st_ready/by_series/stm32cubef4/
diagnostic_cards_json/st_ready_diagnostic_cards_stm32cubef4.json (and
drivers/*/diagnostic_cards_json/*.json).

Usage:
    python pipeline_Automation/upload_f4_diagnostic_datasource.py --remote-user abir.gharbi@st.com [--verbose]
    python pipeline_Automation/upload_f4_diagnostic_datasource.py --remote-user abir.gharbi@st.com --dry-run
"""

import argparse
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BY_SERIES = PROJECT_ROOT / "datasets" / "07_delivery" / "st_ready" / "by_series"
ADD_SCRIPT = PROJECT_ROOT / "pipeline_Automation" / "Add_Data_Source_Files.py"

# Datasource target
KB_ID = 793
DATASOURCE_ID = 28122  # STready_F4_Diagnostic_Datasource

PROCESSOR_PARAMS = '{"label": "{{label}}", "externalURL": "{{externalURL}}", "rootTagPath": "diagnostic_cards"}'


def find_all_f4_diagnostic_json() -> list[Path]:
    """Collect all st_ready_diagnostic_cards_*.json for F4 (main + drivers)."""
    files: list[Path] = []

    # Main F4 diagnostic cards
    main = BY_SERIES / "stm32cubef4" / "diagnostic_cards_json" / "st_ready_diagnostic_cards_stm32cubef4.json"
    if main.exists():
        files.append(main)

    # Driver sub-repos diagnostic cards
    drivers_dir = BY_SERIES / "stm32cubef4" / "drivers"
    if drivers_dir.exists():
        for driver_dir in sorted(drivers_dir.iterdir()):
            if driver_dir.is_dir():
                dc_dir = driver_dir / "diagnostic_cards_json"
                if dc_dir.exists():
                    for f in sorted(dc_dir.glob("st_ready_diagnostic_cards_*.json")):
                        files.append(f)

    return files


def main():
    """CLI entry point: find F4 diagnostic cards JSON files, optionally list them
    (--dry-run), then upload each one via Add_Data_Source_Files.py --operation add.
    """
    parser = argparse.ArgumentParser(description="Upload F4 diagnostic cards to datasource #28122")
    parser.add_argument("--remote-user", required=True, help="Your ST email (e.g. first.last@st.com)")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="List files without uploading")
    args = parser.parse_args()

    files = find_all_f4_diagnostic_json()

    if not files:
        print("No F4 diagnostic cards JSON found!")
        sys.exit(1)

    print(f"Found {len(files)} F4 diagnostic cards JSON to upload to datasource #{DATASOURCE_ID}:")
    for f in files:
        print(f"  {f.relative_to(PROJECT_ROOT)}")

    if args.dry_run:
        print("\n[DRY-RUN] No upload performed.")
        return

    print(f"\nUploading to KB={KB_ID}, datasource={DATASOURCE_ID}...")

    for f in files:
        print(f"\n--- Uploading: {f.name} ---")
        cmd = [
            sys.executable, str(ADD_SCRIPT),
            "--kb", str(KB_ID),
            "--operation", "add",
            "--datasource-id", str(DATASOURCE_ID),
            "--remote-user", args.remote_user,
            "--processor", "JSON",
            "--processor-params", PROCESSOR_PARAMS,
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
