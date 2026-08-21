"""Evaluation stage package for the STM32Cube preprocessing pipeline.

This package groups all quality-control scripts that run after ingestion,
cleaning, enrichment, similarity, chunking, and delivery. Scripts here are
read-mostly diagnostic tools: they compute statistics, run TF-IDF retrieval
simulations, validate JSON documents against `shared/schemas`, and check the
coherence of Alfred (internal LLM) image descriptions against their source
context. Most scripts print reports to the console or write CSV/JSON reports
under `datasets/06_eval_outputs/` or `docs/evaluation/`, without mutating the
pipeline's core datasets.

See `pipeline/evaluation/README.md` for the full list of scripts and how to
run each one.
"""
