# GitHub Actions Automation - PPTX Pack

Use this file as direct copy/paste content into PowerPoint.

---

## Slide 1 - Title

### Title
GitHub Actions Automation for STM32Cube KB Update

### Subtitle
How auto_update_kb.yml orchestrates full preprocessing and upload to KB #793

### Footer
STMicroelectronics - Support & Maintenance - 2026

### Speaker Notes (20-30s)
This automation keeps our Knowledge Base continuously updated. It is triggered on schedule or manually, and it executes a controlled per-series pipeline including preprocessing, validation, and upload.

---

## Slide 2 - End-to-End Flow

### Title
End-to-End Execution Flow

### Content (diagram)
```mermaid
flowchart LR
    A[Trigger\nSchedule or Manual] --> B[Prepare Job\nubuntu-latest]
    B --> C[Normalize Inputs\nValidate series list]
    C --> D[Matrix Build\nOne job per series]
    D --> E[Run-Series Job\nself-hosted Windows]
    E --> F[PowerShell Orchestrator\nRun_Single_Series_Full_Pipeline_And_Upload.ps1]
    F --> G[Delivery + Upload\nKB #793]
    G --> H[Artifacts + Summary]
```

### Speaker Notes (35-45s)
We split responsibilities into two jobs. Prepare normalizes and validates runtime parameters. Run-series executes the real work on self-hosted runner per selected series, then stores artifacts and summary for traceability.

---

## Slide 3 - What Is Inside the yml

### Title
auto_update_kb.yml - Main Sections

### Content
- Trigger block (`on`):
  - schedule: `0 3 1,15 * *`
  - workflow_dispatch with runtime inputs
- Control block:
  - `permissions: contents: read`
  - `concurrency` group to avoid overlapping runs
- Defaults block (`env`):
  - Python version, default series, default mode/policy
- Jobs:
  - `prepare` (input normalization + matrix generation)
  - `run-series` (actual execution on self-hosted)

### Speaker Notes (30-40s)
The file is intentionally structured: trigger and control on top, runtime defaults in env, then two jobs with clear separation. This gives predictable behavior for both scheduled and manual runs.

---

## Slide 4 - Manual Inputs and Their Effect

### Title
Manual Inputs - Runtime Controls

### Content (table)
| Input | Values | Effect |
|---|---|---|
| `series` | CSV list | Select target MCU series |
| `mode` | `Full` / `Prepare` / `Upload` | Choose full run or partial stage |
| `existing_datasource_mode` | `Replace` / `Add` | Existing datasource behavior on conflict |
| `skip_drivers` | true/false | Disable subrepo driver uploads |
| `skip_schema_validation` | true/false | Bypass schema gate |
| `continue_on_workflow_error` | true/false | Continue internal workflow on one-repo failure |
| `placeholder_policy` | `Fail` / `Warn` / `Off` | Gate unresolved Alfred placeholders |
| `max_parallel` | integer | Matrix concurrency limit |

### Speaker Notes (35-45s)
Inputs map directly to script flags. This allows safe smoke tests first, then full production runs with strict gates.

---

## Slide 5 - Series Execution Detail

### Title
Per-Series Execution (run-series job)

### Content
1. Checkout repository
2. Enable Windows long paths
3. Setup Python 3.12 + pip cache
4. Install dependencies (`pip install -r requirements.txt`)
5. Run script:
   - `Run_Single_Series_Full_Pipeline_And_Upload.ps1`
   - with matrix series + selected options
6. Upload artifacts (always)
7. Publish run summary (always)

### Speaker Notes (30-40s)
The `always()` pattern for artifact and summary steps guarantees diagnostics even when execution fails. This is important for support/maintenance operations.

---

## Slide 6 - Reliability and Governance

### Title
Reliability, Gates, and Traceability

### Content
- Validation gates:
  - schema validation
  - placeholder policy gate
- Matrix strategy:
  - `fail-fast: false` to isolate failures per series
- Concurrency:
  - one workflow group per ref
- Traceability:
  - per-series artifact (`st-ready-<SERIES>-<RUN_NUMBER>`)
  - GitHub step summary with effective parameters

### Speaker Notes (35-45s)
We prioritize controlled operation: failures are isolated, outputs are archived, and each run remains auditable with parameters and artifacts.

---

## Slide 7 - Runbook for Operators

### Title
Operational Runbook (Quick)

### Content
1. Ensure self-hosted runner is online
2. Confirm secrets:
   - `ST_CHATGPT_API_KEY`
   - `ST_REMOTE_USER`
3. Run smoke test:
   - `series=G4`, `mode=Prepare`, `max_parallel=1`
4. Promote to production run:
   - `mode=Full`, target series set
5. Verify:
   - job success status
   - artifacts uploaded
   - summary includes expected options

### Speaker Notes (30-40s)
Start small with Prepare mode, then move to Full when checks are green. This reduces production risk.

---

## Slide 8 - Key Files

### Title
Reference Files

### Content
- Workflow:
  - .github/workflows/auto_update_kb.yml
- Main script:
  - pipeline_Automation/workflow/Run_Single_Series_Full_Pipeline_And_Upload.ps1
- Detailed technical guide:
  - docs/automation_kb_update.md
- Short presentation guide:
  - docs/automation_kb_update_presentation.md

### Speaker Notes (15-20s)
These four files are enough to understand, run, and maintain the automation.

---

## Optional 2-Minute Version (for short meetings)

- Slide 1 (Title)
- Slide 2 (Flow)
- Slide 4 (Inputs)
- Slide 6 (Reliability)
- Slide 7 (Runbook)
