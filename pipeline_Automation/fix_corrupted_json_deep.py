"""
Fix severely corrupted JSON files where descriptions contain unescaped quotes/backslashes.

Strategy: Read file as raw text, find [FIGURE_DESCRIPTIONS] blocks,
replace their content with properly escaped descriptions from pdf_image_descriptions.json.

Usage:
    python pipeline_Automation/fix_corrupted_json_deep.py
"""

import json
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DELIVERY_DIR = PROJECT_ROOT / "datasets" / "07_delivery" / "st_ready" / "by_series"
DESCRIPTIONS_FILE = PROJECT_ROOT / "data" / "pdf_image_descriptions.json"


def escape_for_json_string(text: str) -> str:
    """Escape text so it's safe inside a JSON string value."""
    text = text.replace("\\", "\\\\")
    text = text.replace('"', '\\"')
    text = text.replace("\n", "\\n")
    text = text.replace("\r", "\\r")
    text = text.replace("\t", "\\t")
    # Remove other control characters
    text = re.sub(r'[\x00-\x1f]', '', text)
    return text


def rebuild_figure_block(figure_id: str, description: str) -> str:
    """Build a properly escaped figure description line."""
    escaped_desc = escape_for_json_string(description.strip())
    return f"- {figure_id}: {escaped_desc}"


def fix_file_deep(file_path: Path, descriptions: dict[str, str]) -> bool:
    """Fix a file by rebuilding all [FIGURE_DESCRIPTIONS] blocks from source descriptions."""
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as exc:
        print(f"  [ERROR] Cannot read {file_path.name}: {exc}")
        return False

    # Check if already valid
    try:
        json.loads(content)
        return False  # Already OK
    except json.JSONDecodeError:
        pass

    # Find and replace all [FIGURE_DESCRIPTIONS] ... [/FIGURE_DESCRIPTIONS] blocks
    # Pattern matches the entire block including content
    block_pattern = re.compile(
        r'\[FIGURE_DESCRIPTIONS\](.*?)\[/FIGURE_DESCRIPTIONS\]',
        re.DOTALL
    )

    def rebuild_block(match):
        """Rebuild one [FIGURE_DESCRIPTIONS]...[/FIGURE_DESCRIPTIONS] block with properly escaped text."""
        block_content = match.group(1)
        # Extract figure_ids from the block (they follow "- " at start of lines or after newline)
        # The figure_id format: REPO:path/to/file.pdf:pN:fN
        fig_id_pattern = re.compile(r'-\s*([^\s:]+:[^\s:]+\.pdf:p\d+:f\d+):?\s*')
        fig_ids = fig_id_pattern.findall(block_content)

        if not fig_ids:
            # Try to find IDs in a more relaxed way
            fig_id_pattern2 = re.compile(r'(STM32Cube\w+:[^:]+\.pdf:p\d+:f\d+)')
            fig_ids = fig_id_pattern2.findall(block_content)

        if not fig_ids:
            return match.group(0)  # Can't fix, leave as-is

        lines = []
        for fig_id in fig_ids:
            desc = descriptions.get(fig_id, "").strip()
            if desc:
                lines.append(rebuild_figure_block(fig_id, desc))
            else:
                lines.append(f"- {fig_id}: No description available.")

        return "[FIGURE_DESCRIPTIONS] " + " ".join(lines) + " [/FIGURE_DESCRIPTIONS]"

    patched = block_pattern.sub(rebuild_block, content)

    # Verify the result is valid JSON
    try:
        json.loads(patched)
    except json.JSONDecodeError as exc:
        print(f"  [ERROR] Rebuild failed validation for {file_path.name}: {exc}")
        # Try strict=False as fallback
        try:
            data = json.loads(patched, strict=False)
            patched = json.dumps(data, ensure_ascii=False, indent=2)
        except json.JSONDecodeError as exc2:
            print(f"  [ERROR] Even strict=False failed: {exc2}")
            return False

    file_path.write_text(patched, encoding="utf-8")
    return True


def main():
    """Scan delivery ``st_ready_files_*.json`` files and deep-repair any invalid JSON found.

    For each file that fails to parse as JSON, rebuilds its
    ``[FIGURE_DESCRIPTIONS]`` blocks from the source ``pdf_image_descriptions.json``
    with correct escaping, then re-validates before writing.
    """
    # Load descriptions
    if not DESCRIPTIONS_FILE.exists():
        print("[ERROR] pdf_image_descriptions.json not found")
        return

    descriptions = json.loads(DESCRIPTIONS_FILE.read_text(encoding="utf-8"))
    print(f"Loaded {len(descriptions)} descriptions")
    print(f"Scanning: {DELIVERY_DIR}")
    print("=" * 60)

    fixed = 0
    already_ok = 0

    for series_dir in sorted(DELIVERY_DIR.iterdir()):
        if not series_dir.is_dir():
            continue
        files_dir = series_dir / "files_json"
        if not files_dir.exists():
            continue

        for json_file in sorted(files_dir.glob("st_ready_files_*.json")):
            if "summary" in json_file.name:
                continue

            # Check if valid first
            try:
                content = json_file.read_text(encoding="utf-8")
                json.loads(content)
                already_ok += 1
                continue
            except (json.JSONDecodeError, Exception):
                pass

            print(f"  Fixing: {json_file.relative_to(PROJECT_ROOT)}")
            if fix_file_deep(json_file, descriptions):
                print(f"  [FIXED]")
                fixed += 1

    print("=" * 60)
    print(f"Fixed: {fixed}, Already OK: {already_ok}")


if __name__ == "__main__":
    main()
