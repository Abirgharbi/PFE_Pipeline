"""Manual debug script for the V2 issue preprocessing/enrichment logic.

Role in the pipeline: this is a developer utility (not part of the automated
workflow) used to quickly inspect how `PreprocessingModelIssuesV2` classifies
a sample of issues, without writing any output file. It is handy when tuning
heuristics in `preprocessing_model.py` / `stm32cube_preprocessing_heuristics.py`.

Input: `data/clean_issues_<repo>.json` (output of the cleaning stage).
Output: none (prints enriched fields to stdout only).

Run directly, e.g.:
    python -m pipeline.enrichment.debug_preprocessing_issues_v2
(edit the `repo`/`max_issues` defaults in `main()` or call `main(repo=..., max_issues=...)`
from a Python shell to inspect a different repo/sample size).
"""

import json

from pipeline.enrichment.preprocessing_model import PreprocessingModelIssuesV2
from shared.utils.paths import DATA_DIR


def main(repo: str = "STM32CubeH7", max_issues: int = 20) -> None:
    """Print enriched fields for a sample of clean issues of one repo.

    Loads `clean_issues_<repo>.json`, runs each of the first `max_issues`
    issues through `PreprocessingModelIssuesV2.process_clean_issue`, and
    prints the key derived fields (issue_kind, layer, severity, board,
    component, is_valid) for quick manual inspection.

    Args:
        repo: Repository name used to locate `clean_issues_<repo>.json`.
        max_issues: Maximum number of issues (from the start of the file) to
            process and print.

    Raises:
        FileNotFoundError: If the input file does not exist.
    """
    in_path = DATA_DIR / f"clean_issues_{repo}.json"
    if not in_path.exists():
        raise FileNotFoundError(f"File not found: {in_path}")

    with open(in_path, "r", encoding="utf-8") as f:
        issues = json.load(f)

    model = PreprocessingModelIssuesV2()

    for issue in issues[:max_issues]:
        doc = model.process_clean_issue(issue)
        print(f"Issue #{doc['issue_number']} - {doc.get('issue_title')[:60]}")
        print(f"  issue_kind : {doc.get('issue_kind')}")
        print(f"  layer      : {doc.get('layer')}")
        print(f"  severity   : {doc.get('severity')}")
        print(f"  board      : {doc.get('board')}")
        print(f"  component  : {doc.get('component')}")
        print(f"  is_valid   : {doc.get('is_valid')}")
        print("-" * 80)


if __name__ == "__main__":
    main()
