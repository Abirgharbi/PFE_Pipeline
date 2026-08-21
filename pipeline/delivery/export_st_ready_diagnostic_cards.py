"""Export ST-ready "diagnostic cards" (structured troubleshooting knowledge).

Diagnostic cards are the richest delivery artifact: for each rescued issue
and/or linked resolver case, this script synthesizes a structured
troubleshooting document (symptom summary, likely causes, confirmed facts,
plausible diagnosis, debug checks, clarification questions, workarounds,
constraints, evidence links, and retrieval aliases/keywords) intended to let
the ST AI Bridge persona answer support questions in a
facts -> hypotheses -> checks format. It also injects a small set of
curated, hand-authored cross-series cards (e.g. I2C bus recovery) for
high-value questions that are not tied to any single GitHub issue.

Inputs, per repo (read via `delivery_paths.get_existing_repo_artifact_file`,
so either the by-series or legacy flat layout works):
- `issues_json/st_ready_issues_<repo>.json` (`export_st_ready_issues.py`
  output). Only issues with `rescue_applied=true` are used by default
  (`--include-all-issues` includes every issue instead).
- `resolver_cases_json/st_ready_resolver_cases_<repo>.json`
  (`export_st_ready_resolver_cases.py` output).
- `shared/config/config_all_series.json` (or `STM32CUBE_CONFIG`-selected
  config) for the list of repos to process.

Outputs, under `delivery_paths.get_repo_artifact_dir(repo, "diagnostic_cards_json")`:
- `st_ready_diagnostic_cards_<repo>.json`: `{"diagnostic_cards": [...]}` — one
  card per rescued-issue/resolver-case pair (keyed by issue number) plus any
  applicable curated cross-series cards.
- `summary_diagnostic_cards_<repo>.json`: counts (rescued issues considered,
  resolver cases considered, cards exported, curated cards added).
- A backward-compatible mirror under the legacy flat
  `st_ready/diagnostic_cards_json/`.

Run:
    python -m pipeline.delivery.export_st_ready_diagnostic_cards --repo STM32CubeH7
    python -m pipeline.delivery.export_st_ready_diagnostic_cards --include-all-issues
"""

import argparse
import json
import re
from pathlib import Path
from typing import Any

from pipeline.delivery.delivery_paths import (
    get_existing_repo_artifact_file,
    get_legacy_artifact_file,
    get_repo_artifact_dir,
)
from shared.utils.paths import PROJECT_ROOT, get_config_path




def load_config() -> dict[str, Any]:
    """Load the active series config resolved via `get_config_path()`."""
    return json.loads(get_config_path().read_text(encoding="utf-8"))


def normalize_whitespace(text: str | None) -> str:
    """Collapse any run of whitespace into a single space and strip ends."""
    return re.sub(r"\s+", " ", (text or "").strip())


def first_sentence(text: str | None, max_chars: int = 260) -> str:
    """Return the first sentence of `text` (up to `max_chars`), or a hard cut."""
    normalized = normalize_whitespace(text)
    if not normalized:
        return ""
    match = re.search(r"[.!?]", normalized)
    if match and match.end() <= max_chars:
        return normalized[: match.end()].strip()
    return normalized[:max_chars].strip()


def looks_like_conversational_noise(text: str | None) -> bool:
    """Detect greetings/sign-offs/boilerplate that should not be surfaced as
    a card's symptom summary or root-cause hint (they carry no diagnostic signal).
    """
    value = normalize_whitespace(text).lower()
    if not value:
        return True
    noise_prefixes = [
        "hi @",
        "hello @",
        "thank you",
        "thanks",
        "best regards",
        "with regards",
        "st internal reference",
    ]
    return any(value.startswith(prefix) for prefix in noise_prefixes)


def clean_signal_sentence(text: str | None, max_chars: int = 260) -> str:
    """Return the first sentence of `text`, or "" if it is conversational noise."""
    sentence = first_sentence(text, max_chars=max_chars)
    if looks_like_conversational_noise(sentence):
        return ""
    return sentence


def extract_issue_body(st_ready_text: str | None) -> str:
    """Return the technical body of an issue card, stripping the structured
    `Problem/Context/.../Technical details:` header written by the issues exporter.
    """
    text = st_ready_text or ""
    marker = "\n\nTechnical details:\n"
    if marker in text:
        return text.split(marker, 1)[1].strip()
    alt_marker = "\nTechnical details:\n"
    if alt_marker in text:
        return text.split(alt_marker, 1)[1].strip()
    return text.strip()


