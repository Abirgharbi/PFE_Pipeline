"""CLI: split large ST-ready `files_json` payloads into small parts for manual upload.

The ST AI Bridge datasource web UI (manual upload, no API) has practical
size/doc-count limits per uploaded JSON file. This script scans
`st_ready_files_<repo>.json` exports under `datasets/07_delivery/st_ready/by_series/`
and splits any large-enough file into multiple smaller JSON parts that each
keep the same root array key (`files` by default) so they remain valid
standalone ST-ready payloads.

Inputs:
- `datasets/07_delivery/st_ready/by_series/**/files_json/st_ready_files_*.json`
  (glob pattern configurable via `--input-dir`/`--pattern`), produced by
  `export_st_ready_files.py`.

Outputs, under `datasets/07_delivery/st_ready/manual_upload/files_json_split/<repo>/`
(base configurable via `--output-dir`):
- `<source_stem>__part<NNN>.json`: one JSON part per split chunk.
- `summary_<source_stem>__manual_split.json`: per-source split manifest
  (rules used, parts produced).
- `summary_manual_split_files_json.json` (at the output root): overall run
  manifest (processed/skipped/errored sources, totals).

Splitting can be driven by a fixed `--target-parts` count, or by
`--max-docs-per-part`/`--max-payload-kb` thresholds (checked together), and
is skipped for sources below `--min-source-size-kb` unless `--split-all` is
passed.

Run:
    python -m pipeline.delivery.split_st_ready_files_for_manual_upload
    python -m pipeline.delivery.split_st_ready_files_for_manual_upload --target-parts 4 --clean-output
"""

import argparse
import json
import os
import stat
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from shared.utils.paths import PROJECT_ROOT


BYTES_PER_KB = 1024

DEFAULT_INPUT_DIR = PROJECT_ROOT / "datasets" / "07_delivery" / "st_ready" / "by_series"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "datasets" / "07_delivery" / "st_ready" / "manual_upload" / "files_json_split"
DEFAULT_PATTERN = "**/files_json/st_ready_files_*.json"
DEFAULT_ROOT_TAG_PATH = "files"
DEFAULT_MIN_SOURCE_SIZE_KB = 350.0
DEFAULT_MAX_DOCS_PER_PART = 8
DEFAULT_MAX_PAYLOAD_KB = 220
DEFAULT_TARGET_PARTS = 0


def utc_now_iso() -> str:
    """Return the current UTC time as a second-precision ISO 8601 string."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def utc_now_for_path() -> str:
    """Return the current UTC time formatted for use in a folder/file name."""
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def on_rm_error(func: Any, path: str, _exc_info: Any) -> None:
    """`shutil.rmtree` error handler: clear read-only attributes and retry.

    Windows can leave files read-only (e.g. checked out from git), which
    blocks deletion; this best-effort handler unblocks that without failing
    the whole cleanup operation.
    """
    try:
        os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
    except OSError:
        return
    try:
        func(path)
    except OSError:
        pass


def remove_path_with_retry(path: Path, retries: int = 2) -> bool:
    """Delete a file or directory, retrying briefly on transient lock errors.

    Returns True on success (or if the path was already gone), False if it
    remains locked after all retries — the caller then falls back to a
    fresh output directory instead of failing the whole run.
    """
    for attempt in range(retries + 1):
        try:
            if path.is_dir():
                shutil.rmtree(path, onerror=on_rm_error)
            else:
                path.unlink()
            return True
        except FileNotFoundError:
            return True
        except PermissionError:
            try:
                os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
            except OSError:
                pass
            if attempt < retries:
                time.sleep(0.15)
        except OSError:
            if attempt < retries:
                time.sleep(0.15)
    return False


def clean_directory_contents(output_dir: Path) -> list[str]:
    """Delete every entry inside `output_dir` (not the directory itself).

    Returns the names of entries that could not be removed, so the caller
    can decide whether to fall back to a differently named output directory.
    """
    if not output_dir.exists():
        return []

    failed_entries: list[str] = []
    for child in output_dir.iterdir():
        if not remove_path_with_retry(child):
            failed_entries.append(child.name)
    return failed_entries


def build_fallback_output_dir(base_output_dir: Path) -> Path:
    """Build a timestamped sibling directory to use when cleaning the
    requested output directory failed (e.g. a file is locked by another process).
    """
    return base_output_dir.parent / f"{base_output_dir.name}__run_{utc_now_for_path()}"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write `payload` as pretty-printed UTF-8 JSON, creating parent dirs."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_json_object(path: Path) -> dict[str, Any]:
    """Load a JSON file and ensure its root is an object (not an array)."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object at root for {path.name}")
    return payload


