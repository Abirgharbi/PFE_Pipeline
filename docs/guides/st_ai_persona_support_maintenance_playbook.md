# ST AI Persona Support and Maintenance Playbook

Version: 1.0

Audience: Support and Maintenance team, project stakeholders, and technical reviewers.

Scope: End-to-end STM32Cube preprocessing workflow, ST-ready delivery exports, upload operations, and quality governance in a black-box retrieval environment.

Académique :
Conception et évaluation d’une chaîne de prétraitement STM32Cube pour l’alimentation d’un assistant IA technique

Impact métier :
Amélioration de la qualité des réponses d’une IA support STM32 par structuration et livraison ST-ready des données techniques

Orienté architecture :
De GitHub à la knowledge base : architecture de prétraitement STM32Cube pour un assistant IA de support et maintenance

Orienté qualité :
Prétraitement intelligent STM32Cube et gouvernance qualité (30Q/50Q) pour une IA de support industriel

---

## 1. Executive Summary

This project transforms heterogeneous STM32Cube sources (issues, PRs, commits, repository files, release notes, examples) into structured and upload-ready knowledge artifacts for ST AI persona usage.

The value delivered is not only data conversion. The pipeline adds:

- Technical normalization and enrichment (board, component, severity, issue kind, layer).
- Retrieval-oriented packaging with stable templates.
- Traceable resolver and diagnostic artifacts linked to issue and code evidence.
- Repeatable quality control before and after upload.
- Operational scripts for batch upload, manual split strategy, and recurring benchmark campaigns.

Concrete impact already visible:

- 30Q benchmark showed global gain when adding files_json to issues_json.
- H7 files payload reached 4707 exported docs (from 4733 source docs), enabling documentation-aware answers.
- Manual split workflow provides deterministic upload strategy for heavy payloads.

Primary references:

- [pipeline/run_full_workflow.py](../pipeline/run_full_workflow.py)
- [pipeline/delivery/export_st_ready_issues.py](../pipeline/delivery/export_st_ready_issues.py)
- [pipeline/delivery/export_st_ready_files.py](../pipeline/delivery/export_st_ready_files.py)
- [pipeline/delivery/export_st_ready_resolver_cases.py](../pipeline/delivery/export_st_ready_resolver_cases.py)
- [pipeline/delivery/export_st_ready_diagnostic_cards.py](../pipeline/delivery/export_st_ready_diagnostic_cards.py)
- [pipeline_Automation/Add_Data_Source_Files.py](../pipeline_Automation/Add_Data_Source_Files.py)
- [pipeline_Automation/Upload_STReady_New_Batch.ps1](../pipeline_Automation/Upload_STReady_New_Batch.ps1)

---

## 2. Overview of the Project

### 2.1 Business objective

Build a robust and maintainable knowledge preparation layer that improves relevance, traceability, and actionability of AI persona answers on STM32Cube technical topics.

### 2.2 Technical objective

Produce consistent artifacts through a 7-stage flow:

1. Ingestion
2. Cleaning
3. Enrichment
4. Similarity
5. Chunking (optional consumer side)
6. Evaluation
7. Delivery (ST-ready)

### 2.3 Source of truth

Active code paths are under:

- [pipeline/ingestion](../pipeline/ingestion)
- [pipeline/cleaning](../pipeline/cleaning)
- [pipeline/enrichment](../pipeline/enrichment)
- [pipeline/similarity](../pipeline/similarity)
- [pipeline/chunking](../pipeline/chunking)
- [pipeline/evaluation](../pipeline/evaluation)
- [pipeline/delivery](../pipeline/delivery)
- [shared/config](../shared/config)
- [shared/schemas](../shared/schemas)

The legacy src layout is not the active execution baseline.

---

## 3. Overview of the ST AI Persona Solution

### 3.1 Positioning

The persona answer quality depends on three layers:

1. Data quality and structure before upload.
2. Upload contract quality (processor, rootTagPath, stable fields).
3. Runtime answer behavior (guardrails, confidence, evidence usage).

### 3.2 Black-box constraint

Because retrieval/ranking internals are outside project control, improvements must be durable and data-centric:

- Better lexical anchors and metadata.
- Stable structured card templates.
- Explicit evidence fields and confidence policy.
- Repeatable benchmark and drift detection.

This is the core support strategy when direct ranking tuning is unavailable.

---

## 4. Overview of Knowledge Base Construction Process

