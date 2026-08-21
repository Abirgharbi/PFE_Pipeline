"""
Generate detailed evaluation report with charts for the PFE report.

Role in the evaluation stage
-----------------------------
This is the "presentation layer" of the evaluation stage: it re-reads the
same intermediate artifacts as run_full_evaluation.py (raw/clean/docs/sim/
delivery JSON files) but, instead of printing text, renders matplotlib
charts and an Excel workbook suitable for direct inclusion in the PFE report
or a stakeholder presentation. It also optionally compiles a LaTeX report
that embeds the generated charts into a PDF.

Produces:
  - Console summary
  - Excel report with all metrics per stage
  - PNG charts (bar charts, pie charts) for each stage
  - Overall pipeline score dashboard

Inputs
------
- ``data/raw_issues_<repo>.json``, ``data/raw_files_<repo>.json`` (ingestion)
- ``data/clean_issues_<repo>.json``, ``data/clean_files_<repo>.json`` (cleaning)
- ``data/docs_issues_<repo>_v2.json``, ``data/docs_files_<repo>_v2.json`` (enrichment)
- ``data/docs_issues_<repo>_v2_sim.json`` (similarity)
- ``datasets/07_delivery/st_ready/by_series/<repo>/*_json/st_ready_*.json`` and
  ``*_with_alfred_image_text.json`` (delivery + Alfred image enrichment)
- ``docs/evaluation_report.tex`` (optional, only when ``--pdf`` is used)

Usage:
    python pipeline/evaluation/generate_evaluation_report.py --repo STM32CubeH7
    python pipeline/evaluation/generate_evaluation_report.py --all
    python pipeline/evaluation/generate_evaluation_report.py --repo STM32CubeH7 --pdf

Arguments:
    --repo   Repository name to evaluate (default: STM32CubeH7).
    --all    Evaluate every repo listed in the resolved config instead of a single one.
    --pdf    After generating charts/Excel, also compile docs/evaluation_report.tex
             to PDF via pdflatex (requires MiKTeX/TeX Live installed).

Output:
    datasets/07_delivery/st_ready/evaluation_report/
        ├── evaluation_report.xlsx
        ├── 01_ingestion_completeness.png
        ├── 02_cleaning_validity.png
        ├── 03_enrichment_metadata.png
        ├── 03_enrichment_images.png
        ├── 04_similarity_coverage.png
        ├── 05_delivery_volumes.png
        └── 00_pipeline_dashboard.png
"""

import argparse
import json
import subprocess
import shutil
from pathlib import Path
from collections import Counter

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
except ImportError:
    print("Install matplotlib: pip install matplotlib")
    raise SystemExit(1)

try:
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
except ImportError:
    print("Install openpyxl: pip install openpyxl")
    raise SystemExit(1)

from shared.utils.paths import DATA_DIR, get_config_path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = PROJECT_ROOT / "datasets" / "07_delivery" / "st_ready" / "evaluation_report"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Colors
ST_BLUE = "#03234B"
ST_LIGHT_BLUE = "#3CB4E6"
ST_GREEN = "#4CAF50"
ST_ORANGE = "#FF9800"
ST_RED = "#F44336"
ST_GRAY = "#9E9E9E"

SCORE_COLORS = {
    "EXCELLENT": ST_GREEN,
    "GOOD": ST_LIGHT_BLUE,
    "ACCEPTABLE": ST_ORANGE,
    "POOR": ST_RED,
}


def _pct(n, total):
    """Return n/total as a percentage rounded to 1 decimal, or 0.0 if total is 0."""
    if total == 0:
        return 0.0
    return round(n / total * 100, 1)


def _score_label(pct):
    """Map a coverage/success percentage to a qualitative label used for chart coloring."""
    if pct >= 95:
        return "EXCELLENT"
    if pct >= 85:
        return "GOOD"
    if pct >= 70:
        return "ACCEPTABLE"
    return "POOR"


def _safe_pie(ax, values, labels, colors, title, autopct="%1.1f%%", startangle=90, explode=None):
    """Draw a pie chart only when there is data; otherwise show a clear no-data panel."""
    total = sum(float(v) for v in values)
    if total <= 0:
        ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)
        ax.axis("off")
        ax.set_title(title)
        return

    kwargs = {
        "labels": labels,
        "colors": colors,
        "autopct": autopct,
        "startangle": startangle,
    }
    if explode is not None:
        kwargs["explode"] = explode
    ax.pie(values, **kwargs)
    ax.set_title(title)


