"""
Full evaluation pipeline — runs quality checks on each stage output.

Role in the evaluation stage
-----------------------------
This is the primary console-based, text-report evaluation script: for a
given repo (or all configured repos) it re-derives quality metrics directly
from each pipeline stage's output files, independent of any previously
computed stats, so it can be run standalone right after any stage to spot
check data health. It is the CLI counterpart to generate_evaluation_report.py
(which renders the same kind of metrics as charts/Excel instead of text).

Stages evaluated:
  1. Ingestion   — completeness of fetched data
  2. Cleaning    — validity rate, classification coverage
  3. Enrichment  — metadata completeness, image description quality
  4. Similarity  — related_issue_ids coverage
  5. Delivery    — schema conformance, export counts

Inputs
------
- ``data/raw_issues_<repo>.json``, ``data/raw_files_<repo>.json``
- ``data/clean_issues_<repo>.json``, ``data/clean_files_<repo>.json``
- ``data/docs_issues_<repo>_v2.json``, ``data/docs_files_<repo>_v2.json``
- ``data/docs_issues_<repo>_v2_sim.json``
- ``datasets/07_delivery/st_ready/by_series/<repo>/*_json/st_ready_*.json``
  and matching ``summary_*.json`` files

Outputs
-------
- Console-only: per-stage detailed report boxes plus a compact summary table
  with a qualitative score (EXCELLENT/GOOD/ACCEPTABLE/POOR) per stage. No
  files are written.

Usage:
    python pipeline/evaluation/run_full_evaluation.py --repo STM32CubeH7
    python pipeline/evaluation/run_full_evaluation.py --all

Arguments:
    --repo   Repository name to evaluate (default: STM32CubeH7).
    --all    Evaluate every repo listed in the resolved config instead of a single one.
"""

import argparse
import json
from pathlib import Path
from collections import Counter

from shared.utils.paths import DATA_DIR, get_config_path


def _pct(n: int, total: int) -> str:
    """Format n/total as a percentage string; return 'N/A' when total is 0."""
    if total == 0:
        return "N/A"
    return f"{n/total*100:.1f}%"


def _score_label(pct: float) -> str:
    """Map a coverage/success percentage to a qualitative label for reporting."""
    if pct >= 95:
        return "EXCELLENT"
    if pct >= 85:
        return "GOOD"
    if pct >= 70:
        return "ACCEPTABLE"
    return "POOR"


# ============================================================
# STAGE 1: INGESTION
# ============================================================
def eval_ingestion(repo: str) -> dict:
    """Check raw data completeness."""
    results = {"stage": "Ingestion", "repo": repo, "metrics": {}}

    raw_issues = DATA_DIR / f"raw_issues_{repo.lower()}.json"
    raw_files = DATA_DIR / f"raw_files_{repo.lower()}.json"

    if raw_issues.exists():
        issues = json.loads(raw_issues.read_text(encoding="utf-8"))
        results["metrics"]["raw_issues_count"] = len(issues)
        # Check issues have required fields
        with_body = sum(1 for i in issues if (i.get("body") or "").strip())
        results["metrics"]["issues_with_body"] = with_body
        results["metrics"]["issues_with_body_pct"] = round(with_body / max(len(issues), 1) * 100, 1)
    else:
        results["metrics"]["raw_issues_count"] = 0

    if raw_files.exists():
        files = json.loads(raw_files.read_text(encoding="utf-8"))
        results["metrics"]["raw_files_count"] = len(files)
        with_content = sum(1 for f in files if (f.get("content") or "").strip())
        results["metrics"]["files_with_content"] = with_content
        results["metrics"]["files_with_content_pct"] = round(with_content / max(len(files), 1) * 100, 1)
    else:
        results["metrics"]["raw_files_count"] = 0

    return results


# ============================================================
# STAGE 2: CLEANING
# ============================================================
def eval_cleaning(repo: str) -> dict:
    """Evaluate cleaning quality."""
    results = {"stage": "Cleaning", "repo": repo, "metrics": {}}

    # Issues
    clean_issues = DATA_DIR / f"clean_issues_{repo.lower()}.json"
    if clean_issues.exists():
        issues = json.loads(clean_issues.read_text(encoding="utf-8"))
        total = len(issues)
        valid = sum(1 for i in issues if i.get("is_valid", True))
        with_layer = sum(1 for i in issues if i.get("layer"))
        with_severity = sum(1 for i in issues if i.get("severity"))
        with_kind = sum(1 for i in issues if i.get("issue_kind"))
        with_board = sum(1 for i in issues if i.get("board"))
        with_component = sum(1 for i in issues if i.get("component"))

        results["metrics"]["issues_total"] = total
        results["metrics"]["issues_valid"] = valid
        results["metrics"]["issues_valid_pct"] = round(valid / max(total, 1) * 100, 1)
        results["metrics"]["issues_with_layer_pct"] = round(with_layer / max(total, 1) * 100, 1)
        results["metrics"]["issues_with_severity_pct"] = round(with_severity / max(total, 1) * 100, 1)
        results["metrics"]["issues_with_kind_pct"] = round(with_kind / max(total, 1) * 100, 1)
        results["metrics"]["issues_with_board_pct"] = round(with_board / max(total, 1) * 100, 1)
        results["metrics"]["issues_with_component_pct"] = round(with_component / max(total, 1) * 100, 1)

    # Files
    clean_files = DATA_DIR / f"clean_files_{repo.lower()}.json"
    if clean_files.exists():
        files = json.loads(clean_files.read_text(encoding="utf-8"))
        total = len(files)
        type_counts = Counter(f.get("file_type", "other") for f in files)
        other_count = type_counts.get("other", 0)
        classified = total - other_count
        non_empty = sum(1 for f in files if len((f.get("clean_text") or "").strip()) > 50)

        results["metrics"]["files_total"] = total
        results["metrics"]["files_classified_pct"] = round(classified / max(total, 1) * 100, 1)
        results["metrics"]["files_non_empty_pct"] = round(non_empty / max(total, 1) * 100, 1)
        results["metrics"]["file_type_distribution"] = dict(type_counts.most_common(10))

    return results


