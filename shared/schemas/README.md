# Schemas Validation Guide

This folder contains JSON Schema contracts for STM32Cube preprocessing outputs.

## Available schemas

- docs_issues_v2.schema.json: schema for data/docs_issues_*_v2.json
- docs_files_v2.schema.json: schema for data/docs_files_*_v2.json
- chunks_issues_v2.schema.json: schema for data/chunks_issues_*_v2.json
- chunks_files_v2.schema.json: schema for data/chunks_files_*_v2.json
- raw_prs.schema.json: schema for data/raw_prs_*.json
- raw_commits.schema.json: schema for data/raw_commits_*.json
- issue_pr_commit_links.schema.json: schema for data/issue_pr_commit_links_*.json

## Why validate

Schema validation helps you:

- catch structural regressions early,
- ensure compatibility before ST RAG ingestion,
- enforce stable data contracts between pipeline stages.

## Option A: Validate with Python (recommended)

### 1) Install dependency

```bash
pip install jsonschema
```

### 2) Run this one-shot validation script

```bash
python - << "PY"
import json
from pathlib import Path
from jsonschema import validate

root = Path(".")

pairs = [
    ("shared/schemas/docs_issues_v2.schema.json", "data/docs_issues_stm32cubeh7_v2.json"),
    ("shared/schemas/docs_files_v2.schema.json", "data/docs_files_stm32cubeh7_v2.json"),
    ("shared/schemas/chunks_issues_v2.schema.json", "data/chunks_issues_stm32cubeh7_v2.json"),
    ("shared/schemas/chunks_files_v2.schema.json", "data/chunks_files_stm32cubeh7_v2.json"),
]

for schema_rel, data_rel in pairs:
    schema_path = root / schema_rel
    data_path = root / data_rel

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    data = json.loads(data_path.read_text(encoding="utf-8"))

    validate(instance=data, schema=schema)
    print(f"OK: {data_rel} matches {schema_rel}")

print("All validations passed.")
PY
```

## Option B: Validate with Node.js ajv-cli

### 1) Install tool

```bash
npm install -g ajv-cli
```

### 2) Validate examples

```bash
ajv validate -s shared/schemas/docs_issues_v2.schema.json -d data/docs_issues_stm32cubeh7_v2.json
ajv validate -s shared/schemas/docs_files_v2.schema.json -d data/docs_files_stm32cubeh7_v2.json
ajv validate -s shared/schemas/chunks_issues_v2.schema.json -d data/chunks_issues_stm32cubeh7_v2.json
ajv validate -s shared/schemas/chunks_files_v2.schema.json -d data/chunks_files_stm32cubeh7_v2.json
```

## CI integration suggestion

Run schema validation right after each stage:

1. After enrichment: validate docs_issues_v2 and docs_files_v2.
2. After chunking: validate chunks_issues_v2 and chunks_files_v2.
3. Fail CI pipeline if any validation fails.

## Notes

- These schemas are inferred from current project outputs and enforce key enums and required fields.
- Optional fields can be null in many cases (for example board, component, closed_at).
- If you add new fields in pipeline outputs, update the corresponding schema in this folder.