# ============================================================
# DATA COLLECTION
# ============================================================

def collect_ingestion(repo: str) -> dict:
    """Compute raw-data completeness metrics for the ingestion stage.

    Args:
        repo: Repo name used to locate ``raw_issues_<repo>.json`` /
            ``raw_files_<repo>.json`` under DATA_DIR.

    Returns:
        Dict of counts/percentages (issues with body/title/labels, files with
        content). Missing input files simply omit their metrics rather than
        raising, since a repo may not have both issues and files ingested yet.
    """
    metrics = {}
    raw_issues = DATA_DIR / f"raw_issues_{repo.lower()}.json"
    raw_files = DATA_DIR / f"raw_files_{repo.lower()}.json"

    if raw_issues.exists():
        issues = json.loads(raw_issues.read_text(encoding="utf-8"))
        total = len(issues)
        with_body = sum(1 for i in issues if (i.get("body") or "").strip())
        with_title = sum(1 for i in issues if (i.get("title") or "").strip())
        with_labels = sum(1 for i in issues if i.get("labels"))
        metrics["issues_total"] = total
        metrics["issues_with_body"] = with_body
        metrics["issues_with_body_pct"] = _pct(with_body, total)
        metrics["issues_with_title_pct"] = _pct(with_title, total)
        metrics["issues_with_labels_pct"] = _pct(with_labels, total)

    if raw_files.exists():
        files = json.loads(raw_files.read_text(encoding="utf-8"))
        total = len(files)
        with_content = sum(1 for f in files if (f.get("content") or "").strip())
        metrics["files_total"] = total
        metrics["files_with_content"] = with_content
        metrics["files_with_content_pct"] = _pct(with_content, total)

    return metrics


def collect_cleaning(repo: str) -> dict:
    """Compute cleaning-stage metrics: validity rate and classification coverage.

    Args:
        repo: Repo name used to locate ``clean_issues_<repo>.json`` /
            ``clean_files_<repo>.json`` under DATA_DIR.

    Returns:
        Dict with issue validity/metadata coverage percentages, layer and
        severity distributions, and file type classification coverage.
    """
    metrics = {}

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

        metrics["issues_total"] = total
        metrics["issues_valid_pct"] = _pct(valid, total)
        metrics["issues_with_layer_pct"] = _pct(with_layer, total)
        metrics["issues_with_severity_pct"] = _pct(with_severity, total)
        metrics["issues_with_kind_pct"] = _pct(with_kind, total)
        metrics["issues_with_board_pct"] = _pct(with_board, total)
        metrics["issues_with_component_pct"] = _pct(with_component, total)

        # Layer distribution
        metrics["layer_distribution"] = dict(Counter(i.get("layer", "unknown") for i in issues))
        metrics["severity_distribution"] = dict(Counter(i.get("severity", "unknown") for i in issues))

    clean_files = DATA_DIR / f"clean_files_{repo.lower()}.json"
    if clean_files.exists():
        files = json.loads(clean_files.read_text(encoding="utf-8"))
        total = len(files)
        type_counts = Counter(f.get("file_type", "other") for f in files)
        other_count = type_counts.get("other", 0)
        non_empty = sum(1 for f in files if len((f.get("clean_text") or "").strip()) > 50)

        metrics["files_total"] = total
        metrics["files_classified_pct"] = _pct(total - other_count, total)
        metrics["files_non_empty_pct"] = _pct(non_empty, total)
        metrics["file_type_distribution"] = dict(type_counts.most_common())

    return metrics