def extract_docs(payload: dict[str, Any], root_tag_path: str, source_name: str) -> list[Any]:
    """Return the array stored under `root_tag_path` in `payload`, or raise
    if it is missing/not a list (the payload does not match the expected schema).
    """
    docs = payload.get(root_tag_path)
    if not isinstance(docs, list):
        raise ValueError(
            f"Invalid payload in {source_name}: missing array key '{root_tag_path}' at root"
        )
    return docs


def estimate_payload_size_bytes(root_tag_path: str, docs: list[Any]) -> int:
    """Estimate the serialized JSON size (in bytes) of `{root_tag_path: docs}`.

    Used as a proxy for the actual upload payload size when deciding split
    boundaries, without writing the file to disk first.
    """
    payload = {root_tag_path: docs}
    return len(json.dumps(payload, ensure_ascii=False).encode("utf-8"))


def estimate_st_ready_text_chars(docs: list[Any]) -> int:
    """Sum the character length of each doc's `st_ready_text` field.

    Reported per part in the split summary as a rough proxy for how much
    retrieval-relevant text content each uploaded part carries.
    """
    total = 0
    for doc in docs:
        if isinstance(doc, dict):
            text = doc.get("st_ready_text")
            if isinstance(text, str):
                total += len(text)
    return total


def infer_repo_name_from_source(source_path: Path) -> str:
    """Derive the repo name from a `st_ready_files_<repo>.json` file stem."""
    prefix = "st_ready_files_"
    stem = source_path.stem
    if stem.startswith(prefix):
        return stem[len(prefix) :]
    return stem


def split_docs_into_parts(
    docs: list[Any],
    root_tag_path: str,
    max_docs_per_part: int,
    max_payload_bytes: int,
) -> list[list[Any]]:
    """Greedily group `docs` into parts respecting both a max doc count and
    a max estimated payload size per part (whichever limit is hit first).
    """
    if not docs:
        return []

    parts: list[list[Any]] = []
    current: list[Any] = []

    for doc in docs:
        if not current:
            current = [doc]
            continue

        exceeds_docs = max_docs_per_part > 0 and (len(current) + 1) > max_docs_per_part
        exceeds_payload = False
        if not exceeds_docs and max_payload_bytes > 0:
            exceeds_payload = (
                estimate_payload_size_bytes(root_tag_path, current + [doc]) > max_payload_bytes
            )

        if exceeds_docs or exceeds_payload:
            parts.append(current)
            current = [doc]
        else:
            current.append(doc)

    if current:
        parts.append(current)

    return parts


def split_docs_into_target_parts(docs: list[Any], target_parts: int) -> list[list[Any]]:
    """Split `docs` into exactly `target_parts` contiguous, near-equal-sized
    chunks (extra remainder docs distributed to the first chunks).

    Used instead of `split_docs_into_parts` when the caller wants a fixed
    number of upload parts regardless of size/doc-count thresholds.
    """
    if not docs:
        return []
    if target_parts <= 0:
        return [docs]

    effective_parts = min(target_parts, len(docs))
    base_size = len(docs) // effective_parts
    remainder = len(docs) % effective_parts

    parts: list[list[Any]] = []
    start = 0
    for index in range(effective_parts):
        extra = 1 if index < remainder else 0
        part_size = base_size + extra
        end = start + part_size
        parts.append(docs[start:end])
        start = end

    return parts


def split_part_by_payload_limit(
    part_docs: list[Any],
    root_tag_path: str,
    max_payload_bytes: int,
) -> list[list[Any]]:
    """Recursively bisect `part_docs` until each resulting sub-part's
    estimated payload size is within `max_payload_bytes`.

    Applied after `split_docs_into_target_parts`, since a fixed-count split
    can still produce an oversized part when doc sizes are uneven.
    """
    if max_payload_bytes <= 0 or len(part_docs) <= 1:
        return [part_docs]

    payload_size = estimate_payload_size_bytes(root_tag_path=root_tag_path, docs=part_docs)
    if payload_size <= max_payload_bytes:
        return [part_docs]

    mid = len(part_docs) // 2
    if mid <= 0:
        return [part_docs]

    left = split_part_by_payload_limit(
        part_docs=part_docs[:mid],
        root_tag_path=root_tag_path,
        max_payload_bytes=max_payload_bytes,
    )
    right = split_part_by_payload_limit(
        part_docs=part_docs[mid:],
        root_tag_path=root_tag_path,
        max_payload_bytes=max_payload_bytes,
    )
    return left + right


