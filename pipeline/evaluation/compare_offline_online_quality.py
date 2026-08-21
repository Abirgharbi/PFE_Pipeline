"""Compare offline (manual) benchmark scores against online ST Quality Index scores.

Role in the evaluation stage
-----------------------------
The project runs two parallel quality assessments for the same benchmark
question set: an *offline* manual scoring pass (humans grading answers on a
0-7 rubric, recorded in a CSV) and an *online* pass where the deployed ST
ChatGPT persona is graded by the built-in "ST Quality Index" (0-100 score).
This script merges both sources by ``(run_id, question_id)``, normalizes
scales, and produces per-scope (global/issues/files/mixed) averages plus an
A/B delta table, so regressions or improvements between two pipeline/config
versions ("run A" vs "run B") are visible at a glance.

Inputs
------
- Offline scored CSV (default
  ``datasets/06_eval_outputs/h7_eval_30q_scoring_template_results_scored.csv``)
  with columns ``run_id``, ``question_id``, ``question_group``,
  ``total_0_to_7``.
- Online scores CSV (default
  ``datasets/06_eval_outputs/quality_index_30q_online_scores.csv``) with a
  score column named ``quality_index_score_0_to_100``, ``score_0_to_100``, or
  ``score``. This file is optional; if missing, only offline stats are
  produced and a template is written to help fill it in.

Outputs
-------
- Online scores template CSV (pre-filled with run_id/question_id rows,
  empty score column) to guide manual/online score entry.
- Summary CSV and Markdown with per-scope offline/online averages and the
  online-minus-offline delta, plus an ``A->B`` comparison row per scope.

Usage (CLI)
-----------
    python pipeline/evaluation/compare_offline_online_quality.py
    python pipeline/evaluation/compare_offline_online_quality.py \\
        --offline-scored-csv <path> --online-scores-csv <path> \\
        --out-summary-csv <path> --out-summary-md <path>
"""

import argparse
import csv
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from shared.utils.paths import PROJECT_ROOT


def normalize_qid(raw: str | None) -> str:
    """Normalize a question id to the canonical ``Q<NN>`` form (e.g. ``Q07``).

    Accepts already-prefixed ids, bare digits, or ids embedded in other text,
    so offline/online CSVs authored with slightly different conventions can
    still be joined on the same key.
    """
    value = (raw or "").strip().upper()
    if not value:
        return ""
    if value.startswith("Q"):
        return value
    if value.isdigit():
        return f"Q{int(value):02d}"
    match = re.search(r"(\d+)", value)
    if match:
        return f"Q{int(match.group(1)):02d}"
    return value


def qid_sort_key(qid: str) -> tuple[int, str]:
    """Sort key that orders question ids numerically (Q2 before Q10)."""
    match = re.search(r"(\d+)", qid or "")
    if match:
        return int(match.group(1)), qid
    return 9999, qid


