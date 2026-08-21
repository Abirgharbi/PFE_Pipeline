"""
Clean files V3 — Type-aware cleaning.

Reads from: data/clean_files_{repo}.json (existing V1 output)
Writes to:  data/clean_files_{repo}_v3.json (NEW file, never overwrites V1)

Cleaning strategies per file_type:
- release_notes (HTML)  → strip all HTML tags, keep text only
- root_readme / project_readme / doc_readme (Markdown) → remove badges, shields, image links
- driver_source / hal_driver_source / bsp_board_source (.c/.h) → strip license headers, keep API docs
- repo_metadata (package.xml, sbom_cdx.json) → extract key fields only
- middleware_source → strip license headers
- documentation_pdf → already extracted, just normalize whitespace
- other → basic whitespace normalization
"""

import json
import os
import re
from pathlib import Path

from shared.utils.paths import DATA_DIR


# ═══════════════════════════════════════════════════════════════
# HTML CLEANING
# ═══════════════════════════════════════════════════════════════

_SCRIPT_STYLE_RE = re.compile(
    r"<(script|style|head)[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE
)
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_ENTITY_MAP = {
    "&amp;": "&",
    "&lt;": "<",
    "&gt;": ">",
    "&nbsp;": " ",
    "&quot;": '"',
    "&#39;": "'",
    "&apos;": "'",
}
_MULTI_SPACE_RE = re.compile(r"[ \t]+")
_MULTI_NEWLINE_RE = re.compile(r"\n{3,}")


def strip_html(html: str) -> str:
    """Convert HTML to clean plain text."""
    if not html:
        return ""
    text = _HTML_COMMENT_RE.sub("", html)
    text = _SCRIPT_STYLE_RE.sub("", text)
    text = _HTML_TAG_RE.sub(" ", text)
    for entity, char in _ENTITY_MAP.items():
        text = text.replace(entity, char)
    # Decode numeric entities
    text = re.sub(r"&#(\d+);", lambda m: chr(int(m.group(1))), text)
    text = re.sub(r"&#x([0-9a-fA-F]+);", lambda m: chr(int(m.group(1), 16)), text)
    # Normalize whitespace
    text = _MULTI_SPACE_RE.sub(" ", text)
    lines = [line.strip() for line in text.split("\n")]
    text = "\n".join(line for line in lines if line)
    text = _MULTI_NEWLINE_RE.sub("\n\n", text)
    return text.strip()


# ═══════════════════════════════════════════════════════════════
# MARKDOWN CLEANING
# ═══════════════════════════════════════════════════════════════

_BADGE_RE = re.compile(r"!\[[^\]]*\]\(https?://img\.shields\.io[^)]*\)")
_IMAGE_LINK_RE = re.compile(r"!\[[^\]]*\]\([^)]+\)")
_EMPTY_LINK_RE = re.compile(r"\[([^\]]+)\]\(\)")
_HTML_IN_MD_RE = re.compile(r"<(br|hr|img|div|span|center|p)\b[^>]*/?>", re.IGNORECASE)


def clean_markdown(md: str) -> str:
    """Remove badges, image links, and inline HTML from Markdown."""
    if not md:
        return ""
    text = _BADGE_RE.sub("", md)
    text = _IMAGE_LINK_RE.sub("[image removed]", text)
    text = _EMPTY_LINK_RE.sub(r"\1", text)
    text = _HTML_IN_MD_RE.sub("", text)
    # Remove shield.io raw URLs on their own line
    text = re.sub(r"^https?://img\.shields\.io[^\n]*$", "", text, flags=re.MULTILINE)
    # Collapse excessive blank lines
    text = _MULTI_NEWLINE_RE.sub("\n\n", text)
    return text.strip()


# ═══════════════════════════════════════════════════════════════
# SOURCE CODE CLEANING (.c, .h, .s)
# ═══════════════════════════════════════════════════════════════

_LICENSE_BLOCK_RE = re.compile(
    r"/\*\*.*?(?:Copyright|STMicroelectronics|Licensed|SPDX).*?\*/",
    re.DOTALL | re.IGNORECASE,
)
_LICENSE_LINE_RE = re.compile(
    r"^\s*(\*|//).*(?:Copyright|All rights reserved|Licensed under|SPDX-License|Permission is hereby).*$",
    re.MULTILINE | re.IGNORECASE,
)
_EMPTY_COMMENT_BLOCK_RE = re.compile(r"/\*\*?\s*\*/")


