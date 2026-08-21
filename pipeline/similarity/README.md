# pipeline/similarity

## Purpose

The similarity stage links related issues together so retrieval/chatbot
answers can surface similar/duplicate issues. It computes TF-IDF vectors over
each repo's valid enriched issues and pairwise cosine similarity, then
attaches the top-k related issue ids to every doc as `related_issue_ids`.

It runs after `pipeline/enrichment` (issues) and before `pipeline/chunking`.

## Scripts

| Script | Description | Run |
| --- | --- | --- |
| `compute_issue_similarity_v2.py` | For each repo: reads `docs_issues_<repo>_v2.json`, builds a TF-IDF matrix over valid issues' title+body text, computes cosine similarity, and writes `related_issue_ids` (top-k above a minimum similarity threshold) into `docs_issues_<repo>_v2_sim.json`. | `python -m pipeline.similarity.compute_issue_similarity_v2` |

## Typical inputs / outputs

- **Input**: `data/docs_issues_<repo>_v2.json` (from `pipeline/enrichment`).
- **Output**: `data/docs_issues_<repo>_v2_sim.json` (same docs, with
  `related_issue_ids` added).

Default parameters: `top_k=3` related issues, `min_sim=0.4` cosine similarity
threshold (set in `main()`).

## Role in the pipeline

```
enrichment -> similarity (this folder) -> chunking -> evaluation -> delivery
```

`docs_to_chunks_issues_v2.py` (in `pipeline/chunking`) prefers the
`_v2_sim.json` output of this stage over the plain `_v2.json` enrichment
output, falling back to the latter if similarity has not been computed yet.

Config (repo list) is resolved via `shared.utils.paths.get_config_path()`
(default `shared/config/config_all_series.json`, overridable with
`STM32CUBE_CONFIG`).
