---
name: latex-section-writer
description: "Use when: writing or updating a specific LaTeX section in the PFE report. Takes raw data/results and produces properly formatted French academic LaTeX content with tables, equations, and cross-references."
---

# Purpose

Write or update LaTeX sections for the PFE report. Produces clean, compilable LaTeX in French academic style.

# Input

The user provides one of:
- Raw evaluation results (numbers, stats, QI scores)
- A new pipeline feature or improvement description
- A configuration change with before/after metrics
- A new series addition with pipeline output

# Behavior

1. Read the current report to understand existing structure and terminology
2. Identify the target chapter/section
3. Check for existing content on the same topic
4. Write the LaTeX section with:
   - `\section{}` or `\subsection{}` with descriptive French titles
   - `longtable` for data tables (with `\toprule`, `\midrule`, `\bottomrule`)
   - `equation` for formulas
   - `lstlisting` for code samples
   - `\texttt{}` for API/function names
   - `\textbf{}` for key terms on first use
   - Proper `\label{}` for cross-references
5. Insert at the correct location in the .tex file

# Style

- French formal academic (not robotic, humanized)
- Every claim quantified with numbers
- Every choice justified (why? what alternatives? what impact?)
- Show incremental reasoning (problem → solution → result)
- Use transition sentences between subsections
