"""
Enrich ST-ready / PR JSON records by describing embedded images with Alfred Vision.

Role in the automation layer:
    ST-ready delivery JSON (issues, files, resolver cases, diagnostic cards) and raw
    PR/issue JSON often reference screenshots via markdown/HTML image tags,
    ``[IMAGE ATTACHED]`` markers, or an explicit ``image_urls`` field. This script
    downloads each referenced image, sends it to the Alfred Vision API
    (persona ``mdrf_stgithub_analyzer_client``) for a technical description plus
    OCR text, and injects the result back into the record's main text field
    (replacing the placeholder/marker) so downstream KB search and RAG retrieval
    can use the image content as plain text. This is the script referenced by the
    mode's "Alfred Image Enrichment" workflow, typically run against
    ``issues_json/st_ready_issues_with_images_<repo>.json`` before KB upload.

Inputs:
    - One or more ``--input`` JSON files: either a top-level list of records, or a
      dict with a list under a known key (``issues``, ``files``, ``resolver_cases``,
      ``diagnostic_cards``, etc.).
        - Alfred Vision API credentials via env vars: ``ALFRED_CLIENT_APP_NAME``,
            ``ALFRED_API_KEY`` (preferred) or ``ST_CHATGPT_API_KEY``
            (or ``ST_AI_BRIDGE_API_KEY``/``ST_API_KEY``),
      ``ALFRED_API_URL``.

Outputs:
    - A new JSON file (or the input file itself with ``--inplace``) with:
      * the main text field updated to replace image placeholders with
        ``[IMAGE DESCRIPTION] ...`` / ``[IMAGE TEXT] ...`` (unless ``--no-replace-text``),
      * an ``image_analyses`` / ``image_analyses_count`` field per record (unless
        ``--strip-analyses``),
    - A companion ``<output>__alfred_summary.json`` with run statistics.

Usage:
    python pipeline_Automation/alfred/enrich_json_images_with_alfred.py --input <file> --inplace
    python pipeline_Automation/alfred/enrich_json_images_with_alfred.py --input a.json --input b.json --use-proxy
    python pipeline_Automation/alfred/enrich_json_images_with_alfred.py --input <file> --inplace --strip-analyses
"""

import argparse
import base64
import io
import json
import mimetypes
import os
import random
import re
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import hashlib

from PIL import Image
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- Alfred Vision API credentials (persona: mdrf_stgithub_analyzer_client) ---
VISION_CLIENT_APP_NAME = os.getenv("ALFRED_CLIENT_APP_NAME", "mdrf_stgithub_analyzer_client").strip()
VISION_API_KEY = (
    os.getenv("ALFRED_API_KEY")
    or os.getenv("ST_CHATGPT_API_KEY")
    or os.getenv("ST_AI_BRIDGE_API_KEY")
    or os.getenv("ST_API_KEY")
    or ""
).strip()
VISION_URL = os.getenv("ALFRED_API_URL", "https://api-ai-bridge.st.com/chatgpt/api/client-apps").strip()
CHAT_SERVICE_NAME = "chat"

VISION_PROXIES = {
    "http": "http://185.46.212.88:80",
    "https": "http://185.46.212.88:80",
}


def generate_vision_token(timestamp: int, nonce: int) -> str:
    """Generate SHA1 auth token for Alfred Vision API."""
    data_string = f"{VISION_CLIENT_APP_NAME}_{CHAT_SERVICE_NAME}_{VISION_API_KEY}_{timestamp}_{nonce}"
    return hashlib.sha1(data_string.encode("utf-8")).hexdigest()
DEFAULT_PERSONA = "st_copilot"
DEFAULT_TIMEOUT_SECONDS = 120
DEFAULT_MAX_RETRIES = 3
DEFAULT_MAX_RESPONSE_TOKENS = 1024
DEFAULT_MAX_IMAGE_BYTES = 6_000_000

MARKDOWN_IMAGE_RE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)", flags=re.IGNORECASE)
HTML_IMAGE_RE = re.compile(
    r"<img\b[^>]*?\bsrc\s*=\s*['\"]([^'\"]+)['\"][^>]*>", flags=re.IGNORECASE
)
IMAGE_ATTACHED_RE = re.compile(r"\[IMAGE ATTACHED\]", flags=re.IGNORECASE)
DIRECT_URL_RE = re.compile(r"https?://[^\s\]>'\")]+", flags=re.IGNORECASE)


