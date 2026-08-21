"""Quick sanity check on chunk text-length distribution for STM32CubeH7.

Role in the evaluation stage
-----------------------------
A minimal, dependency-free probe used while tuning chunking parameters
(``pipeline/chunking``): it loads a chunking-stage output file and prints
min/max/average chunk character length. This is a fast way to spot chunking
regressions (e.g. chunks that are empty, absurdly long, or too short to be
useful for TF-IDF/RAG retrieval) without running the full statistics suite
in ``test_stats_*_v2.py``.

Inputs
------
- ``data/chunks_issues_stm32cubeh7_v2.json`` and
  ``data/chunks_files_stm32cubeh7_v2.json`` (chunking stage outputs), each a
  list of chunk dicts with a ``text`` field.

Outputs
------
- Console-only: chunk count, min/max/avg text length per file. No files are
  written.

Usage (CLI)
-----------
    python pipeline/evaluation/inspect_chunks_size.py

Note: the repo/file names are hardcoded to STM32CubeH7; adapt the
``inspect(...)`` calls in ``main`` to check another series.
"""

import json

from shared.utils.paths import DATA_DIR


def inspect(path_name: str) -> None:
    """Load one chunks JSON file and print its text-length distribution.

    Args:
        path_name: File name (relative to DATA_DIR) of a chunking-stage
            output, e.g. ``chunks_issues_stm32cubeh7_v2.json``.
    """
    path = DATA_DIR / path_name
    chunks = json.loads(path.read_text(encoding="utf-8"))
    lengths = [len(c.get("text", "")) for c in chunks]
    print(path_name)
    print("  chunks:", len(lengths))
    print("  min len:", min(lengths))
    print("  max len:", max(lengths))
    print("  avg len:", sum(lengths) / len(lengths))
    print()


def main() -> None:
    """Inspect the STM32CubeH7 issues and files chunk files."""
    inspect("chunks_issues_stm32cubeh7_v2.json")
    inspect("chunks_files_stm32cubeh7_v2.json")


if __name__ == "__main__":
    main()
