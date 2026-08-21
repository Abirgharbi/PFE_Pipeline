# Self-Hosted Runner Supervisor Checklist (STM32Cube KB Automation)

This checklist is intended for supervisor validation on a fresh machine.

## 1) Scope

Applies to these workflows:
- `.github/workflows/manual_auto_update_kb.yml`
- `.github/workflows/auto_update_kb.yml`

## 2) Machine prerequisites

1. Windows 10/11 or Windows Server with stable internet.
2. Git installed.
3. Python 3.12+ installed.
4. Runner machine must not sleep/hibernate.
5. At least 20-30 GB free disk space.
6. Outbound network allowed to:
   - `github.com`
   - `api.github.com`
   - `objects.githubusercontent.com`
   - `api-ai-bridge.st.com`

## 3) Register self-hosted runner

1. Repository Settings -> Actions -> Runners -> New self-hosted runner.
2. Choose Windows x64 and run provided commands.
3. Install runner as a service and start it.
4. Confirm runner appears online in repository UI.

## 4) Required repository secrets (current workflows)

Add these in Repository Settings -> Secrets and variables -> Actions.

### Mandatory

1. `RUNNER_CHECK_TOKEN`
- Purpose: used by runner availability API check.
- Used in:
  - `.github/workflows/manual_auto_update_kb.yml`
  - `.github/workflows/auto_update_kb.yml`

2. One Alfred API key secret (at least one must be present)
- `ST_CHATGPT_API_KEY` (recommended)
- or `ST_AI_BRIDGE_API_KEY`
- or `ST_API_KEY`
- Purpose: Alfred image/PDF enrichment before upload.
- Used in:
  - `.github/workflows/manual_auto_update_kb.yml`
  - `.github/workflows/auto_update_kb.yml`
  - `pipeline_Automation/alfred/enrich_pdf_figures_with_alfred.py`
  - `pipeline_Automation/alfred/enrich_json_images_with_alfred.py`

### Optional but recommended for manual/local scripts

1. `ST_GITHUB_ANALYZER_API_KEY`
2. `PERSONA_API_KEY`
3. `ST_CHATGPT_CLIENT_APP`
4. `ST_CLIENT_APP_NAME`

Used mainly by:
- `pipeline_Automation/upload/Add_Data_Source_Files.py`
- `pipeline_Automation/upload/Get_Persona_KBs.py`

## 5) Confidential values policy

1. Never commit secret values in code or JSON configs.
2. Never store secret values in workflow_dispatch inputs.
3. Use GitHub repository secrets only.
4. Rotate tokens periodically and after any exposure.

## 6) Minimum token guidance for RUNNER_CHECK_TOKEN

For a fine-grained PAT:
1. Token bound to this repository.
2. Repository Actions read permissions sufficient to list runners.
3. If 403 persists in runner-check summary, increase repo-level read permission for actions metadata.

## 7) Runner service hardening

1. Configure runner as Windows service.
2. Exclude runner work directory from aggressive antivirus scanning.
3. Keep runner app up-to-date.
4. Enable long paths once:
   - `git config --system core.longpaths true`

## 8) Validation sequence for supervisor

1. Run Manual Auto Update KB with one small series in Full mode.
2. Verify job order:
   - Prepare matrix inputs
   - Check self-hosted runner availability
   - Preprocess <Series>
   - Upload <Series>
3. Check runner summary metrics:
   - runner_ready true
   - online_count > 0
   - idle_count > 0 (or workflow continues if fallback note appears)
4. Check Alfred preflight passes:
   - Alfred API key detected in workflow env.
5. Verify upload completed and datasource response returned.

## 9) Fast troubleshooting map

1. Runner API note shows `http_status_403...`
- Check `RUNNER_CHECK_TOKEN` exists and has proper repo scope.

2. Error says missing Alfred API key
- Add at least one secret:
  - `ST_CHATGPT_API_KEY`
  - `ST_AI_BRIDGE_API_KEY`
  - `ST_API_KEY`

3. Checkout fetch fails with missing git object / parse commit
- Corrupted runner workspace.
- Restart runner service and clean runner work directory.

4. Self-hosted runner lost communication
- Check service health, machine sleep settings, RAM/CPU pressure, and network stability.

## 10) Important current behavior note

`Upload` mode uploads pre-generated ST-ready artifacts. If artifacts were not prepared in the same run (or not available to upload job), prefer `Full` mode for reliable supervisor testing.
