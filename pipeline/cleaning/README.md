# pipeline/cleaning

Cleaning stage of the STM32Cube preprocessing pipeline:

```
ingestion -> cleaning -> enrichment -> similarity -> chunking -> evaluation -> delivery
```

This stage normalizes and sanitizes the raw JSON artifacts produced by
`pipeline/ingestion` (issues and files) before enrichment
(`pipeline/enrichment`) builds structured `docs_v2` records from them.

## Scripts

| Script | Description | How to run |
| --- | --- | --- |
| `clean_issues.py` | Reads `raw_issues_<repo>.json` and builds one normalized `clean_text` block per issue (title + body + comments), stripping inline `<img>` HTML into `[IMAGE ATTACHED]` placeholders and collecting `image_urls`. Uses `cleaning_service.build_clean_issue`. | `python -m pipeline.cleaning.clean_issues` |
| `clean_files.py` | Reads `raw_files_<repo>.json`, normalizes whitespace/line endings, and classifies each file into a `file_type` (e.g. `driver_source`, `root_readme`, `release_notes`, `documentation_pdf`). This is the V1 cleaning pass. | `python -m pipeline.cleaning.clean_files` |
| `clean_files_v3.py` | Reads the V1 output (`clean_files_<repo>.json`) and applies type-aware cleaning per `file_type`: HTML stripping for release notes, markdown badge/image-link removal for READMEs, license-header stripping for source code, register-map filtering for giant CMSIS device headers, and key-field extraction for `package.xml`/SBOM metadata. Writes a new `_v3.json` file; never overwrites V1. | `python -m pipeline.cleaning.clean_files_v3` |
| `cleaning_service.py` | Library used by `clean_issues.py`: `normalize_newlines`, `clean_body_or_comment`, `build_clean_issue`. No CLI. | n/a |

## Typical inputs / outputs

- Inputs (from `pipeline/ingestion`, under `data/`):
  - `raw_issues_<repo>.json`
  - `raw_files_<repo>.json`
- Outputs (under `data/`):
  - `clean_issues_<repo>.json`
  - `clean_files_<repo>.json` (V1: normalized text + `file_type`)
  - `clean_files_<repo>_v3.json` (V3: type-aware cleaned text, additive — does not replace V1)

`clean_files_v3.py` supports the `STM32CUBE_CONFIG` environment variable to
target a single config file; otherwise it processes every
`shared/config/config*.json` file, de-duplicating repos already seen in an
earlier config.

## Role in the pipeline

- `clean_issues.py` output feeds `pipeline/enrichment/issues_to_docs_v2.py`.
- `clean_files.py` / `clean_files_v3.py` output feeds
  `pipeline/enrichment/files_to_docs_v2.py` (V3 is the type-aware variant
  intended for higher-quality chunking/retrieval).