SYSTEM_PROMPT = (
    "You analyze screenshots from GitHub issues and pull requests related to embedded software support. "
    "Return plain text only, no markdown, in this exact format: "
    "DESCRIPTION: <technical visual summary>\n"
    "OCR_TEXT: <all readable text from image, keep line breaks with \\n when possible, write NONE if unreadable>."
)

USER_PROMPT_TEMPLATE = (
    "Analyze this screenshot for support knowledge extraction.\n"
    "Context: {context}\n"
    "Provide a technical description and extract all visible text exactly when readable."
)


def normalize_url(value: str) -> str:
    """Strip surrounding whitespace and angle brackets (``<url>`` markdown form) from a URL."""
    return (value or "").strip().strip("<>")


def dedupe_keep_order(values: list[str]) -> list[str]:
    """Return normalized values with duplicates removed, preserving first-seen order."""
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        key = normalize_url(value)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out


def looks_like_image_url(value: str) -> bool:
    """Heuristically decide whether a URL points to an image (extension or known host pattern)."""
    value = normalize_url(value)
    if not value.startswith("http://") and not value.startswith("https://"):
        return False

    low = value.lower()
    if any(low.endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg")):
        return True
    if "user-attachments" in low and "/assets/" in low:
        return True
    if "github.com" in low and "/assets/" in low:
        return True
    if "objects.githubusercontent.com" in low:
        return True

    return False


def parse_markdown_image_url(raw_group: str) -> str:
    """Extract the URL portion from a markdown image target, handling ``<url>`` and ``url "title"`` forms."""
    value = (raw_group or "").strip()
    if not value:
        return ""

    # Markdown image can be: URL or <URL> or URL "title"
    if value.startswith("<") and ">" in value:
        return normalize_url(value[: value.index(">") + 1])

    return normalize_url(value.split()[0])


def extract_image_urls_from_text(text: str) -> list[str]:
    """Find candidate image URLs in free text: markdown images, HTML <img> tags, and bare URLs."""
    if not isinstance(text, str) or not text:
        return []

    urls: list[str] = []

    for match in MARKDOWN_IMAGE_RE.finditer(text):
        parsed = parse_markdown_image_url(match.group(1))
        if looks_like_image_url(parsed):
            urls.append(parsed)

    for match in HTML_IMAGE_RE.finditer(text):
        parsed = normalize_url(match.group(1))
        if looks_like_image_url(parsed):
            urls.append(parsed)

    for match in DIRECT_URL_RE.finditer(text):
        parsed = normalize_url(match.group(0))
        if looks_like_image_url(parsed):
            urls.append(parsed)

    return dedupe_keep_order(urls)


def extract_image_urls_from_record(record: dict[str, Any]) -> list[str]:
    """Collect all image URLs for a record from its ``image_urls`` field and known text fields."""
    urls: list[str] = []

    raw_urls = record.get("image_urls")
    if isinstance(raw_urls, list):
        for value in raw_urls:
            if isinstance(value, str) and looks_like_image_url(value):
                urls.append(value)
    elif isinstance(raw_urls, str) and looks_like_image_url(raw_urls):
        urls.append(raw_urls)

    for text_field in ("st_ready_text", "resolver_card_text", "body", "clean_text", "text", "description"):
        value = record.get(text_field)
        if isinstance(value, str) and value:
            urls.extend(extract_image_urls_from_text(value))

    return dedupe_keep_order(urls)


def detect_mime_type(image_url: str, content_type_header: str | None) -> str:
    """Determine an image MIME type from the HTTP response header, falling back to the URL extension."""
    if content_type_header:
        mime = content_type_header.split(";")[0].strip().lower()
        if mime.startswith("image/"):
            return mime

    guessed, _ = mimetypes.guess_type(urlparse(image_url).path)
    if guessed and guessed.startswith("image/"):
        return guessed

    return "image/png"


def download_image_as_data_url(
    image_url: str,
    timeout_seconds: int,
    use_proxy: bool,
    max_image_bytes: int,
) -> tuple[str, str, int]:
    """Download an image URL and return it as a base64 data URL, converting to PNG/JPG if needed.

    Alfred's vision endpoint only accepts ``image/png`` or ``image/jpg`` payloads,
    so any other detected MIME type is transcoded to PNG via Pillow. Streams the
    download and aborts early if it exceeds ``max_image_bytes`` to avoid loading
    unexpectedly large files into memory.

    Returns:
        Tuple of (data_url, mime_type, byte_size).

    Raises:
        ValueError: if the image is too large, empty, or cannot be converted.
    """
    response = requests.get(
        image_url,
        timeout=timeout_seconds,
        verify=False,
        proxies=VISION_PROXIES if use_proxy else None,
        allow_redirects=True,
        stream=True,
        headers={"User-Agent": "st-github-analyzer-image-enricher/1.0"},
    )
    response.raise_for_status()

    chunks: list[bytes] = []
    total_size = 0
    for chunk in response.iter_content(chunk_size=8192):
        if not chunk:
            continue
        total_size += len(chunk)
        if total_size > max_image_bytes:
            raise ValueError(
                f"Image too large ({total_size} bytes) for URL {image_url}. "
                f"Increase --max-image-bytes if needed."
            )
        chunks.append(chunk)

    image_bytes = b"".join(chunks)
    if not image_bytes:
        raise ValueError(f"Downloaded image is empty: {image_url}")

    mime_type = detect_mime_type(image_url, response.headers.get("Content-Type"))

    # Alfred only accepts data:image/png;base64 or data:image/jpg;base64
    ACCEPTED_MIMES = {"image/png", "image/jpg"}
    # Normalize image/jpeg -> image/jpg (Alfred rejects "jpeg")
    if mime_type == "image/jpeg":
        mime_type = "image/jpg"
    if mime_type not in ACCEPTED_MIMES:
        try:
            img = Image.open(io.BytesIO(image_bytes))
            buf = io.BytesIO()
            img.convert("RGB").save(buf, format="PNG")
            image_bytes = buf.getvalue()
            mime_type = "image/png"
            total_size = len(image_bytes)
        except Exception as exc:
            raise ValueError(f"Cannot convert {mime_type} to PNG for {image_url}: {exc}") from exc

    encoded = base64.b64encode(image_bytes).decode("ascii")
    data_url = f"data:{mime_type};base64,{encoded}"
    return data_url, mime_type, total_size


def extract_text_from_response(response_json: dict[str, Any]) -> str | None:
    """Best-effort extraction of the completion text from an Alfred API response, trying known response shapes."""
    if not isinstance(response_json, dict):
        return None

    completion = response_json.get("completion")
    if isinstance(completion, str) and completion.strip():
        return completion.strip()

    for key in ("text", "content", "message", "answer"):
        value = response_json.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    choices = response_json.get("choices")
    if isinstance(choices, list) and choices:
        first = choices[0]
        if isinstance(first, dict):
            msg = first.get("message")
            if isinstance(msg, dict):
                content = msg.get("content")
                if isinstance(content, str) and content.strip():
                    return content.strip()

            for key in ("content", "text"):
                value = first.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()

    data_obj = response_json.get("data")
    if isinstance(data_obj, dict):
        completion = data_obj.get("completion")
        if isinstance(completion, str) and completion.strip():
            return completion.strip()

    return None


def parse_description_sections(text: str) -> tuple[str, str]:
    """Split Alfred's structured completion into (description, ocr_text) using the DESCRIPTION/OCR_TEXT markers.

    Falls back to treating the whole text as the description if the expected
    markers are absent, and treats a literal "NONE" OCR value as empty.
    """
    value = (text or "").strip()
    if not value:
        return "", ""

    desc_match = re.search(r"(?is)DESCRIPTION\s*:\s*(.*?)(?:\n\s*OCR_TEXT\s*:|$)", value)
    ocr_match = re.search(r"(?is)OCR_TEXT\s*:\s*(.*)$", value)

    description = desc_match.group(1).strip() if desc_match else value
    ocr_text = ocr_match.group(1).strip() if ocr_match else ""

    if ocr_text.upper() == "NONE":
        ocr_text = ""

    return description, ocr_text


def call_alfred_for_image(
    *,
    data_url: str,
    context: str,
    persona: str,
    remote_user: str | None,
    temperature: float,
    max_response_tokens: int,
    response_format: str,
    reasoning_effort: str | None,
    max_retries: int,
    timeout_seconds: int,
    use_proxy: bool,
) -> dict[str, Any]:
    """Send one image (as data URL) plus context to Alfred Vision and return its parsed analysis.

    Retries across attempts and, within each attempt, tries both "seconds" and
    "milliseconds" timestamp formats since the backend has been observed to
    reject one or the other depending on deployment (error code 2000).

    Returns:
        Dict with keys ``completion``, ``description``, ``ocr_text``.

    Raises:
        ValueError: if required credentials are missing.
        RuntimeError: if all retry attempts fail or the response has no usable text.
    """
    if not VISION_CLIENT_APP_NAME:
        raise ValueError("Missing Alfred client app name. Set ALFRED_CLIENT_APP_NAME.")
    if not VISION_API_KEY:
        raise ValueError(
            "Missing Alfred API key. Set ALFRED_API_KEY "
            "(or ST_CHATGPT_API_KEY/ST_AI_BRIDGE_API_KEY/ST_API_KEY)."
        )

    timestamp_modes = ["seconds", "milliseconds"]
    user_prompt = USER_PROMPT_TEMPLATE.format(context=context)

    last_error: Exception | None = None

    for attempt in range(1, max_retries + 1):
        for mode_idx, mode in enumerate(timestamp_modes):
            timestamp = int(time.time()) if mode == "seconds" else int(time.time() * 1000)
            nonce = random.randint(0, 999999)
            token = generate_vision_token(timestamp, nonce)

            headers = {
                "Content-Type": "application/json",
                "stchatgpt-auth-token": token,
                "stchatgpt-auth-nonce": str(nonce),
            }

            payload: dict[str, Any] = {
                "version": 1,
                "clientAppName": VISION_CLIENT_APP_NAME,
                "service": CHAT_SERVICE_NAME,
                "timestamp": timestamp,
                "temperature": temperature,
                "maxResponseTokens": max_response_tokens,
                "responseFormat": response_format,
                "persona": persona,
                "messages": [
                    {
                        "role": "system",
                        "content": SYSTEM_PROMPT,
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "content": user_prompt,
                            },
                            {
                                "type": "image",
                                "content": data_url,
                            },
                        ],
                    },
                ],
            }
            if remote_user:
                payload["remoteUser"] = remote_user
            if reasoning_effort:
                payload["reasoningEffort"] = reasoning_effort

            try:
                response = requests.post(
                    VISION_URL,
                    json=payload,
                    headers=headers,
                    timeout=timeout_seconds,
                    verify=False,
                    proxies=VISION_PROXIES if use_proxy else None,
                )
                response.raise_for_status()
                response_json = response.json()
            except requests.exceptions.RequestException as exc:
                last_error = exc
                if attempt < max_retries:
                    time.sleep(2**attempt)
                    break
                raise RuntimeError(f"Alfred request failed: {exc}") from exc
            except ValueError as exc:
                last_error = exc
                if attempt < max_retries:
                    time.sleep(2**attempt)
                    break
                raise RuntimeError("Alfred response is not valid JSON.") from exc

            error_code = response_json.get("errorCode")
            error_message = str(response_json.get("message") or "")
            if error_code not in (None, 0):
                # Retry with alternate timestamp if backend rejects timestamp format.
                if error_code == 2000 and "timestamp" in error_message.lower() and mode_idx == 0:
                    continue

                last_error = RuntimeError(f"Alfred API error: errorCode={error_code}, message={error_message}")
                if attempt < max_retries:
                    time.sleep(2**attempt)
                    break
                raise last_error

            completion = extract_text_from_response(response_json)
            if not completion:
                raise RuntimeError(f"Unable to extract completion text from response: {response_json}")

            description, ocr_text = parse_description_sections(completion)
            return {
                "completion": completion,
                "description": description,
                "ocr_text": ocr_text,
            }

    if last_error:
        raise RuntimeError(f"Alfred request failed: {last_error}") from last_error

    raise RuntimeError("Alfred request failed with unknown error.")


