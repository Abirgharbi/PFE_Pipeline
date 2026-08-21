"""Core V2 enrichment models for issues and files.

Role in the pipeline: this module implements the main enrichment logic used
by `issues_to_docs_v2.py` and `files_to_docs_v2.py`. It classifies issues
(bug/question/config-help), detects layer/severity/board/component signals,
flags validity (with a "rescue" mechanism for technical false negatives),
and builds the final "doc" dict schema (with `mcu_series`, `github_url`,
etc.) shared by downstream similarity and chunking stages.

No file I/O happens here; callers (the CLI scripts above) read
`clean_issues_<repo>.json` / `clean_files_<repo>[_v3].json` and write
`docs_issues_<repo>_v2.json` / `docs_files_<repo>_v2[_v3].json`.
"""

import re
import hashlib
from typing import Any
from urllib.parse import quote

from pipeline.chunking.chunk_service import mcu_series_from_repo
from pipeline.enrichment.stm32cube_preprocessing_heuristics import detect_layer, detect_severity


def classify_issue_kind(text: str, labels: list[str]) -> str:
    """Classify an issue into a coarse kind based on labels and text.

    Priority: an explicit "bug"/"internal bug tracker" label always wins.
    Otherwise falls back to simple keyword heuristics for usage questions and
    configuration help, defaulting to "other" when nothing matches.

    Args:
        text: Cleaned issue text (title + body).
        labels: GitHub labels attached to the issue.

    Returns:
        One of "bug_report", "usage_question", "configuration_help", "other".
    """
    labels_lower = [lbl.lower() for lbl in labels]

    if "bug" in labels_lower or "internal bug tracker" in labels_lower:
        return "bug_report"

    txt_lower = text.lower()
    if "how to" in txt_lower or "how do i" in txt_lower or "question" in labels_lower:
        return "usage_question"

    if "configuration" in txt_lower or "configure" in txt_lower or "clock configuration" in txt_lower:
        return "configuration_help"

    return "other"


def has_invalid_label(labels: list[str]) -> bool:
    """Return True if any label marks the issue as invalid/duplicate/wontfix.

    Used by the validity filter in `PreprocessingModelIssuesV2` to exclude
    low-value issues from the knowledge base by default.
    """
    labels_lower = [lbl.lower() for lbl in labels]
    return any(lbl in ("invalid", "duplicate", "wontfix") for lbl in labels_lower)


# Regex signals suggesting the issue describes a concrete, reproducible
# technical problem (HAL/LL API usage, DMA, blocking behavior, faults, etc.).
# Used to "rescue" issues that would otherwise be filtered out as invalid
# (e.g. mislabeled or short) but contain strong technical evidence.
RESCUE_SIGNAL_PATTERNS = [
    r"\bHAL_[A-Za-z0-9_]+\b",
    r"\bLL_[A-Za-z0-9_]+\b",
    r"\bDMA\b",
    r"\bstuck\s+busy\b",
    r"\bblocking\b",
    r"\bdeadlock\b",
    r"\btimeout\b",
    r"\bhardfault\b|\bhard\s+fault\b",
    r"\bcallback\b",
    r"\breproduc(e|ible|tion)\b",
]


def detect_rescue_signals(text: str) -> list[str]:
    """Find which rescue-signal regex patterns match in the given text.

    Args:
        text: Cleaned issue text to scan.

    Returns:
        The subset of `RESCUE_SIGNAL_PATTERNS` (as raw pattern strings) that
        matched at least once, case-insensitively.
    """
    txt = text or ""
    found: list[str] = []
    for pattern in RESCUE_SIGNAL_PATTERNS:
        if re.search(pattern, txt, flags=re.IGNORECASE):
            found.append(pattern)
    return found


