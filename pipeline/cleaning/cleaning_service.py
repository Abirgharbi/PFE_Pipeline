"""Service module: sanitize raw GitHub issue records into clean, RAG-friendly text.

Role in the pipeline
---------------------
Used by `pipeline/cleaning/clean_issues.py`. Converts a raw issue record
(from `data/raw_issues_<repo>.json`) into a single normalized `clean_text`
block (title, body, comments) while stripping inline `<img>` HTML and
collecting the image URLs it points to, for later use by
`pipeline/ingestion` PDF/image handling and Alfred image enrichment.

Inputs
------
- A raw issue dict as produced by `GitHubService.fetch_all_issues`.

Outputs
-------
- A clean issue dict (`build_clean_issue`) with `clean_text`, `image_urls`,
  `images_count`, and the passthrough issue metadata.

This module has no CLI entry point; it is imported, not run directly.
"""

import re

# Matches an HTML <img> tag and captures its src attribute so image URLs can
# be extracted before the tag itself is replaced by a placeholder.
IMG_TAG_RE = re.compile(r"<img\b[^>]*src=[\"']([^\"']+)[\"'][^>]*>", re.IGNORECASE)


def normalize_newlines(text: str) -> str:
    """Normalize Windows/old-Mac line endings to plain `\\n`.

    Args:
        text: Raw text that may contain `\\r\\n` or `\\r` line endings.

    Returns:
        The text with all line endings converted to `\\n`.
    """
    return text.replace("\r\n", "\n").replace("\r", "\n")


def clean_body_or_comment(text: str) -> tuple[str, list[str]]:
    """Clean a single issue body or comment: normalize text and extract images.

    Each `<img src="...">` tag is replaced by a `[IMAGE ATTACHED]` placeholder
    (kept in-place so later stages, e.g. Alfred enrichment, know exactly
    where an image was referenced) while its URL is collected separately.
    Backticks are stripped to avoid noisy inline-code markdown artifacts.

    Args:
        text: Raw issue body or comment text (may contain HTML).

    Returns:
        A tuple of (cleaned text, list of image URLs found, in order of
        appearance).
    """
    if not text:
        return "", []

    text = normalize_newlines(text)
    image_urls: list[str] = []

    def repl(match: re.Match) -> str:
        url = match.group(1)
        image_urls.append(url)
        return "[IMAGE ATTACHED]"

    text = IMG_TAG_RE.sub(repl, text)
    text = text.replace("`", "")
    text = text.strip()
    return text, image_urls


def build_clean_issue(issue: dict) -> dict:
    """Build a single normalized clean-text record from a raw issue.

    Assembles the issue title, cleaned body, and cleaned comments (each
    tagged with author/timestamp) into one `clean_text` block suitable for
    downstream enrichment/chunking, while preserving key metadata fields and
    aggregating all image URLs referenced anywhere in the issue.

    Args:
        issue: A raw issue dict (title, body, comments, labels, etc.).

    Returns:
        A clean issue dict with `clean_text`, `image_urls`, `images_count`,
        and passthrough metadata (repo, issue_number, state, labels, dates,
        github_url).
    """
    lines: list[str] = []

    title = issue.get("title") or ""
    lines.append(f"Title: {title}")
    lines.append("")

    body_raw = issue.get("body") or ""
    body_clean, body_images = clean_body_or_comment(body_raw)

    lines.append("Body:")
    lines.append(body_clean if body_clean else "(no body)")
    lines.append("")

    all_image_urls: list[str] = []
    all_image_urls.extend(body_images)

    comments = issue.get("comments") or []
    if comments:
        lines.append("Comments:")
        for c in comments:
            author = (c.get("author") or "unknown").strip()
            created = c.get("created_at") or ""
            comment_raw = c.get("body") or ""
            comment_clean, comment_images = clean_body_or_comment(comment_raw)
            all_image_urls.extend(comment_images)

            lines.append(f"[{author} - {created}]")
            lines.append(comment_clean if comment_clean else "(empty comment)")
            lines.append("")

    clean_text = "\n".join(lines).strip()

    return {
        "repo": issue.get("repo"),
        "issue_number": issue.get("issue_number"),
        "title": issue.get("title") or "",
        "state": issue.get("state"),
        "labels": issue.get("labels") or [],
        "created_at": issue.get("created_at"),
        "closed_at": issue.get("closed_at"),
        "github_url": issue.get("github_url"),
        "clean_text": clean_text,
        "image_urls": all_image_urls,
        "images_count": len(all_image_urls),
    }
