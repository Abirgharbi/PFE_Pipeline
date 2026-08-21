"""Export enriched STM32Cube file docs into ST-ready file cards (delivery stage).

This script is one of the final delivery exporters: it turns per-repo
`docs_files_<repo>_v2.json` (or `_v3` cleaned variant) enrichment output into
KB-ready JSON "file cards" describing README/Release-Notes/example/BSP
documents, ready for upload to the ST AI Bridge knowledge base.

Inputs:
- `data/docs_files_<repo>_v2.json` (default) or `data/docs_files_<repo>_v3.json`
  (with `--v3`), produced by `pipeline/enrichment/files_to_docs_v2.py`.
- `shared/config/config_all_series.json` (or `STM32CUBE_CONFIG`-selected
  config) for the list of repos and the `owner` used to build GitHub URLs.

Outputs (per repo), under `datasets/07_delivery/st_ready/by_series/...` via
`delivery_paths.get_repo_artifact_dir(repo, "files_json")`:
- `st_ready_files_<repo>.json` (or `_v3` suffix): `{"files": [...]}` array of
  file cards, each with a composed `st_ready_text` retrieval document.
- `summary_files_<repo>.json`: counts and export parameters for traceability.
- A backward-compatible mirror is also written under the legacy flat
  `st_ready/files_json/` folder (skipped for `--v3` to avoid overwriting the
  v2 mirror).

Run:
    python -m pipeline.delivery.export_st_ready_files --repo STM32CubeH7
    python -m pipeline.delivery.export_st_ready_files --v3 --include-invalid
"""

import argparse
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import quote

from pipeline.delivery.delivery_paths import (
    get_legacy_artifact_file,
    get_repo_artifact_dir,
)
from shared.utils.paths import DATA_DIR, PROJECT_ROOT, get_config_path

CONFIG_DIR = PROJECT_ROOT / "shared" / "config"

DEFAULT_SUMMARY_MAX_CHARS = 360
DEFAULT_TECHNICAL_MAX_CHARS = 20000


def load_config() -> dict[str, Any]:
    """Load the active series config resolved via `get_config_path()`."""
    return json.loads(get_config_path().read_text(encoding="utf-8"))


def load_all_repos() -> list[str]:
    """Load repos from all config files (all series)."""
    seen: set[str] = set()
    all_repos: list[str] = []
    for cfg_file in sorted(CONFIG_DIR.glob("config*.json")):
        cfg = json.loads(cfg_file.read_text(encoding="utf-8-sig"))
        for repo in cfg.get("repos", []):
            if repo not in seen:
                seen.add(repo)
                all_repos.append(repo)
    return all_repos


def normalize_whitespace(text: str) -> str:
    """Collapse any run of whitespace into a single space and strip ends."""
    return re.sub(r"\s+", " ", (text or "").strip())


def first_sentence(text: str, max_chars: int = 320) -> str:
    """Return the first sentence of `text` (up to `max_chars`), or a hard cut."""
    s = normalize_whitespace(text)
    if not s:
        return ""
    match = re.search(r"[.!?]", s)
    if match and match.end() <= max_chars:
        return s[: match.end()].strip()
    return s[:max_chars].strip()


def truncate_text(text: str, max_chars: int) -> tuple[str, bool]:
    """Truncate `text` to `max_chars`, returning (text, was_truncated).

    Used to cap technical document bodies so a single oversized file (e.g. a
    large PDF-extracted reference manual) does not blow up the delivery
    payload size; truncation is flagged so the KB can note incompleteness.
    """
    if max_chars <= 0:
        return "", bool(text)
    if len(text) <= max_chars:
        return text, False
    clipped = text[:max_chars].rstrip()
    return clipped, True


def build_github_url(doc: dict[str, Any], url_base: str, root_path: str) -> str | None:
    """Return the doc's GitHub URL, reconstructing it from repo/path if absent."""
    github_url = doc.get("github_url")
    if github_url:
        return github_url

    repo = doc.get("repo")
    path = doc.get("path")
    if not repo or not path:
        return None

    normalized_path = str(path).lstrip("/")
    return f"{url_base}{repo}/{root_path}/{normalized_path}"


def build_path_url(path: str | None) -> str | None:
    """URL-encode a repo-relative file path for safe embedding in a GitHub URL."""
    if not path:
        return None
    normalized_path = str(path).replace("\\", "/").lstrip("/")
    return quote(normalized_path, safe="/")