def build_record_context(record: dict[str, Any], image_url: str) -> str:
    """Build a short context string (repo/id/title/url) sent to Alfred to help it interpret the image."""
    context_parts: list[str] = []
    for key in ("repo", "id", "issue_number", "pr_number", "issue_title", "title", "github_url"):
        value = record.get(key)
        if value is None:
            continue
        context_parts.append(f"{key}={value}")
    context_parts.append(f"image_url={image_url}")
    return ", ".join(context_parts)


def build_inline_image_text(analysis: dict[str, Any]) -> str:
    """Format one image analysis as inline text (``[IMAGE DESCRIPTION] ... [IMAGE TEXT] ...``) for text replacement."""
    if analysis.get("status") != "ok":
        return "[IMAGE DESCRIPTION UNAVAILABLE]"

    description = str(analysis.get("description") or "").strip()
    ocr_text = str(analysis.get("ocr_text") or "").strip()

    parts: list[str] = []
    if description:
        parts.append(f"[IMAGE DESCRIPTION] {description}")
    if ocr_text:
        parts.append(f"[IMAGE TEXT] {ocr_text}")
    if not parts:
        return "[IMAGE DESCRIPTION UNAVAILABLE]"
    return " ".join(parts)


def replace_markdown_image_tags(text: str, analyses_by_url: dict[str, dict[str, Any]]) -> tuple[str, int]:
    """Replace markdown image tags in text with their Alfred analysis, when a matching URL was analyzed."""
    replaced = 0

    def _repl(match: re.Match[str]) -> str:
        # Leave the tag untouched if this URL was not part of the analyzed set.
        nonlocal replaced
        parsed_url = parse_markdown_image_url(match.group(1))
        analysis = analyses_by_url.get(parsed_url)
        if not analysis:
            return match.group(0)
        replaced += 1
        return build_inline_image_text(analysis)

    return MARKDOWN_IMAGE_RE.sub(_repl, text), replaced


