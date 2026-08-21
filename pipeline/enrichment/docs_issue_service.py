"""Legacy (V1) helper to convert a single clean issue into an enriched doc.

Role in the pipeline: used only by the legacy `issues_to_docs.py` CLI script.
Unlike the V2 model (`preprocessing_model.PreprocessingModelIssuesV2`), it
does not apply layer/severity/issue_kind/board/component heuristics or
validity filtering -- it only shapes the raw clean issue dict into the
common "doc" schema shared with `docs_issue_service`-style outputs.

Input: a single clean issue dict (as read from `clean_issues_<repo>.json`).
Output: a single enriched doc dict (written by callers into
`docs_issues_<repo>.json`).
"""

from typing import Any

from pipeline.chunking.chunk_service import mcu_series_from_repo


def clean_issue_to_doc(issue: dict[str, Any], ingest_version: str = "v1.0") -> dict[str, Any]:
    """Convert one clean issue dict into a legacy (V1) enriched doc dict.

    Args:
        issue: Clean issue dict as produced by the cleaning stage, expected
            to contain keys like `repo`, `issue_number`, `labels`,
            `clean_text`, `image_urls`, `images_count`, etc.
        ingest_version: Version tag stored in the output doc's
            `ingest_version` field, for traceability.

    Returns:
        A doc dict with a stable `id` (`<repo>-issue-<number>`), derived
        `mcu_series`, and passthrough fields from the source issue. No
        heuristic classification (layer/severity/board/component) is applied
        here.
    """
    repo = issue.get("repo")
    issue_number = issue.get("issue_number")
    labels = issue.get("labels") or []
    labels_lower = [lbl.lower() for lbl in labels]
    # A confirmed bug is any issue explicitly labeled as such (as opposed to
    # e.g. usage questions or configuration help).
    is_confirmed_bug = any(lbl in ("bug", "internal bug tracker") for lbl in labels_lower)

    doc_id = f"{(repo or '').lower()}-issue-{issue_number}"

    clean_text = issue.get("clean_text") or ""
    image_urls = issue.get("image_urls") or []
    images_count = issue.get("images_count") or 0

    return {
        "id": doc_id,
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
        "ingest_version": ingest_version,
        "clean_text": clean_text,
        "image_urls": image_urls,
        "images_count": images_count,
    }
