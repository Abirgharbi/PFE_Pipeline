---
name: report-quality-audit
description: "Use when: performing a full or partial quality audit of the PFE report, assessing defense readiness, planning incremental improvements, or evaluating report structure against academic standards."
---

# Purpose

Perform structured quality audits of the PFE report and produce prioritized improvement plans. This skill helps maintain the report at defense-ready quality throughout the writing process.

# When to Use

- User asks "what's missing in the report?"
- User asks "is the report ready for defense?"
- Before final compilation
- After a major content addition (to check integration quality)
- When planning next writing session

# Audit Dimensions

| Dimension | Score Range | Criteria |
|-----------|------------|----------|
| Structure | 1-10 | Clear hierarchy, logical flow, no orphan sections |
| Completeness | 1-10 | All expected topics covered for a preprocessing pipeline PFE |
| Quantification | 1-10 | Claims backed by data, tables present, metrics visible |
| CRISP-DM | 1-10 | Methodology explicitly mapped, all 6 phases covered |
| Visual Support | 1-10 | Diagrams for architecture, flows, results; not text-only |
| Academic Quality | 1-10 | French register, transitions, citations, references |
| Coherence | 1-10 | No contradictions, consistent terminology, clean references |
| Defense Readiness | 1-10 | Can withstand jury questions on any section |

# Expected Content Checklist

## Must-Have for Defense

- [ ] Problem statement with quantified business impact
- [ ] State-of-art comparison (at least 3 comparable solutions)
- [ ] Architecture diagram (global pipeline)
- [ ] CRISP-DM mapping diagram or table
- [ ] Implementation details for each pipeline stage
- [ ] Before/after metrics for key improvements
- [ ] Quality Index methodology explanation
- [ ] Results table with multiple configurations
- [ ] Technology justification section
- [ ] Scalability evidence (25 series)
- [ ] Limitations and future work
- [ ] Clean compilation (no LaTeX errors)

## Nice-to-Have (Differentiators)

- [ ] Comparison with commercial solutions (cost, coverage)
- [ ] User feedback quotes
- [ ] Performance metrics (processing time per series)
- [ ] Security considerations
- [ ] Data governance discussion

# Behavior

1. Read the full report
2. Score each dimension for each chapter
3. Produce a heat map:
   - 🟢 (8-10): Strong, defense-ready
   - 🟡 (5-7): Acceptable but can improve
   - 🔴 (1-4): Critical gap, must fix before defense
4. Identify top 5 highest-impact improvements
5. For each improvement, estimate:
   - Effort: Small (< 1 hour), Medium (1-3 hours), Large (> 3 hours)
   - Impact: How much it improves defense readiness
   - Priority = Impact / Effort

# Output Format

```markdown
## Report Quality Audit — [Date]

### Overall Score: X/80 (dimensions × max 10)

### Heat Map
| Chapter | Struct | Complete | Quant | CRISP | Visual | Academic | Coherence | Defense |
|---------|--------|----------|-------|-------|--------|----------|-----------|---------|
| Ch.1    | 🟢 9   | 🟡 7    | 🟡 6  | 🟡 6  | 🔴 3   | 🟢 8    | 🟢 9      | 🟡 7   |
| ...     |        |          |       |       |        |          |           |         |

### Top 5 Improvements
1. [Description] — Effort: Small, Impact: High, Priority: ⭐⭐⭐
2. ...

### Defense Risk Areas
- Jury might ask: "..."
- Current answer quality: ...
- Recommended preparation: ...
```

# Rules

- Be honest about gaps (the user needs truth, not encouragement)
- Prioritize by defense impact (what will the jury ask?)
- Every recommendation must be actionable (not "improve this section")
- Consider the report as a whole (no chapter in isolation)