### 4.1 End-to-end pipeline

High-level flow:

- Raw acquisition from GitHub API and local repos.
- Text normalization and file typing.
- Issue and file enrichment to docs_v2.
- Optional issue similarity links.
- Optional chunk generation.
- Evaluation and schema checks.
- ST-ready export generation.

Main orchestrator:

- [pipeline/run_full_workflow.py](../pipeline/run_full_workflow.py)

Full workflow command:

```bash
python -m pipeline.run_full_workflow --export-st-ready
```

### 4.2 Ingestion details

Issues, PRs, commits, and link extraction:

- [pipeline/ingestion/fetch_issues.py](../pipeline/ingestion/fetch_issues.py)
- [pipeline/ingestion/fetch_prs.py](../pipeline/ingestion/fetch_prs.py)
- [pipeline/ingestion/fetch_commits.py](../pipeline/ingestion/fetch_commits.py)
- [pipeline/ingestion/fetch_issue_pr_commit_links.py](../pipeline/ingestion/fetch_issue_pr_commit_links.py)

Files from local clone:

- [pipeline/ingestion/fetch_files.py](../pipeline/ingestion/fetch_files.py)
- [pipeline/ingestion/file_collect_service.py](../pipeline/ingestion/file_collect_service.py)

Important implemented behavior:

- github_url is generated at file ingestion level with stable blob URL building.

### 4.3 Cleaning and enrichment

- [pipeline/cleaning/clean_files.py](../pipeline/cleaning/clean_files.py) keeps github_url and extraction metadata.
- [pipeline/enrichment/preprocessing_model.py](../pipeline/enrichment/preprocessing_model.py) adds fallback github_url construction if needed.

### 4.4 Evaluation gates

- [pipeline/evaluation/test_stats_issues_v2.py](../pipeline/evaluation/test_stats_issues_v2.py)
- [pipeline/evaluation/test_stats_files_v2.py](../pipeline/evaluation/test_stats_files_v2.py)
- [pipeline/evaluation/test_tfidf_search_issues_v2.py](../pipeline/evaluation/test_tfidf_search_issues_v2.py)
- [pipeline/evaluation/test_tfidf_search_files_v2.py](../pipeline/evaluation/test_tfidf_search_files_v2.py)
- [pipeline/evaluation/validate_schemas.py](../pipeline/evaluation/validate_schemas.py)

---

## 5. ST-ready Export Families (Delivery Layer)

Generated under:

- [datasets/07_delivery/st_ready](../datasets/07_delivery/st_ready)

### 5.1 issues_json

- File pattern: st_ready_issues_<repo>.json
- Root object key: issues
- Script: [pipeline/delivery/export_st_ready_issues.py](../pipeline/delivery/export_st_ready_issues.py)

Core fields:

- id, repo, issue_number, issue_title, state
- layer, component, issue_kind, severity, board
- evidence_strength, rescue_applied, github_url
- delivery_template = st_v2_structured_issue_card
- st_ready_text with fixed sections (Problem, Context, Root cause, Fix, Constraints, Keywords, Technical details)

### 5.2 files_json

- File pattern: st_ready_files_<repo>.json
- Root object key: files
- Script: [pipeline/delivery/export_st_ready_files.py](../pipeline/delivery/export_st_ready_files.py)

Core fields:

- id, repo, path, path_url, file_type
- board, component, category, example_name
- github_url, image metadata, extractor metadata
- delivery_template = st_v2_structured_file_card
- st_ready_text with context + technical details

### 5.3 resolver_cases_json

- File pattern: st_ready_resolver_cases_<repo>.json
- Root object key: resolver_cases
- Script: [pipeline/delivery/export_st_ready_resolver_cases.py](../pipeline/delivery/export_st_ready_resolver_cases.py)

Core fields:

- issue + PR + commit linkage
- resolution_status, link_confidence, link_score
- resolver_card_text
- files_evidence with changed files and matching status to files docs
- impacted modules/components/boards/file types

### 5.4 diagnostic_cards_json

- File pattern: st_ready_diagnostic_cards_<repo>.json
- Root format: JSON array (not object wrapper)
- Script: [pipeline/delivery/export_st_ready_diagnostic_cards.py](../pipeline/delivery/export_st_ready_diagnostic_cards.py)

Core fields:

- symptom_summary, likely_causes, confirmed_facts
- plausible_diagnosis, debug_checks, possible_workarounds
- constraints_or_limits, evidence_refs
- query_aliases, technical_pattern_tags, api_family_tags, keywords
- st_ready_text synthesis block for downstream retrieval