def collect_enrichment(repo: str) -> dict:
    """Compute enrichment-stage metrics: metadata coverage and image description quality.

    Args:
        repo: Repo name used to locate ``docs_issues_<repo>_v2.json`` /
            ``docs_files_<repo>_v2.json`` and delivery Alfred-enriched exports.

    Returns:
        Dict with docs metadata coverage percentages and image-description
        success/failure counts (see inline notes for the multi-source lookup
        strategy).
    """
    metrics = {}

    docs_issues = DATA_DIR / f"docs_issues_{repo.lower()}_v2.json"
    if docs_issues.exists():
        docs = json.loads(docs_issues.read_text(encoding="utf-8"))
        total = len(docs)
        metrics["docs_issues_total"] = total
        metrics["docs_issues_with_layer_pct"] = _pct(sum(1 for d in docs if d.get("layer")), total)
        metrics["docs_issues_with_board_pct"] = _pct(sum(1 for d in docs if d.get("board")), total)
        metrics["docs_issues_with_component_pct"] = _pct(sum(1 for d in docs if d.get("component")), total)

    docs_files = DATA_DIR / f"docs_files_{repo.lower()}_v2.json"
    if docs_files.exists():
        docs = json.loads(docs_files.read_text(encoding="utf-8"))
        total = len(docs)
        metrics["docs_files_total"] = total
        metrics["docs_files_with_board_pct"] = _pct(sum(1 for d in docs if d.get("board")), total)
        metrics["docs_files_with_component_pct"] = _pct(sum(1 for d in docs if d.get("component")), total)

    # Images
    total_images = 0
    images_ok = 0
    desc_lengths = []

    # Priority: Check delivery _with_alfred_image_text files under by_series/ (Alfred enrichment)
    delivery_base = PROJECT_ROOT / "datasets" / "07_delivery" / "st_ready" / "by_series" / repo.lower()
    alfred_files = list(delivery_base.rglob("*_with_alfred_image_text.json")) if delivery_base.exists() else []
    for af in alfred_files:
        try:
            data = json.loads(af.read_text(encoding="utf-8"))
            records = []
            if isinstance(data, dict):
                for key in ("issues", "files", "resolver_cases", "diagnostic_cards", "items"):
                    if isinstance(data.get(key), list):
                        records = data[key]
                        break
            elif isinstance(data, list):
                records = data
            for rec in records:
                urls = rec.get("image_urls") or []
                if isinstance(urls, list) and urls:
                    total_images += len(urls)
                    # The Alfred-enriched delivery text embeds each successful
                    # description inline as a "[IMAGE DESCRIPTION]" marker rather
                    # than a separate structured field, so count occurrences to
                    # estimate how many of this record's image_urls were described.
                    text = rec.get("st_ready_text") or rec.get("resolver_card_text") or ""
                    desc_count = text.count("[IMAGE DESCRIPTION]")
                    images_ok += min(desc_count, len(urls))
                    for _ in range(min(desc_count, len(urls))):
                        desc_lengths.append(200)  # approx avg length placeholder (exact text not extracted here)
                analyses = rec.get("image_analyses") or []
                if analyses and not urls:
                    for a in analyses:
                        total_images += 1
                        if a.get("status") == "ok":
                            images_ok += 1
                            desc_lengths.append(len(a.get("description") or ""))
        except Exception:
            # Tolerate malformed/partial delivery files; one bad file should not
            # abort the whole evaluation report generation.
            continue

    # Fallback: Check intermediate docs for image_records (legacy pipeline)
    if total_images == 0:
        for path in [docs_issues, docs_files]:
            if not path.exists():
                continue
            docs = json.loads(path.read_text(encoding="utf-8"))
            for doc in docs:
                for rec in (doc.get("image_records") or []):
                    total_images += 1
                    desc = rec.get("alfred_description") or rec.get("description") or ""
                    if desc.strip():
                        images_ok += 1
                        desc_lengths.append(len(desc.strip()))

    metrics["images_total"] = total_images
    metrics["images_with_desc"] = images_ok
    metrics["images_failed"] = total_images - images_ok
    metrics["images_success_pct"] = _pct(images_ok, total_images)
    metrics["images_avg_desc_length"] = round(sum(desc_lengths) / max(len(desc_lengths), 1))

    return metrics


def collect_similarity(repo: str) -> dict:
    """Compute similarity-stage metrics: coverage of related_issue_ids links.

    Args:
        repo: Repo name used to locate ``docs_issues_<repo>_v2_sim.json``.

    Returns:
        Dict with related-issue coverage stats, or ``{"status": "NOT_RUN"}``
        if the similarity stage was never executed for this repo.
    """
    metrics = {}
    sim_path = DATA_DIR / f"docs_issues_{repo.lower()}_v2_sim.json"

    if not sim_path.exists():
        metrics["status"] = "NOT_RUN"
        return metrics

    docs = json.loads(sim_path.read_text(encoding="utf-8"))
    total = len(docs)
    with_related = sum(1 for d in docs if d.get("related_issue_ids"))
    related_counts = [len(d.get("related_issue_ids") or []) for d in docs]

    metrics["docs_total"] = total
    metrics["with_related"] = with_related
    metrics["with_related_pct"] = _pct(with_related, total)
    metrics["without_related"] = total - with_related
    metrics["avg_related_per_doc"] = round(sum(related_counts) / max(total, 1), 1)
    metrics["max_related"] = max(related_counts) if related_counts else 0

    return metrics