def compute_issue_evidence_strength(
    clean_text: str,
    is_confirmed_bug: bool,
    rescue_signal_count: int,
    is_valid: bool,
) -> str:
    """Score how strong the technical evidence in an issue is.

    Combines two proxies for technical specificity: the count of "anchor"
    tokens (all-caps identifiers or SNAKE_CASE-style names, e.g. API/macro
    names) and the count of matched rescue signals (see
    `detect_rescue_signals`). An invalid issue is always scored "low"
    regardless of other signals.

    Args:
        clean_text: Cleaned issue text.
        is_confirmed_bug: Whether the issue carries a confirmed-bug label.
        rescue_signal_count: Number of rescue signals detected in the text.
        is_valid: Whether the issue passed the validity filter.

    Returns:
        "high", "medium", or "low".
    """
    if not is_valid:
        return "low"

    # Anchor tokens approximate technical specificity: ALL_CAPS identifiers
    # (e.g. HAL macros) or snake_case-looking names (e.g. function/param names).
    anchor_matches = re.findall(r"\b([A-Z]{2,}[A-Z0-9_\-]{1,}|[A-Za-z]+_[A-Za-z0-9_]+)\b", clean_text or "")
    anchor_count = len(anchor_matches)

    if is_confirmed_bug and (anchor_count >= 2 or rescue_signal_count >= 2):
        return "high"
    if rescue_signal_count >= 2 or anchor_count >= 2:
        return "medium"
    return "low"


# Board name patterns recognized in issue/file text; ordered from most
# specific (Nucleo board names) to generic MCU part-number prefixes.
BOARD_REGEXES = [
    r"NUCLEO-[A-Z0-9]+",
    r"STM32H7[0-9A-Z]+",
    r"STM32F4[0-9A-Z]+",
    r"STM32F7[0-9A-Z]+",
]


def detect_board(text: str) -> str | None:
    """Detect the first matching board/MCU part-number pattern in text.

    Args:
        text: Text to search (uppercased internally for matching).

    Returns:
        The matched board string (as found in the uppercased text), or None
        if no `BOARD_REGEXES` pattern matches.
    """
    txt_upper = text.upper()
    for pattern in BOARD_REGEXES:
        match = re.search(pattern, txt_upper)
        if match:
            return match.group(0)
    return None


# Keyword groups used to guess the STM32 peripheral/middleware component an
# issue or file is about. Keys are the resulting `component` value; values
# are lowercase substrings searched for in the (space-padded) lowered text.
COMPONENT_KEYWORDS = {
    "ETH": ["ethernet", " lan ", " eth "],
    "USB": ["usb", "usb device", "usb_device"],
    "ADC": ["adc"],
    "DMA": [" dma "],
    "UART": ["uart", "usart"],
    "CAN": ["fdcan", " bxcan", " hal_can_", " can1", " can2", "can bus", "canfd"],
    "FREERTOS": ["freertos"],
}


def detect_component(text: str) -> str | None:
    """Detect the first matching STM32 component/peripheral keyword group.

    Args:
        text: Text to search (lowered and padded with spaces internally so
            single-word keywords with leading/trailing spaces can match at
            the text boundaries).

    Returns:
        The component key (e.g. "ETH", "USB", "DMA") from `COMPONENT_KEYWORDS`
        whose first matching keyword is found earliest in dict order, or
        None if nothing matches.
    """
    txt_lower = f" {text.lower()} "
    for component, keywords in COMPONENT_KEYWORDS.items():
        for kw in keywords:
            if kw in txt_lower:
                return component
    return None


def build_file_github_url(repo: str | None, path: str | None, owner: str = "STMicroelectronics") -> str | None:
    """Build a GitHub "blob" URL for a file path within a repo.

    Args:
        repo: Repository name (e.g. "STM32CubeH7").
        path: File path within the repo (may use backslashes; normalized to
            forward slashes and URL-escaped).
        owner: GitHub organization/owner, defaults to "STMicroelectronics".

    Returns:
        A `https://github.com/<owner>/<repo>/blob/master/<path>` URL, or None
        if `repo` or `path` is missing.
    """
    if not repo or not path:
        return None
    path_norm = path.replace("\\", "/").lstrip("/")
    path_escaped = quote(path_norm, safe="/")
    return f"https://github.com/{owner}/{repo}/blob/master/{path_escaped}"