def clean_source_code(code: str) -> str:
    """Strip license headers and excessive boilerplate from C/H/ASM files."""
    if not code:
        return ""
    # Remove full license comment blocks (first one only, usually at top)
    # Find the first block comment that contains copyright
    match = _LICENSE_BLOCK_RE.search(code[:3000])  # Only check first 3000 chars
    if match:
        code = code[: match.start()] + code[match.end() :]
    # Remove standalone license lines
    code = _LICENSE_LINE_RE.sub("", code)
    # Remove empty comment blocks left behind
    code = _EMPTY_COMMENT_BLOCK_RE.sub("", code)
    # Collapse leading blank lines
    code = code.lstrip("\n")
    code = _MULTI_NEWLINE_RE.sub("\n\n", code)
    return code.strip()


# ═══════════════════════════════════════════════════════════════
# CMSIS DEVICE HEADER FILTERING (stm32h5xxxx.h — huge files)
# ═══════════════════════════════════════════════════════════════

# Pattern to detect CMSIS device headers: stm32XXXXX.h in Include/ folder
_CMSIS_DEVICE_HEADER_RE = re.compile(r"(?:^|/)stm32[a-z0-9]+xx\.h$", re.IGNORECASE)

# Threshold: files above this size get filtered (normal .h are <100KB)
_CMSIS_SIZE_THRESHOLD = 100_000  # 100 KB


def is_cmsis_device_header(path: str, content_length: int) -> bool:
    """Detect if a file is a giant CMSIS device header (register map)."""
    filename = Path(path).name.lower()
    # Match patterns like stm32h503xx.h, stm32f446xx.h, etc.
    if not re.match(r"stm32[a-z0-9]+\.h$", filename):
        return False
    return content_length > _CMSIS_SIZE_THRESHOLD


def filter_cmsis_device_header(code: str) -> str:
    """Extract only useful sections from a CMSIS device header:
    - Interrupt vector enum (IRQn_Type)
    - Peripheral base addresses
    - Peripheral typedef structs (register layout)
    Drops: all #define XXX_Pos, #define XXX_Msk bitmask lines.
    """
    sections: list[str] = []

    # 1. Extract IRQn_Type enum (interrupt definitions)
    irq_match = re.search(
        r"(typedef\s+enum\s*\{[^}]*IRQn[^}]*\}[^;]*;)",
        code, re.DOTALL
    )
    if irq_match:
        sections.append("/* ===== Interrupt Number Definition ===== */")
        sections.append(irq_match.group(1))

    # 2. Extract peripheral base addresses block
    #    Looks for: #define PERIPH_BASE, #define xxx_BASE
    base_lines: list[str] = []
    for line in code.split("\n"):
        stripped = line.strip()
        if re.match(r"#define\s+\w+_BASE\s+", stripped):
            base_lines.append(stripped)
        elif re.match(r"#define\s+PERIPH_BASE\s+", stripped):
            base_lines.append(stripped)
    if base_lines:
        sections.append("\n/* ===== Peripheral Base Addresses ===== */")
        sections.append("\n".join(base_lines))

    # 3. Extract peripheral typedef structs (register layout)
    #    These are: typedef struct { ... } XXX_TypeDef;
    typedef_matches = re.finditer(
        r"(typedef\s+struct\s*\{[^}]{10,2000}\}\s*\w+_TypeDef\s*;)",
        code, re.DOTALL
    )
    typedefs = list(typedef_matches)
    if typedefs:
        sections.append("\n/* ===== Peripheral Register Structures ===== */")
        # Keep all structs (they define the register layout — useful for understanding offsets)
        for m in typedefs:
            sections.append(m.group(1))

    # 4. Summary header
    total_defines = code.count("#define")
    total_typedefs = len(typedefs)
    header = (
        f"/* CMSIS Device Header — Filtered for RAG relevance */\n"
        f"/* Original: {len(code):,} chars, {total_defines:,} #defines */\n"
        f"/* Kept: IRQ enum, {len(base_lines)} base addresses, "
        f"{total_typedefs} peripheral structs */\n"
        f"/* Full file: see GitHub link for complete register map */\n"
    )

    if sections:
        return header + "\n\n".join(sections)

    # Fallback: if nothing matched, keep first 5000 chars
    return header + code[:5000]


# ═══════════════════════════════════════════════════════════════
# METADATA CLEANING (package.xml, sbom_cdx.json)
# ═══════════════════════════════════════════════════════════════

