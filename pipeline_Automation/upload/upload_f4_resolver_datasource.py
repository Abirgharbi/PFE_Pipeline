"""
Upload all F4 resolver cases JSON to datasource #28118.

Series-specific batch uploader: appends every st_ready_resolver_cases_*.json file
for STM32CubeF4 (main repo plus per-driver sub-repos under by_series/stm32cubef4/drivers/*)
to existing KB #793 (ST GitHub Analyzer) datasource #28118
(STready_F4_resolver_cases_Datasource) via Add_Data_Source_Files.py
(--operation add).

Required env vars: same as Add_Data_Source_Files.py (PERSONA_API_KEY /
ST_GITHUB_ANALYZER_API_KEY / ST_CHATGPT_API_KEY / ST_AI_BRIDGE_API_KEY / ST_API_KEY).

Required input files: datasets/07_delivery/st_ready/by_series/stm32cubef4/
resolver_cases_json/st_ready_resolver_cases_stm32cubef4.json (and
drivers/*/resolver_cases_json/*.json).

Usage:
    python pipeline_Automation/upload_f4_resolver_datasource.py --remote-user abir.gharbi@st.com [--verbose]
    python pipeline_Automation/upload_f4_resolver_datasource.py --remote-user abir.gharbi@st.com --dry-run
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
DATASOURCE_ID = 28118  # STready_F4_resolver_cases_Datasource

PROCESSOR_PARAMS = '{"label": "{{label}}", "externalURL": "https://github.com/STMicroelectronics/{{repo}}/issues/{{issue_number}}", "rootTagPath": "resolver_cases"}'


def find_all_f4_resolver_json() -> list[Path]:
    """Collect all st_ready_resolver_cases_*.json for F4 (main + drivers)."""
    files: list[Path] = []

    # Main F4 resolver cases
    main = BY_SERIES / "stm32cubef4" / "resolver_cases_json" / "st_ready_resolver_cases_stm32cubef4.json"
    if main.exists():
        files.append(main)

    # Driver sub-repos resolver cases
    drivers_dir = BY_SERIES / "stm32cubef4" / "drivers"
    if drivers_dir.exists():
        for driver_dir in sorted(drivers_dir.iterdir()):
            if driver_dir.is_dir():
                rc_dir = driver_dir / "resolver_cases_json"
                if rc_dir.exists():
                    for f in sorted(rc_dir.glob("st_ready_resolver_cases_*.json")):
                        files.append(f)

    return files


def main():
    """CLI entry point: find F4 resolver cases JSON files, optionally list them
    (--dry-run), then upload each one via Add_Data_Source_Files.py --operation add.
    """
    parser = argparse.ArgumentParser(description="Upload F4 resolver cases to datasource #28118")
    parser.add_argument("--remote-user", required=True, help="Your ST email (e.g. first.last@st.com)")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="List files without uploading")
    args = parser.parse_args()

    files = find_all_f4_resolver_json()

    if not files:
        print("No F4 resolver cases JSON found!")
        sys.exit(1)

    print(f"Found {len(files)} F4 resolver cases JSON to upload to datasource #{DATASOURCE_ID}:")
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
