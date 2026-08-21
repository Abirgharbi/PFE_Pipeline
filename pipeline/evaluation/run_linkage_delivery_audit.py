"""Batch-audit issue<->PR/commit linkage and resolver/diagnostic delivery exports.

Role in the evaluation stage
-----------------------------
This script closes the loop between the linkage stage (issue_pr_commit_links)
and two delivery exports (resolver cases, diagnostic cards) that depend on
it: it (optionally) re-runs those exports, validates the linkage JSON against
its schema, checks that each export's ``summary_*.json`` counts match the
actual exported file contents (catching silent export bugs), and produces a
detailed breakdown of *why* issues ended up "unlinked" (no confirmed PR/commit
evidence) for one target repo. This is the main gate before shipping
resolver/diagnostic knowledge base content.

Inputs
------
- ``data/issue_pr_commit_links_<repo>.json`` (linkage stage output) and its
  ``_summary.json``/``_linked_only.json`` companions.
- ``shared/schemas/issue_pr_commit_links.schema.json`` (JSON Schema for validation).
- ``datasets/07_delivery/st_ready/resolver_cases_json/`` and
  ``diagnostic_cards_json/`` exports and their ``summary_*.json`` files.
- Calls into pipeline.delivery.export_st_ready_resolver_cases and
  pipeline.delivery.export_st_ready_diagnostic_cards to (re)generate exports
  unless ``--skip-export`` is passed.

Outputs
-------
- ``datasets/06_eval_outputs/linkage_delivery_batch_report.json`` / ``.md``:
  export execution status, schema validation results, and summary-coherence
  findings for every repo processed.
- ``datasets/06_eval_outputs/unlinked_audit_<repo>.json`` / ``.md``: reason
  breakdown, label frequency, and issue-number samples for unlinked issues
  in the ``--audit-repo`` target.

Usage (CLI)
-----------
    python pipeline/evaluation/run_linkage_delivery_audit.py
    python pipeline/evaluation/run_linkage_delivery_audit.py --repo STM32CubeH7 --skip-export
    python pipeline/evaluation/run_linkage_delivery_audit.py --audit-repo STM32CubeF4

Arguments:
    --repo                     Repo name, repeatable; defaults to all repos in config.
    --exclude-reference-only   Exclude reference_only resolver cases from export.
    --include-all-issues       Include all issues (not just rescued ones) in diagnostic cards.
    --audit-repo               Repo to run the unlinked-issue reason audit on (default STM32CubeH7).
    --skip-export              Skip re-running exports; only validate/audit existing artifacts.
"""

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import ValidationError, validate

from pipeline.delivery.export_st_ready_diagnostic_cards import export_repo_json as export_diagnostic_repo
from pipeline.delivery.export_st_ready_resolver_cases import export_repo_json as export_resolver_repo
from shared.utils.paths import DATA_DIR, PROJECT_ROOT, get_config_path


def load_config() -> dict[str, Any]:
    """Load the resolved pipeline config (config_all_series.json + overrides)."""
    return json.loads(get_config_path().read_text(encoding="utf-8"))


def load_json(path: Path, fallback: Any) -> Any:
    """Load a JSON file, returning fallback if it's missing or malformed.

    Centralizes the "tolerate missing/corrupt evaluation input" behavior used
    throughout this script, since a repo may not have run every stage yet.
    """
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return fallback


def reason_for_unlinked(record: dict[str, Any]) -> str:
    """Classify why one issue ended up with resolution_status == 'unlinked'.

    Applies a small decision tree over the evidence flags collected by the
    linkage stage (explicit PR/commit references, message-inferred commits,
    commits reached via linked PRs, merge-like commits) to produce an
    actionable root-cause label rather than a generic "unlinked" bucket.

    Args:
        record: One row from ``issue_pr_commit_links_<repo>.json`` with an
            ``evidence`` sub-dict.

    Returns:
        One of: "no_pr_no_commit_signal", "pr_reference_without_commit_trace",
        "message_inferred_only_but_unconfirmed", "merge_only_history", or the
        catch-all "other_mixed_gap".
    """
    evidence = record.get("evidence") or {}
    explicit_pr = bool(evidence.get("explicit_pr_numbers"))
    explicit_commits = bool(evidence.get("explicit_commit_shas"))
    message_commits = bool(evidence.get("message_inferred_commit_shas"))
    via_pr_commits = bool(evidence.get("commits_via_linked_prs"))
    merge_like = bool(evidence.get("merge_like_commit_shas"))

    if not explicit_pr and not explicit_commits and not message_commits and not via_pr_commits:
        return "no_pr_no_commit_signal"
    if explicit_pr and not (explicit_commits or message_commits or via_pr_commits):
        return "pr_reference_without_commit_trace"
    if message_commits and not explicit_pr and not explicit_commits and not via_pr_commits:
        return "message_inferred_only_but_unconfirmed"
    if merge_like and not (explicit_commits or message_commits):
        return "merge_only_history"
    return "other_mixed_gap"