def clean_xml_metadata(xml_content: str) -> str:
    """Extract key fields from package.xml."""
    if not xml_content:
        return ""
    # Extract meaningful tags
    fields = {}
    for tag in ("name", "version", "description", "license", "url", "PackName", "PackVersion"):
        match = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", xml_content, re.DOTALL | re.IGNORECASE)
        if match:
            fields[tag] = match.group(1).strip()
    if fields:
        return "\n".join(f"{k}: {v}" for k, v in fields.items())
    # Fallback: strip XML tags
    return strip_html(xml_content)


def clean_json_metadata(json_content: str) -> str:
    """Extract key fields from sbom_cdx.json or similar."""
    if not json_content:
        return ""
    try:
        data = json.loads(json_content)
    except (json.JSONDecodeError, ValueError):
        return json_content[:2000]  # Truncate if unparseable

    # For SBOM CycloneDX format
    lines = []
    if "metadata" in data:
        meta = data["metadata"]
        if "component" in meta:
            comp = meta["component"]
            lines.append(f"Name: {comp.get('name', 'N/A')}")
            lines.append(f"Version: {comp.get('version', 'N/A')}")
            lines.append(f"Type: {comp.get('type', 'N/A')}")
    if "components" in data:
        lines.append(f"Dependencies count: {len(data['components'])}")
        # List first 20 component names only
        for comp in data["components"][:20]:
            name = comp.get("name", "")
            version = comp.get("version", "")
            lines.append(f"  - {name} {version}")
        if len(data["components"]) > 20:
            lines.append(f"  ... and {len(data['components']) - 20} more")
    if lines:
        return "\n".join(lines)
    # Fallback: first 2000 chars
    return json_content[:2000]


# ═══════════════════════════════════════════════════════════════
# ROUTER — dispatch cleaning by file_type
# ═══════════════════════════════════════════════════════════════

def clean_by_type(text: str, file_type: str, path: str) -> str:
    """Apply type-specific cleaning to file content."""
    if not text:
        return ""

    suffix = Path(path).suffix.lower()

    # HTML files (Release Notes mostly)
    if file_type == "release_notes" and suffix in (".html", ".htm"):
        return strip_html(text)

    # Markdown files
    if file_type in ("root_readme", "project_readme", "doc_readme"):
        return clean_markdown(text)

    # Source code files
    if file_type in ("driver_source", "hal_driver_source", "bsp_board_source",
                     "middleware_source", "cmsis_source", "bsp_component_source",
                     "utilities_content"):
        if suffix in (".c", ".h", ".hpp", ".hh", ".s", ".asm"):
            # Check if it's a giant CMSIS device header → special filter
            if is_cmsis_device_header(path, len(text)):
                return filter_cmsis_device_header(text)
            return clean_source_code(text)
        if suffix in (".md", ".txt"):
            return clean_markdown(text)
        return text.strip()

    # Metadata files
    if file_type == "repo_metadata":
        if path.lower().endswith(".xml"):
            return clean_xml_metadata(text)
        if path.lower().endswith(".json"):
            return clean_json_metadata(text)
        if suffix in (".md",):
            return clean_markdown(text)
        return text.strip()

    # Release notes in markdown format
    if file_type == "release_notes" and suffix in (".md", ".txt"):
        return clean_markdown(text)

    # PDF — already extracted, just normalize
    if file_type == "documentation_pdf":
        return _MULTI_NEWLINE_RE.sub("\n\n", text).strip()

    # Default — basic normalization
    return text.strip()


# ═══════════════════════════════════════════════════════════════
# MAIN EXECUTION
# ═══════════════════════════════════════════════════════════════

def load_all_configs() -> list[dict]:
    """Load all series configs (config.json, config_f4.json, config_h5.json, etc.)."""
    from shared.utils.paths import CONFIG_DIR
    configs = []
    seen_repos: set[str] = set()
    for cfg_file in sorted(CONFIG_DIR.glob("config*.json")):
        # Accept both UTF-8 and UTF-8 with BOM to avoid config parsing failures.
        cfg = json.loads(cfg_file.read_text(encoding="utf-8-sig"))
        # Deduplicate repos across configs
        new_repos = [r for r in cfg.get("repos", []) if r not in seen_repos]
        seen_repos.update(new_repos)
        if new_repos:
            cfg["repos"] = new_repos
            cfg["_source"] = cfg_file.name
            configs.append(cfg)
    return configs


