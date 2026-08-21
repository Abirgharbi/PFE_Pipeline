"""
Upload PDF-enriched files to KB #793 for all 13 series.

Multi-series batch uploader: for each STM32Cube series listed in
SERIES_FILES_DATASOURCES, finds the best available files JSON (preferring the
v3 / PDF-enriched variant produced by the PDF figure/enrichment pipeline over the
base files export) and appends it to that series' existing KB #793
(ST GitHub Analyzer) files datasource, splitting payloads at
--json-split-size (default 200) docs/part.

NOTE: --remote-user is hardcoded below ("abir.gharbi@st.com"); update it if you run
this script under a different ST account.

Required env vars: same as Add_Data_Source_Files.py (PERSONA_API_KEY /
ST_GITHUB_ANALYZER_API_KEY / ST_CHATGPT_API_KEY / ST_AI_BRIDGE_API_KEY / ST_API_KEY).

Required input files: datasets/07_delivery/st_ready/by_series/<series>/files_json/
st_ready_files_<series>_v3.json (or _pdf_enriched.json, or the base st_ready_files_<series>.json).

Usage:
    python pipeline_Automation/upload/upload_pdf_enriched_files_all_series.py --dry-run
    python pipeline_Automation/upload/upload_pdf_enriched_files_all_series.py
    python pipeline_Automation/upload/upload_pdf_enriched_files_all_series.py --only-series stm32cubef0
"""

import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BY_SERIES = PROJECT_ROOT / "datasets" / "07_delivery" / "st_ready" / "by_series"
ADD_SCRIPT = PROJECT_ROOT / "pipeline_Automation" / "upload" / "Add_Data_Source_Files.py"

KB_ID = 793

# Files datasource IDs for all 13 series
SERIES_FILES_DATASOURCES = {
    "stm32cubec0": 29192,
    "stm32cubef0": 29196,
    "stm32cubef1": 29198,
    "stm32cubef2": 29200,
    "stm32cubef3": 29283,
    "stm32cubef4": 29042,   # V3
    "stm32cubef7": 29277,
    "stm32cubeg0": 29274,
    "stm32cubeh5": 29043,   # V3
    "stm32cubeh7": 29041,   # V3
    "stm32cubeh7rs": 29271,
    "stm32cubeu5": 29044,   # V3
    "stm32cubewl": 29045,   # V3
}

# Processor params for files, base64-encoded (not secret data) to safely pass the
# '{{...}}' Mustache-style template placeholders through PowerShell without escaping.
PROCESSOR_PARAMS = 'eyJsYWJlbCI6ICJ7e3JlcG99fSB7e2ZpbGVfdHlwZX19IC0ge3twYXRofX0iLCAiZXh0ZXJuYWxVUkwiOiAiaHR0cHM6Ly9naXRodWIuY29tL1NUTWljcm9lbGVjdHJvbmljcy97e3JlcG99fS97e3Jvb3RfZGlyfX0ve3tyb290X3JlZn19L3t7cGF0aF91cmx9fSIsICJyb290VGFnUGF0aCI6ICJmaWxlcyJ9'

DEFAULT_JSON_SPLIT_SIZE = 200
UPLOAD_DELAY_SEC = 5


def find_files_json(series: str) -> Path | None:
    """Find the best files JSON to upload for a series."""
    files_dir = BY_SERIES / series / "files_json"
    if not files_dir.exists():
        return None

    # Priority: _v3 > _pdf_enriched > base
    candidates = [
        files_dir / f"st_ready_files_{series}_v3.json",
        files_dir / f"st_ready_files_{series}_pdf_enriched.json",
        files_dir / f"st_ready_files_{series}.json",
    ]

    for c in candidates:
        if c.exists():
            return c
    return None


def main():
    """CLI entry point: for each selected series (or --only-series), find the best
    files JSON and upload/append it to that series' existing files datasource via
    Add_Data_Source_Files.py --operation add, throttled by UPLOAD_DELAY_SEC between
    uploads to avoid API rate limiting.
    """
    import argparse
    parser = argparse.ArgumentParser(description="Upload PDF-enriched files to KB")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument(
        "--only-series",
        choices=sorted(SERIES_FILES_DATASOURCES),
        help="Upload only one STM32Cube series, for targeted rollback retries.",
    )
    parser.add_argument(
        "--json-split-size",
        type=int,
        default=DEFAULT_JSON_SPLIT_SIZE,
        help=f"Maximum JSON records per split part. Default: {DEFAULT_JSON_SPLIT_SIZE} for PDF-enriched files.",
    )
    args = parser.parse_args()

    if args.json_split_size <= 0:
        parser.error("--json-split-size must be > 0")

    print(f"Uploading PDF-enriched files to KB #{KB_ID}")
    print()

    uploaded = 0
    skipped = 0

    selected_datasources = SERIES_FILES_DATASOURCES
    if args.only_series:
        selected_datasources = {args.only_series: SERIES_FILES_DATASOURCES[args.only_series]}

    for series, ds_id in selected_datasources.items():
        files_json = find_files_json(series)

        if not files_json:
            print(f"[SKIP] {series}: No files JSON found")
            skipped += 1
            continue

        size_mb = files_json.stat().st_size / (1024 * 1024)
        print(f"[{series}] {files_json.name} ({size_mb:.1f} MB) -> datasource #{ds_id}")

        if args.dry_run:
            uploaded += 1
            continue

        cmd = [
            sys.executable, str(ADD_SCRIPT),
            "--kb", str(KB_ID),
            "--operation", "add",
            "--datasource-id", str(ds_id),
            "--remote-user", "abir.gharbi@st.com",
            "--processor", "JSON",
            "--processor-params", f"base64:{PROCESSOR_PARAMS}",
            "--json-root-mode", "auto",
            "--empty-json-policy", "skip",
            "--json-split-size", str(args.json_split_size),
            "--files", str(files_json),
        ]
        if args.verbose:
            cmd.append("--verbose")

        result = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
        if result.returncode != 0:
            print(f"  [WARN] Upload failed (exit code {result.returncode})")
        else:
            print(f"  [OK] Uploaded")
            uploaded += 1

        # Throttle to avoid rate limiting
        time.sleep(UPLOAD_DELAY_SEC)

    print(f"\nDone. {uploaded} uploaded, {skipped} skipped.")


if __name__ == "__main__":
    main()
