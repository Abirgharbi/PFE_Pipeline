"""Service module: walk a local STM32Cube repo clone and collect raw file artifacts.

Role in the pipeline
---------------------
Used by `pipeline/ingestion/fetch_files.py`. Given a local git clone of an
STM32Cube repo (see `repo_sync_service.ensure_local_repos`), this module
decides which files are relevant for the knowledge base (README, release
notes, technical source under known root folders, documentation PDFs, a
fixed allowlist of top-level metadata files), reads their content (extracting
text from PDFs via `pdf_figure_service` when possible), and builds the raw
file records later consumed by `pipeline/cleaning/clean_files.py`.

Inputs
------
- A local repo root directory (`Path`), typically
  `GitHub_repos/<repo_name>/`.

Outputs
-------
- In-memory list of raw file dicts (`collect_repo_docs`), each with `repo`,
  `path`, `content`, `encoding`, `github_url`, PDF figure metadata, etc.
- `write_raw_files_json` persists that list to a given output file (used by
  the caller to write `data/raw_files_<repo>.json`).

This module has no CLI entry point; it is imported, not run directly.
"""

import json
from pathlib import Path
from typing import Iterable
from urllib.parse import quote

from shared.utils.paths import DATA_DIR
from pipeline.ingestion.pdf_figure_service import extract_pdf_multimodal

try:
    from pypdf import PdfReader  # type: ignore[import-not-found]
except Exception:
    PdfReader = None


DOC_EXTENSIONS = {".md", ".txt", ".htm", ".html"}
TECHNICAL_TEXT_EXTENSIONS = {
    ".c",
    ".h",
    ".hpp",
    ".hh",
    ".s",
    ".asm",
    ".ld",
    ".mk",
    ".cmake",
    ".dox",
    ".rst",
    ".xml",
    ".json",
    ".yml",
    ".yaml",
    ".ini",
    ".cfg",
    ".conf",
    ".csv",
}
PDF_EXTENSION = ".pdf"

TOP_LEVEL_METADATA_FILES = {
    ".deliveryignore",
    ".gitmodules",
    "code_of_conduct.md",
    "contributing.md",
    "license.md",
    "security.md",
    "sw_security_level.md",
    "package.xml",
    "sbom_cdx.json",
}

TECHNICAL_SOURCE_ROOTS = {
    "drivers",
    "middlewares",
    "utilities",
    "components",
    "include",
    "source",
    "inc",
    "src",
}


def is_board_bsp_root(root: str) -> bool:
    """Check if a top-level folder name looks like a board/BSP folder.

    STM32Cube repos expose board support packages under folder names such as
    `stm32f429i-disco`, `stm32h7xx-nucleo`, `stm32l4xx-eval`, etc. This is used
    to whitelist their loose top-level source files as technical content.

    Args:
        root: The first path component (already lowercased by caller).

    Returns:
        True if the folder name starts with "stm32" and contains a known
        board-type suffix tag ("-dk", "-eval", "-disco", "nucleo").
    """
    if not root.startswith("stm32"):
        return False
    return any(tag in root for tag in ("-dk", "-eval", "-disco", "nucleo"))


def build_github_blob_url(owner: str, repo_name: str, rel_path: str, ref: str = "master") -> str:
    """Build a GitHub "blob" URL for a file, for traceability in downstream records.

    Args:
        owner: GitHub organization/user (e.g. "STMicroelectronics").
        repo_name: Repository name.
        rel_path: File path relative to the repo root (OS-native separators ok).
        ref: Git ref/branch to link to (default "master").

    Returns:
        A fully qualified, URL-escaped GitHub blob URL.
    """
    path_norm = (rel_path or "").replace("\\", "/").lstrip("/")
    path_escaped = quote(path_norm, safe="/")
    return f"https://github.com/{owner}/{repo_name}/blob/{ref}/{path_escaped}"


def is_projects_readme(rel_path: Path) -> bool:
    """Check whether a path is a README under a top-level `Projects/` folder.

    Args:
        rel_path: File path relative to the repo root.

    Returns:
        True if the path is a `Projects/.../README*` doc file.
    """
    parts = rel_path.parts
    if len(parts) < 2:
        return False
    if parts[0] != "Projects":
        return False

    filename = parts[-1].lower()
    if not filename.startswith("readme"):
        return False

    return rel_path.suffix.lower() in DOC_EXTENSIONS


def is_release_notes(rel_path: Path) -> bool:
    """Check whether a path is a Release_Notes document (any location).

    Args:
        rel_path: File path relative to the repo root.

    Returns:
        True if the file name starts with "release_notes" and has a doc extension.
    """
    filename = rel_path.parts[-1]
    if not filename.lower().startswith("release_notes"):
        return False
    return rel_path.suffix.lower() in DOC_EXTENSIONS