def load_target_configs() -> list[dict]:
    """Load either the selected config (STM32CUBE_CONFIG) or all configs."""
    selected = os.environ.get("STM32CUBE_CONFIG", "").strip()
    if not selected:
        return load_all_configs()

    selected_path = Path(selected)
    if not selected_path.exists():
        # Fallback to all configs if env points to a missing file.
        print(f"[WARN] STM32CUBE_CONFIG not found: {selected}. Falling back to all configs.")
        return load_all_configs()

    cfg = json.loads(selected_path.read_text(encoding="utf-8-sig"))
    cfg["_source"] = selected_path.name
    return [cfg]


def clean_files_v3_for_repo(repo: str) -> None:
    """Read clean_files_{repo}.json, apply type-aware cleaning, write to _v3.json."""
    in_file = DATA_DIR / f"clean_files_{repo.lower()}.json"
    out_file = DATA_DIR / f"clean_files_{repo.lower()}_v3.json"

    if not in_file.exists():
        print(f"[WARN] Input not found: {in_file}")
        return

    # Be resilient to BOM in generated/edited JSON artifacts.
    files = json.loads(in_file.read_text(encoding="utf-8-sig"))
    cleaned: list[dict] = []
    stats = {"total": 0, "html_stripped": 0, "md_cleaned": 0, "code_stripped": 0,
             "cmsis_filtered": 0, "meta_extracted": 0, "unchanged": 0, "empty_after_clean": 0}

    for f in files:
        stats["total"] += 1
        path = f.get("path", "")
        file_type = f.get("file_type", "other")
        original_text = f.get("clean_text", "")

        cleaned_text = clean_by_type(original_text, file_type, path)

        # Track what happened
        suffix = Path(path).suffix.lower()
        if file_type == "release_notes" and suffix in (".html", ".htm"):
            stats["html_stripped"] += 1
        elif file_type in ("root_readme", "project_readme", "doc_readme"):
            stats["md_cleaned"] += 1
        elif suffix in (".c", ".h", ".hpp", ".s", ".asm") and is_cmsis_device_header(path, len(original_text)):
            stats["cmsis_filtered"] += 1
        elif suffix in (".c", ".h", ".hpp", ".s", ".asm"):
            stats["code_stripped"] += 1
        elif file_type == "repo_metadata":
            stats["meta_extracted"] += 1
        else:
            stats["unchanged"] += 1

        if not cleaned_text:
            stats["empty_after_clean"] += 1

        # Build output record (same schema, just updated clean_text)
        out_record = dict(f)
        out_record["clean_text"] = cleaned_text
        out_record["cleaning_version"] = "v3"
        out_record["original_length"] = len(original_text)
        out_record["cleaned_length"] = len(cleaned_text)
        cleaned.append(out_record)

    # Stream JSON to file to avoid large intermediate string allocation.
    with out_file.open("w", encoding="utf-8") as fh:
        json.dump(cleaned, fh, ensure_ascii=False, indent=2)

    print(f"[CLEAN_V3] {repo}: {stats['total']} files processed -> {out_file.name}")
    print(f"           HTML stripped: {stats['html_stripped']}, "
          f"MD cleaned: {stats['md_cleaned']}, "
          f"Code stripped: {stats['code_stripped']}, "
          f"CMSIS filtered: {stats['cmsis_filtered']}, "
          f"Meta extracted: {stats['meta_extracted']}, "
          f"Unchanged: {stats['unchanged']}")
    if stats["empty_after_clean"]:
        print(f"           [WARN] {stats['empty_after_clean']} files empty after cleaning")


def main() -> None:
    """Entry point: run type-aware cleaning (V3) for every repo in the selected config(s).

    Reads `data/clean_files_<repo>.json` (V1 output) for each repo across the
    target config(s) (see `load_target_configs`) and writes
    `data/clean_files_<repo>_v3.json`, leaving the V1 files untouched.
    """
    configs = load_target_configs()

    print("=" * 60)
    print("CLEAN FILES V3 — Type-aware cleaning")
    print("=" * 60)
    print(f"Input:  data/clean_files_{{repo}}.json")
    print(f"Output: data/clean_files_{{repo}}_v3.json (NEW files)")
    print(f"Configs selected: {[c['_source'] for c in configs]}")
    print("=" * 60)

    total_repos = 0
    for cfg in configs:
        print(f"\n--- {cfg['_source']} ---")
        for repo in cfg["repos"]:
            clean_files_v3_for_repo(repo)
            total_repos += 1

    print(f"\nDone. {total_repos} repos processed. Original files are UNTOUCHED.")


if __name__ == "__main__":
    main()
