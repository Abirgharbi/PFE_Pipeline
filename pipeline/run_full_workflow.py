import argparse

from pipeline.cleaning.clean_files import main as clean_files_main
from pipeline.cleaning.clean_files_v3 import main as clean_files_v3_main
from pipeline.cleaning.clean_issues import main as clean_issues_main
from pipeline.delivery.export_st_ready_diagnostic_cards import export_repo_json as export_diagnostic_cards_repo_json
from pipeline.delivery.export_st_ready_files import export_repo_json as export_files_repo_json
from pipeline.delivery.export_st_ready_issues import export_repo_json as export_issues_repo_json
from pipeline.delivery.export_st_ready_resolver_cases import export_repo_json as export_resolver_cases_repo_json
from pipeline.enrichment.files_to_docs_v2 import main as files_to_docs_v2_main
from pipeline.enrichment.issues_to_docs_v2 import main as issues_to_docs_v2_main
from pipeline.evaluation.test_stats_files_v2 import main as stats_files_main
from pipeline.evaluation.test_stats_issues_v2 import main as stats_issues_main
from pipeline.evaluation.validate_schemas import main as validate_schemas_main
from pipeline.ingestion.fetch_issue_pr_commit_links import main as fetch_issue_pr_commit_links_main
from pipeline.ingestion.fetch_commits import main as fetch_commits_main
from pipeline.ingestion.fetch_files import main as fetch_files_main
from pipeline.ingestion.fetch_issues import main as fetch_issues_main
from pipeline.ingestion.fetch_prs import main as fetch_prs_main
from pipeline.ingestion.repo_sync_service import main as sync_local_repos_main
from pipeline.similarity.compute_issue_similarity_v2 import main as similarity_main
from shared.utils.paths import get_config_path


def chunks_issues_v2_main() -> None:
    """Lazy-load issue chunking so --skip-chunking avoids importing chunking modules."""
    from pipeline.chunking.docs_to_chunks_issues_v2 import main as _main

    _main()


def chunks_files_v2_main() -> None:
    """Lazy-load file chunking so --skip-chunking avoids importing chunking modules."""
    from pipeline.chunking.docs_to_chunks_files_v2 import main as _main

    _main()


def _enrich_pdf_figures_main() -> None:
    """Run Alfred Vision on PDF figure crops (tasks generated during ingestion)."""
    import sys
    from pathlib import Path

    script = Path(__file__).resolve().parents[1] / "pipeline_Automation" / "alfred" / "enrich_pdf_figures_with_alfred.py"
    if not script.exists():
        print(f"[SKIP] Alfred PDF enrichment script not found: {script}")
        return

    # Import and call main directly
    sys.path.insert(0, str(script.parent))
    import importlib.util
    spec = importlib.util.spec_from_file_location("enrich_pdf_figures", str(script))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    # Isolate sys.argv so the sub-script argparse doesn't see workflow args
    original_argv = sys.argv
    sys.argv = [str(script)]
    try:
        mod.main()
    finally:
        sys.argv = original_argv


def load_config() -> dict:
    return __import__("json").loads(get_config_path().read_text(encoding="utf-8"))


def export_st_ready_issues_all() -> None:
    repos = load_config().get("repos", [])
    for repo in repos:
        try:
            total, exported, out_root = export_issues_repo_json(repo=repo, include_invalid=False, comments_chars=1200)
        except FileNotFoundError as exc:
            print(f"[ST-READY:json:issues] {repo}: skipped ({exc})")
            continue
        print(f"[ST-READY:json:issues] {repo}: exported {exported}/{total} -> {out_root}")


def export_st_ready_files_all() -> None:
    repos = load_config().get("repos", [])
    for repo in repos:
        try:
            total, exported, out_root = export_files_repo_json(
                repo=repo,
                include_invalid=False,
                summary_max_chars=240,
                technical_max_chars=4000,
                use_v3=True,
            )
        except FileNotFoundError as exc:
            print(f"[ST-READY:json:files] {repo}: skipped ({exc})")
            continue
        print(f"[ST-READY:json:files] {repo}: exported {exported}/{total} -> {out_root} [V3 clean]")


def export_st_ready_resolver_cases_all() -> None:
    repos = load_config().get("repos", [])
    for repo in repos:
        try:
            total, exported, out_root = export_resolver_cases_repo_json(repo=repo, include_reference_only=False)
        except FileNotFoundError as exc:
            print(f"[ST-READY:json:resolver_cases] {repo}: skipped ({exc})")
            continue
        print(f"[ST-READY:json:resolver_cases] {repo}: exported {exported}/{total} -> {out_root}")