def is_top_level_readme(rel_path: Path) -> bool:
    """Check whether a path is a README at the repo root (not nested).

    Args:
        rel_path: File path relative to the repo root.

    Returns:
        True only for a single-segment path (`README.md` at the root), with a
        recognized doc extension.
    """
    filename = rel_path.name.lower()
    if not filename.startswith("readme"):
        return False
    if rel_path.suffix.lower() not in DOC_EXTENSIONS:
        return False

    parts = rel_path.parts
    if len(parts) == 1:
        return True
    return False


def is_documentation_pdf(rel_path: Path) -> bool:
    """Check whether a path is a PDF under a top-level `Documentation(s)/` folder.

    Args:
        rel_path: File path relative to the repo root.

    Returns:
        True if the first path segment is "documentation"/"documentations"
        (case-insensitive) and the extension is `.pdf`.
    """
    parts = rel_path.parts
    if not parts:
        return False
    if parts[0].lower() not in ("documentation", "documentations"):
        return False
    return rel_path.suffix.lower() == PDF_EXTENSION


def is_top_level_metadata_file(rel_path: Path) -> bool:
    """Check whether a path is a recognized top-level repo metadata file.

    Covers a fixed allowlist (`TOP_LEVEL_METADATA_FILES`, e.g. LICENSE.md,
    package.xml) plus root-level README/Release_Notes files.

    Args:
        rel_path: File path relative to the repo root.

    Returns:
        True if the file is a single-segment path matching the allowlist or
        README/Release_Notes naming convention.
    """
    if len(rel_path.parts) != 1:
        return False

    filename = rel_path.name.lower()
    if filename in TOP_LEVEL_METADATA_FILES:
        return True

    if filename.startswith("readme") and rel_path.suffix.lower() in DOC_EXTENSIONS:
        return True

    if filename.startswith("release_notes") and rel_path.suffix.lower() in DOC_EXTENSIONS:
        return True

    return False


def is_technical_source_file(rel_path: Path) -> bool:
    """Check whether a path is technical source content worth ingesting.

    Includes README/Release_Notes anywhere, and doc/technical-text files
    (see `DOC_EXTENSIONS`/`TECHNICAL_TEXT_EXTENSIONS`) either at the repo
    root or under a known technical source root (`TECHNICAL_SOURCE_ROOTS`) or
    a board/BSP folder (see `is_board_bsp_root`).

    Args:
        rel_path: File path relative to the repo root.

    Returns:
        True if the file should be treated as technical source content.
    """
    parts = rel_path.parts
    if not parts:
        return False

    filename = rel_path.name.lower()
    suffix = rel_path.suffix.lower()

    if filename.startswith("readme") or filename.startswith("release_notes"):
        return True

    if suffix not in DOC_EXTENSIONS and suffix not in TECHNICAL_TEXT_EXTENSIONS:
        return False

    if len(parts) == 1:
        return True

    root = parts[0].lower()
    if root in TECHNICAL_SOURCE_ROOTS:
        return True

    if is_board_bsp_root(root):
        return True

    return False


def should_include_file(repo_root: Path, path: Path) -> bool:
    """Decide whether a filesystem entry should be ingested.

    Combines all the individual classification checks (README variants,
    release notes, documentation PDFs, top-level metadata, technical source)
    into a single inclusion predicate used while walking the repo tree.

    Args:
        repo_root: Root directory of the repo clone.
        path: Candidate file path (absolute or relative to cwd).

    Returns:
        True if `path` is a file and matches at least one inclusion rule.
    """
    if not path.is_file():
        return False

    rel_path = path.relative_to(repo_root)
    return (
        is_projects_readme(rel_path)
        or is_release_notes(rel_path)
        or is_top_level_readme(rel_path)
        or is_documentation_pdf(rel_path)
        or is_top_level_metadata_file(rel_path)
        or is_technical_source_file(rel_path)
    )


def iter_repo_files(repo_root: Path) -> Iterable[Path]:
    """Recursively yield every file under `repo_root` that passes `should_include_file`.

    Args:
        repo_root: Root directory of the repo clone.

    Yields:
        Paths (relative-aware) of files to ingest.
    """
    for p in repo_root.rglob("*"):
        if should_include_file(repo_root, p):
            yield p


