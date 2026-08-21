"""Objective, reproducible rubric scoring for the Alfred vs Persona comparative study.

The manual grading columns in ``comparison_alfred_vs_persona.xlsx`` (exported by
``pipeline_Automation/test_suites/compare_alfred_vs_persona.py``) were never filled in by a
human reviewer. This script applies the same 6-criteria grid (max 10 pts, see
``EVALUATION_COLUMNS`` in that script / the "Grille d'evaluation" sheet) to the raw
``comparison_alfred_vs_persona.json`` transcript using deterministic, pattern-based detection,
so that the comparative-study numbers cited in the PFE report are traceable and reproducible.

Criteria (2 pts unless noted):
  - cite_issue      : cites a GitHub issue number (``#123`` / ``issue #123``)              [+2]
  - hal_function    : names an exact HAL/LL function (``HAL_xxx(`` / ``LL_xxx(``)          [+1]
  - actionable_fix  : gives an immediate actionable fix (code block or numbered steps)     [+2]
  - version_specific: mentions a specific version / release note                          [+2]
  - workaround      : gives an STM32-specific workaround (register/flag/cache reference)   [+2]
  - source_verifiable: references a verifiable source (file, commit, issue, release note)  [+1]

A non-answer (timeout / "could not find enough reliable information") scores 0 on all criteria.

Usage:
    python -m pipeline.evaluation.score_alfred_vs_persona_rubric [--json PATH] [--out PATH]
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

DEFAULT_JSON = Path("datasets/07_delivery/st_ready/evaluation_report/comparison_alfred_vs_persona.json")

ISSUE_RE = re.compile(r"issue\s*#\s*\d+|#\d{1,5}\b", re.IGNORECASE)
HAL_FUNC_RE = re.compile(r"\b(?:HAL|LL)_[A-Za-z0-9_]+\(")
VERSION_RE = re.compile(r"\bv\d+\.\d+(\.\d+)?\b|release[_ ]notes?", re.IGNORECASE)
SOURCE_RE = re.compile(r"readme|release_notes|\.c\b|\.h\b|issue\s*#|commit", re.IGNORECASE)
CODE_BLOCK_RE = re.compile(r"```")
NUMBERED_STEP_RE = re.compile(r"^\s*\d+[).]\s", re.MULTILINE)
WORKAROUND_RE = re.compile(
    r"\bregister|\bflag\b|cache|DCache|MPU|clean|invalidate|workaround|errata|align",
    re.IGNORECASE,
)
NO_ANSWER_RE = re.compile(
    r"request timeout|could not find enough reliable information",
    re.IGNORECASE,
)


def score_answer(text: str) -> dict[str, Any]:
    if not text or NO_ANSWER_RE.search(text):
        return {
            "cite": 0, "hal": 0, "act": 0, "ver": 0, "work": 0, "src": 0,
            "total": 0, "no_answer": True,
        }

    cite = 2 if ISSUE_RE.search(text) else 0
    hal = 1 if HAL_FUNC_RE.search(text) else 0
    act = 2 if (CODE_BLOCK_RE.search(text) or NUMBERED_STEP_RE.search(text)) else 0
    ver = 2 if VERSION_RE.search(text) else 0
    work = 2 if WORKAROUND_RE.search(text) else 0
    src = 1 if SOURCE_RE.search(text) else 0
    total = cite + hal + act + ver + work + src
    return {
        "cite": cite, "hal": hal, "act": act, "ver": ver, "work": work, "src": src,
        "total": total, "no_answer": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--out", type=Path, default=None, help="Optional path to dump per-question scores as JSON")
    args = parser.parse_args()

    rows = json.loads(args.json.read_text(encoding="utf-8"))

    per_question = []
    by_category: dict[str, list[tuple[float, float]]] = defaultdict(list)
    alfred_scores, persona_scores = [], []
    persona_answered = 0

    for r in rows:
        a = score_answer(r["alfred_answer"])
        p = score_answer(r["persona_answer"])
        per_question.append({"question": r["question"], "category": r["category"], "alfred": a, "persona": p})
        by_category[r["category"]].append((a["total"], p["total"]))
        alfred_scores.append(a["total"])
        persona_scores.append(p["total"])
        if not p["no_answer"]:
            persona_answered += 1

    n = len(rows)
    print(f"N = {n}")
    print(f"Alfred avg score:  {sum(alfred_scores) / n:.2f}/10")
    print(f"Persona avg score: {sum(persona_scores) / n:.2f}/10")
    print(f"Persona substantive-answer rate: {persona_answered}/{n} ({100 * persona_answered / n:.1f}%)")
    print("\nPer-category (Alfred, Persona) averages:")
    for cat, pairs in by_category.items():
        a_avg = sum(p[0] for p in pairs) / len(pairs)
        p_avg = sum(p[1] for p in pairs) / len(pairs)
        print(f"  {cat} (n={len(pairs)}): Alfred={a_avg:.2f}  Persona={p_avg:.2f}")

    if args.out:
        args.out.write_text(json.dumps(per_question, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nPer-question scores written to {args.out}")


if __name__ == "__main__":
    main()
