"""
Upload all F4 files JSON (main repo + drivers) to datasource #28103.

Series-specific batch uploader: appends every st_ready_files_*.json file for
STM32CubeF4 (main repo plus per-driver sub-repos under by_series/stm32cubef4/drivers/*)
to existing KB #793 (ST GitHub Analyzer) datasource #28103
(STready_F4_Files_Datasource_JSON_V2), splitting each payload into parts of at most
1000 documents via Add_Data_Source_Files.py (--operation add --json-split-size 1000).

Required env vars: same as Add_Data_Source_Files.py (PERSONA_API_KEY /
ST_GITHUB_ANALYZER_API_KEY / ST_CHATGPT_API_KEY / ST_AI_BRIDGE_API_KEY / ST_API_KEY).

Required input files: datasets/07_delivery/st_ready/by_series/stm32cubef4/
files_json/st_ready_files_stm32cubef4.json (and drivers/*/files_json/*.json).

Usage:
    python pipeline_Automation/upload_f4_files_datasource.py --remote-user prenom.nom@st.com [--verbose]
"""

import argparse
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BY_SERIES = PROJECT_ROOT / "datasets" / "07_delivery" / "st_ready" / "by_series"
ADD_SCRIPT = PROJECT_ROOT / "pipeline_Automation" / "Add_Data_Source_Files.py"

# Datasource target
KB_ID = 793  # ST GitHub Analyzer persona KB
DATASOURCE_ID = 28103  # STready_F4_Files_Datasource_JSON_V2

PROCESSOR_PARAMS = '{"label": "{{repo}} {{file_type}} - {{path}}", "externalURL": "https://github.com/STMicroelectronics/{{repo}}/{{root_dir}}/{{root_ref}}/{{path_url}}", "rootTagPath": "files"}'


def find_all_f4_files_json() -> list[Path]:
    """Collect all st_ready_files_*.json for F4 (main + drivers)."""
    files: list[Path] = []

    # Main F4 files
    main = BY_SERIES / "stm32cubef4" / "files_json" / "st_ready_files_stm32cubef4.json"
    if main.exists():
        files.append(main)

    # Driver sub-repos files
    drivers_dir = BY_SERIES / "stm32cubef4" / "drivers"
    if drivers_dir.exists():
        for driver_dir in sorted(drivers_dir.iterdir()):
            if driver_dir.is_dir():
                files_json_dir = driver_dir / "files_json"
                if files_json_dir.exists():
                    for f in sorted(files_json_dir.glob("st_ready_files_*.json")):
                        files.append(f)

    return files


def main():
    """CLI entry point: find F4 files JSON files, optionally list them (--dry-run),
    then upload each one via Add_Data_Source_Files.py --operation add.
    """
    parser = argparse.ArgumentParser(description="Upload F4 files to datasource #28103")
    parser.add_argument("--remote-user", required=True, help="Your ST email (e.g. first.last@st.com)")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="List files without uploading")
    args = parser.parse_args()

    files = find_all_f4_files_json()

    if not files:
        print("No F4 files JSON found!")
        sys.exit(1)

    print(f"Found {len(files)} F4 files JSON to upload to datasource #{DATASOURCE_ID}:")
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
