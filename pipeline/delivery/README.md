# `pipeline/delivery` — ST-ready delivery stage

This folder implements the **final stage** of the STM32Cube preprocessing
pipeline. It reads cleaned/enriched/linked datasets (issues, files, PR/commit
links) and exports "ST-ready" JSON artifacts under
`datasets/07_delivery/st_ready/`, ready to be uploaded to the ST AI Bridge
persona knowledge base via `pipeline_Automation/upload/Add_Data_Source_Files.py`.

Path resolution for every export/split script goes through
[`delivery_paths.py`](delivery_paths.py), which lays artifacts out per repo
under `datasets/07_delivery/st_ready/by_series/<series>/[drivers/<sub-repo>/]<artifact_dir>/`,
while also mirroring them into a legacy flat `datasets/07_delivery/st_ready/<artifact_dir>/`
folder for backward compatibility.

## Data flow

```
data/docs_issues_<repo>_v2.json ──┐
data/docs_files_<repo>_v2.json ───┤
issue_pr_commit_links_<repo>.json ┘
            │
            ▼
  export_st_ready_issues.py            → issues_json/st_ready_issues_<repo>.json
  export_st_ready_issues_with_images.py → issues_json/st_ready_issues_with_images_<repo>.json
  export_st_ready_files.py             → files_json/st_ready_files_<repo>.json
  export_st_ready_resolver_cases.py    → resolver_cases_json/st_ready_resolver_cases_<repo>.json
            │
            ▼ (issues + resolver cases)
  export_st_ready_diagnostic_cards.py  → diagnostic_cards_json/st_ready_diagnostic_cards_<repo>.json
            │
            ▼ (optional post-processing / manual-upload prep)
  split_st_ready_files_for_manual_upload.py
  split_st_ready_issues_by_component.py → by_component/st_ready_issues_<series>_<component>.json
  split_mixed_resolver_payload.py
  validate_issues_by_component_split.py
            │
            ▼
  pipeline_Automation/upload/Add_Data_Source_Files.py  (upload to ST AI Bridge KB #793)
```

## Scripts

| Script | Description | Run |
| --- | --- | --- |
| [`delivery_paths.py`](delivery_paths.py) | Shared path-resolution helpers (repo→series mapping, by-series vs. legacy flat layout). Not a CLI, imported by every other script here. | n/a |
| [`export_st_ready_issues.py`](export_st_ready_issues.py) | Exports `docs_issues_<repo>_v2.json` into ST-ready issue cards (JSON array or per-issue Markdown). | `python -m pipeline.delivery.export_st_ready_issues --repo STM32CubeH7` |
| [`export_st_ready_issues_with_images.py`](export_st_ready_issues_with_images.py) | Same as above but also extracts `image_urls`, required input for Alfred Vision image enrichment. | `python -m pipeline.delivery.export_st_ready_issues_with_images --repo STM32CubeH7` |
| [`export_st_ready_files.py`](export_st_ready_files.py) | Exports `docs_files_<repo>_v2.json` (README/Release Notes/examples/BSP docs) into ST-ready file cards. | `python -m pipeline.delivery.export_st_ready_files --repo STM32CubeH7` |
| [`export_st_ready_resolver_cases.py`](export_st_ready_resolver_cases.py) | Exports issue→PR/commit linkage (with changed-file evidence) into resolver case cards. | `python -m pipeline.delivery.export_st_ready_resolver_cases --repo STM32CubeH7` |
| [`export_st_ready_diagnostic_cards.py`](export_st_ready_diagnostic_cards.py) | Synthesizes structured troubleshooting cards (facts → hypotheses → checks) from rescued issues + resolver cases, plus curated cross-series cards (e.g. I2C bus recovery). | `python -m pipeline.delivery.export_st_ready_diagnostic_cards --repo STM32CubeH7` |
| [`split_st_ready_files_for_manual_upload.py`](split_st_ready_files_for_manual_upload.py) | Splits large `files_json` exports into small JSON parts for manual (no-API) datasource upload. | `python -m pipeline.delivery.split_st_ready_files_for_manual_upload` |
| [`split_st_ready_issues_by_component.py`](split_st_ready_issues_by_component.py) | Splits an issues-with-images payload into per-STM32-peripheral-component JSON files for finer-grained KB datasources. | `python -m pipeline.delivery.split_st_ready_issues_by_component` |
| [`split_mixed_resolver_payload.py`](split_mixed_resolver_payload.py) | Splits a mixed `resolver_cases` + `diagnostic_cards` JSON payload into two separate upload-ready files. | `python -m pipeline.delivery.split_mixed_resolver_payload --input <mixed.json> --resolver-output <r.json> --diagnostic-output <d.json>` |
| [`validate_issues_by_component_split.py`](validate_issues_by_component_split.py) | Validates a by-component issues split: no duplicate issue IDs, full coverage, no extras. | `python -m pipeline.delivery.validate_issues_by_component_split --summary <summary_by_component_<series>.json>` |

## Typical inputs/outputs

- **Inputs**: `data/docs_issues_<repo>_v2.json`, `data/docs_files_<repo>_v2.json`,
  `data/issue_pr_commit_links_<repo>[_linked_only].json`, `data/raw_commits_<repo>.json`,
  `data/raw_prs_<repo>.json`, plus `shared/config/config_all_series.json`
  (or a series-specific `shared/config/config_<series>.json`, selectable via
  the `STM32CUBE_CONFIG` env var).
- **Outputs**: `datasets/07_delivery/st_ready/by_series/<series>/{issues_json,files_json,resolver_cases_json,diagnostic_cards_json}/*.json`
  (plus `summary_*.json` files for traceability), mirrored under the legacy
  flat `datasets/07_delivery/st_ready/<artifact_dir>/`. Manual-upload and
  by-component splits live under `datasets/07_delivery/st_ready/manual_upload/`
  and `.../by_component/` respectively.

## Connection to `pipeline_Automation/upload`

Once the ST-ready JSON files are exported (and optionally Alfred-enriched or
split), `pipeline_Automation/upload/Add_Data_Source_Files.py` uploads them as
datasources to the ST AI Bridge knowledge base (KB #793, "ST GitHub
Analyzer"), typically with `--operation add --json-split-size 1000`.
Automation wrappers in `pipeline_Automation/workflow/` and
`pipeline_Automation/upload/Upload_STReady_New_Batch.ps1` chain the delivery
exports above with this upload step for a full run across all configured
repos.