def replace_html_image_tags(text: str, analyses_by_url: dict[str, dict[str, Any]]) -> tuple[str, int]:
    """Replace HTML <img> tags in text with their Alfred analysis, when a matching URL was analyzed."""
    replaced = 0

    def _repl(match: re.Match[str]) -> str:
        nonlocal replaced
        parsed_url = normalize_url(match.group(1))
        analysis = analyses_by_url.get(parsed_url)
        if not analysis:
            return match.group(0)
        replaced += 1
        return build_inline_image_text(analysis)

    return HTML_IMAGE_RE.sub(_repl, text), replaced


def replace_image_attached_markers(text: str, ordered_analyses: list[dict[str, Any]]) -> tuple[str, int]:
    """Replace ``[IMAGE ATTACHED]`` markers in order with the corresponding analysis result.

    Markers are matched positionally against ``ordered_analyses`` since raw
    ``[IMAGE ATTACHED]`` markers (unlike markdown/HTML tags) carry no URL to
    match by.
    """
    idx = 0

    def _repl(_: re.Match[str]) -> str:
        nonlocal idx
        if idx < len(ordered_analyses):
            value = build_inline_image_text(ordered_analyses[idx])
            idx += 1
            return value
        return "[IMAGE DESCRIPTION UNAVAILABLE]"

    updated = IMAGE_ATTACHED_RE.sub(_repl, text)
    return updated, idx


