"""Similarity stage of the STM32Cube preprocessing pipeline.

This package links related issues together by computing TF-IDF cosine
similarity between enriched issue documents (`docs_issues_<repo>_v2.json`)
and writing the top-k related issue ids back into each document as
`related_issue_ids` (`docs_issues_<repo>_v2_sim.json`).

See `pipeline/similarity/README.md` for details.
"""
