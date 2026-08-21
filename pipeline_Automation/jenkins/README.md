# Jenkins — CI Automation

[Jenkinsfile_GitHubArtifactsToKB.groovy](Jenkinsfile_GitHubArtifactsToKB.groovy)
is a declarative Jenkins pipeline that automates running the full STM32Cube
preprocessing workflow and uploading results to the ST AI Bridge knowledge
base (KB), on a schedule.

## What it does

- **Trigger:** cron schedule (`H 3 1,15 * *` — twice a month, around 3 AM).
- **Parameters:**
  - `SERIES` — comma-separated list of STM32Cube series to process (e.g. `G4,L0,L1,...`).
  - `MODE` — `Full` (run pipeline + upload), `Prepare` (pipeline only), or `Upload` (upload only).
  - `EXISTING_DATASOURCE_MODE` — `Replace` or `Add` files on an already-existing KB datasource.
  - `PLACEHOLDER_POLICY` — how to handle unresolved Alfred image placeholders (`Fail`/`Warn`/`Off`).
  - `KB_ID` — target Knowledge Base id (default `793`).
  - `JSON_SPLIT_SIZE` — max documents per uploaded JSON part (default `1000`).
  - `PYTHON_EXE` — optional explicit Python interpreter path (defaults to auto-detecting `.venv`).
  - `SKIP_DRIVERS` / `SKIP_SCHEMA_VALIDATION` / `CONTINUE_ON_WORKFLOW_ERROR` /
    `CONTINUE_ON_SERIES_FAILURE` — resilience/skip toggles for partial or best-effort runs.
- **Behavior:** builds are single-concurrency (`disableConcurrentBuilds()`) and
  the last 30 builds are kept (`logRotator`).

## Relationship to the rest of the repo

This Jenkinsfile is the CI equivalent of manually running
[pipeline_Automation/workflow/run_all_series.py](../workflow/README.md) followed
by the relevant [pipeline_Automation/upload](../upload/README.md) scripts — it
exists so the pipeline + upload can run unattended on a recurring schedule
instead of being triggered by hand.