def export_st_ready_diagnostic_cards_all() -> None:
    repos = load_config().get("repos", [])
    for repo in repos:
        try:
            total, exported, out_root = export_diagnostic_cards_repo_json(repo=repo, include_all_issues=False)
        except FileNotFoundError as exc:
            print(f"[ST-READY:json:diagnostic_cards] {repo}: skipped ({exc})")
            continue
        print(f"[ST-READY:json:diagnostic_cards] {repo}: exported {exported}/{total} -> {out_root}")


def export_st_ready_issues_with_images_all() -> None:
    """Export issues with image_urls field for Alfred enrichment."""
    from pipeline.delivery.export_st_ready_issues_with_images import export_repo_json as export_with_images_repo_json
    repos = load_config().get("repos", [])
    for repo in repos:
        try:
            total, exported, out_root = export_with_images_repo_json(repo=repo, include_invalid=False, comments_chars=1200)
        except FileNotFoundError as exc:
            print(f"[ST-READY:json:issues_with_images] {repo}: skipped ({exc})")
            continue
        print(f"[ST-READY:json:issues_with_images] {repo}: exported {exported}/{total} -> {out_root}")


def _patch_pdf_descriptions_in_delivery() -> None:
    """Patch PDF figure descriptions into delivery files (fix timing issue)."""
    import re
    from pathlib import Path

    project_root = Path(__file__).resolve().parents[1]
    data_dir = project_root / "data"
    delivery_dir = project_root / "datasets" / "07_delivery" / "st_ready" / "by_series"
    desc_file = data_dir / "pdf_image_descriptions.json"

    if not desc_file.exists():
        print("  [SKIP] No pdf_image_descriptions.json found")
        return
    if not delivery_dir.exists():
        print("  [SKIP] No delivery files found")
        return

    import json
    descriptions = json.loads(desc_file.read_text(encoding="utf-8"))
    if not descriptions:
        print("  [SKIP] Empty descriptions file")
        return

    pattern = re.compile(
        r"Figure detected on page \d+, but no technical description is available yet for ([^\s]+:p\d+:f\d+)\."
    )

    total = 0
    for series_dir in sorted(delivery_dir.iterdir()):
        if not series_dir.is_dir():
            continue
        files_dir = series_dir / "files_json"
        if not files_dir.exists():
            continue
        for json_file in sorted(files_dir.glob("st_ready_files_*.json")):
            if "summary" in json_file.name:
                continue
            content = json_file.read_text(encoding="utf-8")
            count = 0

            def _replace(match):
                nonlocal count
                fig_id = match.group(1)
                desc = descriptions.get(fig_id, "").strip()
                if desc:
                    count += 1
                    # Escape for JSON string context
                    desc = desc.replace("\\", "\\\\")
                    desc = desc.replace('"', '\\"')
                    desc = desc.replace("\n", "\\n")
                    desc = desc.replace("\r", "\\r")
                    desc = desc.replace("\t", "\\t")
                    return desc
                return match.group(0)

            patched = pattern.sub(_replace, content)
            if count > 0:
                json_file.write_text(patched, encoding="utf-8")
                total += count

    print(f"  Patched {total} PDF figure descriptions across delivery files")


def _enrich_alfred_images_main() -> None:
    """Run Alfred Vision on issue images (st_ready_issues_with_images_*.json)."""
    import sys
    from pathlib import Path

    from pipeline.delivery.delivery_paths import get_repo_series_root

    script = Path(__file__).resolve().parents[1] / "pipeline_Automation" / "alfred" / "enrich_json_images_with_alfred.py"
    if not script.exists():
        print(f"[SKIP] Alfred images enrichment script not found: {script}")
        return

    by_series = Path(__file__).resolve().parents[1] / "datasets" / "07_delivery" / "st_ready" / "by_series"
    if not by_series.exists():
        print("[SKIP] by_series/ not found — run delivery first")
        return

    series_dirs = set()
    for repo in load_config().get("repos", []):
        repo_root = get_repo_series_root(repo)
        if repo_root.parent.name == "drivers":
            series_dirs.add(repo_root.parent.parent)
        else:
            series_dirs.add(repo_root)

    if not series_dirs:
        series_dirs = {path for path in by_series.iterdir() if path.is_dir()}

    for series_dir in sorted(series_dirs):
        if not series_dir.is_dir():
            continue
        issues_dir = series_dir / "issues_json"
        if not issues_dir.exists():
            continue
        # Find with_images file
        candidates = list(issues_dir.glob("st_ready_issues_with_images_*.json"))
        candidates = [c for c in candidates if "alfred" not in c.name and "summary" not in c.name]
        if not candidates:
            continue

        input_file = candidates[0]
        print(f"  [ALFRED-IMG] {series_dir.name}: {input_file.name}")

        original_argv = sys.argv
        sys.argv = [str(script), "--input", str(input_file), "--inplace"]
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location("enrich_json_images", str(script))
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            mod.main()
        except Exception as exc:
            print(f"  [WARN] Alfred images failed for {series_dir.name}: {exc}")
        finally:
            sys.argv = original_argv