def select_main_text_field(record: dict[str, Any]) -> str | None:
    """Return the name of the first known text field present on the record, or None if none match."""
    for key in ("st_ready_text", "resolver_card_text", "body", "clean_text", "text", "description"):
        value = record.get(key)
        if isinstance(value, str):
            return key
    return None


def append_image_context_block(text: str, analyses: list[dict[str, Any]]) -> str:
    """Append a fallback "Image-derived context" section listing all image analyses.

    Used when no recognizable image placeholder was found in the text, so the
    analysis is not silently dropped.
    """
    lines = ["", "", "Image-derived context:"]
    for idx, analysis in enumerate(analyses, start=1):
        url_value = str(analysis.get("image_url") or "")
        if analysis.get("status") != "ok":
            lines.append(f"{idx}. URL: {url_value}")
            lines.append(f"   Description: [ERROR] {analysis.get('error')}")
            continue

        desc = str(analysis.get("description") or "")
        ocr = str(analysis.get("ocr_text") or "")

        lines.append(f"{idx}. URL: {url_value}")
        lines.append(f"   Description: {desc if desc else '[none]'}")
        if ocr:
            lines.append(f"   OCR Text: {ocr}")

    return text + "\n".join(lines)


def find_records_container(data: Any) -> tuple[Any, list[dict[str, Any]], str | None]:
    """Locate the list of record dicts inside parsed JSON, whether it's a top-level list or nested under a known key.

    Returns:
        Tuple of (container, records, root_key). ``container`` is the original
        parsed object (to be reassembled on write), ``root_key`` is the dict key
        the records were found under (None if the input was a top-level list).

    Raises:
        ValueError: if the JSON structure doesn't match any supported shape.
    """
    if isinstance(data, list):
        records = [item for item in data if isinstance(item, dict)]
        return data, records, None

    if isinstance(data, dict):
        preferred_keys = [
            "issues",
            "pull_requests",
            "prs",
            "items",
            "records",
            "files",
            "resolver_cases",
            "diagnostic_cards",
        ]
        for key in preferred_keys:
            value = data.get(key)
            if isinstance(value, list):
                records = [item for item in value if isinstance(item, dict)]
                return data, records, key

    raise ValueError("Unsupported JSON structure: expected list or dict with a list field.")