def main() -> None:
    """CLI entry point: scan for large `files_json` exports and split them
    into manual-upload-ready parts, writing per-source and overall manifests.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Split large ST-ready files_json payloads into smaller JSON parts for manual "
            "datasource upload (without API)."
        )
    )
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--pattern", default=DEFAULT_PATTERN)
    parser.add_argument("--root-tag-path", default=DEFAULT_ROOT_TAG_PATH)
    parser.add_argument(
        "--min-source-size-kb",
        type=float,
        default=DEFAULT_MIN_SOURCE_SIZE_KB,
        help=(
            "Split only when source JSON file size is >= this value. "
            "Use 0 to disable size threshold."
        ),
    )
    parser.add_argument(
        "--max-docs-per-part",
        type=int,
        default=DEFAULT_MAX_DOCS_PER_PART,
        help="Maximum docs per split part.",
    )
    parser.add_argument(
        "--max-payload-kb",
        type=int,
        default=DEFAULT_MAX_PAYLOAD_KB,
        help=(
            "Best-effort max JSON payload size per part in KB. "
            "Use 0 to disable payload-size threshold."
        ),
    )
    parser.add_argument(
        "--target-parts",
        type=int,
        default=DEFAULT_TARGET_PARTS,
        help=(
            "Target number of parts for each source file. "
            "Use 0 to disable and rely on docs/payload thresholds."
        ),
    )
    parser.add_argument(
        "--split-all",
        action="store_true",
        help="Force splitting for all matching files (ignores --min-source-size-kb).",
    )
    parser.add_argument(
        "--clean-output",
        action="store_true",
        help="Delete output directory before writing new split files.",
    )
    args = parser.parse_args()

    if not args.root_tag_path.strip():
        raise ValueError("--root-tag-path cannot be empty")
    if args.min_source_size_kb < 0:
        raise ValueError("--min-source-size-kb must be >= 0")
    if args.max_docs_per_part <= 0:
        raise ValueError("--max-docs-per-part must be > 0")
    if args.max_payload_kb < 0:
        raise ValueError("--max-payload-kb must be >= 0")
    if args.target_parts < 0:
        raise ValueError("--target-parts must be >= 0")

    input_dir = args.input_dir.resolve()
    requested_output_dir = args.output_dir.resolve()
    output_dir = requested_output_dir
    root_tag_path = args.root_tag_path.strip()
    max_payload_bytes = args.max_payload_kb * BYTES_PER_KB

    if not input_dir.exists():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")

    source_files = sorted(input_dir.glob(args.pattern))
    if not source_files:
        raise ValueError(f"No files found in {input_dir} with pattern '{args.pattern}'")

    clean_output_failures: list[str] = []
    if args.clean_output:
        clean_output_failures = clean_directory_contents(output_dir)
        if clean_output_failures:
            output_dir = build_fallback_output_dir(requested_output_dir)
            preview = ", ".join(clean_output_failures[:5])
            if len(clean_output_failures) > 5:
                preview = f"{preview}, ..."
            print(
                "[manual_split_files_json] Warning: could not fully clean output directory "
                f"{requested_output_dir}. Locked entries: {preview}."
            )
            print(
                "[manual_split_files_json] Using fallback output directory: "
                f"{output_dir}"
            )

    output_dir.mkdir(parents=True, exist_ok=True)

    processed_sources: list[dict[str, Any]] = []
    skipped_sources: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    total_parts = 0

    for source_path in source_files:
        try:
            payload = load_json_object(source_path)
            docs = extract_docs(payload, root_tag_path=root_tag_path, source_name=source_path.name)

            source_size_bytes = source_path.stat().st_size
            source_size_kb = round(source_size_bytes / BYTES_PER_KB, 2)
            source_docs = len(docs)

            should_split = args.split_all or source_size_kb >= args.min_source_size_kb
            if not should_split and source_docs > args.max_docs_per_part:
                should_split = True
            if not should_split and args.target_parts > 0 and source_docs > args.target_parts:
                should_split = True

            if not should_split:
                skipped_sources.append(
                    {
                        "source_file": source_path.name,
                        "source_docs": source_docs,
                        "source_size_kb": source_size_kb,
                        "reason": "Below thresholds",
                    }
                )
                continue

            if args.target_parts > 0:
                parts = split_docs_into_target_parts(docs=docs, target_parts=args.target_parts)
                if max_payload_bytes > 0:
                    adjusted_parts: list[list[Any]] = []
                    for part_docs in parts:
                        adjusted_parts.extend(
                            split_part_by_payload_limit(
                                part_docs=part_docs,
                                root_tag_path=root_tag_path,
                                max_payload_bytes=max_payload_bytes,
                            )
                        )
                    parts = adjusted_parts
            else:
                parts = split_docs_into_parts(
                    docs=docs,
                    root_tag_path=root_tag_path,
                    max_docs_per_part=args.max_docs_per_part,
                    max_payload_bytes=max_payload_bytes,
                )
            if not parts:
                skipped_sources.append(
                    {
                        "source_file": source_path.name,
                        "source_docs": source_docs,
                        "source_size_kb": source_size_kb,
                        "reason": "Empty docs array",
                    }
                )
                continue

            repo_name = infer_repo_name_from_source(source_path)
            repo_out_dir = output_dir / repo_name
            repo_out_dir.mkdir(parents=True, exist_ok=True)

            part_entries: list[dict[str, Any]] = []
            for index, part_docs in enumerate(parts, start=1):
                part_file_name = f"{source_path.stem}__part{index:03d}.json"
                part_file_path = repo_out_dir / part_file_name
                part_payload = {root_tag_path: part_docs}
                write_json(part_file_path, part_payload)

                payload_kb = round(
                    estimate_payload_size_bytes(root_tag_path=root_tag_path, docs=part_docs) / BYTES_PER_KB,
                    2,
                )
                text_chars = estimate_st_ready_text_chars(part_docs)

                part_entries.append(
                    {
                        "part_index": index,
                        "file_name": part_file_name,
                        "docs": len(part_docs),
                        "estimated_payload_kb": payload_kb,
                        "st_ready_text_chars": text_chars,
                    }
                )

            summary_file_name = f"summary_{source_path.stem}__manual_split.json"
            summary_path = repo_out_dir / summary_file_name
            summary_payload = {
                "created_at_utc": utc_now_iso(),
                "source_file": source_path.name,
                "source_path": str(source_path),
                "root_tag_path": root_tag_path,
                "source_docs": source_docs,
                "source_size_kb": source_size_kb,
                "split_rules": {
                    "max_docs_per_part": args.max_docs_per_part,
                    "max_payload_kb": args.max_payload_kb,
                    "target_parts": args.target_parts,
                    "min_source_size_kb": args.min_source_size_kb,
                },
                "parts_count": len(part_entries),
                "parts": part_entries,
            }
            write_json(summary_path, summary_payload)

            processed_sources.append(
                {
                    "repo": repo_name,
                    "source_file": source_path.name,
                    "source_docs": source_docs,
                    "source_size_kb": source_size_kb,
                    "parts_count": len(part_entries),
                    "output_dir": str(repo_out_dir),
                    "summary_file": summary_file_name,
                }
            )

            total_parts += len(part_entries)

        except Exception as exc:
            errors.append({"source_file": source_path.name, "error": str(exc)})

    manifest = {
        "created_at_utc": utc_now_iso(),
        "input_dir": str(input_dir),
        "requested_output_dir": str(requested_output_dir),
        "output_dir": str(output_dir),
        "used_fallback_output_dir": output_dir != requested_output_dir,
        "pattern": args.pattern,
        "root_tag_path": root_tag_path,
        "rules": {
            "split_all": bool(args.split_all),
            "min_source_size_kb": args.min_source_size_kb,
            "max_docs_per_part": args.max_docs_per_part,
            "max_payload_kb": args.max_payload_kb,
            "target_parts": args.target_parts,
        },
        "clean_output_locked_entries": clean_output_failures,
        "processed_sources": processed_sources,
        "skipped_sources": skipped_sources,
        "errors": errors,
        "totals": {
            "sources_found": len(source_files),
            "sources_processed": len(processed_sources),
            "sources_skipped": len(skipped_sources),
            "sources_errors": len(errors),
            "parts_created": total_parts,
        },
    }
    manifest_path = output_dir / "summary_manual_split_files_json.json"
    write_json(manifest_path, manifest)

    print(
        "[manual_split_files_json] "
        f"sources_found={len(source_files)}, "
        f"processed={len(processed_sources)}, "
        f"skipped={len(skipped_sources)}, "
        f"errors={len(errors)}, "
        f"parts_created={total_parts}"
    )
    print(f"[manual_split_files_json] output_dir={output_dir}")
    print(f"[manual_split_files_json] manifest={manifest_path}")


if __name__ == "__main__":
    main()