def collect_delivery(repo: str) -> dict:
    """Count ST-ready delivery documents exported per artifact type.

    Args:
        repo: Repo name used to locate
            ``datasets/07_delivery/st_ready/by_series/<repo>/<type>_json/``.

    Returns:
        Dict with per-type document counts (issues/files/resolver_cases/
        diagnostic_cards) and a total.
    """
    metrics = {}

    # Search delivery paths
    delivery_base = PROJECT_ROOT / "datasets" / "07_delivery" / "st_ready" / "by_series" / repo.lower()

    export_types = {
        "issues": "issues_json",
        "files": "files_json",
        "resolver_cases": "resolver_cases_json",
        "diagnostic_cards": "diagnostic_cards_json",
    }

    for name, folder in export_types.items():
        export_dir = delivery_base / folder
        if export_dir.exists():
            json_files = list(export_dir.glob("st_ready_*.json"))
            if json_files:
                try:
                    data = json.loads(json_files[0].read_text(encoding="utf-8"))
                    if isinstance(data, list):
                        metrics[f"{name}_count"] = len(data)
                    elif isinstance(data, dict) and "documents" in data:
                        metrics[f"{name}_count"] = len(data["documents"])
                    else:
                        metrics[f"{name}_count"] = 1
                except Exception:
                    metrics[f"{name}_count"] = 0
            else:
                metrics[f"{name}_count"] = 0
        else:
            metrics[f"{name}_count"] = 0

    metrics["total_delivered"] = sum(v for k, v in metrics.items() if k.endswith("_count"))
    return metrics


# ============================================================
# CHART GENERATION
# ============================================================

def chart_ingestion(metrics: dict, repo: str):
    """Render and save the ingestion-stage chart (issues completeness bars + files pie).

    Args:
        metrics: Output of collect_ingestion.
        repo: Repo name, used only for the chart title.

    Side effects:
        Writes ``01_ingestion_completeness.png`` to OUTPUT_DIR.
    """
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    fig.suptitle(f"Stage 1: Ingestion — {repo}", fontsize=14, fontweight="bold")

    # Issues completeness
    ax = axes[0]
    labels = ["With Body", "With Title", "With Labels"]
    values = [
        metrics.get("issues_with_body_pct", 0),
        metrics.get("issues_with_title_pct", 0),
        metrics.get("issues_with_labels_pct", 0),
    ]
    colors = [SCORE_COLORS[_score_label(v)] for v in values]
    bars = ax.bar(labels, values, color=colors, edgecolor="white", width=0.6)
    ax.set_ylim(0, 105)
    ax.set_ylabel("Percentage (%)")
    ax.set_title(f"Issues Completeness (N={metrics.get('issues_total', 0)})")
    ax.axhline(y=85, color=ST_GRAY, linestyle="--", alpha=0.5, label="GOOD threshold")
    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1, f"{val}%",
                ha="center", va="bottom", fontsize=10, fontweight="bold")

    # Files completeness
    ax = axes[1]
    total_files = metrics.get("files_total", 0)
    with_content = metrics.get("files_with_content", 0)
    without = total_files - with_content
    _safe_pie(
        ax=ax,
        values=[with_content, without],
        labels=["With Content", "Empty"],
        colors=[ST_GREEN, ST_RED],
        title=f"Files Content (N={total_files})",
    )

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "01_ingestion_completeness.png", dpi=150, bbox_inches="tight")
    plt.close()


