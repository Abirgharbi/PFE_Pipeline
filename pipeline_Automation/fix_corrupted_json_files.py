"""
Fix corrupted JSON files that have unescaped control characters.

Uses json decoder with strict=False to parse despite control chars,
then re-serializes properly.

Usage:
    python pipeline_Automation/fix_corrupted_json_files.py
"""

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DELIVERY_DIR = PROJECT_ROOT / "datasets" / "07_delivery" / "st_ready" / "by_series"


def fix_json_file(file_path: Path) -> bool | None:
    """Try to fix a JSON file with control characters.

    Returns:
        True: file was repaired and rewritten.
        False: file was already valid JSON.
        None: file is still invalid and could not be parsed/repaired.
    """
    content = file_path.read_text(encoding="utf-8")

    # First check if it's valid already
    try:
        json.loads(content)
        return False  # Already valid
    except json.JSONDecodeError:
        pass

    # Try parsing with strict=False (allows control chars in strings)
    try:
        data = json.loads(content, strict=False)
    except json.JSONDecodeError as exc:
        print(f"  [ERROR] Cannot parse even with strict=False: {exc}")
        return None

    # Re-serialize properly (this escapes all control chars)
    file_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return True


def main():
    """Scan delivery ``st_ready_files_*.json`` files and fix any with unescaped control characters."""
    print(f"Scanning delivery files for corrupted JSON...")
    print(f"Directory: {DELIVERY_DIR}")
    print("=" * 60)

    fixed = 0
    already_ok = 0
    failed = 0

    for series_dir in sorted(DELIVERY_DIR.iterdir()):
        if not series_dir.is_dir():
            continue
        files_dir = series_dir / "files_json"
        if not files_dir.exists():
            continue

        for json_file in sorted(files_dir.glob("st_ready_files_*.json")):
            if "summary" in json_file.name:
                continue

            result = fix_json_file(json_file)
            if result is True:
                print(f"  [FIXED] {json_file.relative_to(PROJECT_ROOT)}")
                fixed += 1
            elif result is False:
                already_ok += 1
            else:
                failed += 1

    print("=" * 60)
    print(f"Fixed: {fixed}, Already OK: {already_ok}, Failed: {failed}")


if __name__ == "__main__":
    main()