# ============================================================
# STAGE 3: ENRICHMENT
# ============================================================
def eval_enrichment(repo: str) -> dict:
    """Evaluate enrichment quality (docs V2)."""
    results = {"stage": "Enrichment", "repo": repo, "metrics": {}}

    # Issues docs
    docs_issues = DATA_DIR / f"docs_issues_{repo.lower()}_v2.json"
    if docs_issues.exists():
        docs = json.loads(docs_issues.read_text(encoding="utf-8"))
        total = len(docs)
        with_layer = sum(1 for d in docs if d.get("layer"))
        with_board = sum(1 for d in docs if d.get("board"))
        with_component = sum(1 for d in docs if d.get("component"))

        results["metrics"]["docs_issues_total"] = total
        results["metrics"]["docs_issues_with_layer_pct"] = round(with_layer / max(total, 1) * 100, 1)
        results["metrics"]["docs_issues_with_board_pct"] = round(with_board / max(total, 1) * 100, 1)
        results["metrics"]["docs_issues_with_component_pct"] = round(with_component / max(total, 1) * 100, 1)

    # Files docs
    docs_files = DATA_DIR / f"docs_files_{repo.lower()}_v2.json"
    if docs_files.exists():
        docs = json.loads(docs_files.read_text(encoding="utf-8"))
        total = len(docs)
        with_board = sum(1 for d in docs if d.get("board"))
        with_component = sum(1 for d in docs if d.get("component"))
        with_example = sum(1 for d in docs if d.get("example_name"))

        results["metrics"]["docs_files_total"] = total
        results["metrics"]["docs_files_with_board_pct"] = round(with_board / max(total, 1) * 100, 1)
        results["metrics"]["docs_files_with_component_pct"] = round(with_component / max(total, 1) * 100, 1)
        results["metrics"]["docs_files_with_example_pct"] = round(with_example / max(total, 1) * 100, 1)

    # Image descriptions
    total_images = 0
    images_with_desc = 0
    desc_lengths = []

    for path in [docs_issues, docs_files]:
        if not path.exists():
            continue
        docs = json.loads(path.read_text(encoding="utf-8"))
        for doc in docs:
            for rec in (doc.get("image_records") or []):
                total_images += 1
                desc = rec.get("alfred_description") or rec.get("description") or ""
                if desc.strip():
                    images_with_desc += 1
                    desc_lengths.append(len(desc.strip()))

    results["metrics"]["images_total"] = total_images
    results["metrics"]["images_with_description"] = images_with_desc
    results["metrics"]["images_success_rate_pct"] = round(images_with_desc / max(total_images, 1) * 100, 1)
    results["metrics"]["images_avg_desc_length"] = round(sum(desc_lengths) / max(len(desc_lengths), 1), 0)

    return results


# ============================================================
# STAGE 4: SIMILARITY
# ============================================================
def eval_similarity(repo: str) -> dict:
    """Evaluate similarity enrichment."""
    results = {"stage": "Similarity", "repo": repo, "metrics": {}}

    sim_path = DATA_DIR / f"docs_issues_{repo.lower()}_v2_sim.json"
    if not sim_path.exists():
        results["metrics"]["status"] = "NOT_RUN"
        return results

    docs = json.loads(sim_path.read_text(encoding="utf-8"))
    total = len(docs)
    with_related = sum(1 for d in docs if d.get("related_issue_ids"))
    related_counts = [len(d.get("related_issue_ids") or []) for d in docs]
    avg_related = round(sum(related_counts) / max(total, 1), 1)

    results["metrics"]["docs_total"] = total
    results["metrics"]["with_related_issues"] = with_related
    results["metrics"]["with_related_pct"] = round(with_related / max(total, 1) * 100, 1)
    results["metrics"]["avg_related_per_doc"] = avg_related

    return results


