"""
Patch PDF figure descriptions into existing delivery files.

Instead of re-running the full pipeline (40+ min), this script directly replaces
placeholder text in st_ready_files_*.json with actual Alfred descriptions from
data/pdf_image_descriptions.json.

Usage:
    python pipeline_Automation/patch_pdf_descriptions_in_delivery.py
    python pipeline_Automation/patch_pdf_descriptions_in_delivery.py --series U3
    python pipeline_Automation/patch_pdf_descriptions_in_delivery.py --dry-run
"""

import argparse
import json
import os
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
DELIVERY_DIR = PROJECT_ROOT / "datasets" / "07_delivery" / "st_ready" / "by_series"
DESCRIPTIONS_FILE = DATA_DIR / "pdf_image_descriptions.json"

PLACEHOLDER_PATTERN = re.compile(
    r"Figure detected on page \d+, but no technical description is available yet for ([^\s]+:p\d+:f\d+)\."
)


def series_to_slug(series: str) -> str:
    value = (series or "").strip().lower()
    if not value:
        return ""
    if value.startswith("stm32cube"):
        return value
    return f"stm32cube{value}"


def build_description_candidates(series: str | None) -> list[Path]:
    candidates: list[Path] = [DESCRIPTIONS_FILE]

    if series:
        slug = series_to_slug(series)
        if slug:
            series_root = DELIVERY_DIR / slug
            candidates.append(series_root / "pdf_image_descriptions.json")
            candidates.append(series_root / "meta" / "pdf_image_descriptions.json")
            candidates.append(series_root / "metadata" / "pdf_image_descriptions.json")
            for nested in sorted(series_root.rglob("pdf_image_descriptions.json")):
                if nested not in candidates:
                    candidates.append(nested)

    seen: set[str] = set()
    unique: list[Path] = []
    for item in candidates:
        key = str(item.resolve()) if item.exists() else str(item)
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def load_descriptions(series: str | None = None) -> tuple[dict[str, str], Path | None]:
    """Load Alfred figure descriptions from default and series-local locations.

    Returns the descriptions map and the source path that was used.
    """
    candidates = build_description_candidates(series)

    for path in candidates:
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"[WARN] Failed to parse descriptions JSON at {path}: {exc}")
            continue
        if not isinstance(data, dict):
            print(f"[WARN] Descriptions JSON is not an object at {path}; skipping this file.")
            continue

        cleaned = {str(k): str(v) for k, v in data.items() if isinstance(v, str) and str(v).strip()}
        if cleaned:
            return cleaned, path
        print(f"[INFO] Descriptions file is empty at {path}; trying next candidate.")

    level = "INFO" if os.environ.get("GITHUB_ACTIONS") == "true" else "WARN"
    for path in candidates:
        print(f"[{level}] Descriptions file not found: {path}")
    print("[INFO] PDF patch step is optional; continuing without Alfred PDF descriptions.")
    return {}, None


def patch_file(file_path: Path, descriptions: dict[str, str], dry_run: bool = False) -> int:
    """Patch a single delivery JSON file. Returns number of replacements made."""
    content = file_path.read_text(encoding="utf-8")

    replacements = 0

    def replace_placeholder(match: re.Match) -> str:
        """Replace one "no technical description available yet" placeholder with its real description, if known."""
        nonlocal replacements
        figure_id = match.group(1)
        desc = descriptions.get(figure_id, "").strip()
        if desc:
            replacements += 1
            # Escape for JSON string context: newlines, tabs, backslashes, quotes
            desc = desc.replace("\\", "\\\\")
            desc = desc.replace('"', '\\"')
            desc = desc.replace("\n", "\\n")
            desc = desc.replace("\r", "\\r")
            desc = desc.replace("\t", "\\t")
            return desc
        return match.group(0)  # Keep original if no description found

    patched = PLACEHOLDER_PATTERN.sub(replace_placeholder, content)

    if replacements > 0 and not dry_run:
        file_path.write_text(patched, encoding="utf-8")

    return replacements


def scan_existing_pdf_descriptions(target_delivery_dir: Path) -> tuple[int, int]:
    """Return (files_with_descriptions, files_with_placeholders) in delivery JSON files."""
    files_with_descriptions = 0
    files_with_placeholders = 0

    patterns = ("st_ready_files_*.json", "*_pdf_enriched*.json")
    candidates: list[Path] = []
    for pattern in patterns:
        candidates.extend(target_delivery_dir.rglob(pattern))

    for json_file in sorted(set(candidates)):
        if "summary" in json_file.name:
            continue
        if json_file.parent.name != "files_json":
            continue
        try:
            content = json_file.read_text(encoding="utf-8")
        except Exception:
            continue

        if "[FIGURE_DESCRIPTIONS]" in content:
            files_with_descriptions += 1
        if PLACEHOLDER_PATTERN.search(content):
            files_with_placeholders += 1

    return files_with_descriptions, files_with_placeholders


def main():
    """CLI entry point: patch placeholder figure descriptions across all delivery files in place."""
    parser = argparse.ArgumentParser(description="Patch PDF descriptions into delivery files")
    parser.add_argument("--series", default="", help="Series code or slug (e.g. U3 or stm32cubeu3)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be changed without writing")
    args = parser.parse_args()

    series = args.series.strip()
    target_delivery_dir = DELIVERY_DIR
    if series:
        target_delivery_dir = DELIVERY_DIR / series_to_slug(series)
        if not target_delivery_dir.exists():
            print(f"[WARN] Delivery directory not found for series '{series}': {target_delivery_dir}")
            return

    descriptions, source_path = load_descriptions(series=series or None)
    if not descriptions:
        described_files, placeholder_files = scan_existing_pdf_descriptions(target_delivery_dir)
        if described_files > 0:
            print(
                "[INFO] Alfred PDF descriptions are already present in delivery output "
                f"({described_files} file(s) contain [FIGURE_DESCRIPTIONS])."
            )
        if placeholder_files > 0:
            print(
                "[WARN] PDF placeholders still exist in delivery output "
                f"({placeholder_files} file(s))."
            )
        print("[INFO] No descriptions loaded. Skipping PDF patch step.")
        return

    source_label = source_path.name if source_path else DESCRIPTIONS_FILE.name
    print(f"Loaded {len(descriptions)} PDF figure descriptions from {source_label}")
    print(f"Scanning delivery files in: {target_delivery_dir}")
    print(f"{'DRY RUN - no files will be modified' if args.dry_run else 'LIVE - files will be patched'}")
    print("=" * 60)

    total_replacements = 0
    files_patched = 0

    # Find all file delivery JSONs, including driver/subrepo exports under drivers/*/files_json/.
    patterns = ("st_ready_files_*.json", "*_pdf_enriched*.json")
    candidates = []
    for pattern in patterns:
        candidates.extend(target_delivery_dir.rglob(pattern))

    for json_file in sorted(set(candidates)):
        if "summary" in json_file.name:
            continue
        if json_file.parent.name != "files_json":
            continue

        count = patch_file(json_file, descriptions, dry_run=args.dry_run)
        if count > 0:
            print(f"  {json_file.relative_to(PROJECT_ROOT)}: {count} descriptions injected")
            total_replacements += count
            files_patched += 1

    print("=" * 60)
    print(f"Total: {total_replacements} placeholders replaced in {files_patched} files")
    if args.dry_run:
        print("(dry run — re-run without --dry-run to apply)")


if __name__ == "__main__":
    main()