STEPS = [
    ("Ingestion issues", fetch_issues_main),
    ("Ingestion pull requests", fetch_prs_main),
    ("Ingestion commits", fetch_commits_main),
    ("Ingestion issue-pr-commit links", fetch_issue_pr_commit_links_main),
    ("Ingestion sync local repos", sync_local_repos_main),
    ("Ingestion files", fetch_files_main),
    ("Alfred PDF figure descriptions", _enrich_pdf_figures_main),
    ("Cleaning issues", clean_issues_main),
    ("Cleaning files", clean_files_main),
    ("Cleaning files V3", clean_files_v3_main),
    ("Enrichment issues V2", issues_to_docs_v2_main),
    ("Enrichment files V2", files_to_docs_v2_main), 
    ("Similarity issues V2", similarity_main),
    ("Chunking issues V2", chunks_issues_v2_main),
    ("Chunking files V2", chunks_files_v2_main),
    ("Stats issues V2", stats_issues_main),
    ("Stats files V2", stats_files_main),
    ("Schema validation", validate_schemas_main),
]


def main(skip_ingestion: bool = False, skip_chunking: bool = False, continue_on_error: bool = False, export_st_ready: bool = False, enrich_pdf: bool = True) -> None:
    steps = STEPS
    if skip_ingestion:
        steps = [step for step in steps if not step[0].startswith("Ingestion")]
    if not enrich_pdf:
        steps = [step for step in steps if not step[0].startswith("Alfred")]
    if skip_chunking:
        steps = [step for step in steps if not step[0].startswith("Chunking")]
    if export_st_ready:
        steps = steps + [
            ("Delivery ST-ready issues", export_st_ready_issues_all),
            ("Delivery ST-ready files", export_st_ready_files_all),
            ("Delivery ST-ready resolver cases", export_st_ready_resolver_cases_all),
            ("Delivery ST-ready diagnostic cards", export_st_ready_diagnostic_cards_all),
            ("Patch PDF descriptions into delivery", _patch_pdf_descriptions_in_delivery),
            ("Delivery ST-ready issues with images", export_st_ready_issues_with_images_all),
            ("Alfred image descriptions", _enrich_alfred_images_main),
        ]

    for idx, (label, fn) in enumerate(steps, start=1):
        print(f"\n[{idx}/{len(steps)}] {label}...")
        try:
            fn()
        except Exception as exc:
            print(f"[ERROR] Step '{label}' failed: {exc}")
            if not continue_on_error:
                raise
            print("[WARN] Continuing to next step because --continue-on-error is enabled.")
    print("\nWorkflow completed successfully.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run full STM32Cube preprocessing workflow.")
    parser.add_argument(
        "--skip-ingestion",
        action="store_true",
        help="Skip GitHub ingestion steps and use existing raw files.",
    )
    parser.add_argument(
        "--skip-chunking",
        action="store_true",
        help="Skip local chunking (ST platform handles chunking at upload).",
    )
    parser.add_argument(
        "--no-enrich-pdf",
        action="store_true",
        help="Skip Alfred Vision enrichment of PDF figures.",
    )
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Continue running next steps when one step fails.",
    )
    parser.add_argument(
        "--export-st-ready",
        action="store_true",
        help="Run ST-ready delivery exports after preprocessing and validation.",
    )
    args = parser.parse_args()
    main(
        skip_ingestion=args.skip_ingestion,
        skip_chunking=args.skip_chunking,
        continue_on_error=args.continue_on_error,
        export_st_ready=args.export_st_ready,
        enrich_pdf=not args.no_enrich_pdf,
    )
