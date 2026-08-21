# ST KB A/B/C Test Protocol for STM32Cube Issues

## Goal

Measure whether ST-ready exported issues improve answer quality versus raw and default docs uploads.

## Datasets to Compare

- Dataset A: raw issues upload (baseline)
- Dataset B: docs_issues_v2 upload (current preprocessing, default export)
- Dataset C: ST-ready issue cards generated with:
  - python -m pipeline.delivery.export_st_ready_issues --repo STM32CubeH7

## Upload Recommendation

Create three different KB data sources and keep all other persona settings identical.

- Source A: raw_issues_stm32cubeh7.json
- Source B: docs_issues_stm32cubeh7_v2.json
- Source C: datasets/07_delivery/st_ready/issues/stm32cubeh7/*.md

## Query Set

Use the same 30 questions for all datasets.

Suggested mix:
- 10 bug diagnosis questions
- 10 configuration/help questions
- 10 dual-core / power / synchronization questions

## Evaluation Sheet

For each question and dataset, score the answer with:

- Top-1 correctness (0/1)
- Technical precision (0-2)
- Source relevance (0-2)
- Hallucination risk (0-2, inverse: 2 = low risk)
- Actionability (0-2)

Total per question per dataset: /9

## Decision Rule

Choose the dataset with:

1. Highest average total score
2. Highest Top-1 correctness
3. Lowest hallucination risk score variance

If C beats A and B, keep preprocessing and switch to ST-ready export as delivery format.

## Fast Tracking

If you want quick evidence before full 30-question run:

- Run 10 representative queries first
- If C improves Top-1 by >= 20% versus A, continue with full evaluation

## Notes

- Keep persona, temperature, and max tokens fixed across tests.
- Ask each question with exactly the same wording for A/B/C.
- Keep logs of returned sources to inspect failure cases.
