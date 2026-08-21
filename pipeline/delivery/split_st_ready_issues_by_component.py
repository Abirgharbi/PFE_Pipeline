"""CLI: split ST-ready issue payloads into per-STM32-component JSON files.

Uploading one giant `st_ready_issues_with_images_<repo>.json` as a single KB
datasource makes retrieval noisier (queries about I2C can match SPI issues,
etc.). This script splits such a payload into one file per hardware
component (e.g. I2C, SPI, UART), so each component can be uploaded as its own
ST AI Bridge datasource (`issues_<SERIES>_<COMPONENT>`), improving retrieval
precision.

Inputs (first pattern that matches under `--input-root`, in priority order):
1. `**/issues_json/st_ready_issues_with_images_*_with_alfred_image_text.json`
   (Alfred-enriched, preferred).
2. `**/issues_json/st_ready_issues_with_images_*.json` (pre-Alfred).
3. `**/issues_json/st_ready_issues_*_with_alfred_image_text.json`.
4. `**/issues_json/st_ready_issues_*.json` (no images).

Component detection per issue (`get_component_detection`), highest priority first:
1. The issue's own `component` field, if it is a known STM32 peripheral/driver
   name (`GENERIC_DRIVER_COMPONENTS`).
2. The `component=` value parsed from the `Context:` line in `st_ready_text`.
3. A weighted vote combining `Keywords:`, GitHub `labels`, and uppercase
   technical tokens found anywhere in the title/text, with stricter score
   thresholds for ambiguous acronyms (`AMBIGUOUS_COMPONENTS`, e.g. CAN/COMP/TIM)
   to avoid false positives on common English words.

Issues where no component can be confidently detected are grouped under
`UNCATEGORIZED` and written to a repo-level (no component suffix) file.

Outputs, under `<source_dir>/<output_subdir>/` (default `by_component/`,
sibling of the source `issues_json` folder):
- `st_ready_issues_<series>_<component>.json`: `{"issues": [...]}` per component.
- `st_ready_issues_<series>.json`: uncategorized issues (if any).
- `summary_by_component_<series>.json`: per-component counts and detection
  source stats, consumed by `validate_issues_by_component_split.py`.
- `component_detection_trace_<series>.json`: per-issue detection trace for
  debugging misclassifications.

Run:
    python -m pipeline.delivery.split_st_ready_issues_by_component
    python -m pipeline.delivery.split_st_ready_issues_by_component --input-file <path> --dry-run
"""

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from shared.utils.paths import PROJECT_ROOT


DEFAULT_INPUT_ROOT = PROJECT_ROOT / "datasets" / "07_delivery" / "st_ready" / "by_series"
DEFAULT_INPUT_PATTERN = "**/issues_json/st_ready_issues_with_images_*_with_alfred_image_text.json"
FALLBACK_INPUT_PATTERNS = [
    "**/issues_json/st_ready_issues_with_images_*.json",
    "**/issues_json/st_ready_issues_*_with_alfred_image_text.json",
    "**/issues_json/st_ready_issues_*.json",
]
DEFAULT_OUTPUT_SUBDIR = "by_component"
UNKNOWN_COMPONENT = "UNCATEGORIZED"
# Known STM32 peripheral/driver acronyms used to validate a detected component
# candidate. Restricting to this allowlist avoids splitting on arbitrary
# uppercase words that are not real hardware components.
GENERIC_DRIVER_COMPONENTS = {
    "ADC", "CAN", "CEC", "COMP", "CORDIC", "CORTEX", "CRC", "CRS", "CRYP", "DAC",
    "DCACHE", "DCMI", "DELAYBLOCK", "DFSDM", "DMA", "DMAMUX", "DMA2D", "DSI", "DTS",
    "ETH", "EXTI", "FDCAN", "FIREWALL", "FLASH", "FMAC", "FMC", "GFXMMU", "GFXTIM",
    "GPIO", "GPU2D", "GTZC", "HASH", "HRTIM", "HSEM", "HSPI", "I2C", "ICACHE", "IPCC",
    "IRDA", "IWDG", "JPEG", "LCD", "LPGPIO", "LPTIM", "LTDC", "MDF", "MDIOS", "MDMA",
    "MRSUBG", "OSPI", "OPAMP", "OTFDEC", "PKA", "PSSI", "PWR", "QSPI", "RAMCFG", "RAMECC",
    "RCC", "RNG", "RTC", "SAI", "SDMMC", "SMARTCARD", "SPDIFRX", "SPI", "SWPMI", "TIM",
    "TSC", "UART", "UCPD", "USART", "USB", "WWDG", "XSPI",
}
# Merge near-synonym raw values onto the canonical acronym used across the KB.
COMPONENT_ALIASES = {
    "ETHERNET": "ETH",
    "USB_OTG": "USB",
    "I2C": "I2C",
    "SPI": "SPI",
    "UART": "UART",
    "TIMERS": "TIM",
    "TIMER": "TIM",
}
# These acronyms collide with common English words/abbreviations ("can", "comp",
# "tim"), so weak single-mention evidence is not enough to assign them.
AMBIGUOUS_COMPONENTS = {"CAN", "COMP", "TIM"}
COMPONENT_PATTERNS = {
    comp: re.compile(rf"(?<![A-Z0-9_]){re.escape(comp)}(?![A-Z0-9_])")
    for comp in GENERIC_DRIVER_COMPONENTS
}