def to_float(raw: str | None) -> float | None:
    """Best-effort string-to-float conversion, returning None for blank/invalid values."""
    value = (raw or "").strip()
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def load_offline_scored(path: Path) -> dict[tuple[str, str], dict[str, Any]]:
    """Load the manually-scored offline benchmark CSV.

    Args:
        path: CSV with columns run_id/question_id/question_group/total_0_to_7.

    Returns:
        Mapping of (run_id, question_id) -> row dict, including the score
        normalized to a 0-100 scale for direct comparison with the online
        Quality Index.

    Raises:
        FileNotFoundError: If the offline CSV does not exist (this file is
        the required baseline; there is no meaningful comparison without it).
    """
    if not path.exists():
        raise FileNotFoundError(f"Offline scored file not found: {path}")

    out: dict[tuple[str, str], dict[str, Any]] = {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            run_id = (row.get("run_id") or "").strip()
            qid = normalize_qid(row.get("question_id"))
            if not run_id or not qid:
                continue

            offline_total = to_float(row.get("total_0_to_7"))
            if offline_total is None:
                continue

            key = (run_id, qid)
            out[key] = {
                "run_id": run_id,
                "dataset_label": (row.get("dataset_label") or "").strip(),
                "question_id": qid,
                "question_group": (row.get("question_group") or "").strip().lower() or "unknown",
                "offline_total_0_to_7": offline_total,
                # Normalize the 0-7 rubric score to a 0-100 scale so it can be
                # directly compared/subtracted against the online Quality Index.
                "offline_total_0_to_100": round((offline_total / 7.0) * 100.0, 2),
            }
    return out


def detect_online_score_column(fieldnames: list[str]) -> str | None:
    """Find which of the accepted score column names is present in a CSV header.

    Different exports of the online Quality Index use slightly different
    column names; this checks a priority list case-insensitively.

    Returns:
        The actual (original-case) column name found, or None if none match.
    """
    candidates = [
        "quality_index_score_0_to_100",
        "score_0_to_100",
        "score",
    ]
    lowered = {name.lower(): name for name in fieldnames}
    for candidate in candidates:
        if candidate.lower() in lowered:
            return lowered[candidate.lower()]
    return None


def load_online_scores(path: Path) -> dict[tuple[str, str], dict[str, Any]]:
    """Load the online ST Quality Index scores CSV, if present.

    Args:
        path: CSV with a score column (see detect_online_score_column) and
            run_id/question_id columns.

    Returns:
        Mapping of (run_id, question_id) -> row dict. Returns an empty dict
        (not an error) when the file does not exist yet, since online scores
        are typically collected after the offline pass and may not be ready.

    Raises:
        ValueError: If the file exists but has none of the accepted score
        column names.
    """
    if not path.exists():
        return {}

    out: dict[tuple[str, str], dict[str, Any]] = {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        score_col = detect_online_score_column(fieldnames)
        if score_col is None:
            raise ValueError(
                "Online scores file must contain one of: "
                "quality_index_score_0_to_100, score_0_to_100, score"
            )

        for row in reader:
            run_id = (row.get("run_id") or "").strip()
            qid = normalize_qid(row.get("question_id"))
            if not run_id or not qid:
                continue

            online_score = to_float(row.get(score_col))
            key = (run_id, qid)
            out[key] = {
                "run_id": run_id,
                "question_id": qid,
                "dataset_label": (row.get("dataset_label") or "").strip(),
                "question_group": (row.get("question_group") or "").strip().lower(),
                "online_score_0_to_100": online_score,
                "online_reason": (row.get("quality_index_reason") or row.get("reason") or "").strip(),
            }
    return out


def write_online_template(path: Path, offline_rows: dict[tuple[str, str], dict[str, Any]]) -> None:
    """Write a blank online-scores CSV template pre-populated from offline rows.

    This lets a reviewer fill in only the score/reason columns for each
    (run_id, question_id) pair that already has an offline score, instead of
    re-typing identifying columns by hand.

    Args:
        path: Output CSV path for the template.
        offline_rows: Offline rows keyed by (run_id, question_id), used to
            derive the rows to pre-fill.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = sorted(
        offline_rows.values(),
        key=lambda item: (item.get("run_id") or "", qid_sort_key(item.get("question_id") or "")),
    )
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "run_id",
                "dataset_label",
                "question_id",
                "question_group",
                "quality_index_score_0_to_100",
                "quality_index_reason",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "run_id": row.get("run_id"),
                    "dataset_label": row.get("dataset_label"),
                    "question_id": row.get("question_id"),
                    "question_group": row.get("question_group"),
                    "quality_index_score_0_to_100": "",
                    "quality_index_reason": "",
                }
            )


def merge_offline_online(
    offline_rows: dict[tuple[str, str], dict[str, Any]],
    online_rows: dict[tuple[str, str], dict[str, Any]],
) -> list[dict[str, Any]]:
    """Join offline and online rows on (run_id, question_id) and compute deltas.

    Args:
        offline_rows: Offline scores keyed by (run_id, question_id).
        online_rows: Online scores keyed by (run_id, question_id); may be
            missing entries when online scoring is incomplete.

    Returns:
        List of merged row dicts, one per offline row, sorted by run_id then
        question id. ``delta_online_minus_offline`` is None when the online
        score for that key is not yet available.
    """
    merged: list[dict[str, Any]] = []
    for key, offline in sorted(offline_rows.items(), key=lambda item: (item[0][0], qid_sort_key(item[0][1]))):
        online = online_rows.get(key, {})
        online_score = online.get("online_score_0_to_100")
        offline_score = offline.get("offline_total_0_to_100")
        delta = None
        if isinstance(online_score, (float, int)) and isinstance(offline_score, (float, int)):
            delta = round(float(online_score) - float(offline_score), 2)

        merged.append(
            {
                "run_id": offline.get("run_id"),
                "dataset_label": offline.get("dataset_label") or online.get("dataset_label") or "",
                "question_id": offline.get("question_id"),
                "question_group": offline.get("question_group") or online.get("question_group") or "unknown",
                "offline_total_0_to_7": offline.get("offline_total_0_to_7"),
                "offline_total_0_to_100": offline_score,
                "online_score_0_to_100": online_score,
                "delta_online_minus_offline": delta,
                "online_reason": online.get("online_reason") or "",
            }
        )
    return merged


def aggregate_summary(merged_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Aggregate merged rows into per-scope averages plus an A/B delta table.

    Each row is counted both under its own ``run_id`` and under a synthetic
    "global" scope, and both under its ``question_group`` and the same
    "global" scope, so the summary answers both "how did run X do overall"
    and "how did run X do on issues-only questions" without a second pass.
    When both run "A" and run "B" exist for a scope, an extra ``A->B`` row is
    appended with the point-by-point difference, making regressions/gains
    immediately visible.

    Args:
        merged_rows: Rows produced by merge_offline_online.

    Returns:
        List of summary rows (per-scope averages, followed by A->B deltas).
    """
    by_scope: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in merged_rows:
        run_id = row.get("run_id") or ""
        group = row.get("question_group") or "unknown"
        by_scope[(run_id, "global")].append(row)
        by_scope[(run_id, group)].append(row)

    scope_order = {"global": 0, "issues": 1, "files": 2, "mixed": 3}
    summary_rows: list[dict[str, Any]] = []
    for (run_id, scope), rows in sorted(
        by_scope.items(), key=lambda item: (item[0][0], scope_order.get(item[0][1], 99), item[0][1])
    ):
        offline_vals = [float(r["offline_total_0_to_7"]) for r in rows if r.get("offline_total_0_to_7") is not None]
        offline_100_vals = [float(r["offline_total_0_to_100"]) for r in rows if r.get("offline_total_0_to_100") is not None]
        online_vals = [float(r["online_score_0_to_100"]) for r in rows if r.get("online_score_0_to_100") is not None]

        offline_avg_0_to_7 = round(sum(offline_vals) / len(offline_vals), 2) if offline_vals else None
        offline_avg_0_to_100 = round(sum(offline_100_vals) / len(offline_100_vals), 2) if offline_100_vals else None
        online_avg_0_to_100 = round(sum(online_vals) / len(online_vals), 2) if online_vals else None
        delta_online_minus_offline = None
        if offline_avg_0_to_100 is not None and online_avg_0_to_100 is not None:
            delta_online_minus_offline = round(online_avg_0_to_100 - offline_avg_0_to_100, 2)

        dataset_label = ""
        for row in rows:
            label = (row.get("dataset_label") or "").strip()
            if label:
                dataset_label = label
                break

        online_coverage = f"{len(online_vals)}/{len(rows)}"
        notes = "offline only"
        if online_vals:
            notes = f"online coverage {online_coverage}"

        summary_rows.append(
            {
                "scope": scope,
                "run_id": run_id,
                "dataset_label": dataset_label,
                "offline_avg_total_0_to_7": offline_avg_0_to_7,
                "offline_avg_0_to_100": offline_avg_0_to_100,
                "online_avg_0_to_100": online_avg_0_to_100,
                "delta_online_minus_offline_points": delta_online_minus_offline,
                "notes": notes,
            }
        )

    # Build A/B comparison rows: for each scope where both runs "A" and "B"
    # exist, compute the point-by-point delta (B - A) to highlight regressions/gains.
    by_scope_run = {(row["scope"], row["run_id"]): row for row in summary_rows}
    ab_rows: list[dict[str, Any]] = []
    for scope in sorted({row["scope"] for row in summary_rows}, key=lambda s: scope_order.get(s, 99)):
        row_a = by_scope_run.get((scope, "A"))
        row_b = by_scope_run.get((scope, "B"))
        if not row_a or not row_b:
            continue

        def safe_diff(key: str) -> float | None:
            left = row_a.get(key)
            right = row_b.get(key)
            if left is None or right is None:
                return None
            return round(float(right) - float(left), 2)

        ab_rows.append(
            {
                "scope": scope,
                "run_id": "A->B",
                "dataset_label": f"{row_a.get('dataset_label') or 'A'}->{row_b.get('dataset_label') or 'B'}",
                "offline_avg_total_0_to_7": safe_diff("offline_avg_total_0_to_7"),
                "offline_avg_0_to_100": safe_diff("offline_avg_0_to_100"),
                "online_avg_0_to_100": safe_diff("online_avg_0_to_100"),
                "delta_online_minus_offline_points": safe_diff("delta_online_minus_offline_points"),
                "notes": "positive means B better than A",
            }
        )

    return summary_rows + ab_rows


def write_summary_csv(path: Path, summary_rows: list[dict[str, Any]]) -> None:
    """Write the per-scope summary (and A/B delta rows) to a CSV file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "scope",
                "run_id",
                "dataset_label",
                "offline_avg_total_0_to_7",
                "offline_avg_0_to_100",
                "online_avg_0_to_100",
                "delta_online_minus_offline_points",
                "notes",
            ],
        )
        writer.writeheader()
        writer.writerows(summary_rows)


def write_summary_markdown(path: Path, summary_rows: list[dict[str, Any]]) -> None:
    """Write the same summary as a human-readable Markdown table with a legend."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Offline vs Online Evaluation Summary",
        "",
        "Columns:",
        "- offline_avg_total_0_to_7: local manual score average (/7)",
        "- offline_avg_0_to_100: offline score normalized to /100",
        "- online_avg_0_to_100: ST Quality Index score average (/100)",
        "- delta_online_minus_offline_points: online - offline(normalized)",
        "",
        "| scope | run_id | dataset_label | offline_avg_total_0_to_7 | offline_avg_0_to_100 | online_avg_0_to_100 | delta_online_minus_offline_points | notes |",
        "|---|---|---|---:|---:|---:|---:|---|",
    ]
    for row in summary_rows:
        lines.append(
            "| {scope} | {run_id} | {dataset_label} | {offline_avg_total_0_to_7} | {offline_avg_0_to_100} | {online_avg_0_to_100} | {delta_online_minus_offline_points} | {notes} |".format(
                scope=row.get("scope") or "",
                run_id=row.get("run_id") or "",
                dataset_label=row.get("dataset_label") or "",
                offline_avg_total_0_to_7=row.get("offline_avg_total_0_to_7") if row.get("offline_avg_total_0_to_7") is not None else "",
                offline_avg_0_to_100=row.get("offline_avg_0_to_100") if row.get("offline_avg_0_to_100") is not None else "",
                online_avg_0_to_100=row.get("online_avg_0_to_100") if row.get("online_avg_0_to_100") is not None else "",
                delta_online_minus_offline_points=row.get("delta_online_minus_offline_points") if row.get("delta_online_minus_offline_points") is not None else "",
                notes=row.get("notes") or "",
            )
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    """CLI entry point: load offline/online CSVs, merge, aggregate, and write reports."""
    parser = argparse.ArgumentParser(
        description=(
            "Compare offline manual benchmark scores with online ST Quality Index scores "
            "and produce A/B summaries by block."
        )
    )
    parser.add_argument(
        "--offline-scored-csv",
        type=Path,
        default=PROJECT_ROOT / "datasets" / "06_eval_outputs" / "h7_eval_30q_scoring_template_results_scored.csv",
        help="Offline scored CSV with columns run_id/question_id/question_group/total_0_to_7.",
    )
    parser.add_argument(
        "--online-scores-csv",
        type=Path,
        default=PROJECT_ROOT / "datasets" / "06_eval_outputs" / "quality_index_30q_online_scores.csv",
        help="Online Quality Index CSV with score column quality_index_score_0_to_100.",
    )
    parser.add_argument(
        "--write-online-template",
        type=Path,
        default=PROJECT_ROOT / "datasets" / "06_eval_outputs" / "quality_index_30q_online_scores_template.csv",
        help="Template path for online scores import.",
    )
    parser.add_argument(
        "--out-summary-csv",
        type=Path,
        default=PROJECT_ROOT / "datasets" / "06_eval_outputs" / "offline_online_30q_summary.csv",
        help="Output CSV summary path.",
    )
    parser.add_argument(
        "--out-summary-md",
        type=Path,
        default=PROJECT_ROOT / "datasets" / "06_eval_outputs" / "offline_online_30q_summary.md",
        help="Output Markdown summary path.",
    )
    args = parser.parse_args()

    offline_rows = load_offline_scored(args.offline_scored_csv)
    write_online_template(args.write_online_template, offline_rows)

    online_rows = load_online_scores(args.online_scores_csv)
    merged_rows = merge_offline_online(offline_rows, online_rows)
    summary_rows = aggregate_summary(merged_rows)

    write_summary_csv(args.out_summary_csv, summary_rows)
    write_summary_markdown(args.out_summary_md, summary_rows)

    print(f"[OFFLINE/ONLINE] Offline rows: {len(offline_rows)}")
    print(f"[OFFLINE/ONLINE] Online rows loaded: {len(online_rows)}")
    print(f"[OFFLINE/ONLINE] Online template: {args.write_online_template}")
    print(f"[OFFLINE/ONLINE] Summary CSV: {args.out_summary_csv}")
    print(f"[OFFLINE/ONLINE] Summary MD: {args.out_summary_md}")


if __name__ == "__main__":
    main()
