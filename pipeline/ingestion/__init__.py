"""Ingestion stage of the STM32Cube preprocessing pipeline.

This package fetches raw data from GitHub (issues, pull requests, commits,
issue/PR/commit linkage) via the REST API, and collects raw file artifacts
(README, release notes, source files, documentation PDFs) from local repo
clones under `GitHub_repos/`. Outputs are written as JSON under `data/` and
consumed by `pipeline.cleaning`.

See `pipeline/ingestion/README.md` for details on each script.
"""