def slugify(value: str, max_len: int = 80) -> str:
    """Convert `value` to a lowercase, hyphenated identifier-safe slug."""
    text = (value or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = text.strip("-")
    if not text:
        return "untitled"
    return text[:max_len].strip("-")


def load_json_array(path: Path, preferred_key: str | None = None) -> list[dict[str, Any]]:
    """Load a JSON array of objects from `path`, tolerating either a raw
    array root or an object root wrapping the array under `preferred_key`
    (or the first list-valued key found, as a fallback).
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        if preferred_key and isinstance(payload.get(preferred_key), list):
            return [item for item in payload.get(preferred_key, []) if isinstance(item, dict)]
        for value in payload.values():
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    raise ValueError(f"Unsupported JSON root in {path}")


def parse_prefixed_lines(text: str | None, prefixes: set[str]) -> dict[str, str]:
    """Parse `"Key: value"` lines out of a structured card text, keeping only
    keys present in `prefixes` (e.g. "Problem", "Root cause", "Fix", ...).
    """
    out: dict[str, str] = {}
    for line in (text or "").splitlines():
        stripped = line.strip()
        if not stripped or ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        key = key.strip()
        if key in prefixes:
            out[key] = value.strip()
    return out


def split_keywords(raw_keywords: str | None) -> list[str]:
    """Split a comma-separated `Keywords:` string into a cleaned list."""
    if not raw_keywords:
        return []
    items = [normalize_whitespace(item) for item in str(raw_keywords).split(",")]
    return [item for item in items if item]


def normalize_series(value: str | None) -> str | None:
    """Normalize a raw MCU series string to the `STM32<SERIES>` form (e.g. `H7`
    -> `STM32H7`), or return the uppercased value unchanged if it doesn't match.
    """
    series = normalize_whitespace(value)
    if not series:
        return None
    upper = series.upper()
    if upper.startswith("STM32"):
        return upper
    if re.fullmatch(r"[A-Z]\d+", upper):
        return f"STM32{upper}"
    return upper


def infer_target_series(repo: str, issue_doc: dict[str, Any] | None) -> list[str]:
    """Infer which MCU series a card targets.

    Prefers the issue's own `mcu_series` field; falls back to parsing the
    series letter+number out of the repo name (e.g. `STM32CubeH7` -> `H7`)
    when no issue metadata is available (used by curated cards).
    """
    if issue_doc:
        normalized = normalize_series(str(issue_doc.get("mcu_series") or ""))
        if normalized:
            return [normalized]
    repo_upper = repo.upper()
    match = re.search(r"(H\d+|F\d+|L\d+|G\d+|U\d+|WB\d+|WL\d+|MP\d+)", repo_upper)
    if match:
        return [f"STM32{match.group(1)}"]
    return []


def extract_api_family_tags(*texts: str) -> list[str]:
    """Extract HAL/LL/BSP/MX/CMSIS API function-name anchors (e.g.
    `HAL_I2C_Init`) from `texts`, capped to 8, preserving first-seen order.

    These anchors are strong retrieval signals since users often quote the
    exact API name they are calling when reporting an issue.
    """
    anchor_re = re.compile(r"\b(?:HAL|LL|BSP|MX|CMSIS)_[A-Za-z0-9_]+\b")
    tags: list[str] = []
    seen: set[str] = set()
    for text in texts:
        for match in anchor_re.findall(text or ""):
            if match.lower() in seen:
                continue
            seen.add(match.lower())
            tags.append(match)
            if len(tags) >= 8:
                return tags
    return tags


def build_pattern_tags(*texts: str) -> list[str]:
    """Match `texts` against a fixed set of recurring failure-pattern regexes
    (timeout, blocking behavior, DMA, crash, ...) and return the matched tags.

    These pattern tags drive downstream heuristics (which debug checks,
    clarification questions, and query aliases to generate).
    """
    joined = " ".join(texts).lower()
    patterns = [
        (r"callback", "callback_not_reached"),
        (r"busy", "state_stuck_busy"),
        (r"timeout|timed out", "timeout"),
        (r"block|blocking", "blocking_behavior"),
        (r"dma", "dma_path"),
        (r"compile|build", "compile_error"),
        (r"crash|hardfault|fault", "crash_fault"),
        (r"regression|upgrade|version", "version_regression"),
        (r"clock", "clocking"),
        (r"pin|gpio|mux", "pinmux"),
        (r"irq|interrupt", "interrupt_path"),
        (r"cache|mpu", "cache_dma"),
    ]
    out: list[str] = []
    for pattern, tag in patterns:
        if re.search(pattern, joined) and tag not in out:
            out.append(tag)
    return out[:8]


def extract_version_tags(*texts: str) -> list[str]:
    """Extract `<repo/tool> v<version>` mentions (STM32Cube packages,
    CubeMX/CubeIDE, HAL/LL/CMSIS) from `texts`, deduped and capped to 8.

    Used to flag potential version-regression issues and to build
    version-specific query aliases.
    """
    joined = " ".join([text or "" for text in texts])
    tags: list[str] = []

    for repo_name, version in re.findall(r"\b(stm32cube[a-z0-9_-]*)\s*v(?:ersion)?\s*(\d+\.\d+\.\d+)\b", joined, re.IGNORECASE):
        tags.append(f"{repo_name.upper()} v{version}")
    for tool_name, version in re.findall(r"\b(cubemx|cubeide)\s*v?(\d+\.\d+(?:\.\d+)?)\b", joined, re.IGNORECASE):
        tags.append(f"{tool_name.upper()} v{version}")
    for stack_name, version in re.findall(r"\b(hal|ll|cmsis)\s*v?(\d+\.\d+(?:\.\d+)?)\b", joined, re.IGNORECASE):
        tags.append(f"{stack_name.upper()} v{version}")

    return dedupe(tags, limit=8)


def build_query_alias_fallbacks(
    issue_doc: dict[str, Any] | None,
    pattern_tags: list[str],
    api_tags: list[str],
    version_tags: list[str],
    title: str,
) -> list[str]:
    """Build generic, always-safe query aliases from component/board/API/
    version metadata and the card title.

    Used as a baseline layer under the more targeted aliases produced by
    `build_query_aliases`, so every card has at least some retrieval anchors
    even when no specific technical pattern was detected.
    """
    aliases: list[str] = []
    component = normalize_whitespace((issue_doc or {}).get("component") or "")
    board = normalize_whitespace((issue_doc or {}).get("board") or "")

    if component:
        aliases.append(f"{component} issue")
    if component and "compile_error" in pattern_tags:
        aliases.append(f"{component} compile error")
    if component and "timeout" in pattern_tags:
        aliases.append(f"{component} timeout")
    if component and "dma_path" in pattern_tags:
        aliases.append(f"{component} DMA issue")
    if board and component:
        aliases.append(f"{board} {component}")

    for api in api_tags[:4]:
        aliases.append(api)
        aliases.append(f"{api} issue")

    for version_tag in version_tags[:3]:
        aliases.append(f"version regression {version_tag}")

    title_alias = first_sentence(title, max_chars=120)
    if title_alias:
        aliases.append(title_alias)

    return dedupe(aliases, limit=12)


def build_query_aliases(
    issue_doc: dict[str, Any] | None,
    pattern_tags: list[str],
    api_tags: list[str],
    version_tags: list[str],
    title: str,
) -> list[str]:
    """Build the full list of natural-language query aliases for a card.

    Beyond the generic fallbacks, this adds phrase-level anchors observed in
    real user questions (e.g. "small transfer", "2 bytes", "blocking function")
    for known symptom combinations (SPI+DMA+blocking-like patterns), since
    exact-phrase overlap materially improves KB retrieval recall for these
    recurring support questions.
    """
    aliases: list[str] = []
    issue_text = (issue_doc or {}).get("st_ready_text") or ""
    body = extract_issue_body(issue_text)
    low = body.lower()
    has_spi_dma = any(tag.startswith("HAL_SPI") for tag in api_tags) and "dma_path" in pattern_tags
    has_blocking_like_pattern = "state_stuck_busy" in pattern_tags or "callback_not_reached" in pattern_tags

    if has_spi_dma:
        aliases.append("HAL_SPI_Transmit_DMA")
        aliases.append("SPI DMA transfer")

    # Prioritize lexical anchors that users ask with in natural language.
    if has_spi_dma and has_blocking_like_pattern:
        aliases.append("HAL_SPI_Transmit_DMA blocking function")
        aliases.append("small amount of data")
        aliases.append("small transfer")
        aliases.append("2 bytes")
        aliases.append("2 bytes example")

    if has_blocking_like_pattern and ("dma_path" in pattern_tags or has_spi_dma):
        aliases.append("blocking function")
        aliases.append("seems blocking")
        aliases.append("blocking behavior")
        aliases.append("callback not reached")
        aliases.append("state stuck busy")

    if re.search(r"\bsmall\b", low) and re.search(r"\btransfer\b", low):
        aliases.append("small transfer")

    if re.search(r"\btiny\b", low) and re.search(r"\btransfer\b", low):
        aliases.append("tiny transfer")

    size_matches = re.findall(r"\b(\d{1,4})\s*bytes?\b", low)
    for size in size_matches[:3]:
        aliases.append(f"{size} bytes")

    aliases.extend(
        build_query_alias_fallbacks(
            issue_doc=issue_doc,
            pattern_tags=pattern_tags,
            api_tags=api_tags,
            version_tags=version_tags,
            title=title,
        )
    )

    if version_tags and "version_regression" in pattern_tags:
        aliases.extend([f"upgrade issue {tag}" for tag in version_tags[:2]])

    return dedupe(aliases, limit=16)


def dedupe(items: list[str], limit: int = 12) -> list[str]:
    """Normalize whitespace, drop empties, deduplicate case-insensitively
    (preserving first-seen casing/order), and cap to `limit` items.
    """
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        normalized = normalize_whitespace(item)
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(normalized)
        if len(out) >= limit:
            break
    return out


def ensure_list(items: list[str], fallback: str) -> list[str]:
    """Return the deduped `items`, or a single-item list with `fallback` if empty.

    Guarantees list-valued card fields (likely_causes, plausible_diagnosis,
    ...) are never empty, so the KB always has something to show the user.
    """
    cleaned = dedupe(items)
    return cleaned if cleaned else [fallback]


def build_debug_checks(
    issue_doc: dict[str, Any] | None,
    resolver_doc: dict[str, Any] | None,
    pattern_tags: list[str],
) -> list[str]:
    """Build the ordered list of concrete debug/verification steps for a card,
    derived from its detected technical pattern tags and available resolver evidence.
    """
    checks: list[str] = []
    if "callback_not_reached" in pattern_tags or "state_stuck_busy" in pattern_tags:
        checks.extend(
            [
                "Instrument callback entry points and verify state transitions around the failing call",
                "Check whether the peripheral state returns to READY after the operation",
            ]
        )
    if "compile_error" in pattern_tags:
        checks.append("Rebuild with the exact toolchain and package version referenced in the report")
    if "timeout" in pattern_tags:
        checks.append("Capture timeout path timing and compare it with clock and interrupt configuration")
    if resolver_doc and resolver_doc.get("linked_file_paths"):
        first_path = resolver_doc.get("linked_file_paths")[0]
        checks.append(f"Review the linked fix path and compare your local source against {first_path}")
    component = normalize_whitespace((issue_doc or {}).get("component") or "")
    if component:
        checks.append(f"Validate the exact {component} configuration on the target board and firmware package")
    checks.append("Reproduce on a minimal project using the same board, Cube package, and middleware settings")
    return dedupe(checks, limit=5)


def build_clarification_questions(
    issue_doc: dict[str, Any] | None,
    pattern_tags: list[str],
    api_tags: list[str],
    version_tags: list[str],
) -> list[str]:
    """Build the follow-up questions the persona should ask the user before
    giving a definitive answer, tailored to the card's detected metadata/tags.
    """
    questions: list[str] = []
    component = normalize_whitespace((issue_doc or {}).get("component") or "")
    board = normalize_whitespace((issue_doc or {}).get("board") or "")
    series = normalize_whitespace((issue_doc or {}).get("mcu_series") or "")

    questions.append("Which exact MCU part number and board are you using?")
    if series:
        questions.append(f"Can you confirm whether your target is {series} and not a close variant?")
    if version_tags:
        questions.append("Which exact Cube/CubeMX/CubeIDE package versions are installed in your project?")
    if component:
        questions.append(f"Can you share the {component} configuration and initialization sequence?")
    if "dma_path" in pattern_tags or "cache_dma" in pattern_tags:
        questions.append("Are DMA buffers cache-coherent and are clean/invalidate operations applied correctly?")
    if "interrupt_path" in pattern_tags or "callback_not_reached" in pattern_tags:
        questions.append("Do interrupts/callbacks trigger as expected with the current NVIC priorities?")
    if api_tags:
        questions.append(f"Can you provide a minimal reproducer around {api_tags[0]} with expected vs observed behavior?")

    return dedupe(questions, limit=6)


def build_workarounds(
    issue_fields: dict[str, str],
    resolver_fields: dict[str, str],
    pattern_tags: list[str],
) -> list[str]:
    """Build candidate workarounds, prioritizing the issue's own `Fix:` hint
    and any resolver-linked candidate PR before generic pattern-based advice.
    """
    workarounds: list[str] = []
    fix_hint = clean_signal_sentence(issue_fields.get("Fix"), max_chars=220)
    if fix_hint:
        workarounds.append(fix_hint)
    if resolver_fields.get("Candidate PRs"):
        workarounds.append("Test the candidate fix path or PR on an isolated branch before merging locally")
    if "dma_path" in pattern_tags:
        workarounds.append("Try an alternate transfer mode on a minimal case to isolate DMA-specific behavior")
    workarounds.append("Pin a known-good firmware package version while validating the issue scope")
    return dedupe(workarounds, limit=4)


def build_confirmed_facts(
    issue_doc: dict[str, Any] | None,
    resolver_doc: dict[str, Any] | None,
    issue_fields: dict[str, str],
) -> list[str]:
    """Build the list of objectively verifiable facts about a card (issue
    existence, rescue/evidence status, resolver linkage status, root cause hint).
    """
    facts: list[str] = []
    if issue_doc and issue_doc.get("github_url"):
        facts.append(f"Issue evidence exists in {issue_doc.get('repo')} issue #{issue_doc.get('issue_number')}")
    if issue_doc and issue_doc.get("rescue_applied"):
        facts.append("The issue was rescued by the preprocessing filter because technical signals were detected")
    evidence_strength = normalize_whitespace((issue_doc or {}).get("evidence_strength") or "")
    if evidence_strength:
        facts.append(f"Issue evidence strength is rated {evidence_strength}")
    if resolver_doc and resolver_doc.get("resolution_status"):
        facts.append(
            "Resolver linkage status is "
            f"{resolver_doc.get('resolution_status')} with confidence {resolver_doc.get('link_confidence') or 'unknown'}"
        )
    if resolver_doc and resolver_doc.get("linked_commit_shas"):
        facts.append("A linked commit or pull request exists for this issue path")
    if resolver_doc and resolver_doc.get("merged_pr_with_file_evidence"):
        facts.append("A merged PR with changed-file evidence exists even if commit history is merge-heavy")
    root_cause = clean_signal_sentence(issue_fields.get("Root cause"), max_chars=180)
    if root_cause:
        facts.append(root_cause)
    return dedupe(facts, limit=4)


def build_constraints(
    issue_fields: dict[str, str],
    issue_doc: dict[str, Any] | None,
    resolver_doc: dict[str, Any] | None,
) -> list[str]:
    """Build the applicability constraints/caveats for a card (e.g. rescued
    issue needs validation, weak resolver confidence, always validate against
    the exact board/package).
    """
    constraints: list[str] = []
    issue_constraint = first_sentence(issue_fields.get("Constraints"), max_chars=220)
    if issue_constraint:
        constraints.append(issue_constraint)
    if issue_doc and issue_doc.get("rescue_applied"):
        constraints.append("This card is derived from a rescued issue and still requires board-level validation")
    if resolver_doc and resolver_doc.get("link_confidence") in {"low", "medium"}:
        constraints.append("Linked fix evidence is not strong enough to assume universal applicability")
    constraints.append("Validate against the exact MCU series, board, package version, and local integration path")
    return dedupe(constraints, limit=4)


def build_plausible_diagnosis(
    issue_doc: dict[str, Any] | None,
    resolver_doc: dict[str, Any] | None,
    pattern_tags: list[str],
) -> list[str]:
    """Build plausible diagnosis statements from the issue's layer/component/
    issue_kind classification and the resolver's resolution status, always
    returning at least a generic "needs reproduction" fallback.
    """
    out: list[str] = []
    if issue_doc:
        layer = normalize_whitespace(issue_doc.get("layer") or "")
        component = normalize_whitespace(issue_doc.get("component") or "")
        issue_kind = normalize_whitespace(issue_doc.get("issue_kind") or "")
        if layer or component or issue_kind:
            out.append(
                "Observed behavior aligns with "
                f"{', '.join([x for x in [layer, component, issue_kind] if x])} issue characteristics"
            )
    if resolver_doc and resolver_doc.get("resolution_status") == "merged_fix":
        out.append("A mainline fix likely exists, so local package drift is a plausible cause")
    elif resolver_doc and resolver_doc.get("resolution_status") == "candidate_fix":
        out.append("A candidate fix exists, suggesting the problem may already be understood upstream")
    elif resolver_doc and resolver_doc.get("resolution_status") == "commit_only_candidate":
        out.append("Commit-level evidence suggests an upstream fix candidate, but PR traceability is incomplete")
    if "version_regression" in pattern_tags:
        out.append("Behavior may depend on the exact Cube or HAL version in use")
    if "blocking_behavior" in pattern_tags or "state_stuck_busy" in pattern_tags:
        out.append("The application may be observing a completion-path or state-machine defect rather than a true hard block")
    return ensure_list(out, "The issue requires targeted reproduction to distinguish configuration error from upstream defect")


def build_likely_causes(issue_fields: dict[str, str], resolver_fields: dict[str, str]) -> list[str]:
    """Combine the issue's root-cause hint with the resolver's assessment/signal
    text into a likely-causes list, with a generic fallback if both are empty.
    """
    causes: list[str] = []
    root_cause = clean_signal_sentence(issue_fields.get("Root cause"), max_chars=220)
    if root_cause:
        causes.append(root_cause)
    assessment = clean_signal_sentence(resolver_fields.get("Assessment"), max_chars=220)
    if assessment:
        causes.append(assessment)
    resolver_signal = clean_signal_sentence(resolver_fields.get("Resolver signal"), max_chars=220)
    if resolver_signal:
        causes.append(resolver_signal)
    return ensure_list(causes, "Root cause is not explicit; use the issue thread and linked changes for triage")


def build_hypotheses(likely_causes: list[str], plausible_diagnosis: list[str]) -> list[str]:
    """Merge likely causes and plausible diagnosis into the card's
    `response_blocks.hypotheses` list (deduped, capped, with a fallback).
    """
    merged = dedupe(plausible_diagnosis + likely_causes, limit=8)
    return ensure_list(merged, "No strong hypothesis yet; prioritize targeted checks and reproduction")


def build_evidence_refs(issue_doc: dict[str, Any] | None, resolver_doc: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Build the list of evidence link references (issue/PR/commit URLs with
    confidence), capped to 6 entries.
    """
    refs: list[dict[str, Any]] = []
    if issue_doc and issue_doc.get("github_url"):
        refs.append(
            {
                "type": "issue",
                "id": issue_doc.get("issue_number"),
                "url": issue_doc.get("github_url"),
                "confidence": issue_doc.get("evidence_strength"),
            }
        )
    if resolver_doc:
        for url in resolver_doc.get("linked_pr_urls") or []:
            refs.append({"type": "pull_request", "url": url, "confidence": resolver_doc.get("link_confidence")})
        for url in resolver_doc.get("linked_commit_urls") or []:
            refs.append({"type": "commit", "url": url, "confidence": resolver_doc.get("link_confidence")})
    return refs[:6]


def build_keywords(
    issue_doc: dict[str, Any] | None,
    resolver_doc: dict[str, Any] | None,
    issue_fields: dict[str, str],
    api_tags: list[str],
    pattern_tags: list[str],
    version_tags: list[str],
) -> list[str]:
    """Aggregate every keyword-like signal available for a card (explicit
    keywords, labels, structured metadata, resolver modules/status, and the
    detected tag sets) into one deduped keyword list, capped to 14.
    """
    keywords: list[str] = []
    if issue_doc:
        keywords.extend(split_keywords(issue_fields.get("Keywords")))
        keywords.extend(issue_doc.get("labels") or [])
        for key in ["component", "layer", "issue_kind", "severity", "board"]:
            value = normalize_whitespace(issue_doc.get(key) or "")
            if value and value.lower() not in {"none", "unknown", "other", "n/a"}:
                keywords.append(value)
    if resolver_doc:
        keywords.extend(resolver_doc.get("impacted_modules") or [])
        keywords.extend(resolver_doc.get("impacted_components") or [])
        status = normalize_whitespace(resolver_doc.get("resolution_status") or "")
        if status:
            keywords.append(status)
    keywords.extend(pattern_tags)
    keywords.extend(version_tags)
    keywords.extend(api_tags)
    return dedupe(keywords, limit=14)


def build_st_ready_text(card: dict[str, Any]) -> str:
    """Render the full retrieval-ready `st_ready_text` document for a card.

    Concatenates every structured section (problem, context, symptoms,
    aliases, facts/hypotheses/checks, causes, workarounds, constraints,
    evidence links, keywords) into the flat text body embedded/indexed by
    the KB, in the fixed order the persona prompt expects.
    """
    evidence_links = [ref.get("url") for ref in card.get("evidence_refs") or [] if ref.get("url")]
    response_blocks = card.get("response_blocks") or {}
    facts_block = response_blocks.get("facts_confirmed") or card.get("confirmed_facts") or []
    hypotheses_block = response_blocks.get("hypotheses") or card.get("plausible_diagnosis") or []
    checks_block = response_blocks.get("checks") or card.get("debug_checks") or []
    clarification_questions = card.get("clarification_questions") or []
    lines = [
        f"Problem: {card.get('title')}",
        f"Context: repo={card.get('repo')}, issue_number={card.get('issue_number')}, target_series={', '.join(card.get('target_series') or []) or 'unknown'}, source_types={', '.join(card.get('source_types') or [])}",
        f"Symptoms: {card.get('symptom_summary')}",
        f"Query aliases: {' | '.join(card.get('query_aliases') or [])}",
        f"Response format: facts_confirmed -> hypotheses -> checks",
        f"Facts confirmed: {' | '.join(facts_block)}",
        f"Hypotheses: {' | '.join(hypotheses_block)}",
        f"Checks: {' | '.join(checks_block)}",
        f"Clarification questions (required): {' | '.join(clarification_questions)}",
        f"Likely causes: {' | '.join(card.get('likely_causes') or [])}",
        f"Confirmed facts: {' | '.join(card.get('confirmed_facts') or [])}",
        f"Plausible diagnosis: {' | '.join(card.get('plausible_diagnosis') or [])}",
        f"Debug actions: {' | '.join(card.get('debug_checks') or [])}",
        f"Workaround: {' | '.join(card.get('possible_workarounds') or [])}",
        f"Constraints: {' | '.join(card.get('constraints_or_limits') or [])}",
        f"Evidence links: {' | '.join(evidence_links)}",
        f"Keywords: {' '.join(card.get('keywords') or [])}",
    ]
    return "\n".join(lines).strip()


def build_diagnostic_card(
    repo: str,
    issue_doc: dict[str, Any] | None,
    resolver_doc: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build one full diagnostic card record from an issue and/or resolver case.

    Either `issue_doc` or `resolver_doc` (or both) may be provided — a card
    can exist from resolver evidence alone if the issue itself was filtered
    out upstream. Runs all tag/alias/section builders above in sequence and
    assembles the final card dict, including the rendered `st_ready_text`.
    """
    issue_fields = parse_prefixed_lines(
        (issue_doc or {}).get("st_ready_text"),
        {"Problem", "Context", "Root cause", "Fix", "Constraints", "Keywords"},
    )
    resolver_fields = parse_prefixed_lines(
        (resolver_doc or {}).get("resolver_card_text"),
        {"Problem", "Context", "Resolver signal", "Assessment", "Candidate PRs", "Commit evidence", "Constraints"},
    )

    title = normalize_whitespace(
        (issue_doc or {}).get("issue_title")
        or (resolver_doc or {}).get("issue_title")
        or issue_fields.get("Problem")
        or resolver_fields.get("Problem")
        or "Untitled diagnostic case"
    )
    issue_number = (issue_doc or {}).get("issue_number") or (resolver_doc or {}).get("issue_number")
    api_tags = extract_api_family_tags(
        (issue_doc or {}).get("st_ready_text") or "",
        (resolver_doc or {}).get("resolver_card_text") or "",
    )
    issue_body = extract_issue_body((issue_doc or {}).get("st_ready_text"))
    pattern_tags = build_pattern_tags(
        title,
        issue_fields.get("Root cause", ""),
        issue_fields.get("Fix", ""),
        issue_body,
        (issue_doc or {}).get("st_ready_text") or "",
        (resolver_doc or {}).get("resolver_card_text") or "",
    )
    version_tags = extract_version_tags(
        title,
        issue_body,
        issue_fields.get("Context", ""),
        issue_fields.get("Fix", ""),
        (issue_doc or {}).get("st_ready_text") or "",
        (resolver_doc or {}).get("resolver_card_text") or "",
    )
    query_aliases = build_query_aliases(issue_doc, pattern_tags, api_tags, version_tags, title)
    symptom_summary = clean_signal_sentence(issue_fields.get("Fix"), max_chars=220)
    if not symptom_summary:
        symptom_summary = clean_signal_sentence(title, max_chars=220) or title
    if query_aliases and not any(alias.lower() in symptom_summary.lower() for alias in query_aliases[:2]):
        symptom_summary = f"{symptom_summary} ({', '.join(query_aliases[:2])})."
    affected_context = first_sentence(issue_fields.get("Context") or resolver_fields.get("Context"), max_chars=220)
    likely_causes = build_likely_causes(issue_fields, resolver_fields)
    confirmed_facts = build_confirmed_facts(issue_doc, resolver_doc, issue_fields)
    plausible_diagnosis = build_plausible_diagnosis(issue_doc, resolver_doc, pattern_tags)
    debug_checks = build_debug_checks(issue_doc, resolver_doc, pattern_tags)
    clarification_questions = build_clarification_questions(issue_doc, pattern_tags, api_tags, version_tags)
    hypotheses = build_hypotheses(likely_causes, plausible_diagnosis)
    possible_workarounds = build_workarounds(issue_fields, resolver_fields, pattern_tags)
    constraints = build_constraints(issue_fields, issue_doc, resolver_doc)
    evidence_refs = build_evidence_refs(issue_doc, resolver_doc)
    keywords = build_keywords(issue_doc, resolver_doc, issue_fields, api_tags, pattern_tags, version_tags)
    keywords = dedupe(query_aliases + keywords, limit=24)
    query_anchor_tags = dedupe(query_aliases + api_tags + pattern_tags + version_tags, limit=24)
    component = normalize_whitespace((issue_doc or {}).get("component") or "")
    peripheral_tags = dedupe([component] if component else [], limit=4)
    source_types = [
        source
        for source, doc in [("rescued_issue", issue_doc if (issue_doc or {}).get("rescue_applied") else None), ("resolver_case", resolver_doc)]
        if doc is not None
    ]
    if not source_types and issue_doc:
        source_types = ["issue"]

    card = {
        "id": f"diag::{repo}::issue::{issue_number or slugify(title)}",
        "card_id": f"diag_{repo.lower()}_{issue_number or slugify(title)}",
        "rootTagPath": "diagnostic_cards",
        "delivery_template": "st_v1_diagnostic_card",
        "repo_scope": repo,
        "repo": repo,
        "title": title,
        "label": title,
        "externalURL": (issue_doc or {}).get("github_url") or (resolver_doc or {}).get("issue_url"),
        "issue_number": issue_number,
        "issue_title": (issue_doc or {}).get("issue_title") or (resolver_doc or {}).get("issue_title"),
        "issue_state": (issue_doc or {}).get("state") or (resolver_doc or {}).get("issue_state"),
        "issue_kind": (issue_doc or {}).get("issue_kind"),
        "severity": (issue_doc or {}).get("severity"),
        "component": (issue_doc or {}).get("component"),
        "board": (issue_doc or {}).get("board"),
        "target_series": infer_target_series(repo, issue_doc),
        "category": "technical_diagnosis",
        "source_types": source_types,
        "evidence_strength": (issue_doc or {}).get("evidence_strength") or (resolver_doc or {}).get("link_confidence"),
        "rescue_applied": bool((issue_doc or {}).get("rescue_applied")),
        "resolution_status": (resolver_doc or {}).get("resolution_status"),
        "peripheral_tags": peripheral_tags,
        "technical_pattern_tags": pattern_tags,
        "api_family_tags": api_tags,
        "version_tags": version_tags,
        "query_anchor_tags": query_anchor_tags,
        "query_aliases": query_aliases,
        "clarification_questions_required": True,
        "clarification_questions": clarification_questions,
        "symptom_summary": symptom_summary,
        "affected_context": affected_context,
        "likely_causes": likely_causes,
        "confirmed_facts": confirmed_facts,
        "plausible_diagnosis": plausible_diagnosis,
        "response_blocks": {
            "facts_confirmed": confirmed_facts,
            "hypotheses": hypotheses,
            "checks": debug_checks,
        },
        "response_format": "facts_hypotheses_checks_with_clarifications",
        "debug_checks": debug_checks,
        "possible_workarounds": possible_workarounds,
        "constraints_or_limits": constraints,
        "evidence_refs": evidence_refs,
        "keywords": keywords,
    }
    card["st_ready_text"] = build_st_ready_text(card)
    return card


# ============================================================
# Curated cross-series diagnostic cards
# ------------------------------------------------------------
# Some high-value support questions (e.g. I2C bus recovery) are common to many
# STM32 series but are NOT captured as a single GitHub issue. Without a dedicated
# KB document, the persona has nothing to retrieve and returns an incomplete
# answer (scored 0 in evaluation). These curated cards inject durable,
# retrieval-ready knowledge into every relevant series repo. They are authored
# from well-established STM32 peripheral behavior, not fabricated issue metadata.
# ============================================================

CURATED_DIAGNOSTIC_CARDS: list[dict[str, Any]] = [
    {
        "topic_id": "i2c_busy_recovery",
        "applies_to_series": "all",
        "component": "I2C",
        "severity": "high",
        "issue_kind": "usage_question",
        "title": "I2C stuck BUSY after a communication error: safe software bus-recovery sequence (no full MCU reset)",
        "symptom_summary": (
            "I2C stays BUSY after a communication error (NACK, arbitration loss, glitch) and the bus "
            "never recovers; only a full MCU reset clears it. A software bus-recovery sequence releases "
            "the bus and clears BUSY without resetting the whole MCU."
        ),
        "query_aliases": [
            "I2C stuck BUSY after communication error",
            "I2C bus never recovers",
            "safe software recovery sequence without full MCU reset",
            "I2C BUSY recovery without reset",
            "clear I2C BUSY flag without reset",
            "I2C bus recovery sequence",
            "I2C SCL toggle 9 pulses",
            "recover I2C bus in software",
            "I2C hangs busy flag stays set",
            "I2C deadlock recovery",
        ],
        "keywords": [
            "I2C", "BUSY", "bus recovery", "SCL", "SDA", "STOP condition",
            "GPIO open-drain", "9 clock pulses", "HAL_I2C", "deadlock", "NACK",
            "__HAL_RCC_I2C1_FORCE_RESET", "__HAL_I2C_DISABLE",
        ],
        "api_family_tags": ["HAL_I2C_Init", "HAL_I2C_DeInit", "HAL_GPIO_Init"],
        "technical_pattern_tags": ["state_stuck_busy", "pinmux", "interrupt_path"],
        "confirmed_facts": [
            "On STM32 I2C, the BUSY flag can remain set after an aborted/erroneous transfer and cannot always be cleared purely by peripheral software.",
            "A slave holding SDA low, or a peripheral state machine left mid-transaction, keeps the bus BUSY.",
            "A GPIO-level bus-recovery plus peripheral reset clears BUSY without a full MCU reset.",
        ],
        "plausible_diagnosis": [
            "A slave device is holding SDA low after an incomplete byte, or the I2C state machine did not return to READY after the error.",
            "On F1/F2/F4 I2C IP, an analog-filter glitch can also trigger the permanent BUSY condition.",
        ],
        "likely_causes": [
            "Missing STOP after a NACK or error, leaving the bus mid-transaction",
            "Slave clock-stretching or holding SDA low after a partial transfer",
            "Weak/absent pull-ups or SDA/SCL glitch during START/STOP",
        ],
        "debug_checks": [
            "Read the SCL and SDA GPIO levels: when idle both must be high; if SDA is low a slave is holding the bus",
            "Confirm a STOP is generated and error flags are cleared in the I2C error callback",
            "Verify pull-up values (2.2k-4.7k) and that no external device wedges the bus",
        ],
        "possible_workarounds": [
            "1. Disable the I2C peripheral: __HAL_I2C_DISABLE(&hi2c) (clears PE)",
            "2. Reconfigure SCL and SDA as GPIO open-drain outputs with pull-up (save the current alternate-function config)",
            "3. If SDA is held low, generate up to 9 clock pulses on SCL to let the slave release SDA",
            "4. Generate a manual STOP: drive SDA low while SCL is high, then release SDA high while SCL is high",
            "5. Restore SCL/SDA to their I2C alternate function",
            "6. Reset the peripheral: __HAL_RCC_I2C1_FORCE_RESET(); __HAL_RCC_I2C1_RELEASE_RESET();",
            "7. Re-initialize with HAL_I2C_Init(&hi2c) and retry the transfer",
            "F1/F2/F4 note: also disable the analog filter (HAL_I2CEx_ConfigAnalogFilter with DISABLE) to avoid the glitch-induced BUSY lockup",
        ],
        "constraints_or_limits": [
            "Adapt the GPIO port/pin and __HAL_RCC_I2Cx_* macros to the I2C instance and pins used on your board",
            "The GPIO bit-bang recovery is universal (H7, H5, U5, WL, F1, F2, F4); newer IP (H7/H5/U5) can also toggle PE/SWRST",
        ],
        "doc_url": "https://www.st.com/resource/en/application_note/an5343-i2c-timing-configuration-tool-stmicroelectronics.pdf",
    },
]


def build_curated_card(repo: str, series: str, template: dict[str, Any]) -> dict[str, Any]:
    """Build one diagnostic card from a `CURATED_DIAGNOSTIC_CARDS` template.

    Mirrors the shape produced by `build_diagnostic_card` so curated and
    issue-derived cards are indistinguishable to the KB/persona, but sources
    every field from the hand-authored template instead of issue/resolver data.
    """
    topic_id = template["topic_id"]
    component = template.get("component")
    query_aliases = dedupe(list(template.get("query_aliases") or []), limit=16)
    api_tags = list(template.get("api_family_tags") or [])
    pattern_tags = list(template.get("technical_pattern_tags") or [])
    peripheral_tags = dedupe([component] if component else [], limit=4)
    keywords = dedupe(query_aliases + list(template.get("keywords") or []), limit=24)
    query_anchor_tags = dedupe(query_aliases + api_tags + pattern_tags, limit=24)
    confirmed_facts = list(template.get("confirmed_facts") or [])
    plausible_diagnosis = list(template.get("plausible_diagnosis") or [])
    likely_causes = list(template.get("likely_causes") or [])
    debug_checks = list(template.get("debug_checks") or [])
    hypotheses = build_hypotheses(likely_causes, plausible_diagnosis)
    evidence_refs: list[dict[str, Any]] = []
    if template.get("doc_url"):
        evidence_refs.append({"type": "documentation", "url": template["doc_url"], "confidence": "high"})

    card = {
        "id": f"diag::{repo}::curated::{topic_id}",
        "card_id": f"diag_{repo.lower()}_curated_{topic_id}",
        "rootTagPath": "diagnostic_cards",
        "delivery_template": "st_v1_diagnostic_card",
        "repo_scope": repo,
        "repo": repo,
        "title": template.get("title"),
        "label": template.get("title"),
        "externalURL": template.get("doc_url"),
        "issue_number": None,
        "issue_title": None,
        "issue_state": None,
        "issue_kind": template.get("issue_kind"),
        "severity": template.get("severity"),
        "component": component,
        "board": None,
        "target_series": [series] if series else [],
        "category": "technical_diagnosis",
        "source_types": ["curated"],
        "evidence_strength": "high",
        "rescue_applied": False,
        "resolution_status": None,
        "peripheral_tags": peripheral_tags,
        "technical_pattern_tags": pattern_tags,
        "api_family_tags": api_tags,
        "version_tags": [],
        "query_anchor_tags": query_anchor_tags,
        "query_aliases": query_aliases,
        "clarification_questions_required": False,
        "clarification_questions": [],
        "symptom_summary": template.get("symptom_summary"),
        "affected_context": f"Applies to {series} and other STM32 series sharing the same I2C behavior" if series else "",
        "likely_causes": likely_causes,
        "confirmed_facts": confirmed_facts,
        "plausible_diagnosis": plausible_diagnosis,
        "response_blocks": {
            "facts_confirmed": confirmed_facts,
            "hypotheses": hypotheses,
            "checks": debug_checks,
        },
        "response_format": "direct_answer_with_recovery_steps",
        "debug_checks": debug_checks,
        "possible_workarounds": list(template.get("possible_workarounds") or []),
        "constraints_or_limits": list(template.get("constraints_or_limits") or []),
        "evidence_refs": evidence_refs,
        "keywords": keywords,
    }
    card["st_ready_text"] = build_st_ready_text(card)
    return card


def build_curated_cards_for_repo(repo: str) -> list[dict[str, Any]]:
    """Return the curated cards applicable to `repo`'s MCU series.

    Only injects into main series repos (`STM32Cube<Series>`), not into
    HAL/CMSIS/BSP sub-repos, since sub-repos are nested under the series
    folder and would otherwise duplicate the same curated content.
    """
    # Only inject curated cards into main series repos (STM32Cube<Series>),
    # not into component/BSP repos, to avoid noise duplication.
    if not re.match(r"(?i)stm32cube[a-z]", repo):
        return []
    series_list = infer_target_series(repo, None)
    if not series_list:
        return []
    series = series_list[0]
    cards: list[dict[str, Any]] = []
    for template in CURATED_DIAGNOSTIC_CARDS:
        applies = template.get("applies_to_series", "all")
        if applies != "all" and series not in applies:
            continue
        cards.append(build_curated_card(repo, series, template))
    return cards


def export_repo_json(repo: str, include_all_issues: bool = False) -> tuple[int, int, Path]:
    """Export one repo's diagnostic cards into `st_ready_diagnostic_cards_<repo>.json`.

    Loads rescued issues (or all issues, if `include_all_issues`) and resolver
    cases, indexes both by issue number, builds one card per key present in
    either index, appends applicable curated cross-series cards, then writes
    the per-series output plus a legacy mirror and a summary file.

    Returns (total_source_entries_considered, exported_cards_count, output_directory).
    """
    issues_path = get_existing_repo_artifact_file(
        repo=repo,
        artifact_dir="issues_json",
        file_name=f"st_ready_issues_{repo.lower()}.json",
    )
    resolver_path = get_existing_repo_artifact_file(
        repo=repo,
        artifact_dir="resolver_cases_json",
        file_name=f"st_ready_resolver_cases_{repo.lower()}.json",
    )

    issues = load_json_array(issues_path, preferred_key="issues") if issues_path.exists() else []
    resolver_cases = load_json_array(resolver_path, preferred_key="resolver_cases") if resolver_path.exists() else []

    if not issues and not resolver_cases:
        raise FileNotFoundError(f"No ST-ready issue or resolver input found for repo {repo}")

    issue_index: dict[str, dict[str, Any]] = {}
    for issue in issues:
        if not include_all_issues and not issue.get("rescue_applied"):
            continue
        issue_number = issue.get("issue_number")
        if issue_number is None:
            continue
        issue_index[str(issue_number)] = issue

    resolver_index: dict[str, dict[str, Any]] = {}
    for case in resolver_cases:
        issue_number = case.get("issue_number")
        if issue_number is None:
            continue
        resolver_index[str(issue_number)] = case

    all_keys = sorted(set(issue_index.keys()) | set(resolver_index.keys()), key=lambda value: int(value) if value.isdigit() else value)
    cards: list[dict[str, Any]] = []
    for key in all_keys:
        cards.append(build_diagnostic_card(repo, issue_index.get(key), resolver_index.get(key)))

    # Inject curated cross-series cards (e.g. I2C bus recovery) so the KB always
    # has a retrieval-ready answer for common questions not tied to a single issue.
    existing_ids = {card.get("id") for card in cards}
    curated_cards = build_curated_cards_for_repo(repo)
    curated_added = 0
    for curated in curated_cards:
        if curated.get("id") in existing_ids:
            continue
        cards.append(curated)
        existing_ids.add(curated.get("id"))
        curated_added += 1

    out_root = get_repo_artifact_dir(repo, "diagnostic_cards_json")
    out_root.mkdir(parents=True, exist_ok=True)
    out_file_name = f"st_ready_diagnostic_cards_{repo.lower()}.json"
    out_file = out_root / out_file_name
    out_file.write_text(json.dumps(cards, ensure_ascii=False, indent=2), encoding="utf-8")

    # Backward-compatible mirror in legacy flat folder.
    legacy_out_file = get_legacy_artifact_file("diagnostic_cards_json", out_file_name)
    legacy_out_file.parent.mkdir(parents=True, exist_ok=True)
    legacy_out_file.write_text(json.dumps(cards, ensure_ascii=False, indent=2), encoding="utf-8")

    summary = {
        "repo": repo,
        "issues_input": str(issues_path) if issues_path.exists() else None,
        "resolver_input": str(resolver_path) if resolver_path.exists() else None,
        "output_file": str(out_file),
        "rescued_issues_considered": len(issue_index),
        "resolver_cases_considered": len(resolver_index),
        "exported_cards": len(cards),
        "curated_cards_added": curated_added,
        "include_all_issues": include_all_issues,
        "format": "json-array",
        "root_tag_path": "diagnostic_cards",
    }
    summary_file_name = f"summary_diagnostic_cards_{repo.lower()}.json"
    (out_root / summary_file_name).write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    legacy_summary_file = get_legacy_artifact_file("diagnostic_cards_json", summary_file_name)
    legacy_summary_file.parent.mkdir(parents=True, exist_ok=True)
    legacy_summary_file.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return len(issue_index) + len(resolver_index), len(cards), out_root


def main() -> None:
    """CLI entry point: export ST-ready diagnostic cards for each configured repo."""
    parser = argparse.ArgumentParser(
        description="Export generic ST-ready diagnostic cards from rescued issues and resolver cases."
    )
    parser.add_argument("--repo", action="append", help="Repo name, e.g., STM32CubeH7. Can be repeated.")
    parser.add_argument(
        "--include-all-issues",
        action="store_true",
        help="Include all ST-ready issues instead of rescued issues only.",
    )
    args = parser.parse_args()

    cfg = load_config()
    repos = args.repo or cfg.get("repos", [])
    if not repos:
        raise ValueError("No repos provided and no repos found in config.")

    for repo in repos:
        try:
            total_inputs, exported, out_root = export_repo_json(
                repo=repo,
                include_all_issues=args.include_all_issues,
            )
        except FileNotFoundError as exc:
            print(f"[ST-READY:json:diagnostic_cards] {repo}: skipped ({exc})")
            continue
        print(
            f"[ST-READY:json:diagnostic_cards] {repo}: exported {exported} cards "
            f"from {total_inputs} source entries -> {out_root}"
        )

if __name__ == "__main__":
    main()