"""Shared chunk-building helpers for the chunking stage.

Role in the pipeline: reused by all chunking CLI scripts
(`docs_to_chunks_issues_v2.py`, `docs_to_chunks_files_v2.py`,
`docs_to_chunks_issues.py`, `issues_to_chunks.py`) to split a doc's
`clean_text` into one or more RAG-ready "chunk" dicts (each with an `id`,
`text`, and `metadata` dict). Also provides `mcu_series_from_repo`, used
both here and by the enrichment stage to derive `mcu_series` from a repo
name.

No file I/O happens in this module; it is pure text/dict transformation.
"""

from typing import Any


def mcu_series_from_repo(repo: str | None) -> str | None:
    """Infer the coarse MCU series (e.g. "H7", "F4", "H5") from a repo name.

    Args:
        repo: Repository name (e.g. "STM32CubeH7"), or None.

    Returns:
        The matched series string, or None if `repo` is falsy or no known
        series substring is found. Note: checks are ordered and only the
        first match wins, so a repo name containing multiple series
        substrings would only report the first one checked.
    """
    if not repo:
        return None
    repo = repo.upper()
    if "H7" in repo:
        return "H7"
    if "F4" in repo:
        return "F4"
    if "H5" in repo:
        return "H5"
    return None


def split_by_paragraphs(text: str, max_chars: int = 1200) -> list[str]:
    """Split text into chunks of at most `max_chars`, preferring paragraph breaks.

    Paragraphs (separated by blank lines) are greedily packed into the
    current chunk as long as the running length stays within `max_chars`.
    A single paragraph longer than `max_chars` is hard-split into
    fixed-size slices, since it cannot be kept whole without exceeding the
    limit.

    Args:
        text: Full text to split (e.g. a doc's `clean_text`).
        max_chars: Maximum number of characters per chunk.

    Returns:
        A list of chunk strings, in original order. Empty if `text` has no
        non-blank paragraphs.
    """
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    current = ""

    for p in paragraphs:
        # Oversized paragraphs can't fit in one chunk on their own, so slice
        # them into max_chars-sized pieces before the normal packing logic.
        while len(p) > max_chars:
            chunks.append(p[:max_chars])
            p = p[max_chars:]

        if len(current) + len(p) + 2 <= max_chars:
            # Still room in the current chunk (+2 accounts for the "\n\n" join).
            current = (current + "\n\n" + p).strip() if current else p.strip()
        else:
            # Adding this paragraph would overflow: flush current chunk and
            # start a new one with this paragraph.
            if current:
                chunks.append(current)
            current = p.strip()

    if current:
        chunks.append(current)

    return chunks


def doc_issue_to_chunks(doc: dict[str, Any], max_chars: int = 1200) -> list[dict[str, Any]]:
    """Split an enriched issue doc into one or more chunk dicts.

    Args:
        doc: Enriched issue doc (from `docs_issues_<repo>_v2[_sim].json`),
            expected to contain `clean_text` and an `id`.
        max_chars: Maximum characters per chunk, forwarded to
            `split_by_paragraphs`.

    Returns:
        A list of chunk dicts, each with:
        - `id`: `<doc_id>-<chunk_index>`.
        - `text`: the chunk's text slice.
        - `metadata`: a copy of `doc` (minus `clean_text`, to avoid
          duplicating the full text) plus `chunk_index` and `chunk_count`.
        Falls back to a single chunk containing the (possibly empty) full
        text if paragraph splitting yields no parts.
    """
    text = doc.get("clean_text") or ""
    parts = split_by_paragraphs(text, max_chars=max_chars)

    chunks: list[dict[str, Any]] = []

    if not parts:
        parts = [text]

    chunk_count = len(parts)
    base_id = doc.get("id") or "unknown-doc"

    for idx, part in enumerate(parts):
        metadata = dict(doc)
        metadata.pop("clean_text", None)

        metadata["chunk_index"] = idx
        metadata["chunk_count"] = chunk_count

        chunks.append(
            {
                "id": f"{base_id}-{idx}",
                "text": part,
                "metadata": metadata,
            }
        )

    return chunks


def doc_file_to_chunks(doc: dict[str, Any], max_chars: int = 1200) -> list[dict[str, Any]]:
    """Split an enriched file doc into one or more chunk dicts.

    Identical logic to `doc_issue_to_chunks`, kept as a separate function
    for clarity/symmetry between the issues and files chunking pipelines
    (and to allow future divergence, e.g. file-type-specific splitting).

    Args:
        doc: Enriched file doc (from `docs_files_<repo>_v2.json`), expected
            to contain `clean_text` and an `id`.
        max_chars: Maximum characters per chunk, forwarded to
            `split_by_paragraphs`.

    Returns:
        A list of chunk dicts (see `doc_issue_to_chunks` for the shape).
    """
    text = doc.get("clean_text") or ""
    parts = split_by_paragraphs(text, max_chars=max_chars)

    chunks: list[dict[str, Any]] = []

    if not parts:
        parts = [text]

    chunk_count = len(parts)
    base_id = doc.get("id") or "unknown-file"

    for idx, part in enumerate(parts):
        metadata = dict(doc)
        metadata.pop("clean_text", None)

        metadata["chunk_index"] = idx
        metadata["chunk_count"] = chunk_count

        chunks.append(
            {
                "id": f"{base_id}-{idx}",
                "text": part,
                "metadata": metadata,
            }
        )

    return chunks


def clean_issue_to_chunk(issue: dict, ingest_version: str = "v1.0") -> dict:
    """Convert a raw clean issue directly into a single legacy (V1) chunk.

    Role in the pipeline: used only by the legacy `issues_to_chunks.py` CLI
    script, which skips the enrichment stage entirely and chunks clean
    issues directly (always as exactly one chunk, unlike the V2 flow which
    splits `clean_text` by paragraphs).

    Args:
        issue: Clean issue dict (from `clean_issues_<repo>.json`).
        ingest_version: Version tag stored in the chunk's metadata.

    Returns:
        A single chunk dict with `id` `<repo>-issue-<number>-0`, the full
        `clean_text` as `text`, and a `metadata` dict mirroring the legacy
        V1 doc schema (see `docs_issue_service.clean_issue_to_doc`).
    """
    repo = issue.get("repo")
    issue_number = issue.get("issue_number")

    text = issue.get("clean_text") or ""
    labels = issue.get("labels") or []
    labels_lower = [lbl.lower() for lbl in labels]
    is_confirmed_bug = any(lbl in ("bug", "internal bug tracker") for lbl in labels_lower)

    image_urls = issue.get("image_urls") or []
    images_count = issue.get("images_count") or 0

    metadata = {
        "source_kind": "issue",
        "repo": repo,
        "mcu_package": repo,
        "mcu_series": mcu_series_from_repo(repo),
        "type": "issue",
        "path": None,
        "github_url": issue.get("github_url"),
        "board": None,
        "category": None,
        "component": None,
        "example_name": None,
        "issue_number": issue_number,
        "issue_title": issue.get("title") or "",
        "state": issue.get("state"),
        "labels": labels,
        "is_confirmed_bug": is_confirmed_bug,
        "created_at": issue.get("created_at"),
        "closed_at": issue.get("closed_at"),
        "chunk_index": 0,
        "chunk_count": 1,
        "ingest_version": ingest_version,
        "image_urls": image_urls,
        "images_count": images_count,
    }

    return {
        "id": f"{(repo or '').lower()}-issue-{issue_number}-0",
        "text": text,
        "metadata": metadata,
    }