def chart_cleaning(metrics: dict, repo: str):
    """Render and save the cleaning-stage chart (classification coverage, file types, severity).

    Args:
        metrics: Output of collect_cleaning.
        repo: Repo name, used only for the chart title.

    Side effects:
        Writes ``02_cleaning_validity.png`` to OUTPUT_DIR.
    """
    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    fig.suptitle(f"Stage 2: Cleaning — {repo}", fontsize=14, fontweight="bold")

    # Issues classification coverage
    ax = axes[0]
    labels = ["Valid", "Layer", "Severity", "Kind", "Board", "Component"]
    values = [
        metrics.get("issues_valid_pct", 0),
        metrics.get("issues_with_layer_pct", 0),
        metrics.get("issues_with_severity_pct", 0),
        metrics.get("issues_with_kind_pct", 0),
        metrics.get("issues_with_board_pct", 0),
        metrics.get("issues_with_component_pct", 0),
    ]
    colors = [SCORE_COLORS[_score_label(v)] for v in values]
    bars = ax.barh(labels, values, color=colors, edgecolor="white")
    ax.set_xlim(0, 105)
    ax.set_xlabel("Coverage (%)")
    ax.set_title("Issues Classification Coverage")
    ax.axvline(x=85, color=ST_GRAY, linestyle="--", alpha=0.5)
    for bar, val in zip(bars, values):
        ax.text(bar.get_width() + 1, bar.get_y() + bar.get_height()/2, f"{val}%",
                va="center", fontsize=9)

    # File type distribution
    ax = axes[1]
    file_types = metrics.get("file_type_distribution", {})
    if file_types:
        top_types = dict(sorted(file_types.items(), key=lambda x: x[1], reverse=True)[:8])
        ax.barh(list(top_types.keys()), list(top_types.values()), color=ST_LIGHT_BLUE)
        ax.set_xlabel("Count")
        ax.set_title("File Type Distribution (Top 8)")
    else:
        ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)

    # Severity distribution
    ax = axes[2]
    severity = metrics.get("severity_distribution", {})
    if severity:
        sev_colors = {"critical": ST_RED, "high": ST_ORANGE, "medium": "#FFC107", "low": ST_GREEN, "unknown": ST_GRAY}
        labels_s = list(severity.keys())
        values_s = list(severity.values())
        colors_s = [sev_colors.get(l, ST_GRAY) for l in labels_s]
        _safe_pie(
            ax=ax,
            values=values_s,
            labels=labels_s,
            colors=colors_s,
            title="Issue Severity Distribution",
            autopct="%1.0f%%",
        )
    else:
        ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "02_cleaning_validity.png", dpi=150, bbox_inches="tight")
    plt.close()


def chart_enrichment(metrics: dict, repo: str):
    """Render and save the enrichment-stage chart (metadata coverage, image description success).

    Args:
        metrics: Output of collect_enrichment.
        repo: Repo name, used only for the chart title.

    Side effects:
        Writes ``03_enrichment_metadata.png`` to OUTPUT_DIR.
    """
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    fig.suptitle(f"Stage 3: Enrichment — {repo}", fontsize=14, fontweight="bold")

    # Metadata coverage
    ax = axes[0]
    labels = ["Layer", "Board", "Component"]
    values = [
        metrics.get("docs_issues_with_layer_pct", 0),
        metrics.get("docs_issues_with_board_pct", 0),
        metrics.get("docs_issues_with_component_pct", 0),
    ]
    colors = [SCORE_COLORS[_score_label(v)] for v in values]
    bars = ax.bar(labels, values, color=colors, edgecolor="white", width=0.5)
    ax.set_ylim(0, 105)
    ax.set_ylabel("Coverage (%)")
    ax.set_title("Issues Metadata Coverage")
    ax.axhline(y=85, color=ST_GRAY, linestyle="--", alpha=0.5)
    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1, f"{val}%",
                ha="center", fontsize=10, fontweight="bold")

    # Image descriptions
    ax = axes[1]
    ok = metrics.get("images_with_desc", 0)
    fail = metrics.get("images_failed", 0)
    _safe_pie(
        ax=ax,
        values=[ok, fail],
        labels=[f"Success ({ok})", f"Failed ({fail})"],
        colors=[ST_GREEN, ST_RED],
        title=f"Image Descriptions (N={metrics.get('images_total', 0)})",
        explode=(0, 0.05),
    )

    # Desc length distribution info
    ax = axes[2]
    avg_len = metrics.get("images_avg_desc_length", 0)
    success_pct = metrics.get("images_success_pct", 0)
    score = _score_label(success_pct)

    text = (
        f"Image Analysis Summary\n"
        f"{'─'*30}\n"
        f"Total images:      {metrics.get('images_total', 0)}\n"
        f"Described:         {ok}\n"
        f"Failed:            {fail}\n"
        f"Success rate:      {success_pct}%\n"
        f"Avg desc length:   {avg_len} chars\n"
        f"{'─'*30}\n"
        f"Score: {score}"
    )
    ax.text(0.1, 0.5, text, transform=ax.transAxes, fontsize=11,
            verticalalignment="center", fontfamily="monospace",
            bbox=dict(boxstyle="round", facecolor=SCORE_COLORS[score], alpha=0.2))
    ax.axis("off")

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "03_enrichment_metadata.png", dpi=150, bbox_inches="tight")
    plt.close()