def utc_now_iso() -> str:
    """Return the current UTC time as a second-precision ISO 8601 string."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json_object(path: Path) -> dict[str, Any]:
    """Load a JSON file and ensure its root is an object (not an array)."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object at root for {path}")
    return payload


def save_json(path: Path, payload: dict[str, Any]) -> None:
    """Write `payload` as pretty-printed UTF-8 JSON, creating parent dirs."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def normalize_component(raw: Any) -> str:
    """Canonicalize a raw component value to an uppercase, underscore-joined
    token (or `UNCATEGORIZED` if empty/placeholder), applying known aliases.
    """
    value = "" if raw is None else str(raw).strip()
    if not value:
        return UNKNOWN_COMPONENT

    lowered = value.lower()
    if lowered in {"none", "unknown", "other", "n/a", "na", "null"}:
        return UNKNOWN_COMPONENT

    canonical = re.sub(r"[^A-Za-z0-9]+", "_", value.upper()).strip("_")
    canonical = COMPONENT_ALIASES.get(canonical, canonical)
    return canonical or UNKNOWN_COMPONENT


def is_generic_driver_component(component: str) -> bool:
    """Return True if `component` is one of the known STM32 peripheral acronyms."""
    return component in GENERIC_DRIVER_COMPONENTS


def _normalize_candidate_token(raw: str) -> str:
    """Normalize a free-text token the same way as `normalize_component`,
    without the empty/placeholder handling (used for token-scoring candidates).
    """
    token = re.sub(r"[^A-Za-z0-9]+", "_", (raw or "").upper()).strip("_")
    token = COMPONENT_ALIASES.get(token, token)
    return token


def _extract_context_component(st_ready_text: str) -> str:
    """Extract the `component=` value from the structured `Context:` line.

    This is the highest-confidence signal because it was written explicitly
    by the upstream enrichment stage, not inferred from free text.
    """
    if not st_ready_text:
        return UNKNOWN_COMPONENT
    match = re.search(r"\bcomponent=([^,\n]+)", st_ready_text, flags=re.IGNORECASE)
    if not match:
        return UNKNOWN_COMPONENT
    candidate = normalize_component(match.group(1).strip())
    if is_generic_driver_component(candidate):
        return candidate
    return UNKNOWN_COMPONENT


def _extract_keyword_components(st_ready_text: str) -> list[str]:
    """Return known component acronyms found in the card's `Keywords:` line."""
    if not st_ready_text:
        return []
    match = re.search(r"^Keywords:\s*(.+)$", st_ready_text, flags=re.IGNORECASE | re.MULTILINE)
    if not match:
        return []

    found: list[str] = []
    for part in match.group(1).split(","):
        candidate = normalize_component(part.strip())
        if is_generic_driver_component(candidate):
            found.append(candidate)
    return found