def split_root_path(root_path: str) -> tuple[str, str]:
    """Split a GitHub `"blob/master"`-style root path into (root_dir, root_ref)."""
    normalized = (root_path or "").strip("/")
    if "/" not in normalized:
        return normalized or "blob", "master"
    left, right = normalized.split("/", 1)
    return left or "blob", right or "master"


def compose_st_ready_text(
    doc: dict[str, Any],
    summary_max_chars: int,
    technical_max_chars: int,
) -> str:
    """Compose the retrieval-ready text body embedded in each file card.

    Produces a short human-readable summary line plus a (possibly truncated)
    "Technical details" section, so the KB can surface a quick summary while
    still exposing the full document content for detailed answers.
    """
    clean = normalize_whitespace(doc.get("clean_text") or "")
    snippet = first_sentence(clean, max_chars=summary_max_chars)
    technical_details, was_truncated = truncate_text(clean, technical_max_chars)

    if was_truncated:
        technical_details = (
            f"{technical_details} "
            f"[technical_details_truncated original_chars={len(clean)} kept_chars={len(technical_details)}]"
        )

    images_count = int(doc.get("images_count") or 0)
    content_extractor = doc.get("content_extractor") or "text"

    context_line = ", ".join(
        [
            f"repo={doc.get('repo')}",
            f"mcu_series={doc.get('mcu_series')}",
            f"file_type={doc.get('file_type')}",
            f"path={doc.get('path')}",
            f"board={doc.get('board')}",
            f"component={doc.get('component')}",
            f"category={doc.get('category')}",
            f"example_name={doc.get('example_name')}",
        ]
    )

    lines = [
        f"Document: {doc.get('path') or 'unknown'}",
        f"Context: {context_line}",
        f"Summary: {snippet or 'Technical reference document extracted from STM32Cube repository.'}",
        f"Visual assets: {images_count}",
        f"Content extractor: {content_extractor}",
        "Constraints: Validate against exact STM32 series/board and firmware package before applying.",
        "",
        "Technical details:",
        technical_details,
    ]
    return "\n".join(lines).strip()