### 5.5 Delivery traceability

Each export writes summary_*.json metadata with input/output paths and counts.

Example snapshots (STM32CubeH7):

- issues exported: 264 / 296
  - [datasets/07_delivery/st_ready/issues_json/summary_stm32cubeh7.json](../datasets/07_delivery/st_ready/issues_json/summary_stm32cubeh7.json)
- files exported: 4707 / 4733
  - [datasets/07_delivery/st_ready/files_json/summary_files_stm32cubeh7.json](../datasets/07_delivery/st_ready/files_json/summary_files_stm32cubeh7.json)
- resolver cases exported: 4
  - [datasets/07_delivery/st_ready/resolver_cases_json/summary_resolver_cases_stm32cubeh7.json](../datasets/07_delivery/st_ready/resolver_cases_json/summary_resolver_cases_stm32cubeh7.json)
- diagnostic cards exported: 45
  - [datasets/07_delivery/st_ready/diagnostic_cards_json/summary_diagnostic_cards_stm32cubeh7.json](../datasets/07_delivery/st_ready/diagnostic_cards_json/summary_diagnostic_cards_stm32cubeh7.json)

---

## 6. Resolver Cases: Utility, Limits, and Score Logic

### 6.1 Why resolver cases matter

Resolver cases convert issue-PR-commit linkage into support-usable evidence cards.

They are useful for:

- Avoiding unsupported "fixed" claims.
- Showing confidence level per linkage.
- Guiding engineers to likely patch files and upstream evidence.

### 6.2 Resolver score equation

Source function:

- [pipeline/ingestion/fetch_issue_pr_commit_links.py](../pipeline/ingestion/fetch_issue_pr_commit_links.py)

Rule:

- +0.5 if at least one explicit linked PR
- +0.3 if at least one linked merged PR
- else +0.1 if explicit PR exists but no merged PR
- +0.2 if at least one meaningful linked commit
- score capped to 1.0

Confidence mapping:

- high if score >= 0.9
- medium if score >= 0.5
- low if score > 0
- none if score = 0

Resolution status mapping:

- merged_fix: merged PR + meaningful commit
- candidate_fix: explicit PR + meaningful commit
- reference_only: explicit PR only
- unlinked: no actionable linkage

### 6.3 Practical known limitations

- candidate_fix can still be unconfirmed for all boards and versions.
- changed file list can remain commit_only if no exact path match in files docs.
- status can be correct while applicability is still board/version dependent.

Support policy:

- Treat candidate_fix as probable, not guaranteed.
- Keep explicit validation constraints in final answer.

---

## 7. Diagnostic Cards: Utility, Observed Issues, and Fix Axes

### 7.1 Why diagnostic cards matter

Diagnostic cards are synthesis objects for troubleshooting answers.

They combine:

- rescued issue signal
- resolver evidence
- pattern tags
- generated checks and workarounds

### 7.2 Card generation logic

Main generator:

- [pipeline/delivery/export_st_ready_diagnostic_cards.py](../pipeline/delivery/export_st_ready_diagnostic_cards.py)

Key mechanisms:

- Pattern extraction from issue/resolver text (timeout, dma_path, callback_not_reached, etc).
- API anchor extraction (HAL_*, LL_*, BSP_*, MX_*, CMSIS_*).
- Query alias generation for known lexical forms.
- Evidence refs from issue/PR/commit URLs.

### 7.3 Observed quality issues in current cards

From generated outputs, typical weak points include:

- Some cards have empty query_aliases.
- Some likely_causes keep conversational noise.
- Some symptom_summary entries are too generic.

Relevant sample file:

- [datasets/07_delivery/st_ready/diagnostic_cards_json/st_ready_diagnostic_cards_stm32cubeh7.json](../datasets/07_delivery/st_ready/diagnostic_cards_json/st_ready_diagnostic_cards_stm32cubeh7.json)

### 7.4 Durable corrective actions

- Strengthen conversational-noise filtering for root cause lines.
- Enforce minimum alias density for high-value peripherals.
- Add mandatory anchor injection for common user phrasings (blocking function, callback not reached, bus-off, etc).
- Add card-level validation rules before export.

---

## 8. Upload Best Practices Before API Call

### 8.1 Data pre-check checklist