def _extract_label_components(issue: dict[str, Any]) -> list[str]:
    """Return known component acronyms found among the issue's GitHub labels."""
    labels = issue.get("labels")
    if not isinstance(labels, list):
        return []

    found: list[str] = []
    for label in labels:
        if not isinstance(label, str):
            continue
        candidate = normalize_component(label.strip())
        if is_generic_driver_component(candidate):
            found.append(candidate)
    return found


def _score_components_from_upper_tokens(text: str) -> dict[str, int]:
    """Score candidate components by counting UPPERCASE technical tokens in `text`.

    Restricting to uppercase tokens (instead of any word match) avoids
    accidentally matching common lowercase English words like "can" or "comp".
    """
    scores: dict[str, int] = {}
    if not text:
        return scores

    # Use only UPPERCASE/technical-looking tokens to avoid matching common words like "can".
    tokens = re.findall(r"\b[A-Z][A-Z0-9_\-/]{1,}\b", text)
    for token in tokens:
        candidate = _normalize_candidate_token(token)
        if not is_generic_driver_component(candidate):
            continue
        scores[candidate] = scores.get(candidate, 0) + 1
    return scores


def find_component_in_st_ready_text(issue: dict[str, Any]) -> str:
    """Infer a component for `issue` from its title/`st_ready_text` when the
    `component` field is missing or not a recognized peripheral name.

    Combines several signals in a weighted vote (context line > keywords/
    labels > raw uppercase tokens) and applies confidence guardrails so a
    single weak/ambiguous mention (or a tie) does not force a wrong split.
    """
    text_parts = [
        str(issue.get("issue_title") or ""),
        str(issue.get("st_ready_text") or ""),
    ]
    raw_text = "\n".join(text_parts)
    if not raw_text.strip():
        return UNKNOWN_COMPONENT

    # 1) Structured context line has the highest priority when valid.
    context_component = _extract_context_component(str(issue.get("st_ready_text") or ""))
    if context_component != UNKNOWN_COMPONENT:
        return context_component

    # 2) Keywords and labels are reliable structured hints.
    votes: dict[str, int] = {}
    for candidate in _extract_keyword_components(str(issue.get("st_ready_text") or "")):
        votes[candidate] = votes.get(candidate, 0) + 3
    for candidate in _extract_label_components(issue):
        votes[candidate] = votes.get(candidate, 0) + 2

    # 3) Technical uppercase token evidence from full text.
    token_scores = _score_components_from_upper_tokens(raw_text)
    for candidate, score in token_scores.items():
        votes[candidate] = votes.get(candidate, 0) + score

    if not votes:
        return UNKNOWN_COMPONENT

    sorted_candidates = sorted(votes.items(), key=lambda kv: (-kv[1], kv[0]))
    best_component, best_score = sorted_candidates[0]

    # Confidence guardrails: avoid weak ambiguous predictions.
    min_score = 3 if best_component in AMBIGUOUS_COMPONENTS else 2
    if best_score < min_score:
        return UNKNOWN_COMPONENT

    # If tie with same score, avoid unstable assignment.
    if len(sorted_candidates) > 1 and sorted_candidates[1][1] == best_score:
        return UNKNOWN_COMPONENT

    return best_component


def get_component_detection(issue: dict[str, Any]) -> tuple[str, str]:
    """Return (component, detection_source) for one issue.

    `detection_source` is one of `"component_field"`, `"st_ready_text"`, or
    `"none"`, recorded in the summary/trace files for auditability.
    """
    component_from_field = normalize_component(issue.get("component"))
    if component_from_field != UNKNOWN_COMPONENT and is_generic_driver_component(component_from_field):
        return component_from_field, "component_field"

    component_from_text = find_component_in_st_ready_text(issue)
    if component_from_text != UNKNOWN_COMPONENT:
        return component_from_text, "st_ready_text"

    return UNKNOWN_COMPONENT, "none"


