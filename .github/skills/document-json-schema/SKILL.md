---
name: document-json-schema
description: "Use when: documenting JSON structures from docs/chunks and ST-ready delivery outputs, inferring fields and types from examples, and updating schema docs/contracts under docs/ and shared/schemas/."
---

# Purpose

This skill helps generate clear, human-readable documentation for the JSON outputs produced by the STM32Cube preprocessing pipeline:

- `docs_issues_*_v2.json`
- `docs_issues_*_v2_sim.json`
- `docs_files_*_v2.json`
- `chunks_issues_*_v2.json`
- `chunks_files_*_v2.json`
- `st_ready_issues_*.json`
- `st_ready_files_*.json`
- `st_ready_resolver_cases_*.json`
- `st_ready_diagnostic_cards_*.json`
- `summary_*.json` (delivery summaries)

# Behavior

When this skill is invoked, it must:

1. Take as input one or more JSON examples from the output files above.
2. Infer the JSON schema:
   - root format (array, object with top-level key, scalar metadata),
   - field names,
   - expected types (string, int, bool, list, etc.),
   - meaning of each field in the STM32Cube context,
   - whether the field is optional or required.
3. Produce Markdown documentation suitable for a file like `docs/json_schemas.md`, organized with:
   - a title for each JSON type (e.g. "Schema docs_issues_v2"),
   - a bullet list or table describing each field.
4. For ST-ready payloads, explicitly document consumer-facing expectations (for example `rootTagPath`, `delivery_template`, evidence refs, query aliases).
5. Stay grounded in this project: explanations must be specific to STM32Cube preprocessing and delivery.
6. When schema contract files exist under `shared/schemas/`, align the documentation with those contracts and mention mismatches.
