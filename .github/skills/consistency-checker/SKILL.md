---
name: consistency-checker
description: "Use when: checking for duplicated content, terminology inconsistencies, factual contradictions, or structural problems across the PFE report. Produces actionable findings with exact locations and suggested fixes."
---

# Purpose

Detect and report consistency problems in the PFE report to ensure it reads as a unified, professional academic document.

# When to Use

- After adding new content (check it doesn't contradict existing)
- Before final submission (full consistency audit)
- When user reports "something seems wrong" or "I think I repeated this"
- After large structural changes (chapter reordering, content moves)

# Detection Rules

## Duplication Detection
- Two paragraphs with >70% word overlap = likely duplicate
- Same table/figure appearing in two chapters
- Same pipeline stage described in both implementation and evaluation chapters
- Repeated definitions of the same term

## Terminology Rules (Project Glossary)

| Canonical (use this) | Variants (flag these) |
|---------------------|----------------------|
| enrichissement | annotation, labellisation, tagging, labeling |
| pipeline de prétraitement | pipeline de traitement, preprocessing pipeline |
| base de connaissances | knowledge base, BDD |
| Indice de Qualité (QI) | Quality Index, score qualité, score de qualité |
| carte diagnostique | diagnostic card, fiche diagnostic, carte de diagnostic |
| cas résolveur | resolver case, cas de résolution |
| recherche hybride | hybrid search, recherche mixte |
| nettoyage V3 | cleaning V3, nettoyage type-aware |
| livraison ST-ready | ST-ready delivery, export ST-ready |
| Alfred Vision | Alfred, Alfred Tool, outil Alfred |
| NovaX | Nova X, Nova-X |

## Number Consistency
- Series count must be consistent everywhere (currently: 25 total)
- QI scores must match the evaluation chapter data
- File/issue counts must match pipeline output stats
- Datasource IDs must match config_all_series.json

## Structural Checks
- Every `\ref{}` must point to an existing `\label{}`
- Every `\cite{}` must have a `\bibitem{}`
- Every chapter introduction should summarize what follows
- Every chapter conclusion should link forward to the next

# Output Format

```markdown
## Finding #N: [Category]
- **Location**: Chapter X, Section Y (line ~Z)
- **Severity**: Critical / Moderate / Minor
- **Issue**: [description]
- **Evidence**: "[quoted text A]" vs "[quoted text B]"
- **Fix**: [specific action]
```

# Behavior

1. Read the specified scope (full report or specific chapters)
2. Index all key terms, numbers, and definitions with their locations
3. Cross-reference for inconsistencies
4. Produce findings sorted by severity
5. For each finding, provide:
   - The exact problem
   - Both conflicting locations
   - A specific fix (which one to keep, what to change)