def chart_similarity(metrics: dict, repo: str):
    """Render and save the similarity-stage chart (related-issue coverage pie).

    Args:
        metrics: Output of collect_similarity.
        repo: Repo name, used only for the chart title.

    Side effects:
        Writes ``04_similarity_coverage.png`` to OUTPUT_DIR.
    """
    fig, ax = plt.subplots(1, 1, figsize=(8, 5))
    fig.suptitle(f"Stage 4: Similarity — {repo}", fontsize=14, fontweight="bold")

    if metrics.get("status") == "NOT_RUN":
        ax.text(0.5, 0.5, "Similarity stage not executed", ha="center", va="center",
                transform=ax.transAxes, fontsize=14)
        ax.axis("off")
    else:
        with_rel = metrics.get("with_related", 0)
        without = metrics.get("without_related", 0)
        _safe_pie(
            ax=ax,
            values=[with_rel, without],
            labels=[f"With Related ({with_rel})", f"No Related ({without})"],
            colors=[ST_LIGHT_BLUE, ST_GRAY],
            title=f"Issues with Similar Links (avg={metrics.get('avg_related_per_doc', 0)} per doc)",
        )

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "04_similarity_coverage.png", dpi=150, bbox_inches="tight")
    plt.close()


def chart_delivery(metrics: dict, repo: str):
    """Render and save the delivery-stage chart (exported document volumes per type).

    Args:
        metrics: Output of collect_delivery.
        repo: Repo name, used only for the chart title.

    Side effects:
        Writes ``05_delivery_volumes.png`` to OUTPUT_DIR.
    """
    fig, ax = plt.subplots(1, 1, figsize=(10, 5))
    fig.suptitle(f"Stage 5: Delivery — {repo}", fontsize=14, fontweight="bold")

    categories = ["Issues", "Files", "Resolver Cases", "Diagnostic Cards"]
    values = [
        metrics.get("issues_count", 0),
        metrics.get("files_count", 0),
        metrics.get("resolver_cases_count", 0),
        metrics.get("diagnostic_cards_count", 0),
    ]
    colors = [ST_BLUE, ST_LIGHT_BLUE, ST_GREEN, ST_ORANGE]
    bars = ax.bar(categories, values, color=colors, edgecolor="white", width=0.6)
    ax.set_ylabel("Documents Exported")
    ax.set_title(f"ST-Ready Delivery Volumes (Total: {sum(values)})")
    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5, str(val),
                ha="center", va="bottom", fontsize=11, fontweight="bold")

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "05_delivery_volumes.png", dpi=150, bbox_inches="tight")
    plt.close()


def chart_dashboard(all_metrics: dict, repo: str):
    """Generate overall pipeline quality dashboard.

    Combines one representative percentage metric per stage into a single
    horizontal bar chart, giving a one-glance view of pipeline health across
    all five stages.

    Args:
        all_metrics: Dict keyed by stage name ("ingestion", "cleaning",
            "enrichment", "similarity", "delivery") mapping to each stage's
            collect_* output.
        repo: Repo name, used only for the chart title.

    Side effects:
        Writes ``00_pipeline_dashboard.png`` to OUTPUT_DIR.
    """
    fig, ax = plt.subplots(1, 1, figsize=(12, 6))

    stages = ["Ingestion", "Cleaning", "Enrichment", "Similarity", "Delivery"]
    key_metrics = [
        all_metrics["ingestion"].get("issues_with_body_pct", 0),
        all_metrics["cleaning"].get("issues_valid_pct", 0),
        all_metrics["enrichment"].get("images_success_pct", 0),
        all_metrics["similarity"].get("with_related_pct", 0),
        min(100, all_metrics["delivery"].get("total_delivered", 0) / max(1, all_metrics["delivery"].get("total_delivered", 1)) * 100) if all_metrics["delivery"].get("total_delivered", 0) > 0 else 0,
    ]

    # Delivery has no natural "percent complete" metric (it's a count), so treat
    # "at least one document exported" as a pass/fail 100%/0% signal instead.
    if all_metrics["delivery"].get("total_delivered", 0) > 0:
        key_metrics[4] = 100.0

    colors = [SCORE_COLORS[_score_label(v)] for v in key_metrics]

    bars = ax.barh(stages, key_metrics, color=colors, edgecolor="white", height=0.6)
    ax.set_xlim(0, 110)
    ax.set_xlabel("Score (%)", fontsize=12)
    ax.set_title(f"Pipeline Quality Dashboard — {repo}", fontsize=14, fontweight="bold")

    # Threshold lines
    ax.axvline(x=95, color=ST_GREEN, linestyle="--", alpha=0.4, label="EXCELLENT (95%)")
    ax.axvline(x=85, color=ST_LIGHT_BLUE, linestyle="--", alpha=0.4, label="GOOD (85%)")
    ax.axvline(x=70, color=ST_ORANGE, linestyle="--", alpha=0.4, label="ACCEPTABLE (70%)")

    for bar, val in zip(bars, key_metrics):
        score = _score_label(val)
        ax.text(bar.get_width() + 1, bar.get_y() + bar.get_height()/2,
                f"{val}% ({score})", va="center", fontsize=10, fontweight="bold")

    ax.legend(loc="lower right", fontsize=9)
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "00_pipeline_dashboard.png", dpi=150, bbox_inches="tight")
    plt.close()