def audit_unlinked(repo: str) -> dict[str, Any]:
    """Compute and write a breakdown of unlinked issues for one repo.

    Args:
        repo: Repo name whose linkage file to audit.

    Returns:
        Dict with unlinked rate, reason breakdown, sample issue numbers per
        reason (capped at 25), and top unlinked labels; also includes the
        paths of the JSON/Markdown reports written as a side effect.

    Side effects:
        Writes ``unlinked_audit_<repo>.json`` and ``.md`` under
        ``datasets/06_eval_outputs``.
    """
    links_path = DATA_DIR / f"issue_pr_commit_links_{repo.lower()}.json"
    links = load_json(links_path, [])
    if not isinstance(links, list):
        links = []

    total = len(links)
    unlinked = [row for row in links if isinstance(row, dict) and row.get("resolution_status") == "unlinked"]

    reason_counts: Counter[str] = Counter()
    reason_samples: dict[str, list[int]] = defaultdict(list)
    label_counts: Counter[str] = Counter()

    for row in unlinked:
        reason = reason_for_unlinked(row)
        reason_counts[reason] += 1
        issue_number = row.get("issue_number")
        if isinstance(issue_number, int) and len(reason_samples[reason]) < 25:
            reason_samples[reason].append(issue_number)
        for label in row.get("issue_labels") or []:
            if isinstance(label, str) and label.strip():
                label_counts[label.strip()] += 1

    out = {
        "repo": repo,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input_file": str(links_path),
        "issues_total": total,
        "unlinked_issues": len(unlinked),
        "unlinked_rate": round((len(unlinked) / total) if total else 0.0, 4),
        "reason_breakdown": dict(reason_counts),
        "reason_samples": {k: v for k, v in reason_samples.items()},
        "top_unlinked_labels": [{"label": label, "count": count} for label, count in label_counts.most_common(20)],
    }

    out_root = PROJECT_ROOT / "datasets" / "06_eval_outputs"
    out_root.mkdir(parents=True, exist_ok=True)
    json_path = out_root / f"unlinked_audit_{repo.lower()}.json"
    md_path = out_root / f"unlinked_audit_{repo.lower()}.md"

    json_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        f"# Unlinked Audit - {repo}",
        "",
        f"- Issues total: {out['issues_total']}",
        f"- Unlinked issues: {out['unlinked_issues']}",
        f"- Unlinked rate: {out['unlinked_rate']}",
        "",
        "## Reason breakdown",
    ]
    for reason, count in reason_counts.most_common():
        lines.append(f"- {reason}: {count}")

    lines.append("")
    lines.append("## Top unlinked labels")
    for item in out["top_unlinked_labels"][:12]:
        lines.append(f"- {item['label']}: {item['count']}")

    lines.append("")
    lines.append("## Issue samples per reason")
    for reason, issue_numbers in reason_samples.items():
        lines.append(f"- {reason}: {', '.join(str(x) for x in issue_numbers)}")

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    out["json_output"] = str(json_path)
    out["md_output"] = str(md_path)
    return out


def validate_issue_links_schema(repos: list[str]) -> list[dict[str, Any]]:
    """Validate each repo's linkage JSON file against its JSON Schema.

    Args:
        repos: Repo names to validate.

    Returns:
        List of per-repo result dicts with status "ok"/"missing"/"invalid"
        and an error message when applicable.
    """
    schema_path = PROJECT_ROOT / "shared" / "schemas" / "issue_pr_commit_links.schema.json"
    schema = load_json(schema_path, {})

    results: list[dict[str, Any]] = []
    for repo in repos:
        data_path = DATA_DIR / f"issue_pr_commit_links_{repo.lower()}.json"
        payload = load_json(data_path, None)
        entry = {
            "repo": repo,
            "data_file": str(data_path),
            "status": "ok",
            "error": None,
        }
        if payload is None:
            entry["status"] = "missing"
            entry["error"] = "data file not found or invalid json"
            results.append(entry)
            continue
        try:
            validate(instance=payload, schema=schema)
        except ValidationError as exc:
            entry["status"] = "invalid"
            entry["error"] = exc.message
        results.append(entry)
    return results