1. Verify root JSON shape expected by each datasource.
2. Verify summary_*.json count coherence with payload size.
3. Verify resolver/diagnostic cards include evidence_refs and useful anchors.
4. Verify github_url coverage for files and issues.
5. Filter invalid docs unless explicitly needed.

### 8.2 Operational pre-check checklist

1. Confirm KB ID and datasource IDs.
2. Confirm remote-user is a valid corporate email.
3. Confirm processor is JSON with correct rootTagPath.
4. Confirm link templates are valid and not URL-broken.
5. Run auth precheck before heavy upload.

### 8.3 Never-do list

- Do not upload files_json under STANDARD processor.
- Do not use wrong rootTagPath key.
- Do not rely on unresolved datasource state after delete; backend can mark datasource as deleted.
- Do not treat candidate_fix as merged_fix in final user answer.

---

## 9. API Specs and Accepted Structures (Uploader Contract)

Primary uploader:

- [pipeline_Automation/Add_Data_Source_Files.py](../pipeline_Automation/Add_Data_Source_Files.py)

Batch wrapper:

- [pipeline_Automation/Upload_STReady_New_Batch.ps1](../pipeline_Automation/Upload_STReady_New_Batch.ps1)

### 9.1 Supported operations

- add: upload to existing datasource id
- new: create datasource then upload
- delete: delete datasource files / datasource entry handling path

### 9.2 Processor contract

Supported processors:

- PDF, JSON, CSV, STANDARD

For this project, JSON is required for ST-ready payload families.

### 9.3 JSON root behavior

When processor JSON and json-root-mode auto are used:

- Accepts array root directly.
- Accepts object root with one array key and can flatten.
- Accepts object root with multiple keys only when one key can be selected (preferred keys include diagnostic_cards, resolver_cases, issues, files, etc).
- Can normalize array into object with rootTagPath when needed.

If rootTagPath is provided and does not match payload key, upload is blocked before API call.

### 9.4 Empty payload policies

Supported policies:

- skip (default): ignore empty arrays
- upload: send anyway
- fail: abort process

### 9.5 Request payload modes

Supported modes:

- flat (recommended default)
- wrapped
- wrapped-json-part

### 9.6 Retry and conflict handling

Implemented protections include:

- retry on transient HTTP and API error patterns.
- skip existing files in add mode unless strict mode requested.
- handle datasource name conflict by resolving existing datasource id from kb-list.

---

## 10. Why Files JSON Split Exists (and Why 50 Parts)

### 10.1 Problem statement

Some files_json payloads are very large for upload and indexing stability.

Example (STM32CubeH7):

- source docs: 4707
- source payload size: about 57.6 MB

See:

- [datasets/07_delivery/st_ready/manual_upload/files_json_split_tuned/summary_manual_split_files_json.json](../datasets/07_delivery/st_ready/manual_upload/files_json_split_tuned/summary_manual_split_files_json.json)

### 10.2 Split strategy options

Default split strategy:

- Max docs per part and optional payload size cap.
- Good for strict payload control.
- Can produce many parts (example manifest shows very high part counts).

Tuned split strategy for manual operation:

- target-parts 50
- max-payload-kb 0
- split-all enabled

This improves operational handling by reducing part explosion and preserving upload rhythm.

### 10.3 Manual split scripts

- [pipeline_Automation/Prepare_Manual_Files_Splits.ps1](../pipeline_Automation/Prepare_Manual_Files_Splits.ps1)
- [pipeline_Automation/Prepare_Manual_Files_Splits_STM32CubeH7_50Parts.ps1](../pipeline_Automation/Prepare_Manual_Files_Splits_STM32CubeH7_50Parts.ps1)
- [pipeline/delivery/split_st_ready_files_for_manual_upload.py](../pipeline/delivery/split_st_ready_files_for_manual_upload.py)

### 10.4 Manual upload folder policy

Reference:

- [datasets/07_delivery/st_ready/manual_upload/README.md](../datasets/07_delivery/st_ready/manual_upload/README.md)

Key settings for files datasource:

- rootTagPath = files
- Link URL template = {{github_url}}
- Link label template = {{path}}

Upload order is part001, part002, ..., with per-source summary and global manifest retained for traceability.

---

## 11. Full Automation Process

The operational process uses GitHub Actions for cloud execution and PowerShell scripts for local fallback.

### 11.1 Pipeline run

```bash
python -m pipeline.run_full_workflow --export-st-ready
```

Common options:

```bash
python -m pipeline.run_full_workflow --skip-ingestion --continue-on-error --export-st-ready
```

### 11.2 Issues-only refresh + export

```powershell
./pipeline_Automation/Run_Issues_Pipeline_For_All_Repos.ps1 -WithSimilarity -WithChunking
```

### 11.3 Diagnostic cards refresh

```powershell
./pipeline_Automation/Generate_Diagnostic_Cards_For_All_Repos.ps1
```

### 11.4 Manual files split prep

```powershell
./pipeline_Automation/Prepare_Manual_Files_Splits.ps1 -CleanOutput
```

H7 tuned 50 parts:

```powershell
./pipeline_Automation/Prepare_Manual_Files_Splits_STM32CubeH7_50Parts.ps1
```

### 11.5 Batch upload (all ST-ready families)

```powershell
./pipeline_Automation/Upload_STReady_New_Batch.ps1 -RemoteUser your.name@st.com -Operation add
```

Typical production usage:

- Add mode for stable existing datasources.
- New mode for clean rebuild or after delete behavior.
- Optional delete for files datasource with recreate strategy handled by script logic.

---

## 12. Test Methodology Before ST Quality Index

### 12.1 Gate 1: Stats quality

Run:

```bash
python -m pipeline.evaluation.test_stats_issues_v2
python -m pipeline.evaluation.test_stats_files_v2
```

Objective:

- detect major distribution anomalies
- validate metadata coverage

### 12.2 Gate 2: Retrieval smoke test (TF-IDF)

Run:

```bash
python -m pipeline.evaluation.test_tfidf_search_issues_v2
python -m pipeline.evaluation.test_tfidf_search_files_v2
```

Objective:

- verify lexical retrievability and anchor preservation before runtime upload.

### 12.3 Gate 3: Schema validation

Run:

```bash
python -m pipeline.evaluation.validate_schemas
```

Objective:

- ensure core docs/chunks contract consistency before delivery stage.

### 12.4 Gate 4: 30Q A/B campaign

References:

- [datasets/06_eval_outputs/h7_eval_30q_questions.md](../datasets/06_eval_outputs/h7_eval_30q_questions.md)
- [datasets/06_eval_outputs/h7_eval_30q_scored_summary.csv](../datasets/06_eval_outputs/h7_eval_30q_scored_summary.csv)

Observed result snapshot:

- issues_only global avg total_0_to_7: 2.93
- issues_plus_files global avg total_0_to_7: 5.33

Interpretation:

- files_json addition strongly improves files and mixed question blocks.
- some mixed regressions remain and require targeted corrective cards and alias hardening.

---

## 13. Recurring 50Q ST Quality Index Process

### 13.1 Why recurring 50Q

The 50Q suite is a stability monitor for real support behavior across:

- peripheral diagnosis
- uncertainty handling
- evidence discipline
- policy compliance under ambiguity

### 13.2 Assets

- [datasets/07_delivery/st_ready/h7_test_suite_excel_ready.csv](../datasets/07_delivery/st_ready/h7_test_suite_excel_ready.csv)
- [datasets/07_delivery/st_ready/h7_test_suite_persona_50q_excel_ready.csv](../datasets/07_delivery/st_ready/h7_test_suite_persona_50q_excel_ready.csv)
- [datasets/07_delivery/st_ready/run_h7_50q_ab_test.ps1](../datasets/07_delivery/st_ready/run_h7_50q_ab_test.ps1)
- [docs/st_quality_50q_corrective_plan.md](st_quality_50q_corrective_plan.md)

### 13.3 Execution baseline

```powershell
./datasets/07_delivery/st_ready/run_h7_50q_ab_test.ps1
```

Outputs are stored in:

- [datasets/06_eval_outputs](../datasets/06_eval_outputs)

### 13.4 Review and scoring policy

Use scoring dimensions defined in A/B protocol:

- top-1 correctness
- technical precision
- source relevance
- hallucination risk (inverse scoring)
- actionability

Reference:

- [docs/st_kb_ab_test_protocol.md](st_kb_ab_test_protocol.md)

### 13.5 Corrective thresholds

Current corrective plan target:

- P0 questions must reach >= 70
- Q44/Q45/Q46/Q48 must reach >= 80
- no zero score across full 50Q run

### 13.6 Suggested cadence

- Weekly 50Q for active tuning phases.
- Bi-weekly 50Q for stabilized phases.
- Mandatory 50Q before major datasource refresh.