def export_repo_json(
    repo: str,
    include_invalid: bool,
    summary_max_chars: int,
    technical_max_chars: int,
    use_v3: bool = False,
) -> tuple[int, int, Path]:
    """Export one repo's `docs_files_*.json` into a `st_ready_files_*.json` card set.

    Reads the enrichment file for `repo` (v2 by default, v3 when `use_v3`),
    filters out invalid docs unless `include_invalid`, builds one file card per
    remaining doc, and writes the per-series output plus a legacy mirror and a
    summary file.

    Returns (total_docs_in_input, exported_docs_count, output_directory).
    """
    # v3 is an alternate cleaned dataset used for controlled A/B comparisons;
    # it is written to separate `_v3`-suffixed files so it never overwrites
    # the v2 delivery output that may already be uploaded to the KB.
    suffix = "_v3" if use_v3 else "_v2"
    in_path = DATA_DIR / f"docs_files_{repo.lower()}{suffix}.json"
    if not in_path.exists():
        raise FileNotFoundError(f"Input file not found: {in_path}")

    out_root = get_repo_artifact_dir(repo, "files_json")
    out_root.mkdir(parents=True, exist_ok=True)

    cfg = load_config()
    owner = cfg.get("owner", "STMicroelectronics")
    url_base = f"https://github.com/{owner}/"
    root_path = "blob/master"
    root_dir, root_ref = split_root_path(root_path)

    docs = json.loads(in_path.read_text(encoding="utf-8"))
    total = len(docs)

    payload_docs: list[dict[str, Any]] = []
    for doc in docs:
        if not include_invalid and not doc.get("is_valid", True):
            continue

        payload_docs.append(
            {
                "id": doc.get("id"),
                "url_base": url_base,
                "repo": doc.get("repo"),
                "root_path": root_path,
                "root_dir": root_dir,
                "root_ref": root_ref,
                "mcu_series": doc.get("mcu_series"),
                "path": doc.get("path"),
                "path_url": build_path_url(doc.get("path")),
                "file_type": doc.get("file_type"),
                "board": doc.get("board"),
                "category": doc.get("category"),
                "component": doc.get("component"),
                "example_name": doc.get("example_name"),
                "github_url": build_github_url(doc, url_base=url_base, root_path=root_path),
                "image_urls": doc.get("image_urls") or [],
                "image_records": doc.get("image_records") or [],
                "images_count": doc.get("images_count") or 0,
                "content_extractor": doc.get("content_extractor") or "text",
                "pdf_task_file": doc.get("pdf_task_file"),
                "is_valid": doc.get("is_valid"),
                "delivery_template": "st_v2_structured_file_card",
                "st_ready_text": compose_st_ready_text(
                    doc,
                    summary_max_chars=summary_max_chars,
                    technical_max_chars=technical_max_chars,
                ),
            }
        )

    export_payload = {
        "files": payload_docs,
    }

    version_tag = "_v3" if use_v3 else ""
    out_file_name = f"st_ready_files_{repo.lower()}{version_tag}.json"
    out_file = out_root / out_file_name
    out_file.write_text(json.dumps(export_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    # Backward-compatible mirror in legacy flat folder (skip for v3 to avoid overwrite).
    if not use_v3:
        legacy_out_file = get_legacy_artifact_file("files_json", out_file_name)
        legacy_out_file.parent.mkdir(parents=True, exist_ok=True)
        legacy_out_file.write_text(json.dumps(export_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    summary = {
        "repo": repo,
        "input_file": str(in_path),
        "output_file": str(out_file),
        "total_docs": total,
        "exported_docs": len(payload_docs),
        "include_invalid": include_invalid,
        "format": "json",
        "root_tag_path": "files",
        "summary_max_chars": summary_max_chars,
        "technical_max_chars": technical_max_chars,
        "cleaning_version": "v3" if use_v3 else "v2",
    }
    summary_file_name = f"summary_files_{repo.lower()}{version_tag}.json"
    (out_root / summary_file_name).write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )

    if not use_v3:
        legacy_summary_file = get_legacy_artifact_file("files_json", summary_file_name)
        legacy_summary_file.parent.mkdir(parents=True, exist_ok=True)
        legacy_summary_file.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    return total, len(payload_docs), out_root


def main() -> None:
    """CLI entry point: export ST-ready file cards for each configured repo."""
    parser = argparse.ArgumentParser(description="Export docs_files_v2 into ST-ready JSON file cards.")
    parser.add_argument("--repo", action="append", help="Repo name, e.g., STM32CubeH7. Can be repeated.")
    parser.add_argument("--v3", action="store_true", help="Use V3 cleaned inputs and write to _v3 output files (no overwrite).")
    parser.add_argument("--include-invalid", action="store_true", help="Include is_valid=false docs.")
    parser.add_argument(
        "--summary-max-chars",
        type=int,
        default=DEFAULT_SUMMARY_MAX_CHARS,
        help=f"Maximum characters for the summary sentence (default: {DEFAULT_SUMMARY_MAX_CHARS})",
    )
    parser.add_argument(
        "--technical-max-chars",
        type=int,
        default=DEFAULT_TECHNICAL_MAX_CHARS,
        help=f"Maximum characters for technical details per document (default: {DEFAULT_TECHNICAL_MAX_CHARS})",
    )
    args = parser.parse_args()

    if args.summary_max_chars <= 0:
        raise ValueError("--summary-max-chars must be > 0")
    if args.technical_max_chars <= 0:
        raise ValueError("--technical-max-chars must be > 0")
    if args.technical_max_chars < args.summary_max_chars:
        raise ValueError("--technical-max-chars must be >= --summary-max-chars")

    cfg = load_config()
    repos = args.repo or (load_all_repos() if args.v3 else cfg.get("repos", []))

    if not repos:
        raise ValueError("No repos provided and no repos found in config.")

    for repo in repos:
        try:
            total, exported, out_root = export_repo_json(
                repo=repo,
                include_invalid=args.include_invalid,
                summary_max_chars=args.summary_max_chars,
                technical_max_chars=args.technical_max_chars,
                use_v3=args.v3,
            )
            tag = " [V3 clean]" if args.v3 else ""
            print(f"[ST-READY:json:files] {repo}: exported {exported}/{total} -> {out_root}{tag}")
        except FileNotFoundError as e:
            print(f"[SKIP] {repo}: {e}")
            continue


if __name__ == "__main__":
    main()
