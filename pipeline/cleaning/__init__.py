"""Cleaning stage of the STM32Cube preprocessing pipeline.

This package normalizes and sanitizes the raw JSON artifacts produced by
`pipeline.ingestion` (issues and files), stripping HTML/markdown noise,
license boilerplate, and inline images, before enrichment
(`pipeline.enrichment`) builds structured "docs_v2" records from them.

See `pipeline/cleaning/README.md` for details on each script.
"""
