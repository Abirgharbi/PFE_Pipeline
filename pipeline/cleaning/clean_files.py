"""Cleaning stage (V1): normalize raw file content and classify each file's type.

Role in the pipeline
---------------------
Consumes `data/raw_files_<repo>.json` (from `pipeline/ingestion/fetch_files.py`)
and produces `data/clean_files_<repo>.json`: whitespace-normalized text plus a
`file_type` classification (e.g. driver_source, root_readme, release_notes)
used by later stages, notably `pipeline/cleaning/clean_files_v3.py` (which
applies type-aware cleaning on top of this output) and enrichment
(`files_to_docs_v2.py`).

Inputs
------
- Config: resolved via `shared.utils.paths.get_config_path()` (default
  `shared/config/config_all_series.json`, overridable with `STM32CUBE_CONFIG`).
  Uses `repos`.
- `data/raw_files_<repo>.json` for each configured repo.

Outputs
-------
- `data/clean_files_<repo>.json`: list of cleaned file records with
  `clean_text`, `file_type`, and passthrough metadata (path, github_url,
  image/PDF task references).

How to run
----------
No CLI arguments; run as a module: `python -m pipeline.cleaning.clean_files`.
"""

import json

from shared.utils.paths import DATA_DIR, get_config_path


def load_config() -> dict:
    """Load and parse the active pipeline configuration JSON file.

    Returns:
        The parsed configuration as a dict.
    """
    cfg_path = get_config_path()
    return json.loads(cfg_path.read_text(encoding="utf-8"))


def is_bsp_board_root(path: str) -> bool:
    """Check if a top-level folder name looks like a board/BSP folder.

    Args:
        path: A forward-slash file path (first segment is checked).

    Returns:
        True if the first path segment starts with "stm32" and contains a
        known board-type suffix tag ("-dk", "-eval", "-disco", "nucleo").
    """
    root = path.split("/", 1)[0]
    if not root.startswith("stm32"):
        return False
    return any(tag in root for tag in ("-dk", "-eval", "-disco", "nucleo"))


def detect_file_type(path: str) -> str:
    """Classify a repo-relative file path into a coarse `file_type` category.

    The classification drives type-aware cleaning downstream (see
    `clean_files_v3.clean_by_type`) and metadata used in enrichment/delivery.
    Rules are checked in priority order (e.g. release notes before generic
    README detection) since some paths could match more than one pattern.

    Args:
        path: File path relative to the repo root (OS-native separators ok).

    Returns:
        One of a fixed set of type labels (e.g. "documentation_pdf",
        "release_notes", "project_readme", "driver_source", ... or "other"
        if nothing matches).
    """
    p = path.replace("\\", "/").lower()

    if p.startswith(("documentation/", "documentations/")) and p.endswith(".pdf"):
        return "documentation_pdf"

    if "release_notes" in p or "releasenotes" in p:
        return "release_notes"

    if "projects/" in p:
        return "project_readme"

    if p.endswith("readme.md") or p.endswith("readme.txt"):
        if "/documentation/" in p:
            return "doc_readme"
        return "root_readme"

    if p in {
        "code_of_conduct.md",
        "contributing.md",
        "license.md",
        "security.md",
        "sw_security_level.md",
        "package.xml",
        "sbom_cdx.json",
        ".deliveryignore",
        ".gitmodules",
    }:
        return "repo_metadata"

    if p.startswith("drivers/"):
        return "driver_source"

    if p.startswith("src/") or p.startswith("inc/"):
        return "hal_driver_source"

    if p.startswith("middlewares/"):
        return "middleware_source"

    if p.startswith("utilities/"):
        return "utilities_content"

    if p.startswith("components/"):
        return "bsp_component_source"

    if p.startswith("include/") or p.startswith("source/"):
        return "cmsis_source"

    if is_bsp_board_root(p):
        return "bsp_board_source"

    if "/" not in p and p.startswith("stm32") and p.endswith((".c", ".h", ".hpp", ".s", ".asm")):
        return "bsp_board_source"

    return "other"


def clean_content(text: str) -> str:
    """Normalize line endings and strip surrounding whitespace.

    Args:
        text: Raw file content.

    Returns:
        The normalized text, or an empty string if input is falsy.
    """
    if not text:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text.strip()


def clean_files_for_repo(repo: str) -> None:
    """Clean and classify all raw files for a single repo, writing the result to disk.

    Args:
        repo: Repository name (used to resolve input/output file paths).

    Side Effects:
        Writes `data/clean_files_<repo>.json`. Prints a warning and returns
        early if the input raw file does not exist.
    """
    in_file = DATA_DIR / f"raw_files_{repo.lower()}.json"
    out_file = DATA_DIR / f"clean_files_{repo.lower()}.json"

    if not in_file.exists():
        print(f"[WARN] raw_files not found for {repo}: {in_file}")
        return

    raw_files = json.loads(in_file.read_text(encoding="utf-8"))
    clean_files: list[dict] = []

    for f in raw_files:
        path = f.get("path") or ""
        content = f.get("content") or ""
        encoding = f.get("encoding") or "utf-8"
        github_url = f.get("github_url")
        media_urls = f.get("media_urls") or []
        image_records = f.get("image_records") or []
        images_count = f.get("images_count") or len(image_records)
        content_extractor = f.get("content_extractor") or "text"
        pdf_task_file = f.get("pdf_task_file")

        clean_text = clean_content(content)
        file_type = detect_file_type(path)

        clean_files.append(
            {
                "repo": repo,
                "path": path,
                "clean_text": clean_text,
                "file_type": file_type,
                "encoding": encoding,
                "github_url": github_url,
                "media_urls": media_urls,
                "image_records": image_records,
                "images_count": images_count,
                "content_extractor": content_extractor,
                "pdf_task_file": pdf_task_file,
            }
        )

    out_file.write_text(
        json.dumps(clean_files, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[CLEAN] {len(clean_files)} cleaned files -> {out_file}")


def main() -> None:
    """Entry point: clean and classify raw files for every configured repo."""
    cfg = load_config()
    repos = cfg["repos"]

    for repo in repos:
        clean_files_for_repo(repo)

    print("Done clean_files.")


if __name__ == "__main__":
    main()
