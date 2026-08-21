---
name: evaluation-analyzer
description: "Use when: interpreting Quality Index results, pipeline stats outputs, or comparison benchmarks. Produces analysis tables, trend explanations, and improvement recommendations for the PFE report."
---

# Purpose

Analyze evaluation data from the STM32Cube preprocessing pipeline and produce structured insights for the PFE report.

# Input Types

1. **Quality Index test results**: QI score, number of questions, date, configuration
2. **Pipeline stats**: output of `test_stats_issues_v2.py` or `test_stats_files_v2.py`
3. **Comparison data**: Alfred vs Persona scores, V2 vs V3 metrics, before/after enrichment
4. **Alfred summary files**: `*__alfred_summary.json` with success/failure counts

# Analysis Framework

For each new result:

1. **What changed?** — Identify the configuration or content change
2. **What was the measured impact?** — Quantify with numbers (QI delta, %, counts)
3. **Why?** — Explain the root cause of improvement or regression
4. **So what?** — State the implication for the system and the user
5. **What next?** — Suggest the logical next improvement

# Output

Produce LaTeX content with:
- Summary table of results
- Trend analysis (is QI improving? which component drives the change?)
- Comparison with previous configuration
- Recommendations for next steps
- Properly labeled figures/tables for cross-reference

# Quality Index History

| Date | Test | QI | Questions | Content |
|------|------|-----|-----------|---------|
| 20 Apr | H7 Issues seules | 54 | 50 | Issues H7 only |
| 20 Apr | H7 Prompt Fix | 57 | 50 | + System prompt |
| 24 Apr | H7 Config Tool | 61 | 50 | + Hybrid search |
| 28 Apr | H7 + Diag Cards | 94 | 50 | + Resolver + Diagnostic |
| 08 May | H7 Real Cases | 88 | 4 | ST Community cases |
| 02 Jun | Multi-series v1 | 83 | 4 | First multi-series |
| 08 Jun | Multi-series full | 54 | 52 | 5 series, 52 questions |