def build_stable_file_doc_id(repo: str | None, path: str | None) -> str:
    """Build a deterministic file doc ID that is stable across Python runs.

    Uses SHA1 over the normalized key ``<repo_lower>:<path_forward_slash>``
    and keeps the existing ``<repo>-file-...`` prefix shape so downstream
    chunk IDs and exports remain structurally compatible.
    """
    repo_key = (repo or "").lower()
    path_key = (path or "").replace("\\", "/").lstrip("/")
    digest = hashlib.sha1(f"{repo_key}:{path_key}".encode("utf-8")).hexdigest()[:16]
    return f"{repo_key}-file-{digest}"


class PreprocessingConfig:
    """Feature-flag configuration for the V2 preprocessing/enrichment models.

    Attributes:
        version: Ingest version tag stored on produced docs.
        enable_filtering: Whether to apply the short-text/invalid-label
            validity filter (with rescue) to issues.
        enable_issue_kind: Whether to compute `issue_kind` for issues.
        enable_board_detection: Whether to run `detect_board`.
        enable_component_detection: Whether to run `detect_component`.
    """

    def __init__(self, version: str = "v2.0") -> None:
        """Initialize config with all detection features enabled by default."""
        self.version = version
        self.enable_filtering = True
        self.enable_issue_kind = True
        self.enable_board_detection = True
        self.enable_component_detection = True


class PreprocessingModelIssuesV2:
    """V2 enrichment model that turns a clean issue dict into a doc dict."""

    def __init__(self, config: PreprocessingConfig | None = None) -> None:
        """Initialize with the given config, or a default `PreprocessingConfig`."""
        self.config = config or PreprocessingConfig()

    def process_clean_issue(self, issue: dict[str, Any]) -> dict[str, Any]:
        """Enrich a single clean issue into the V2 doc schema.

        Applies (depending on `self.config` flags): validity filtering with a
        rescue mechanism for technical false negatives, evidence-strength
        scoring, layer/severity detection, issue-kind classification, and
        board/component detection.

        Args:
            issue: Clean issue dict (from `clean_issues_<repo>.json`).

        Returns:
            An enriched doc dict with the standard fields (id, mcu_series,
            github_url, labels, ...) plus `is_valid`, `rescue_applied`,
            `rescue_signal_count`, `evidence_strength`,
            `filter_invalid_reasons`, `layer`, `severity`, and optionally
            `issue_kind`, `board`, `component`.
        """
        repo = issue.get("repo")
        issue_number = issue.get("issue_number")
        labels: list[str] = issue.get("labels") or []
        labels_lower = [lbl.lower() for lbl in labels]

        clean_text: str = issue.get("clean_text") or ""

        is_confirmed_bug = any(lbl in ("bug", "internal bug tracker") for lbl in labels_lower)

        is_valid = True
        invalid_reasons: list[str] = []
        if self.config.enable_filtering:
            if len(clean_text) < 100:
                is_valid = False
                invalid_reasons.append("short_text")
            if has_invalid_label(labels):
                is_valid = False
                invalid_reasons.append("invalid_label")

        rescue_signals = detect_rescue_signals(clean_text)
        rescue_applied = False
        if not is_valid and rescue_signals and len(clean_text) >= 120:
            # Rescue likely technical false negatives (e.g., mislabeled but reproducible HAL/DMA regressions).
            is_valid = True
            rescue_applied = True

        evidence_strength = compute_issue_evidence_strength(
            clean_text=clean_text,
            is_confirmed_bug=is_confirmed_bug,
            rescue_signal_count=len(rescue_signals),
            is_valid=is_valid,
        )

        doc: dict[str, Any] = {
            "id": f"{(repo or '').lower()}-issue-{issue_number}",
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
            "ingest_version": self.config.version,
            "clean_text": clean_text,
            "image_urls": issue.get("image_urls") or [],
            "images_count": issue.get("images_count") or 0,
            "is_valid": is_valid,
            "rescue_applied": rescue_applied,
            "rescue_signal_count": len(rescue_signals),
            "evidence_strength": evidence_strength,
            "filter_invalid_reasons": invalid_reasons,
        }

        doc["layer"] = detect_layer(clean_text)
        doc["severity"] = detect_severity(clean_text, labels)

        if self.config.enable_issue_kind:
            doc["issue_kind"] = classify_issue_kind(clean_text, labels)

        if self.config.enable_board_detection:
            board = detect_board(clean_text)
            if board:
                doc["board"] = board

        if self.config.enable_component_detection:
            component = detect_component(clean_text)
            if component:
                doc["component"] = component

        return doc