# ============================================================
# STAGE 5: DELIVERY
# ============================================================
def eval_delivery(repo: str) -> dict:
    """Evaluate ST-ready delivery outputs."""
    results = {"stage": "Delivery", "repo": repo, "metrics": {}}

    delivery_base = Path(DATA_DIR).parent / "datasets" / "07_delivery" / "st_ready" / "by_series" / repo.lower()

    if not delivery_base.exists():
        # Try alternate path
        delivery_base = DATA_DIR / ".." / "datasets" / "07_delivery" / "st_ready" / "by_series" / repo.lower()

    export_types = ["issues_json", "files_json", "resolver_cases_json", "diagnostic_cards_json"]

    for export_type in export_types:
        export_dir = delivery_base / export_type
        if export_dir.exists():
            json_files = list(export_dir.glob("st_ready_*.json"))
            if json_files:
                data = json.loads(json_files[0].read_text(encoding="utf-8"))
                if isinstance(data, list):
                    count = len(data)
                elif isinstance(data, dict) and "documents" in data:
                    count = len(data["documents"])
                else:
                    count = 1
                results["metrics"][f"{export_type}_count"] = count
            else:
                results["metrics"][f"{export_type}_count"] = 0
        else:
            results["metrics"][f"{export_type}_count"] = 0

    # Check summaries
    summary_files = list(delivery_base.rglob("summary_*.json")) if delivery_base.exists() else []
    results["metrics"]["summary_files_present"] = len(summary_files)

    return results


# ============================================================
# REPORT
# ============================================================
def print_stage_report(result: dict) -> None:
    """Print a boxed console report for a single stage's evaluation result.

    Args:
        result: A dict as returned by one of the eval_* functions, with keys
            ``stage``, ``repo``, and ``metrics``.
    """
    stage = result["stage"]
    repo = result["repo"]
    metrics = result["metrics"]

    print(f"\n┌{'─'*58}┐")
    print(f"│  {stage.upper():^54}  │")
    print(f"│  Repo: {repo:<48}  │")
    print(f"├{'─'*58}┤")

    for key, value in metrics.items():
        if isinstance(value, dict):
            print(f"│  {key}:")
            for k, v in value.items():
                print(f"│    {k}: {v}")
        else:
            label = key.replace("_", " ").title()
            if "pct" in key.lower():
                score = _score_label(value) if isinstance(value, (int, float)) else ""
                print(f"│  {label:<40} {value:>6}%  {score}")
            else:
                print(f"│  {label:<40} {value:>8}")

    print(f"└{'─'*58}┘")


def print_summary_table(all_results: list[dict]) -> None:
    """Print a compact summary table.

    For each stage, picks a single representative metric (defined by the
    hardcoded mapping below) so the summary fits in one line per stage
    instead of dumping every metric again.

    Args:
        all_results: List of per-stage result dicts (stage/repo/metrics),
            one per eval_* call.
    """
    print(f"\n{'='*70}")
    print(f"  EVALUATION SUMMARY")
    print(f"{'='*70}")
    print(f"  {'Stage':<15} {'Key Metric':<35} {'Value':<10} {'Score'}")
    print(f"  {'-'*15} {'-'*35} {'-'*10} {'-'*10}")

    for r in all_results:
        stage = r["stage"]
        metrics = r["metrics"]

        # Pick the most representative metric per stage
        if stage == "Ingestion":
            key = "issues_with_body_pct"
            label = "Issues with body"
        elif stage == "Cleaning":
            key = "issues_valid_pct"
            label = "Issues valid"
        elif stage == "Enrichment":
            key = "images_success_rate_pct"
            label = "Image desc success rate"
        elif stage == "Similarity":
            key = "with_related_pct"
            label = "Issues with related links"
        elif stage == "Delivery":
            key = "summary_files_present"
            label = "Summary files generated"
        else:
            key = list(metrics.keys())[0] if metrics else "N/A"
            label = key

        value = metrics.get(key, "N/A")
        if isinstance(value, (int, float)) and "pct" in key:
            score = _score_label(value)
            print(f"  {stage:<15} {label:<35} {value:>6}%   {score}")
        else:
            print(f"  {stage:<15} {label:<35} {str(value):>8}")

    print(f"{'='*70}\n")


# ============================================================
# MAIN
# ============================================================
def main():
    """CLI entry point: run all five stage evaluations and print detailed + summary reports."""
    parser = argparse.ArgumentParser(description="Run full evaluation pipeline")
    parser.add_argument("--repo", default="STM32CubeH7", help="Repository name")
    parser.add_argument("--all", action="store_true", help="Run for all repos in config")
    args = parser.parse_args()

    if args.all:
        cfg = json.loads(get_config_path().read_text(encoding="utf-8"))
        repos = cfg.get("repos", [args.repo])
    else:
        repos = [args.repo]

    for repo in repos:
        print(f"\n{'#'*60}")
        print(f"#  EVALUATING: {repo}")
        print(f"{'#'*60}")

        all_results = []

        # Run each stage evaluation
        all_results.append(eval_ingestion(repo))
        all_results.append(eval_cleaning(repo))
        all_results.append(eval_enrichment(repo))
        all_results.append(eval_similarity(repo))
        all_results.append(eval_delivery(repo))

        # Print detailed reports
        for r in all_results:
            print_stage_report(r)

        # Print summary
        print_summary_table(all_results)


if __name__ == "__main__":
    main()