def extract_pdf_text(path: Path) -> str:
    """Extract plain text from a PDF using `pypdf` as a lightweight fallback.

    Used when the richer multimodal extraction (`extract_pdf_multimodal`,
    which also renders pages and detects figures) raises an exception.

    Args:
        path: Path to the PDF file.

    Returns:
        Concatenated page text, or an empty string if `pypdf` is unavailable
        or extraction fails.
    """
    if PdfReader is None:
        print(f"[WARN] pypdf not installed; cannot read PDF {path}. Install with: pip install pypdf")
        return ""

    try:
        reader = PdfReader(str(path))
        pages_text: list[str] = []
        for page in reader.pages:
            pages_text.append(page.extract_text() or "")
        return "\n".join(t for t in pages_text if t).strip()
    except Exception as exc:
        print(f"[WARN] Cannot extract PDF text from {path}: {exc}")
        return ""


def read_text_file_content(path: Path) -> tuple[str, str]:
    """Read a text file, tolerating non-UTF-8 encodings common in legacy sources.

    Args:
        path: Path to the text file.

    Returns:
        A tuple of (content, extractor_label). `extractor_label` is "text" on
        success, or "none" if the file could not be decoded/read at all.
    """
    try:
        return path.read_text(encoding="utf-8"), "text"
    except UnicodeDecodeError:
        # Some legacy STM32 source files use Latin-1; retry before giving up.
        try:
            return path.read_text(encoding="latin-1"), "text"
        except Exception as exc:
            print(f"[WARN] Cannot read {path}: {exc}")
            return "", "none"


def collect_repo_docs(repo_name: str, repo_root: Path, owner: str = "STMicroelectronics") -> list[dict]:
    """Walk a repo clone and build raw file records for every ingestible file.

    For each file matched by `iter_repo_files`, this builds a GitHub blob URL
    and reads its content: PDFs go through the multimodal figure-extraction
    pipeline (`extract_pdf_multimodal`), falling back to plain `pypdf` text
    extraction on failure; other files are read as text (UTF-8/Latin-1).

    Args:
        repo_name: Repository name (used for URLs and PDF asset folder naming).
        repo_root: Local path to the repo clone.
        owner: GitHub organization/user for URL building.

    Returns:
        A list of raw file dicts ready to be written via `write_raw_files_json`.

    Raises:
        FileNotFoundError: If `repo_root` does not exist (repo not cloned).
    """
    if not repo_root.exists():
        raise FileNotFoundError(
            f"Repository folder does not exist: {repo_root}. "
            "Check that you cloned the repository."
        )

    raw_files: list[dict] = []
    print(f"=== Scanning {repo_name} in {repo_root} ===")

    count = 0
    for file_path in iter_repo_files(repo_root):
        count += 1
        rel_path = file_path.relative_to(repo_root)
        rel_path_str = str(rel_path).replace("\\", "/")
        print(f"  [{count}] Reading file: {rel_path}")

        github_url = build_github_blob_url(
            owner=owner,
            repo_name=repo_name,
            rel_path=rel_path_str,
        )

        content = ""
        extractor = "none"
        figure_records = []
        media_urls = []
        images_count = 0
        pdf_task_file = None

        if file_path.suffix.lower() == PDF_EXTENSION:
            try:
                result = extract_pdf_multimodal(
                    pdf_path=file_path,
                    repo_name=repo_name,
                    rel_path=rel_path_str,
                    source_pdf_url=github_url,
                    data_dir=DATA_DIR,
                )
                content = result.get("content", "")
                figure_records = result.get("figure_records", [])
                images_count = result.get("figures_count", 0)
                extractor = result.get("content_extractor", "pypdf+render+opencv")
                pdf_task_file = result.get("task_file")
            except Exception as exc:
                # Multimodal extraction (render + OpenCV figure detection) can fail
                # on malformed/protected PDFs; degrade gracefully to text-only.
                print(f"[WARN] Multimodal PDF extraction failed for {file_path}: {exc}")
                content = extract_pdf_text(file_path)
                extractor = "pypdf_fallback"
                figure_records = []
                images_count = 0
        else:
            content, extractor = read_text_file_content(file_path)

        raw_files.append(
            {
                "repo": repo_name,
                "path": rel_path_str,
                "content": content,
                "encoding": "utf-8",
                "github_url": github_url,
                "media_urls": media_urls,
                "image_records": figure_records,
                "images_count": images_count,
                "content_extractor": extractor,
                "pdf_task_file": pdf_task_file,
            }
        )

    print(f"=== {len(raw_files)} files collected for {repo_name} ===")
    return raw_files


def write_raw_files_json(raw_files: list[dict], output_file: Path) -> None:
    """Serialize collected raw file records to a JSON file.

    Args:
        raw_files: List of raw file dicts from `collect_repo_docs`.
        output_file: Destination path (typically `data/raw_files_<repo>.json`).
    """
    output_file.write_text(
        json.dumps(raw_files, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Written to {output_file}")