class PreprocessingModelFilesV2:
    """V2 enrichment model that turns a clean file dict into a doc dict."""

    def __init__(self, config: PreprocessingConfig | None = None) -> None:
        """Initialize with the given config, or a default `PreprocessingConfig`."""
        self.config = config or PreprocessingConfig()

    def process_clean_file(self, file_obj: dict[str, Any]) -> dict[str, Any]:
        """Enrich a single clean file record into the V2 doc schema.

        Args:
            file_obj: Clean file dict (from `clean_files_<repo>[_v3].json`),
                expected to contain keys like `repo`, `path`, `clean_text`,
                `file_type`, `media_urls`, `image_records`.

        Returns:
            An enriched doc dict with a deterministic stable `id`
            (`<repo>-file-<sha1(repo:path)>`), derived `mcu_series`, `github_url`
            (built from `repo`/`path` if not already present), `is_valid`
            flag (based on cleaned text length), and detected `board`,
            `component`, and `example_name` (extracted from an `Examples/`
            path segment) when applicable.
        """
        repo = file_obj.get("repo")
        path = file_obj.get("path") or ""
        clean_text: str = file_obj.get("clean_text") or ""
        file_type: str = file_obj.get("file_type") or "other"
        media_urls: list[str] = file_obj.get("media_urls") or []
        image_records: list[dict[str, Any]] = file_obj.get("image_records") or []

        legacy_doc_id = f"{(repo or '').lower()}-file-{abs(hash(path))}"
        doc_id = build_stable_file_doc_id(repo=repo, path=path)
        is_valid = len(clean_text) >= 100

        doc: dict[str, Any] = {
            "id": doc_id,
            "legacy_id": legacy_doc_id,
            "source_kind": "file",
            "repo": repo,
            "mcu_package": repo,
            "mcu_series": mcu_series_from_repo(repo),
            "type": "file",
            "path": path,
            "file_type": file_type,
            "github_url": file_obj.get("github_url") or build_file_github_url(repo=repo, path=path),
            "board": None,
            "category": None,
            "component": None,
            "example_name": None,
            "ingest_version": self.config.version,
            "clean_text": clean_text,
            "image_urls": media_urls,
            "image_records": image_records,
            "images_count": file_obj.get("images_count") or len(image_records),
            "content_extractor": file_obj.get("content_extractor") or "text",
            "pdf_task_file": file_obj.get("pdf_task_file"),
            "is_valid": is_valid,
        }

        text_for_detection = path + "\n" + clean_text

        board = detect_board(text_for_detection)
        if board:
            doc["board"] = board

        component = detect_component(text_for_detection)
        if component:
            doc["component"] = component

        # Example projects live under an "Examples/<ExampleName>/..." path
        # segment; extract that name to use as a human-readable label.
        parts = path.replace("\\", "/").split("/")
        if "Examples" in parts:
            idx = parts.index("Examples")
            if idx + 1 < len(parts):
                doc["example_name"] = parts[idx + 1]

        return doc