def check_summary_coherence(repo: str) -> dict[str, Any]:
    """Cross-check each export's summary_*.json counts against its actual file contents.

    A mismatch here typically indicates an export script bug (e.g. a summary
    written before the last few records were filtered out) rather than a data
    quality issue, so it is reported separately from schema/linkage problems.

    Args:
        repo: Repo name to check (linkage summary, resolver cases summary,
            diagnostic cards summary).

    Returns:
        Dict with status "ok"/"warning" and a list of human-readable problem
        descriptions (empty when status is "ok").
    """
    problems: list[str] = []

    links_summary_path = DATA_DIR / f"issue_pr_commit_links_{repo.lower()}_summary.json"
    links_summary = load_json(links_summary_path, {})
    links = load_json(DATA_DIR / f"issue_pr_commit_links_{repo.lower()}.json", [])
    linked_only = load_json(DATA_DIR / f"issue_pr_commit_links_{repo.lower()}_linked_only.json", [])

    if isinstance(links_summary, dict):
        expected_linked = int(links_summary.get("linked_issues") or 0)
        if expected_linked != len(linked_only):
            problems.append(
                f"linked_issues mismatch: summary={expected_linked}, linked_only_file={len(linked_only)}"
            )
        expected_unlinked = int(links_summary.get("unlinked_issues") or 0)
        real_unlinked = len([row for row in links if isinstance(row, dict) and row.get("resolution_status") == "unlinked"])
        if expected_unlinked != real_unlinked:
            problems.append(
                f"unlinked_issues mismatch: summary={expected_unlinked}, computed={real_unlinked}"
            )

    resolver_summary_path = PROJECT_ROOT / "datasets" / "07_delivery" / "st_ready" / "resolver_cases_json" / f"summary_resolver_cases_{repo.lower()}.json"
    resolver_summary = load_json(resolver_summary_path, {})
    resolver_output_path = None
    if isinstance(resolver_summary, dict) and resolver_summary.get("output_file"):
        resolver_output_path = Path(str(resolver_summary.get("output_file")))
    if not resolver_output_path:
        resolver_output_path = (
            PROJECT_ROOT
            / "datasets"
            / "07_delivery"
            / "st_ready"
            / "resolver_cases_json"
            / f"st_ready_resolver_cases_{repo.lower()}.json"
        )

    resolver_payload = load_json(resolver_output_path, {})
    resolver_cases = resolver_payload.get("resolver_cases") if isinstance(resolver_payload, dict) else []
    if isinstance(resolver_summary, dict):
        expected_exported = int(resolver_summary.get("exported_cases") or 0)
        if expected_exported != len(resolver_cases or []):
            problems.append(
                f"resolver exported_cases mismatch: summary={expected_exported}, file={len(resolver_cases or [])}"
            )

    diag_summary_path = PROJECT_ROOT / "datasets" / "07_delivery" / "st_ready" / "diagnostic_cards_json" / f"summary_diagnostic_cards_{repo.lower()}.json"
    diag_summary = load_json(diag_summary_path, {})
    diag_output_path = None
    if isinstance(diag_summary, dict) and diag_summary.get("output_file"):
        diag_output_path = Path(str(diag_summary.get("output_file")))
    if not diag_output_path:
        diag_output_path = (
            PROJECT_ROOT
            / "datasets"
            / "07_delivery"
            / "st_ready"
            / "diagnostic_cards_json"
            / f"st_ready_diagnostic_cards_{repo.lower()}.json"
        )

    diag_payload = load_json(diag_output_path, [])
    if not isinstance(diag_payload, list):
        diag_payload = []
    if isinstance(diag_summary, dict):
        expected_cards = int(diag_summary.get("exported_cards") or 0)
        if expected_cards != len(diag_payload):
            problems.append(
                f"diagnostic exported_cards mismatch: summary={expected_cards}, file={len(diag_payload)}"
            )

    return {
        "repo": repo,
        "status": "ok" if not problems else "warning",
        "problems": problems,
    }