def transform_records(
    records: list[dict[str, Any]],
    *,
    persona: str,
    remote_user: str | None,
    temperature: float,
    max_response_tokens: int,
    response_format: str,
    reasoning_effort: str | None,
    max_retries: int,
    timeout_seconds: int,
    use_proxy: bool,
    max_records: int,
    max_images_per_record: int,
    max_image_bytes: int,
    replace_text: bool,
    append_when_no_placeholder: bool,
    strip_analyses: bool = False,
) -> dict[str, int]:
    """Analyze images for each record and optionally rewrite its text field in place.

    Iterates records that contain at least one image URL, calls Alfred for each
    (unless already cached in this run, since the same screenshot can be quoted
    in multiple text fields of the same record), stores an ``image_analyses``
    list on the record, and — unless ``replace_text`` is False — replaces
    markdown/HTML/``[IMAGE ATTACHED]`` placeholders in the main text field with
    the analysis text.

    Returns:
        A stats dict with counters used for the run summary.
    """
    stats = {
        "records_total": len(records),
        "records_processed": 0,
        "records_with_images": 0,
        "records_updated_text": 0,
        "images_found": 0,
        "images_described_ok": 0,
        "images_failed": 0,
        "cache_hits": 0,
    }

    cache: dict[str, dict[str, Any]] = {}

    for index, record in enumerate(records):
        if max_records > 0 and index >= max_records:
            break

        image_urls = extract_image_urls_from_record(record)
        if max_images_per_record > 0:
            image_urls = image_urls[:max_images_per_record]

        if not image_urls:
            continue

        stats["records_processed"] += 1
        stats["records_with_images"] += 1
        stats["images_found"] += len(image_urls)
        print(f"  [{stats['records_processed']}/{stats['records_with_images']}] Record {record.get('id', index)} — {len(image_urls)} image(s)")

        analyses: list[dict[str, Any]] = []
        img_counter = 0

        for image_url in image_urls:
            img_counter += 1
            if image_url in cache:
                stats["cache_hits"] += 1
                analyses.append(dict(cache[image_url]))
                continue

            analysis: dict[str, Any] = {
                "image_url": image_url,
                "status": "error",
                "description": "",
                "ocr_text": "",
                "error": "",
            }

            try:
                print(f"    img {img_counter}/{len(image_urls)}: downloading...", end="", flush=True)
                data_url, mime_type, image_size = download_image_as_data_url(
                    image_url=image_url,
                    timeout_seconds=timeout_seconds,
                    use_proxy=use_proxy,
                    max_image_bytes=max_image_bytes,
                )

                print(f" calling Alfred...", end="", flush=True)
                context = build_record_context(record, image_url=image_url)
                response_data = call_alfred_for_image(
                    data_url=data_url,
                    context=context,
                    persona=persona,
                    remote_user=remote_user,
                    temperature=temperature,
                    max_response_tokens=max_response_tokens,
                    response_format=response_format,
                    reasoning_effort=reasoning_effort,
                    max_retries=max_retries,
                    timeout_seconds=timeout_seconds,
                    use_proxy=use_proxy,
                )

                analysis.update(
                    {
                        "status": "ok",
                        "mime_type": mime_type,
                        "image_size": image_size,
                        "description": response_data.get("description") or "",
                        "ocr_text": response_data.get("ocr_text") or "",
                        "completion": response_data.get("completion") or "",
                    }
                )
                stats["images_described_ok"] += 1
                print(f" OK")
            except Exception as exc:  # noqa: BLE001 - keep processing on failures
                analysis["error"] = str(exc)
                stats["images_failed"] += 1
                print(f"  [ERROR] {image_url[:80]}... -> {exc}")  # diagnostic

            cache[image_url] = dict(analysis)
            analyses.append(analysis)

        record["image_analyses"] = analyses
        record["image_analyses_count"] = len([a for a in analyses if a.get("status") == "ok"])

        if strip_analyses:
            record.pop("image_analyses", None)
            record.pop("image_analyses_count", None)

        if not replace_text:
            continue

        text_field = select_main_text_field(record)
        if not text_field:
            continue

        original_text = record.get(text_field)
        if not isinstance(original_text, str):
            continue

        by_url = {str(item.get("image_url") or ""): item for item in analyses}

        updated_text, replaced_markdown = replace_markdown_image_tags(original_text, by_url)
        updated_text, replaced_html = replace_html_image_tags(updated_text, by_url)
        updated_text, replaced_markers = replace_image_attached_markers(updated_text, analyses)

        replaced_total = replaced_markdown + replaced_html + replaced_markers

        if replaced_total == 0 and append_when_no_placeholder:
            updated_text = append_image_context_block(updated_text, analyses)
            replaced_total = 1

        if replaced_total > 0 and updated_text != original_text:
            record[text_field] = updated_text
            stats["records_updated_text"] += 1

    return stats


