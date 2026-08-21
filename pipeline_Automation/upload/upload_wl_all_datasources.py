"""
Create datasources and upload all WL data to KB #793.

Creates 4 datasources:
  - STready_WL_Issues_Datasource
  - STready_WL_Files_Datasource_JSON_V2
  - STready_WL_resolver_cases_Datasource
  - STready_WL_Diagnostic_Datasource

All-in-one series bootstrap script for STM32CubeWL: for each of the four ST-ready
document kinds (issues, files, resolver_cases, diagnostic_cards), creates a new KB
#793 (ST GitHub Analyzer) datasource (--operation new) using every matching JSON
file found under by_series/stm32cubewl/ (main repo + drivers/*), or, when re-run
with --upload-only and explicit --*-id flags, appends files to already-created
datasources (--operation add). Alfred-enriched and summary_*.json files are skipped.

NOTE: --remote-user is hardcoded below ("abir.gharbi@st.com"); update it if you run
this script under a different ST account.

Required env vars: same as Add_Data_Source_Files.py (PERSONA_API_KEY /
ST_GITHUB_ANALYZER_API_KEY / ST_CHATGPT_API_KEY / ST_AI_BRIDGE_API_KEY / ST_API_KEY).

Required input files: datasets/07_delivery/st_ready/by_series/stm32cubewl/
{issues,files,resolver_cases,diagnostic_cards}_json/*.json (and drivers/*/... equivalents).

Usage:
    python pipeline_Automation/upload_wl_all_datasources.py --dry-run
    python pipeline_Automation/upload_wl_all_datasources.py --verbose
    python pipeline_Automation/upload_wl_all_datasources.py --create-only   # create datasources without uploading
"""

import argparse
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BY_SERIES = PROJECT_ROOT / "datasets" / "07_delivery" / "st_ready" / "by_series"
ADD_SCRIPT = PROJECT_ROOT / "pipeline_Automation" / "Add_Data_Source_Files.py"

KB_ID = 793
SERIES = "stm32cubewl"

DATASOURCES = {
    "issues": {
        "name": "STready_WL_Issues_Datasource",
        "processor_params": '{"label": "{{repo}} issue #{{issue_number}} - {{issue_title}}", "externalURL": "https://github.com/STMicroelectronics/{{repo}}/issues/{{issue_number}}", "rootTagPath": "issues"}',
        "subdir": "issues_json",
        "glob": "st_ready_issues_*.json",
    },
    "files": {
        "name": "STready_WL_Files_Datasource_JSON_V2",
        "processor_params": '{"label": "{{repo}} {{file_type}} - {{path}}", "externalURL": "https://github.com/STMicroelectronics/{{repo}}/{{root_dir}}/{{root_ref}}/{{path_url}}", "rootTagPath": "files"}',
        "subdir": "files_json",
        "glob": "st_ready_files_*.json",
    },
    "resolver": {
        "name": "STready_WL_resolver_cases_Datasource",
        "processor_params": '{"label": "{{label}}", "externalURL": "https://github.com/STMicroelectronics/{{repo}}/issues/{{issue_number}}", "rootTagPath": "resolver_cases"}',
        "subdir": "resolver_cases_json",
        "glob": "st_ready_resolver_cases_*.json",
    },
    "diagnostic": {
        "name": "STready_WL_Diagnostic_Datasource",
        "processor_params": '{"label": "{{label}}", "externalURL": "{{externalURL}}", "rootTagPath": "diagnostic_cards"}',
        "subdir": "diagnostic_cards_json",
        "glob": "st_ready_diagnostic_cards_*.json",
    },
}


def find_json_files(subdir: str, glob_pattern: str) -> list[Path]:
    """Collect JSON files matching glob_pattern under the WL main repo and driver
    sub-repos for the given document-kind subdir (e.g. 'issues_json'), skipping
    Alfred-enriched and summary_*.json files.
    """
    files: list[Path] = []
    series_dir = BY_SERIES / SERIES

    # Main repo
    main_dir = series_dir / subdir
    if main_dir.exists():
        for f in sorted(main_dir.glob(glob_pattern)):
            if "alfred" in f.name or "summary" in f.name:
                continue
            files.append(f)

    # Drivers
    drivers_dir = series_dir / "drivers"
    if drivers_dir.exists():
        for driver_dir in sorted(drivers_dir.iterdir()):
            if driver_dir.is_dir():
                fdir = driver_dir / subdir
                if fdir.exists():
                    for f in sorted(fdir.glob(glob_pattern)):
                        if "alfred" in f.name or "summary" in f.name:
                            continue
                        files.append(f)
    return files