def write_batch_report(report: dict[str, Any]) -> tuple[Path, Path]:
    """Write the combined batch audit report (JSON + Markdown) to disk.

    Args:
        report: Aggregate dict with export_results/schema_validation/
            summary_coherence/unlinked_audit sections.

    Returns:
        Tuple of (json_path, md_path) written.
    """
    out_root = PROJECT_ROOT / "datasets" / "06_eval_outputs"
    out_root.mkdir(parents=True, exist_ok=True)

    json_path = out_root / "linkage_delivery_batch_report.json"
    md_path = out_root / "linkage_delivery_batch_report.md"

    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Linkage Delivery Batch Report",
        "",
        f"- Generated at: {report.get('generated_at')}",
        f"- Repos: {', '.join(report.get('repos') or [])}",
        f"- Exports executed: {report.get('exports_executed')}",
        "",
        "## Export results",
    ]

    for item in report.get("export_results", []):
        lines.append(
            f"- {item.get('repo')}: resolver={item.get('resolver_status')} diagnostic={item.get('diagnostic_status')}"
        )

    lines.append("")
    lines.append("## Schema validation")
    for item in report.get("schema_validation", []):
        status = item.get("status")
        if status == "ok":
            lines.append(f"- {item.get('repo')}: ok")
        else:
            lines.append(f"- {item.get('repo')}: {status} ({item.get('error')})")

    lines.append("")
    lines.append("## Summary coherence")
    for item in report.get("summary_coherence", []):
        if item.get("status") == "ok":
            lines.append(f"- {item.get('repo')}: ok")
        else:
            lines.append(f"- {item.get('repo')}: warning")
            for problem in item.get("problems") or []:
                lines.append(f"  - {problem}")

    unlinked = report.get("unlinked_audit") or {}
    if unlinked:
        lines.append("")
        lines.append("## Unlinked audit")
        lines.append(
            f"- {unlinked.get('repo')}: {unlinked.get('unlinked_issues')}/{unlinked.get('issues_total')} "
            f"(rate={unlinked.get('unlinked_rate')})"
        )
        for reason, count in (unlinked.get("reason_breakdown") or {}).items():
            lines.append(f"- {reason}: {count}")

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def main() -> None:
    """CLI entry point: run exports, validate schema/coherence, and audit unlinked issues."""
    parser = argparse.ArgumentParser(
        description="Run resolver/diagnostic exports for repos, then validate schema/coherence and audit unlinked issues."
    )
    parser.add_argument("--repo", action="append", help="Repo name, repeatable. Defaults to config repos.")
    parser.add_argument(
        "--exclude-reference-only",
        action="store_true",
        help="Exclude reference_only resolver cases from export.",
    )
    parser.add_argument(
        "--include-all-issues",
        action="store_true",
        help="Include all issues when generating diagnostic cards (default: rescued only).",
    )
    parser.add_argument(
        "--audit-repo",
        default="STM32CubeH7",
        help="Repo to audit for unlinked linkage gaps (default: STM32CubeH7).",
    )
    parser.add_argument(
        "--skip-export",
        action="store_true",
        help="Skip export calls and only run validations/audit on current artifacts.",
    )
    args = parser.parse_args()

    cfg = load_config()
    repos = args.repo or cfg.get("repos", [])
    if not repos:
        raise ValueError("No repos provided and no repos found in config")

    include_reference_only = not args.exclude_reference_only

    export_results: list[dict[str, Any]] = []
    if not args.skip_export:
        for repo in repos:
            result: dict[str, Any] = {
                "repo": repo,
                "resolver_status": "ok",
                "diagnostic_status": "ok",
                "resolver_error": None,
                "diagnostic_error": None,
            }
            try:
                export_resolver_repo(repo=repo, include_reference_only=include_reference_only)
            except Exception as exc:  # noqa: BLE001
                result["resolver_status"] = "error"
                result["resolver_error"] = str(exc)
            try:
                export_diagnostic_repo(repo=repo, include_all_issues=args.include_all_issues)
            except Exception as exc:  # noqa: BLE001
                result["diagnostic_status"] = "error"
                result["diagnostic_error"] = str(exc)
            export_results.append(result)
    else:
        for repo in repos:
            export_results.append(
                {
                    "repo": repo,
                    "resolver_status": "skipped",
                    "diagnostic_status": "skipped",
                    "resolver_error": None,
                    "diagnostic_error": None,
                }
            )

    schema_validation = validate_issue_links_schema(repos)
    summary_coherence = [check_summary_coherence(repo) for repo in repos]
    unlinked_audit = audit_unlinked(args.audit_repo)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repos": repos,
        "exports_executed": not args.skip_export,
        "export_results": export_results,
        "schema_validation": schema_validation,
        "summary_coherence": summary_coherence,
        "unlinked_audit": unlinked_audit,
    }

    json_path, md_path = write_batch_report(report)

    print(f"[BATCH] report json -> {json_path}")
    print(f"[BATCH] report md   -> {md_path}")
    print(f"[BATCH] unlinked audit -> {unlinked_audit.get('json_output')}")


if __name__ == "__main__":
    main()
