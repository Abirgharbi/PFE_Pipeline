# Upload — ST AI Bridge Knowledge Base Uploaders

This folder contains the scripts that push the "ST-ready" JSON produced by
`pipeline/delivery` (under `datasets/07_delivery/st_ready/**`) into ST's internal
**AI Bridge** REST API (`https://api-ai-bridge.st.com/chatgpt/api/client-apps`),
as datasources attached to the **"ST GitHub Analyzer"** persona Knowledge Base
(KB **#793**).

## Authentication

All scripts authenticate with an HMAC/SHA1 token derived from
`clientAppName + serviceName + apiKey + timestamp + nonce`. The API key is **never**
hardcoded — it is read from the first non-empty environment variable among:

```
PERSONA_API_KEY, ST_GITHUB_ANALYZER_API_KEY, ST_CHATGPT_API_KEY,
ST_AI_BRIDGE_API_KEY, ST_API_KEY
```

or passed explicitly via `--api-key` to `Add_Data_Source_Files.py`.

You can also configure runtime values (remote user, KB id, datasource ids, split
size, etc.) from a JSON file instead of CLI flags — see
[README_upload_runtime_config.md](README_upload_runtime_config.md) and
[upload_runtime_config.example.json](upload_runtime_config.example.json).

**Security note:** do not commit real API keys, tokens, or `upload_runtime_config.json`
(only the `.example.json` template should be tracked). The internal proxy IP
hardcoded in some scripts is ST-network-specific — adjust or remove it outside
that network.

## Core / reusable tools

| Script | Purpose |
|---|---|
| [Add_Data_Source_Files.py](Add_Data_Source_Files.py) | Generic CLI: create (`new`), append (`add`), or wipe (`delete`) a KB datasource. Used by every batch script below via subprocess. Handles large-payload splitting, retries, and datasource name-conflict reuse. |
| [Get_Persona_KBs.py](Get_Persona_KBs.py) | Lists KBs attached to the persona; also acts as the legacy source of `clientAppName`/`apiKey`/`proxies`/`generate_token()` imported by other scripts. |
| [Chat_With_Persona_KB.py](Chat_With_Persona_KB.py) | Sends a question to the persona's chat endpoint to manually verify KB answers after an upload. |
| [create_missing_resolver_datasources.py](create_missing_resolver_datasources.py) | One-off helper to (re)create the U5/WL resolver_cases datasources. |

## Series-specific batch uploaders

| Script | Series / kind | Target datasource |
|---|---|---|
| [upload_f4_files_datasource.py](upload_f4_files_datasource.py) | F4 files (main + drivers) | #28103 |
| [upload_f4_files_main_only.py](upload_f4_files_main_only.py) | F4 files (main repo only) | #28103 |
| [upload_f4_resolver_datasource.py](upload_f4_resolver_datasource.py) | F4 resolver_cases | #28118 |
| [upload_f4_diagnostic_datasource.py](upload_f4_diagnostic_datasource.py) | F4 diagnostic_cards | #28122 |
| [upload_h5_files_datasource.py](upload_h5_files_datasource.py) | H5 files (main + drivers) | #28163 |
| [upload_h5_issues_datasource.py](upload_h5_issues_datasource.py) | H5 issues (main + drivers) | #28158 |
| [upload_h5_resolver_datasource.py](upload_h5_resolver_datasource.py) | H5 resolver_cases | #28164 |
| [upload_h5_diagnostic_datasource.py](upload_h5_diagnostic_datasource.py) | H5 diagnostic_cards | #28165 |
| [upload_u5_all_datasources.py](upload_u5_all_datasources.py) | U5 issues/files/resolver_cases/diagnostic_cards | creates all 4 |
| [upload_wl_all_datasources.py](upload_wl_all_datasources.py) | WL issues/files/resolver_cases/diagnostic_cards | creates all 4 |
| [upload_alfred_issues_all_series.py](upload_alfred_issues_all_series.py) | All series, Alfred-enriched issues | reuses existing per-series issues datasources |
| [upload_pdf_enriched_files_all_series.py](upload_pdf_enriched_files_all_series.py) | All series, PDF/image-enriched files | reuses existing per-series files datasources |

Most series scripts accept `--remote-user`, `--dry-run`, and `--verbose`; several
hardcode a default `--remote-user` value that should be updated for your own
ST account. Run any script with `-h` for its exact CLI options.

## Typical flow

1. Run `pipeline/delivery` exports to produce `datasets/07_delivery/st_ready/**`.
2. Run the relevant series batch script (or `Add_Data_Source_Files.py` directly)
   to upload/append the JSON to the target KB datasource.
3. Use `Chat_With_Persona_KB.py` to sanity-check that the KB now answers correctly.

`Upload_All_Drivers.ps1` and `Upload_STReady_New_Batch.ps1` (PowerShell) wrap
these Python tools for batch/CI use — see
[pipeline_Automation/workflow](../workflow/README.md) for the higher-level
automation scripts that call into this folder.
