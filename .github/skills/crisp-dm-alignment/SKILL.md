---
name: crisp-dm-alignment
description: "Use when: verifying that report content maps to CRISP-DM phases, identifying missing methodological coverage, proposing transitional sentences that explicitly connect implementation to methodology."
---

# Purpose

Verify and strengthen CRISP-DM alignment in the PFE report. This skill helps ensure that the report demonstrates rigorous adherence to the CRISP-DM methodology at every level.

# When to Use

- Before writing a new section (to determine which CRISP-DM phase it belongs to)
- After writing content (to verify phase linkage is explicit)
- During audit (to produce a full coverage matrix)
- When the user asks "where does this fit in CRISP-DM?"

# CRISP-DM Phase Mapping for This Project

## Phase 1: Business Understanding
- Problem: ST engineers spend too long finding STM32 answers
- Objective: Automated KB with Quality Index > 80
- Success criteria: Coverage of 25 series, response accuracy on technical questions
- Constraints: Must use ST internal platform (ST ChatGPT), enterprise security

## Phase 2: Data Understanding
- Sources: 25 GitHub repos × (issues + PRs + commits + files + PDFs)
- Volume: ~60,000+ raw artifacts across all series
- Quality issues: HTML noise, license headers, CMSIS bloat, encoding problems
- Exploration: stats scripts (`test_stats_issues_v2.py`, `test_stats_files_v2.py`)

## Phase 3: Data Preparation
- Cleaning V1 (basic) + V3 (type-aware): HTML strip, CMSIS filter, license removal
- Enrichment: NLP heuristics extract structured metadata (layer, severity, board, component)
- Similarity: TF-IDF cosine links related issues
- Chunking: segment documents for optimal retrieval
- Validation: JSON Schema gates ensure quality contracts

## Phase 4: Modeling
- TF-IDF as lightweight similarity model (no GPU, fast iteration)
- Delivery templates as "model" for structuring RAG context
- KB search configuration as retrieval "model" (hybrid vs semantic vs fulltext)
- Threshold tuning: similarity 0.3, semantic 0.55

## Phase 5: Evaluation
- Quality Index: automated scoring across configurations
- A/B testing: strategy S0-S6 comparison
- Error analysis: categorized failures (retrieval miss, wrong series, hallucination)
- Benchmark: 96-question multi-series evaluation

## Phase 6: Deployment
- KB upload automation (Add_Data_Source_Files.py, per-series datasources)
- CI/CD (Jenkins pipeline, Jenkinsfile)
- Monitoring: QI regression detection
- Maintenance: `--skip-repo-sync` for incremental updates, `--continue-on-error` for resilience

# Output

When invoked, produce:
1. The CRISP-DM phase(s) the content belongs to
2. A suggested introductory sentence connecting to the methodology
3. Any gaps that should be addressed to strengthen phase coverage

# Example

Input: "I'm writing about the V3 cleaning pipeline"
Output:
- **Phase**: Data Preparation (Phase 3)
- **Suggested intro**: "Dans le cadre de la phase de préparation des données (CRISP-DM), le nettoyage V3 implémente des stratégies type-aware..."
- **Gap check**: Ensure before/after size metrics are included (demonstrates measurable preparation impact)