def get_series_tag(issues: list[dict[str, Any]], source_path: Path) -> str:
    """Derive a short series tag (e.g. `H7`) used in output file names.

    Tries the first issue's `mcu_series`/`repo` fields first, then falls back
    to parsing the `stm32cube<series>` segment out of the source file path.
    """
    if issues:
        first = issues[0]
        mcu_series = str(first.get("mcu_series") or "").strip().upper()
        if mcu_series:
            return re.sub(r"[^A-Z0-9]+", "", mcu_series) or "UNK"

        repo = str(first.get("repo") or "").strip().upper()
        if repo.startswith("STM32CUBE"):
            suffix = repo.replace("STM32CUBE", "", 1)
            suffix = re.sub(r"[^A-Z0-9]+", "", suffix)
            if suffix:
                return suffix

    match = re.search(r"stm32cube([a-z0-9]+)", source_path.as_posix(), flags=re.IGNORECASE)
    if match:
        return match.group(1).upper()

    return "UNK"


def split_payload_by_component(
    source_path: Path,
    output_subdir: str,
    datasource_prefix: str,
    dry_run: bool,
) -> dict[str, Any]:
    """Split one ST-ready issues payload into per-component files.

    Detects each issue's component (`get_component_detection`), groups issues
    accordingly, writes one JSON file per component plus an uncategorized
    file for undetected ones, and always writes a summary describing the
    split (even in `--dry-run`, only file writes are skipped).
    """
    payload = load_json_object(source_path)
    issues = payload.get("issues")
    if not isinstance(issues, list):
        raise ValueError(f"Missing 'issues' array in {source_path}")

    issue_objects = [item for item in issues if isinstance(item, dict)]
    series_tag = get_series_tag(issue_objects, source_path)

    grouped: dict[str, list[dict[str, Any]]] = {}
    null_component_issues: list[dict[str, Any]] = []
    detection_trace_rows: list[dict[str, Any]] = []
    detection_source_counts: dict[str, int] = {
        "component_field": 0,
        "st_ready_text": 0,
        "none": 0,
    }
    for issue in issue_objects:
        component, source = get_component_detection(issue)
        detection_source_counts[source] = detection_source_counts.get(source, 0) + 1
        issue_out = dict(issue)
        issue_out["component_original"] = issue.get("component")
        issue_out["detected_component"] = None if component == UNKNOWN_COMPONENT else component
        issue_out["component_detection_source"] = source

        if component != UNKNOWN_COMPONENT:
            # Keep payload consistency: files grouped by a component expose that component value.
            issue_out["component"] = component

        detection_trace_rows.append(
            {
                "id": issue.get("id"),
                "issue_number": issue.get("issue_number"),
                "component_field": issue.get("component"),
                "detected_component": None if component == UNKNOWN_COMPONENT else component,
                "detection_source": source,
            }
        )

        if component == UNKNOWN_COMPONENT:
            null_component_issues.append(issue_out)
            continue
        grouped.setdefault(component, []).append(issue_out)

    out_dir = source_path.parent / output_subdir
    manifest_rows: list[dict[str, Any]] = []

    for component in sorted(grouped.keys()):
        component_issues = grouped[component]
        datasource_name = f"{datasource_prefix}_{series_tag}_{component}"
        file_name = f"st_ready_issues_{series_tag.lower()}_{component.lower()}.json"
        out_file = out_dir / file_name

        out_payload = {
            "issues": component_issues,
        }
        if not dry_run:
            save_json(out_file, out_payload)

        manifest_rows.append(
            {
                "series": series_tag,
                "component": component,
                "datasource_name": datasource_name,
                "issues_count": len(component_issues),
                "output_file": str(out_file),
            }
        )

    if null_component_issues:
        null_file = out_dir / f"st_ready_issues_{series_tag.lower()}.json"
        null_payload = {
            "issues": null_component_issues,
        }
        if not dry_run:
            save_json(null_file, null_payload)

        manifest_rows.append(
            {
                "series": series_tag,
                "component": None,
                "datasource_name": f"{datasource_prefix}_{series_tag}",
                "issues_count": len(null_component_issues),
                "output_file": str(null_file),
            }
        )

    summary = {
        "source_file": str(source_path),
        "output_dir": str(out_dir),
        "created_at": utc_now_iso(),
        "series": series_tag,
        "source_issues_count": len(issue_objects),
        "components_count": len(grouped),
        "null_component_issues_count": len(null_component_issues),
        "detection_source_counts": detection_source_counts,
        "datasources": manifest_rows,
        "dry_run": dry_run,
    }

    summary_file = out_dir / f"summary_by_component_{series_tag.lower()}.json"
    if not dry_run:
        save_json(summary_file, summary)

        trace_file = out_dir / f"component_detection_trace_{series_tag.lower()}.json"
        save_json(
            trace_file,
            {
                "series": series_tag,
                "source_file": str(source_path),
                "rows": detection_trace_rows,
            },
        )

    return summary