# ============================================================
# EXCEL REPORT
# ============================================================

def generate_excel_report(all_metrics: dict, repo: str):
    """Write a multi-sheet Excel workbook (one sheet per stage) with metric/value/score columns.

    Nested dict values (e.g. distributions) are skipped in the flat table
    since Excel cells can't hold structured data; only scalar metrics are
    shown, with a color-coded score column for percentage metrics.

    Args:
        all_metrics: Dict keyed by stage name mapping to each stage's
            collect_* output.
        repo: Unused for content but kept for API symmetry with chart_* functions.

    Side effects:
        Writes ``evaluation_report.xlsx`` to OUTPUT_DIR.
    """
    wb = Workbook()

    header_fill = PatternFill(start_color="03234B", end_color="03234B", fill_type="solid")
    header_font = Font(bold=True, size=11, color="FFFFFF")
    thin_border = Border(
        left=Side(style="thin"), right=Side(style="thin"),
        top=Side(style="thin"), bottom=Side(style="thin"),
    )

    for stage_name, metrics in all_metrics.items():
        ws = wb.create_sheet(title=stage_name.capitalize())
        ws.column_dimensions["A"].width = 40
        ws.column_dimensions["B"].width = 20
        ws.column_dimensions["C"].width = 15

        # Header
        for col, header in enumerate(["Metric", "Value", "Score"], start=1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.border = thin_border

        row = 2
        for key, value in metrics.items():
            if isinstance(value, dict):
                continue  # Skip nested dicts in main table
            ws.cell(row=row, column=1, value=key.replace("_", " ").title()).border = thin_border
            ws.cell(row=row, column=2, value=value).border = thin_border
            if "pct" in key and isinstance(value, (int, float)):
                score = _score_label(value)
                cell = ws.cell(row=row, column=3, value=score)
                cell.border = thin_border
                color_map = {"EXCELLENT": "4CAF50", "GOOD": "3CB4E6", "ACCEPTABLE": "FF9800", "POOR": "F44336"}
                cell.fill = PatternFill(start_color=color_map.get(score, "FFFFFF"),
                                       end_color=color_map.get(score, "FFFFFF"), fill_type="solid")
                cell.font = Font(bold=True, color="FFFFFF")
            row += 1

    # Remove default sheet
    if "Sheet" in wb.sheetnames:
        del wb["Sheet"]

    xlsx_path = OUTPUT_DIR / "evaluation_report.xlsx"
    wb.save(xlsx_path)
    print(f"  Excel report: {xlsx_path}")


# ============================================================
# MAIN
# ============================================================

def main():
    """CLI entry point: collect metrics, render charts/Excel, optionally compile PDF."""
    parser = argparse.ArgumentParser(description="Generate evaluation report with charts")
    parser.add_argument("--repo", default="STM32CubeH7", help="Repository name")
    parser.add_argument("--all", action="store_true", help="Run for all repos in config")
    parser.add_argument("--pdf", action="store_true", help="Also compile LaTeX to PDF")
    args = parser.parse_args()

    if args.all:
        cfg = json.loads(get_config_path().read_text(encoding="utf-8"))
        repos = cfg.get("repos", [args.repo])
    else:
        repos = [args.repo]

    for repo in repos:
        print(f"\n{'#'*60}")
        print(f"#  GENERATING EVALUATION REPORT: {repo}")
        print(f"{'#'*60}")

        # Collect all metrics
        all_metrics = {
            "ingestion": collect_ingestion(repo),
            "cleaning": collect_cleaning(repo),
            "enrichment": collect_enrichment(repo),
            "similarity": collect_similarity(repo),
            "delivery": collect_delivery(repo),
        }

        # Generate charts
        print("\n  Generating charts...")
        chart_ingestion(all_metrics["ingestion"], repo)
        print("    ✓ 01_ingestion_completeness.png")

        chart_cleaning(all_metrics["cleaning"], repo)
        print("    ✓ 02_cleaning_validity.png")

        chart_enrichment(all_metrics["enrichment"], repo)
        print("    ✓ 03_enrichment_metadata.png")

        chart_similarity(all_metrics["similarity"], repo)
        print("    ✓ 04_similarity_coverage.png")

        chart_delivery(all_metrics["delivery"], repo)
        print("    ✓ 05_delivery_volumes.png")

        chart_dashboard(all_metrics, repo)
        print("    ✓ 00_pipeline_dashboard.png")

        # Generate Excel
        print("\n  Generating Excel report...")
        generate_excel_report(all_metrics, repo)

        # Print summary
        print(f"\n  {'='*50}")
        print(f"  PIPELINE QUALITY SUMMARY — {repo}")
        print(f"  {'='*50}")
        summary = {
            "Ingestion": all_metrics["ingestion"].get("issues_with_body_pct", 0),
            "Cleaning": all_metrics["cleaning"].get("issues_valid_pct", 0),
            "Enrichment": all_metrics["enrichment"].get("images_success_pct", 0),
            "Similarity": all_metrics["similarity"].get("with_related_pct", 0),
        }
        for stage, pct in summary.items():
            score = _score_label(pct)
            print(f"  {stage:<15} {pct:>6.1f}%   {score}")
        print(f"  {'='*50}")
        print(f"\n  All outputs in: {OUTPUT_DIR}")

    # --- LaTeX PDF compilation ---
    if args.pdf:
        tex_path = PROJECT_ROOT / "docs" / "evaluation_report.tex"
        if not tex_path.exists():
            print(f"\n  ERROR: LaTeX source not found: {tex_path}")
            raise SystemExit(1)

        # Check pdflatex available
        pdflatex = shutil.which("pdflatex")
        if not pdflatex:
            print("\n  ERROR: pdflatex not found. Install MiKTeX or TeX Live.")
            print("         Download: https://miktex.org/download")
            raise SystemExit(1)

        print(f"\n{'#'*60}")
        print(f"#  COMPILING LaTeX → PDF")
        print(f"{'#'*60}")

        # Copy chart PNGs next to tex for relative paths
        # The tex uses relative paths ../datasets/07_delivery/...
        # So we compile from docs/ directory
        compile_dir = tex_path.parent
        cmd = [pdflatex, "-interaction=nonstopmode", "-output-directory", str(OUTPUT_DIR), str(tex_path)]

        # Run twice for TOC
        for pass_num in (1, 2):
            print(f"\n  pdflatex pass {pass_num}/2...")
            result = subprocess.run(cmd, cwd=str(compile_dir), capture_output=True, text=True)
            if result.returncode != 0 and pass_num == 2:
                print(f"  WARNING: pdflatex returned code {result.returncode}")
                # Show last 20 lines of log for debugging
                log_lines = result.stdout.split("\n")
                for line in log_lines[-20:]:
                    if line.strip():
                        print(f"    {line}")

        pdf_path = OUTPUT_DIR / "evaluation_report.pdf"
        if pdf_path.exists():
            print(f"\n  ✓ PDF generated: {pdf_path}")
        else:
            # Try finding it in docs/
            alt_pdf = compile_dir / "evaluation_report.pdf"
            if alt_pdf.exists():
                shutil.move(str(alt_pdf), str(pdf_path))
                print(f"\n  ✓ PDF generated: {pdf_path}")
            else:
                print(f"\n  ✗ PDF generation failed. Check LaTeX errors above.")

        # Clean aux files
        for ext in (".aux", ".log", ".toc", ".lof", ".out"):
            for cleanup_dir in (OUTPUT_DIR, compile_dir):
                aux_file = cleanup_dir / f"evaluation_report{ext}"
                if aux_file.exists():
                    aux_file.unlink()

    print(f"\n{'#'*60}")
    print(f"#  DONE")
    print(f"{'#'*60}")


if __name__ == "__main__":
    main()