def build_output_path(input_path: Path, output_dir: Path | None, inplace: bool) -> Path:
    """Compute the output file path: the input path itself if ``inplace``, else a sibling ``*_with_alfred_image_text`` file."""
    if inplace:
        return input_path

    out_name = f"{input_path.stem}_with_alfred_image_text{input_path.suffix}"
    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir / out_name

    return input_path.with_name(out_name)


def process_file(
    input_path: Path,
    output_path: Path,
    *,
    persona: str,
    remote_user: str | None,
    temperature: float,
    max_response_tokens: int,
    response_format: str,
    reasoning_effort: str | None,
    max_retries: int,
    timeout_seconds: int,
    use_proxy: bool,
    max_records: int,
    max_images_per_record: int,
    max_image_bytes: int,
    replace_text: bool,
    append_when_no_placeholder: bool,
    strip_analyses: bool = False,
) -> dict[str, Any]:
    """Load one input JSON file, enrich its records via Alfred, and write the result plus a summary file.

    Returns:
        A summary dict (also written to ``<output>__alfred_summary.json``) with
        input/output paths and the stats from ``transform_records``.

    Raises:
        FileNotFoundError: if ``input_path`` does not exist.
    """
    if not input_path.exists():
        raise FileNotFoundError(f"Input JSON file not found: {input_path}")

    # Be tolerant to UTF-8 BOM (common with some PowerShell writes).
    data = json.loads(input_path.read_text(encoding="utf-8-sig"))
    container, records, root_key = find_records_container(data)

    stats = transform_records(
        records=records,
        persona=persona,
        remote_user=remote_user,
        temperature=temperature,
        max_response_tokens=max_response_tokens,
        response_format=response_format,
        reasoning_effort=reasoning_effort,
        max_retries=max_retries,
        timeout_seconds=timeout_seconds,
        use_proxy=use_proxy,
        max_records=max_records,
        max_images_per_record=max_images_per_record,
        max_image_bytes=max_image_bytes,
        replace_text=replace_text,
        append_when_no_placeholder=append_when_no_placeholder,
        strip_analyses=strip_analyses,
    )

    if isinstance(container, list):
        output_data: Any = container
    else:
        output_data = dict(container)
        if root_key:
            output_data[root_key] = records

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output_data, ensure_ascii=False, indent=2), encoding="utf-8")

    summary = {
        "input_file": str(input_path),
        "output_file": str(output_path),
        "root_key": root_key or "<list>",
        **stats,
    }

    summary_path = output_path.with_name(f"{output_path.stem}__alfred_summary.json")
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    return summary


