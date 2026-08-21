"""Print basic distribution statistics for enriched "files" documents (V2/V3).

This is a lightweight, dependency-free stats check for the enrichment stage
output on non-issue files (README, release notes, project files, docs)
before they are chunked and delivered. Despite the module's `test_` prefix
it is a standalone reporting script, not a pytest test — see the
`analyze-stats` skill for how to interpret its output.

Role in the evaluation stage: quick sanity check that `file_type`, `board`,
and `component` enrichment fields are populated with sensible, non-empty
values across a repo's corpus, and that the valid/total doc ratio looks
reasonable.

Inputs:
    - `data/docs_files_<repo>_v3.json` if present, else
      `data/docs_files_<repo>_v2.json` (repo defaults to the first
      `STM32Cube*` entry in `shared/config/config_all_series.json`).

Outputs:
    - Console-only: total/valid doc counts and top file_type/board/component
      breakdowns. No files are written.

CLI usage:
    python pipeline/evaluation/test_stats_files_v2.py
    (no CLI args; `main(repo=...)` can be called programmatically with a
    specific repo name)
"""

import json
from collections import Counter

from shared.utils.paths import DATA_DIR, get_config_path


def get_default_repo() -> str:
    """Return the first STM32Cube* repo from the shared config, or the first repo overall.

    Used to pick a default repo when the caller does not specify one.
    """
    cfg = json.loads(get_config_path().read_text(encoding="utf-8-sig"))
    repos = cfg.get("repos", [])
    return next((repo for repo in repos if str(repo).lower().startswith("stm32cube")), repos[0])


def print_counter(title: str, counter: Counter, max_items: int | None = None) -> None:
    """Print a `Counter` as a titled, underlined list of "key: count" lines.

    Args:
        title: Section heading printed above the counts.
        counter: Counter mapping category values to occurrence counts.
        max_items: If set, only the N most common items are printed.
    """
    print(f"\n{title}")
    print("-" * len(title))
    items = counter.most_common(max_items) if max_items else counter.items()
    for k, v in items:
        print(f"{k!r}: {v}")


def main(repo: str | None = None) -> None:
    """Load a repo's enriched files docs and print file_type/board/component stats.

    Args:
        repo: Repo name (e.g. "STM32CubeH7"). If None, resolved via
            `get_default_repo()`.

    Side effects:
        Prints stats to stdout. Prints a warning and returns early if the
        expected input JSON does not exist (no exception raised).
    """
    if repo is None:
        repo = get_default_repo()
    # Prefer the v3 enrichment output if present (newer schema), else fall
    # back to v2 for repos not yet migrated.
    path = DATA_DIR / f"docs_files_{repo.lower()}_v3.json"
    if not path.exists():
        path = DATA_DIR / f"docs_files_{repo.lower()}_v2.json"
    if not path.exists():
        print(f"[WARN] Stats files skipped; input not found: {path}")
        return
    docs = json.loads(path.read_text(encoding="utf-8"))

    file_types = Counter(d.get("file_type") for d in docs)
    boards = Counter(d.get("board") for d in docs if d.get("board"))
    components = Counter(d.get("component") for d in docs if d.get("component"))
    valid = sum(1 for d in docs if d.get("is_valid", True))
    total = len(docs)

    print(f"Stats files V2 for {repo}")
    print(f"Total docs: {total}, valid: {valid}")
    print_counter("File types", file_types)
    print_counter("Top boards", boards, max_items=10)
    print_counter("Top components", components, max_items=10)


if __name__ == "__main__":
    main()