### 13.7 Offline vs Online (ST Quality Index) difference

The ST Quality Index online tool evaluates question quality from an uploaded spreadsheet and returns per-question details.

Typical online input columns:

- Question
- Expected Answer
- Tag

Typical online output behavior:

- score per question (for example 70/100)
- QUESTION #N DETAILS
- textual reason and quality remarks

Important distinction:

- Offline benchmark in this repo uses manual scoring grids (/7 or /9 depending on protocol).
- Online ST Quality Index returns platform scores (/100) with explanation text.

To compare both worlds on the same scale:

- offline_norm_0_to_100 = (offline_total_0_to_7 / 7) * 100
- delta_online_minus_offline = online_score_0_to_100 - offline_norm_0_to_100

Automation script available:

- [pipeline/evaluation/compare_offline_online_quality.py](../pipeline/evaluation/compare_offline_online_quality.py)

Run:

```bash
python -m pipeline.evaluation.compare_offline_online_quality
```

Generated artifacts:

- [datasets/06_eval_outputs/quality_index_30q_online_scores_template.csv](../datasets/06_eval_outputs/quality_index_30q_online_scores_template.csv)
- [datasets/06_eval_outputs/offline_online_30q_summary.csv](../datasets/06_eval_outputs/offline_online_30q_summary.csv)
- [datasets/06_eval_outputs/offline_online_30q_summary.md](../datasets/06_eval_outputs/offline_online_30q_summary.md)

Interpretation policy for A/B by block:

- Compare A vs B in issues/files/mixed blocks independently.
- Track both offline gain and online gain.
- Promote a change only when online gain confirms offline gain or explains justified divergence.

---

## 14. Correcting in a Black-Box Tool: Practical Strategy

### 14.1 Rule of intervention

Do not patch one answer at a time. Patch generator logic and contracts.

### 14.2 Priority order

1. Data contract correctness (root key, metadata, url fields).
2. Lexical anchor density in cards.
3. Confidence and uncertainty behavior.
4. Split/upload operational reliability.

### 14.3 Typical failure to corrective mapping

- Failure: I DO NOT KNOW on known topic
  - Correction: add alias anchors + evidence refs + broaden diagnostic query_aliases.

- Failure: confident but unsupported claim
  - Correction: enforce merged_fix/candidate_fix policy in answer guidance.

- Failure: wrong source family cited
  - Correction: rebalance issue/file card coverage and ensure file docs are uploaded and indexed.

- Failure: upload accepted but retrieval weak
  - Correction: verify rootTagPath, processor, and payload split strategy; then re-run benchmark.

---

## 15. Documentation of the Two Agents

### 15.1 STM32Cube Preprocessing Agent

Definition:

- [.github/agents/STM32CubePreprocessing.agent.md](../.github/agents/STM32CubePreprocessing.agent.md)

Role:

- Analyze and document pipeline and ST-ready outputs.
- Explain schema, data flow, and quality checks.
- Prioritize durable fixes for retrieval quality.

### 15.2 STM32Cube PDF Vision Agent

Definition:

- [.github/agents/STM32CubePdfVision.agent.md](../.github/agents/STM32CubePdfVision.agent.md)

Role:

- Process extracted PDF images.
- Produce technical textual descriptions.
- Feed image descriptions back into file preprocessing quality.

### 15.3 Supporting skills

- [.github/skills/analyze-stats/SKILL.md](../.github/skills/analyze-stats/SKILL.md)
- [.github/skills/chunking-strategies/SKILL.md](../.github/skills/chunking-strategies/SKILL.md)
- [.github/skills/document-json-schema/SKILL.md](../.github/skills/document-json-schema/SKILL.md)

---

## 16. Presentation-Ready Storyline

This section can be used directly in deck structure.

### 16.1 Slide block A: Overview of the project

Message:

- We built a full preprocessing and delivery chain, not only a dataset export.
- The work is measurable, traceable, and maintainable.

Evidence to show:

- pipeline map
- artifact lineage
- count summaries and benchmark outputs

### 16.2 Slide block B: Overview of ST AI persona solution

Message:

- Value comes from data discipline + operational contract + quality governance.
- Black-box constraints are handled by durable data-side engineering.

Evidence to show:

- upload contract schema
- confidence policy in resolver cards
- recurring quality loop (30Q + 50Q)

### 16.3 Slide block C: Overview of KB construction process

Message:

- ingest -> clean -> enrich -> evaluate -> deliver
- each stage has scripts, outputs, and validation gates

Evidence to show:

- run_full_workflow entrypoint
- summary files for each export family

### 16.4 Slide block D: Short demo

Recommended 6-8 minute demo:

1. Show one issue card + one file card + one resolver case + one diagnostic card.
2. Run one benchmark question where issues+files outperforms issues-only.
3. Show upload-ready split folder and manifest traceability.

### 16.5 Slide block E: Status of work (objective/progress/todo)

Objective:

- Stable and explainable support-grade AI behavior.

Progress:

- Full ST-ready exports implemented.
- Files github_url propagation fixed.
- 30Q benchmark framework and scored outputs available.
- 50Q corrective plan established.

Todo:

- Improve diagnostic alias density.
- Reduce conversational noise in generated causes.
- Keep recurring 50Q governance with acceptance thresholds.

### 16.6 Slide block F: Q and A

Recommended Q and A strategy:

- Lead with evidence paths, not assumptions.
- Separate confirmed facts from plausible diagnosis.
- Always mention confidence and constraints.

---

## 17. Support and Maintenance Operating Model

### 17.1 Weekly operating cycle

1. Pull latest sources and rerun selected pipeline stages.
2. Run quality gates (stats, tfidf smoke, schema).
3. Export ST-ready families.
4. Run 30Q spot-check or full 50Q based on release risk.
5. Upload with traceability manifest.
6. Archive outputs and decision notes.

### 17.2 Incident response for answer quality regression

1. Classify failure type (coverage, confidence, evidence, format).
2. Identify affected family (issues/files/resolver/diagnostic).
3. Patch generator logic (not one-off content).
4. Re-run targeted benchmark subset first.
5. Validate full suite before deployment.

### 17.3 Minimum evidence bundle per release

- summary files for all four export families
- upload command log
- split manifest (if manual split used)
- benchmark scored CSV and change notes

---

## 18. Appendix: Core Commands

### 18.1 Full workflow + delivery

```bash
python -m pipeline.run_full_workflow --export-st-ready
```

### 18.2 Targeted delivery exports

```bash
python -m pipeline.delivery.export_st_ready_issues --repo STM32CubeH7
python -m pipeline.delivery.export_st_ready_files --repo STM32CubeH7
python -m pipeline.delivery.export_st_ready_resolver_cases --repo STM32CubeH7
python -m pipeline.delivery.export_st_ready_diagnostic_cards --repo STM32CubeH7
```

### 18.3 Manual files split

```powershell
./pipeline_Automation/Prepare_Manual_Files_Splits.ps1 -CleanOutput
./pipeline_Automation/Prepare_Manual_Files_Splits_STM32CubeH7_50Parts.ps1
```

### 18.4 Batch upload

```powershell
./pipeline_Automation/Upload_STReady_New_Batch.ps1 -RemoteUser your.name@st.com -Operation add
```

### 18.5 Evaluation

```bash
python -m pipeline.evaluation.test_stats_issues_v2
python -m pipeline.evaluation.test_stats_files_v2
python -m pipeline.evaluation.validate_schemas
```

---

## 19. Closing Statement

This repository now supports a complete support-grade lifecycle:

- technical data preparation,
- delivery contract control,
- operational upload process,
- and continuous quality governance.

The project value is demonstrated by measurable benchmark gains, strong traceability, and a practical CI/CD operating model (GitHub Actions + PowerShell) ready for Support and Maintenance execution.
----------------------------

Voici une version plus claire, directement collable dans tes slides PPT.

Slide 1 — Diagnostic Cards: But Métier
Une Diagnostic Card répond à une question support immédiate: quoi vérifier maintenant pour isoler vite la cause probable et réduire le temps de diagnostic.

Message clé:
On transforme des données techniques brutes en checklist actionnable pour le support et la maintenance.

Slide 2 — Comment La Card Est Construite (Automatique)

Fusion des sources par issue_number:
issues ST-ready + resolver cases ST-ready.
Référence: export_st_ready_diagnostic_cards.py:522

Parsing des signaux textuels:
Problem, Context, Root cause, Fix, Resolver signal, Assessmen
----------------------------

Je vais lire la fonction de calcul dans le script de liens issue-PR-commit pour te donner l’équation exacte (avec les poids réels) et une explication slide-ready.

Read fetch_issue_pr_commit_links.py, lines 1 to 260