def parse_args() -> argparse.Namespace:
    """Define and parse the CLI arguments for this script."""
    parser = argparse.ArgumentParser(
        description=(
            "Read image URLs from ST-ready/PR JSON, send images (base64 data URL) to Alfred vision, "
            "and write a new JSON with image analyses and optional text replacement."
        )
    )
    parser.add_argument(
        "--input",
        action="append",
        required=True,
        help="Input JSON path. Can be repeated.",
    )
    parser.add_argument(
        "--output-dir",
        help="Optional output directory. By default, output file is created next to input.",
    )
    parser.add_argument("--inplace", action="store_true", help="Overwrite input JSON files.")
    parser.add_argument("--persona", default=DEFAULT_PERSONA, help=f"Persona name (default: {DEFAULT_PERSONA}).")
    parser.add_argument("--remote-user", default="", help="Remote user email, if required by persona policy.")
    parser.add_argument("--temperature", type=float, default=0.2, help="Sampling temperature.")
    parser.add_argument(
        "--max-response-tokens",
        type=int,
        default=DEFAULT_MAX_RESPONSE_TOKENS,
        help=f"Max response tokens (default: {DEFAULT_MAX_RESPONSE_TOKENS}).",
    )
    parser.add_argument(
        "--response-format",
        choices=["text", "json_object"],
        default="text",
        help="Response format requested to chat API.",
    )
    parser.add_argument(
        "--reasoning-effort",
        choices=["none", "low", "medium", "high"],
        default=None,
        help="Reasoning effort when supported by backend model.",
    )
    parser.add_argument("--max-retries", type=int, default=DEFAULT_MAX_RETRIES, help="Retry attempts per image.")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS, help="HTTP timeout in seconds.")
    parser.add_argument("--use-proxy", action="store_true", help="Use proxy settings from Get_Persona_KBs.py.")
    parser.add_argument(
        "--max-records",
        type=int,
        default=0,
        help="Process only first N records (0 = all). Useful for pilot runs.",
    )
    parser.add_argument(
        "--max-images-per-record",
        type=int,
        default=4,
        help="Limit number of images processed per record (0 = all).",
    )
    parser.add_argument(
        "--max-image-bytes",
        type=int,
        default=DEFAULT_MAX_IMAGE_BYTES,
        help=f"Max downloaded image size in bytes (default: {DEFAULT_MAX_IMAGE_BYTES}).",
    )
    parser.add_argument(
        "--no-replace-text",
        action="store_true",
        help="Do not modify text fields. Only append image_analyses metadata.",
    )
    parser.add_argument(
        "--no-append-image-context",
        action="store_true",
        help="When no image placeholder is found, do not append an image-derived context block.",
    )
    parser.add_argument(
        "--strip-analyses",
        action="store_true",
        help="Remove image_analyses and image_analyses_count from output (lighter JSON for KB upload).",
    )
    return parser.parse_args()


def main() -> None:
    """CLI entry point: process each ``--input`` file and print a JSON run summary."""
    args = parse_args()

    output_dir = Path(args.output_dir).resolve() if args.output_dir else None
    replace_text = not args.no_replace_text
    append_when_no_placeholder = not args.no_append_image_context
    strip_analyses = args.strip_analyses

    if args.max_retries <= 0:
        raise ValueError("--max-retries must be > 0")
    if args.timeout <= 0:
        raise ValueError("--timeout must be > 0")
    if args.max_response_tokens <= 0:
        raise ValueError("--max-response-tokens must be > 0")
    if args.max_image_bytes <= 0:
        raise ValueError("--max-image-bytes must be > 0")

    summaries: list[dict[str, Any]] = []

    for raw_input_path in args.input:
        input_path = Path(raw_input_path).expanduser().resolve()
        output_path = build_output_path(input_path, output_dir=output_dir, inplace=args.inplace)

        summary = process_file(
            input_path=input_path,
            output_path=output_path,
            persona=args.persona,
            remote_user=(args.remote_user.strip() or None),
            temperature=args.temperature,
            max_response_tokens=args.max_response_tokens,
            response_format=args.response_format,
            reasoning_effort=args.reasoning_effort,
            max_retries=args.max_retries,
            timeout_seconds=args.timeout,
            use_proxy=args.use_proxy,
            max_records=args.max_records,
            max_images_per_record=args.max_images_per_record,
            max_image_bytes=args.max_image_bytes,
            replace_text=replace_text,
            append_when_no_placeholder=append_when_no_placeholder,
            strip_analyses=strip_analyses,
        )
        summaries.append(summary)

        print(
            f"[OK] {input_path.name} -> {output_path.name} | "
            f"records_with_images={summary['records_with_images']} "
            f"images_ok={summary['images_described_ok']} images_failed={summary['images_failed']}"
        )

    print("\nRun summary:")
    print(json.dumps(summaries, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
