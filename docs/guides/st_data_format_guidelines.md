# ST Knowledge Base Data Format Guidelines

## Goal

Define a delivery format that improves retrieval quality in ST unstructured knowledge ingestion while keeping the STM32Cube preprocessing signal.

## Recommended Unit Of Knowledge

- One document per issue.
- One primary technical problem per document.
- Keep exact technical anchors (MCU names, APIs, error codes, peripheral names).

## Required JSON Fields

For each exported issue object:

- `id` (string)
- `repo` (string)
- `mcu_series` (string)
- `issue_number` (number)
- `issue_title` (string)
- `state` (string)
- `layer` (string)
- `component` (string)
- `issue_kind` (string)
- `severity` (string)
- `board` (string)
- `labels` (list of strings)
- `github_url` (string)
- `is_valid` (boolean)
- `delivery_template` (string, current value: `st_v2_structured_issue_card`)
- `st_ready_text` (string)

## Required `st_ready_text` Structure

The exported text should follow this fixed layout:

1. `Problem: <issue_title>`
2. `Context: repo=..., mcu_series=..., board=..., component=..., layer=..., issue_kind=..., severity=..., state=..., issue_number=...`
3. `Root cause: <short root cause hint>`
4. `Fix: <short actionable fix hint>`
5. `Constraints: <safety and applicability constraints>`
6. `Keywords: <deduplicated technical anchors>`
7. `Technical details:`
8. `<clean issue body>`
9. Optional `Key comments:`
10. `<condensed comments>`

## Retrieval Quality Checks

Use this checklist before loading data into ST KB:

- Top-1 retrieval gives the correct issue topic for benchmark queries.
- No cross-topic confusion between near issues (for example SDMMC/MDMA vs ADC/BOOST).
- Cited source corresponds to the active tested dataset.
- Critical technical terms appear in both query and `st_ready_text`.
- Documents are not over-compressed (missing root cause/fix signals).

## Known Failure Patterns

- Too short summaries with weak technical anchors.
- Overly long forum-like narratives with high noise.
- Missing board/MCU/component context in first lines.
- Mixing multiple independent issues in one entry.

## Current Project Decision

Based on current benchmark observations:

- Keep `docs_issues_v2` as the strongest semantic source.
- Use ST-ready export as a delivery layer, not as a replacement for preprocessing.
- Improve ST retrieval robustness through stable text template and keyword anchors.