Voici l’équation exacte du score resolver, telle qu’implémentée dans fetch_issue_pr_commit_links.py:31.

[
\text{score}
\min!\Big(
1,;
0.5\cdot \mathbf{1}{(\text{explicit_pr_count}>0)}
+
0.3\cdot \mathbf{1}{(\text{merged_pr_count}>0)}
+
0.1\cdot \mathbf{1}{(\text{explicit_pr_count}>0 ;\land; \text{merged_pr_count}=0)}
+
0.2\cdot \mathbf{1}{(\text{meaningful_commit_count}>0)}
\Big)
]

Explication simple:

+0.5 si au moins une PR est explicitement liée à l’issue.
+0.3 si au moins une de ces PR est mergée.
Sinon +0.1 (cas PR liée mais non mergée).
+0.2 si au moins un commit “meaningful” est lié (les commits de merge pur sont exclus).
Le score est plafonné à 1.0.
Ensuite le niveau de confiance est mappé comme ça (dans fetch_issue_pr_commit_links.py:47):

high si score (\ge 0.9)
medium si score (\ge 0.5)
low si score (>0)
none sinon
Tu peux mettre en slide:
Score = force des preuves de lien issue↔PR↔commit, avec priorité aux PR explicites, bonus si PR mergée, et validation technique par commits non-merge.
--------------------------------
Slide: Diagnostic Confidence dans Diagnostic Cards

Il n existe pas de fonction dediee nommee diagnosis_confidence.

La confiance de la carte vient du champ evidence_strength, avec fallback sur link_confidence.

Assignation dans la carte: export_st_ready_diagnostic_cards.py:500

Logique exacte: evidence_strength = issue_doc.evidence_strength sinon resolver_doc.link_confidence

Source prioritaire cote issue:

Calcul dans preprocessing_model.py:53
Injection dans le doc issue: preprocessing_model.py:191
Regles:
issue invalide => low
confirmed bug + signaux techniques suffisants => high
sinon, signaux techniques suffisants => medium
sinon => low
Source fallback cote resolver:

Calcul via score_and_confidence dans fetch_issue_pr_commit_links.py:31
Commits significatifs seulement, merge-like filtres via fetch_issue_pr_commit_links.py:18
𝑠
𝑐
𝑜
𝑟
𝑒
=
min
⁡
(
1.0
,
 
0.5
⋅
1
𝑃
𝑅
 
𝑒
𝑥
𝑝
𝑙
𝑖
𝑐
𝑖
𝑡
𝑒
+
0.3
⋅
1
𝑃
𝑅
 
𝑚
𝑒
𝑟
𝑔
𝑒
+
0.1
⋅
1
𝑃
𝑅
 
𝑒
𝑥
𝑝
𝑙
𝑖
𝑐
𝑖
𝑡
𝑒
 
∧
 
𝑝
𝑎
𝑠
 
𝑚
𝑒
𝑟
𝑔
𝑒
+
0.2
⋅
1
𝑐
𝑜
𝑚
𝑚
𝑖
𝑡
 
𝑠
𝑖
𝑔
𝑛
𝑖
𝑓
𝑖
𝑐
𝑎
𝑡
𝑖
𝑓
)
score=min(1.0, 0.5⋅1 
PR explicite
​
 +0.3⋅1 
PR merge
​
 +0.1⋅1 
PR explicite ∧ pas merge
​
 +0.2⋅1 
commit significatif
​
 )
Mapping:

high si 
𝑠
𝑐
𝑜
𝑟
𝑒
≥
0.9
score≥0.9
medium si 
𝑠
𝑐
𝑜
𝑟
𝑒
≥
0.5
score≥0.5
low si 
𝑠
𝑐
𝑜
𝑟
𝑒
>
0
score>0
none sinon
Impact dans la carte:

confidence reprise dans evidence_refs (issue/PR/commit): export_st_ready_diagnostic_cards.py:365
si link_confidence est low ou medium, ajout d une contrainte de prudence: export_st_ready_diagnostic_cards.py:311
Script oral (20-30 sec):

Dans notre pipeline, la confidence de diagnostic n est pas recalculee dans les Diagnostic Cards. On reutilise d abord evidence_strength venant du preprocessing issue, et seulement en fallback link_confidence venant du resolver. Donc la qualite de confiance depend de deux etages amont: robustesse des signaux techniques issue et robustesse du chainage issue PR commit.
GPT-5.3-Codex • 1x