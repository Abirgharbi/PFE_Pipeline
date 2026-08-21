"""
Evaluate Alfred image descriptions quality.

Role in the evaluation stage
-----------------------------
After Alfred Vision enrichment converts ``[IMAGE ATTACHED]`` markers into
textual descriptions, this script checks how well that enrichment worked
before the data is considered ready for delivery/upload. It scans every
``image_records`` entry across enriched issues/files docs and produces
success/failure counts, so a drop in description coverage (e.g. Alfred API
quota exhaustion, malformed image URLs) is caught early instead of silently
shipping ``[IMAGE DESCRIPTION UNAVAILABLE]`` placeholders to the KB.

Analyzes all enriched issues/files that contain image_records with
alfred_description, and produces stats:
- Total images processed
- Images with description (non-empty)
- Images without description (failed)
- Average description length
- Sample of short descriptions (likely low quality)

Inputs
------
- ``data/docs_issues_<repo>_v2.json`` and ``data/docs_files_<repo>_v2.json``
  (enrichment stage outputs), read for each document's ``image_records``
  list (each record expected to carry ``alfred_description``/``description``
  and ``url``).

Outputs
------
- Console report per repo (counts, success rate, sample short descriptions).
- When run with ``--all``, an additional global summary across all repos.
- No files are written; this is a read-only diagnostic script.

Usage (CLI)
-----------
    python pipeline/evaluation/eval_image_descriptions.py --repo STM32CubeH7
    python pipeline/evaluation/eval_image_descriptions.py --all
"""

import argparse
import json
from pathlib import Path
from collections import Counter

from shared.utils.paths import DATA_DIR


def evaluate_image_descriptions(repo: str) -> dict:
    """Scan a repo's enriched issues/files docs and compute image-description stats.

    Args:
        repo: Repo name (e.g. ``STM32CubeH7``); matched case-insensitively
            against the ``docs_issues_<repo>_v2.json`` / ``docs_files_<repo>_v2.json``
            filenames.

    Returns:
        Dict with total/with_description/without_description/empty_description
        counts, average description length, and a sample of suspiciously
        short descriptions (potential low-quality Alfred output).
    """
    
    # Try enriched issues first
    results = {
        "repo": repo,
        "total_images": 0,
        "with_description": 0,
        "without_description": 0,
        "empty_description": 0,
        "avg_description_length": 0,
        "short_descriptions": [],  # < 20 chars
        "description_lengths": [],
    }
    
    # Check docs_issues
    issues_path = DATA_DIR / f"docs_issues_{repo.lower()}_v2.json"
    files_path = DATA_DIR / f"docs_files_{repo.lower()}_v2.json"
    
    all_image_records = []
    
    for path in [issues_path, files_path]:
        if not path.exists():
            continue
        docs = json.loads(path.read_text(encoding="utf-8"))
        for doc in docs:
            records = doc.get("image_records") or []
            for rec in records:
                all_image_records.append(rec)
    
    results["total_images"] = len(all_image_records)
    
    if not all_image_records:
        print(f"[{repo}] No image records found.")
        return results
    
    for rec in all_image_records:
        desc = rec.get("alfred_description") or rec.get("description") or ""
        
        if desc.strip():
            results["with_description"] += 1
            length = len(desc.strip())
            results["description_lengths"].append(length)
            
            # Flag very short descriptions as likely low-quality/generic Alfred output
            # (e.g. "Image." or "Screenshot") worth spot-checking manually.
            if length < 20:
                results["short_descriptions"].append({
                    "url": rec.get("url", "")[:80],
                    "description": desc.strip(),
                })
        else:
            results["without_description"] += 1
    
    # Empty = explicitly empty string vs None
    results["empty_description"] = sum(
        1 for r in all_image_records
        if (r.get("alfred_description") or r.get("description")) == ""
    )
    
    if results["description_lengths"]:
        results["avg_description_length"] = round(
            sum(results["description_lengths"]) / len(results["description_lengths"]), 1
        )
    
    return results


def print_report(results: dict) -> None:
    """Print a human-readable console report for one repo's evaluation results.

    Args:
        results: Dict returned by evaluate_image_descriptions.
    """
    repo = results["repo"]
    total = results["total_images"]
    
    print(f"\n{'='*60}")
    print(f"  IMAGE DESCRIPTION EVALUATION — {repo}")
    print(f"{'='*60}")
    print(f"  Total images found:          {total}")
    print(f"  With description:            {results['with_description']} ({_pct(results['with_description'], total)})")
    print(f"  Without description (failed): {results['without_description']} ({_pct(results['without_description'], total)})")
    print(f"  Avg description length:      {results['avg_description_length']} chars")
    
    if results["short_descriptions"]:
        print(f"\n  ⚠ Short descriptions (< 20 chars): {len(results['short_descriptions'])}")
        for s in results["short_descriptions"][:5]:
            print(f"    - \"{s['description']}\" | {s['url']}")
    
    # Quality score
    if total > 0:
        success_rate = results["with_description"] / total * 100
        quality = "GOOD" if success_rate >= 90 else "ACCEPTABLE" if success_rate >= 70 else "POOR"
        print(f"\n  SUCCESS RATE: {success_rate:.1f}% — {quality}")
    
    print(f"{'='*60}\n")


def _pct(n: int, total: int) -> str:
    """Format n/total as a percentage string, guarding against division by zero."""
    if total == 0:
        return "0%"
    return f"{n/total*100:.1f}%"


def main():
    """CLI entry point: evaluate one repo or all configured repos and print reports."""
    parser = argparse.ArgumentParser(description="Evaluate image description quality")
    parser.add_argument("--repo", default="STM32CubeH7", help="Repository name")
    parser.add_argument("--all", action="store_true", help="Evaluate all repos from config")
    args = parser.parse_args()
    
    if args.all:
        from shared.utils.paths import get_config_path
        cfg = json.loads(get_config_path().read_text(encoding="utf-8"))
        repos = cfg.get("repos", [args.repo])
    else:
        repos = [args.repo]
    
    all_results = []
    for repo in repos:
        results = evaluate_image_descriptions(repo)
        print_report(results)
        all_results.append(results)
    
    # Global summary
    if len(all_results) > 1:
        total_imgs = sum(r["total_images"] for r in all_results)
        total_ok = sum(r["with_description"] for r in all_results)
        total_fail = sum(r["without_description"] for r in all_results)
        print(f"\n{'='*60}")
        print(f"  GLOBAL SUMMARY ({len(all_results)} repos)")
        print(f"{'='*60}")
        print(f"  Total images:     {total_imgs}")
        print(f"  With description: {total_ok} ({_pct(total_ok, total_imgs)})")
        print(f"  Failed:           {total_fail} ({_pct(total_fail, total_imgs)})")
        print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
