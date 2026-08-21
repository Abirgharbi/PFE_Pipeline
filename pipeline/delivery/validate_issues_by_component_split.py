"""CLI: validate a by-component issues split produced by
`split_st_ready_issues_by_component.py`.

After splitting a `st_ready_issues_with_images_<repo>.json` payload into
per-component files (`by_component/st_ready_issues_<series>_<component>.json`),
this script cross-checks the split output against the original source file to
catch data-integrity regressions before those files are uploaded as separate
KB datasources. It verifies:

- No issue ID/`issue_number` appears in more than one component file
  (duplicates would cause the same issue to be retrievable from two
  datasources).
- Every issue from the source file is present in exactly one split file
  (no silently dropped issues).
- No split file contains IDs that are not in the source file (no
  fabricated/leftover records from a stale run).

Input:
- `--summary`: path to a `summary_by_component_<series>.json` file written by
  `split_st_ready_issues_by_component.py`. It references the original
  `source_file` and the list of per-component `output_file` paths
  (`datasources`), which this script reads.

Exit behavior:
- Prints a report to stdout; exits with status 1 (`SystemExit(1)`) if any
  duplicates, missing IDs, or extra IDs are found, so it can be used as a CI
  gate in the delivery workflow.

Run:
    python -m pipeline.delivery.validate_issues_by_component_split \\
        --summary <path/to/summary_by_component_<series>.json>
"""

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    """Load a JSON file and ensure its root is an object (not an array)."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected object at root: {path}")
    return payload


def extract_issue_id(issue: dict[str, Any]) -> str:
    """Return a stable identity key for an issue record.

    Prefers the delivery `id` field; falls back to `issue_number` (prefixed
    to avoid collisions with the `id` namespace) so records missing `id` can
    still be tracked for duplicate/coverage checks.
    """
    issue_id = issue.get("id")
    if issue_id:
        return str(issue_id)
    issue_number = issue.get("issue_number")
    if issue_number is not None:
        return f"issue_number:{issue_number}"
    raise ValueError("Issue record has neither 'id' nor 'issue_number'.")


def main() -> None:
    """CLI entry point: load the split summary, compare split files against
    the source file, print a report, and raise `SystemExit(1)` on failure.
    """
    parser = argparse.ArgumentParser(
        description="Validate no duplicates across by_component issue files and check coverage against source."
    )
    parser.add_argument("--summary", required=True, help="Path to summary_by_component_<series>.json")
    args = parser.parse_args()

    summary_path = Path(args.summary).resolve()
    summary = load_json(summary_path)

    source_file = Path(str(summary.get("source_file") or "")).resolve()
    if not source_file.exists():
        raise FileNotFoundError(f"Source file not found from summary: {source_file}")

    datasources = summary.get("datasources")
    if not isinstance(datasources, list):
        raise ValueError("Summary missing 'datasources' list.")

    source_payload = load_json(source_file)
    source_issues = source_payload.get("issues")
    if not isinstance(source_issues, list):
        raise ValueError("Source payload missing 'issues' array.")

    source_ids = {extract_issue_id(issue) for issue in source_issues if isinstance(issue, dict)}

    id_to_files: dict[str, list[str]] = defaultdict(list)
    total_rows = 0

    for row in datasources:
        if not isinstance(row, dict):
            continue
        output_file = row.get("output_file")
        if not output_file:
            continue
        out_path = Path(str(output_file)).resolve()
        if not out_path.exists():
            raise FileNotFoundError(f"Output file listed in summary not found: {out_path}")

        out_payload = load_json(out_path)
        issues = out_payload.get("issues")
        if not isinstance(issues, list):
            raise ValueError(f"Output file missing 'issues' array: {out_path}")

        for issue in issues:
            if not isinstance(issue, dict):
                continue
            issue_id = extract_issue_id(issue)
            id_to_files[issue_id].append(out_path.name)
            total_rows += 1

    duplicate_ids = {issue_id: files for issue_id, files in id_to_files.items() if len(files) > 1}
    split_ids = set(id_to_files.keys())

    missing_ids = sorted(source_ids - split_ids)
    extra_ids = sorted(split_ids - source_ids)

    print("[validate_issues_by_component_split]")
    print(f"  source_issues={len(source_ids)}")
    print(f"  split_issues_unique={len(split_ids)}")
    print(f"  split_rows_total={total_rows}")
    print(f"  duplicates={len(duplicate_ids)}")
    print(f"  missing_vs_source={len(missing_ids)}")
    print(f"  extra_vs_source={len(extra_ids)}")

    if duplicate_ids:
        print("\nDuplicate IDs detected:")
        for issue_id, files in sorted(duplicate_ids.items()):
            print(f"  - {issue_id}: {', '.join(files)}")

    if missing_ids:
        print("\nMissing IDs from split output:")
        for issue_id in missing_ids[:50]:
            print(f"  - {issue_id}")
        if len(missing_ids) > 50:
            print(f"  ... ({len(missing_ids) - 50} more)")

    if extra_ids:
        print("\nExtra IDs in split output (not in source):")
        for issue_id in extra_ids[:50]:
            print(f"  - {issue_id}")
        if len(extra_ids) > 50:
            print(f"  ... ({len(extra_ids) - 50} more)")

    if duplicate_ids or missing_ids or extra_ids:
        raise SystemExit(1)

    print("\nResult: OK (no duplicates, full coverage, no extras).")


if __name__ == "__main__":
    main()