def resolve_source_files(input_root: Path, pattern: str) -> list[Path]:
    """Resolve one best source file per `issues_json` directory.

    Priority per directory:
    1) `pattern` (usually Alfred-enriched with-images)
    2) each pattern in `FALLBACK_INPUT_PATTERNS`, in order

    This guarantees coverage of root + drivers/subrepos even when each repo has
    a different available variant (with Alfred, with-images only, or plain issues).
    """
    pattern_priority = [pattern] + list(FALLBACK_INPUT_PATTERNS)
    issues_dirs = sorted({path.parent for path in input_root.glob("**/issues_json/*.json")})

    selected: list[Path] = []
    for issues_dir in issues_dirs:
        chosen: Path | None = None
        for pat in pattern_priority:
            # Convert repo-root pattern to issues_json-local file glob.
            local_glob = pat.split("issues_json/", 1)[-1]
            matches = sorted(issues_dir.glob(local_glob))
            if matches:
                chosen = matches[0]
                break
        if chosen is not None:
            selected.append(chosen)

    # Preserve deterministic order and remove duplicates.
    return sorted(set(selected))


def main() -> None:
    """CLI entry point: split one file (`--input-file`) or every matching
    file under `--input-root` into per-component ST-ready issue payloads.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Split ST-ready issues-with-images payloads into per-component JSON files "
            "for datasource upload (issues_<SERIES>_<COMPONENT>)."
        )
    )
    parser.add_argument("--input-file", type=Path, help="Single source JSON file to split.")
    parser.add_argument("--input-root", type=Path, default=DEFAULT_INPUT_ROOT)
    parser.add_argument("--pattern", default=DEFAULT_INPUT_PATTERN)
    parser.add_argument("--output-subdir", default=DEFAULT_OUTPUT_SUBDIR)
    parser.add_argument("--datasource-prefix", default="issues")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    summaries: list[dict[str, Any]] = []

    if args.input_file:
        source_files = [args.input_file.resolve()]
    else:
        input_root = args.input_root.resolve()
        if not input_root.exists():
            raise FileNotFoundError(f"Input root not found: {input_root}")
        source_files = resolve_source_files(input_root=input_root, pattern=args.pattern)

    if not source_files:
        raise ValueError(
            "No source files found. Expected ST-ready issues-with-images JSON files "
            "(with or without Alfred suffix)."
        )

    for source_path in source_files:
        if not source_path.exists():
            raise FileNotFoundError(f"Input file not found: {source_path}")

        summary = split_payload_by_component(
            source_path=source_path,
            output_subdir=args.output_subdir,
            datasource_prefix=args.datasource_prefix,
            dry_run=args.dry_run,
        )
        summaries.append(summary)
        print(
            "[split_issues_by_component] "
            f"series={summary['series']} components={summary['components_count']} "
            f"issues={summary['source_issues_count']} output={summary['output_dir']}"
        )

    total_components = sum(int(s.get("components_count", 0)) for s in summaries)
    total_issues = sum(int(s.get("source_issues_count", 0)) for s in summaries)
    print(
        "[split_issues_by_component] done "
        f"files={len(summaries)} components={total_components} issues={total_issues}"
    )


if __name__ == "__main__":
    main()