def create_datasource(ds_name: str, processor_params: str, files: list[Path], verbose: bool) -> int:
    """Create a new datasource (with files) and return exit code."""
    print(f"\n{'='*60}")
    print(f"Creating datasource: {ds_name}")
    print(f"{'='*60}")
    cmd = [
        sys.executable, str(ADD_SCRIPT),
        "--kb", str(KB_ID),
        "--operation", "new",
        "--datasource-name", ds_name,
        "--remote-user", "abir.gharbi@st.com",
        "--processor", "JSON",
        "--processor-params", processor_params,
        "--json-split-size", "1000",
        "--empty-json-policy", "skip",
    ]
    if files:
        cmd.append("--files")
        cmd.extend(str(f) for f in files)
    if verbose:
        cmd.append("--verbose")
    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
    return result.returncode


def upload_files(datasource_id: int, processor_params: str, files: list[Path], verbose: bool):
    """Upload files to an existing datasource."""
    for f in files:
        print(f"\n--- Uploading: {f.name} ---")
        cmd = [
            sys.executable, str(ADD_SCRIPT),
            "--kb", str(KB_ID),
            "--operation", "add",
            "--datasource-id", str(datasource_id),
            "--remote-user", "abir.gharbi@st.com",
            "--processor", "JSON",
            "--processor-params", processor_params,
            "--json-split-size", "1000",
            "--files", str(f),
        ]
        if verbose:
            cmd.append("--verbose")
        result = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
        if result.returncode != 0:
            print(f"[WARN] Upload failed for {f.name} (exit code {result.returncode})")
        else:
            print(f"[OK] {f.name}")


def main():
    """CLI entry point: list matching files per document kind, then either create
    the four WL datasources (default / --create-only) or append files to existing
    ones (--upload-only with --issues-id/--files-id/--resolver-id/--diagnostic-id).
    """
    parser = argparse.ArgumentParser(description="Create WL datasources and upload data")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="List files without creating/uploading")
    parser.add_argument("--create-only", action="store_true", help="Only create datasources, don't upload files")
    parser.add_argument("--upload-only", action="store_true", help="Skip creation, upload to existing datasource IDs")
    parser.add_argument("--issues-id", type=int, help="Existing datasource ID for issues")
    parser.add_argument("--files-id", type=int, help="Existing datasource ID for files")
    parser.add_argument("--resolver-id", type=int, help="Existing datasource ID for resolver cases")
    parser.add_argument("--diagnostic-id", type=int, help="Existing datasource ID for diagnostic cards")
    args = parser.parse_args()

    print(f"Series: WL ({SERIES})")
    print(f"KB: {KB_ID}")
    print()

    for key, ds in DATASOURCES.items():
        files = find_json_files(ds["subdir"], ds["glob"])
        print(f"[{ds['name']}] {len(files)} files:")
        for f in files:
            print(f"    {f.relative_to(PROJECT_ROOT)}")

    if args.dry_run:
        print("\n[DRY-RUN] No action performed.")
        return

    # Step 1: Create datasources (pass main file to avoid empty-array error)
    if not args.upload_only:
        print("\n" + "=" * 60)
        print("STEP 1: Creating datasources")
        print("=" * 60)
        for key, ds in DATASOURCES.items():
            all_files = find_json_files(ds["subdir"], ds["glob"])
            rc = create_datasource(ds["name"], ds["processor_params"], all_files, args.verbose)
            if rc != 0:
                print(f"[WARN] Failed to create {ds['name']} (exit code {rc})")
            else:
                print(f"[OK] Created {ds['name']}")

        if args.create_only:
            print("\n[CREATE-ONLY] Datasources created. Note the IDs from the responses above,")
            print("then re-run with --upload-only --issues-id X --files-id Y --resolver-id Z --diagnostic-id W")
            return

    # Step 2: Upload files (requires datasource IDs)
    if args.upload_only:
        ds_ids = {
            "issues": args.issues_id,
            "files": args.files_id,
            "resolver": args.resolver_id,
            "diagnostic": args.diagnostic_id,
        }
        missing = [k for k, v in ds_ids.items() if v is None]
        if missing:
            print(f"ERROR: Missing datasource IDs for: {', '.join(missing)}")
            print("Provide them with --issues-id, --files-id, --resolver-id, --diagnostic-id")
            sys.exit(1)

        print("\n" + "=" * 60)
        print("STEP 2: Uploading files")
        print("=" * 60)
        for key, ds in DATASOURCES.items():
            files = find_json_files(ds["subdir"], ds["glob"])
            if files:
                print(f"\n>>> {ds['name']} (datasource #{ds_ids[key]})")
                upload_files(ds_ids[key], ds["processor_params"], files, args.verbose)

        print("\nDone.")
    else:
        print("\nDatasources created. Now note the IDs from the API responses above,")
        print("then re-run with:")
        print(f"  python pipeline_Automation/upload_wl_all_datasources.py --upload-only "
              f"--issues-id <ID> --files-id <ID> --resolver-id <ID> --diagnostic-id <ID> --verbose")


if __name__ == "__main__":
    main()
