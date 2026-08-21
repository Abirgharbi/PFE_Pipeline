# Evaluation Protocol & Benchmark Results - Slides Ready

## Slide 0 - Big Picture: From Raw Data to Reliable Answers

Title:
- From Raw STM32 Signals to Reliable Support Answers

Objective:
- Align everyone on the full journey before technical deep dive.

Opening context:
- We are building a STM32Cube support knowledge base.
- The knowledge base is still under construction and improves through iterative cycles.

End-to-end flow (what this work covers):
1) Data preparation:
- ingestion -> cleaning -> enrichment -> similarity
2) Support content generation:
- generate resolver cases and diagnostic cards from prepared evidence
3) Delivery for ST tool:
- package outputs into ST-ready JSON contracts
4) Runtime and evaluation:
- upload, live runs, offline and online quality checks, improvement loop

Current reality to make explicit:
- Out-of-scope or weak-context cases still appear in live behavior.
- This is expected at current maturity and handled through corrective iterations.

Roadmap message:
- Target is not only higher scores, but stable, explainable, and production-ready behavior.

Speaker note:
- "First we build trustworthy support content, then we package it for ST, then we validate and improve."

---

## Slide 0a - General Project Context: Where We Started, What We Are Doing, Why

Objective:
- Put the audience in context in 60 seconds before technical details.

Where we started:
- STM32 support knowledge was scattered across GitHub issues, PRs, commits, files, and PDF figures.
- Raw data was noisy and heterogeneous (different formats, weak links, uneven technical quality).
- Without structuring this data, retrieval quality and answer consistency were unstable.

What we are doing now:
- Build an end-to-end preprocessing pipeline that turns raw GitHub signals into reliable support evidence.
- Generate support intelligence artifacts:
  - resolver cases (fix traceability from issue/PR/commit evidence)
  - diagnostic cards (structured troubleshooting logic for the assistant)
- Export ST-ready contracts so the ST tool can ingest the knowledge safely.
- Evaluate continuously (offline + online) and regenerate artifacts after each quality gap.

Why this project matters:
- Reduce generic and unhelpful answers in real support conversations.
- Increase technical traceability (every answer can be linked to evidence).
- Make behavior more stable, explainable, and production-ready.
- Shorten the improvement loop: detect gaps, fix generators, re-export, re-evaluate.

Current phase (today):
- The KB is operational but still improving through iterative quality cycles.
- Priority is not just score increase; priority is robust, auditable, and reproducible support behavior.

Speaker note (simple story):
- "We started from fragmented raw signals. We are now converting them into structured support knowledge and ST-ready artifacts. The goal is simple: more reliable answers, with clear evidence, and faster improvement at each iteration."

---

## Slide 0bis - Project Map: Blocks and Ownership

Objective:
- Show who does what, where, and what is produced.

Block 1 - Off-domain R&D Lab (PC)
- Mission: test retrieval behavior and chunking strategies offline.
- Outputs: benchmark evidence and preprocessing recommendations.
- Status field: [NOT STARTED | IN PROGRESS | DONE]
- Last update: [YYYY-MM-DD]

Block 2 - Data Preparation Pipeline
- Mission: normalize and enrich raw sources into reliable evidence.
- Flow: ingestion -> cleaning -> enrichment -> similarity.
- Outputs: docs_v2, docs_v2_sim, issue_pr_commit_links.
- Status field: [NOT STARTED | IN PROGRESS | DONE]
- Last update: [YYYY-MM-DD]

Block 3 - Support Content Generation
- Mission: generate resolver cases and diagnostic cards from prepared evidence.
- Outputs: support content with confidence, facts, hypotheses, and checks.
- Status field: [NOT STARTED | IN PROGRESS | DONE]
- Last update: [YYYY-MM-DD]

Block 4 - Delivery for ST Tool
- Mission: package generated content into ST-acceptable files.
- Outputs: ST-ready JSON files + summary files.
- Gate: schema, count coherence, traceability before upload.
- Status field: [NOT STARTED | IN PROGRESS | DONE]
- Last update: [YYYY-MM-DD]

Block 5 - ST Tool Runtime
- Upload + RAG indexing in background.
- Possible live outcomes:
  - Useful answer
  - Generic answer
  - Runtime exception
  - Out-of-scope ST case (expected abstention)
- Status field: [NOT STARTED | IN PROGRESS | DONE]
- Last update: [YYYY-MM-DD]

Block 6 - Evaluation and Improvement Loop
- Offline: controlled benchmark by block.
- Online: live runs and quality index.
- Decision: fix pipeline and regenerate when regressions appear.
- Status field: [NOT STARTED | IN PROGRESS | DONE]
- Last update: [YYYY-MM-DD]

Narration line (opening):
- "This map is our tracking dashboard: owner, status, last update, and next move for each block."

---

## Slide 0ter - Why These Agents Matter

Objective:
- Explain the real business need behind each agent in one slide.

Agent 1 - STM32Cube Preprocessing Agent
- Real need: prevent noisy or weak evidence from entering support content.
- Role: quality and traceability co-pilot for the pipeline.
- Core actions:
  - analyze data flow, JSON outputs, benchmark signals
  - document schemas, test outcomes, delivery behavior
  - compare preprocessing and retrieval strategies
- Value:
  - cleaner input to generation and delivery
  - faster quality fixes between iterations

Agent 2 - STM32Cube PDF Vision Agent
- Real need: turn diagram-only PDF knowledge into searchable technical evidence.
- Role: figure and diagram understanding co-pilot.
- Core actions:
  - read pdf_image_tasks_<repo>.jsonl
  - analyze extracted figures and diagrams
  - produce injectable technical descriptions for the KB
- Value:
  - keeps hidden PDF knowledge usable by the AI
  - reduces information loss from image-only documents

Traceability fields to keep updated in presentation:
- Owner
- Input source
- Output artifacts
- Current status (NOT STARTED | IN PROGRESS | DONE)
- Last update (YYYY-MM-DD)
- Next action
- Main KPI

---

## Slide 0quater - Critical Split: Data Generation vs Delivery

Objective:
- Make the boundary explicit and avoid scope confusion.

Part A - Data Generation (Resolver + Diagnostic Intelligence)
- Goal: generate support reasoning content from prepared evidence.
- Inputs:
  - data/docs_*_v2.json and data/docs_*_v2_sim.json
  - data/issue_pr_commit_links_*.json
- Produces:
  - resolver logic (status, confidence, file evidence, actions)
  - diagnostic logic (symptoms, likely causes, confirmed facts, checks)
- Quality focus: evidence strength, technical relevance, traceability.

Part B - Delivery (ST Contract Packaging)
- Goal: package generated content into files accepted by the ST tool.
- Produces:
  - datasets/07_delivery/st_ready/*/st_ready_*.json
  - datasets/07_delivery/st_ready/*/summary_*.json
- Quality focus:
  - accepted by the ST tool without upload rejection
  - correct required fields and root structure
  - summary counts exactly match exported payloads
  - traceable links to source evidence are preserved

Key difference to say clearly:
- Data Generation answers: what support knowledge should be delivered.
- Delivery answers: how that knowledge must be formatted for the ST platform.
- ST tool applies its own chunking at runtime; local chunking is only for offline evaluation.

Concrete example - Issue 343 from docs_v2 to st_ready_issues:

Before (docs_v2 source):
- File: data/docs_issues_stm32cubeh7_v2.json
- Record id: stm32cubeh7-issue-343
- Core raw evidence fields:
  - issue_title: [Bug]: HAL_CRYP_Decrypt_DMA fails when transfer size is > 65535 bytes
  - clean_text: bug summary + detailed description + expected/actual behavior + comments
  - metadata: board=STM32H7XX, component=DMA, layer=HAL, issue_kind=bug_report, severity=medium

After (ST upload contract):
- File: datasets/07_delivery/st_ready/issues_json/st_ready_issues_stm32cubeh7.json
- Same record id: stm32cubeh7-issue-343
- delivery_template: st_v2_structured_issue_card
- st_ready_text: normalized structure consumed by the RAG engine.

Structure: st_ready_text (issues) - fields exposed to the moteur RAG
- Problem
- Context
- Constraints
- Root cause
- Fix
- Keywords
- Technical details
- Key comments

Example st_ready_text excerpt (Issue 343):
```text
Problem: [Bug]: HAL_CRYP_Decrypt_DMA fails when transfer size is > 65535 bytes
Context: repo=STM32CubeH7, mcu_series=H7, board=STM32H7XX, component=DMA, layer=HAL, issue_kind=bug_report, severity=medium, evidence_strength=high, rescue_applied=False, state=open, issue_number=343
Constraints: Validate against exact MCU/board configuration and CubeMX/CubeH7 version before applying.
Root cause: Maintainer confirmed the point and tracked it internally (ST Internal Reference: CDM0061687).
Fix: Clarify/adjust DMA size handling when DataWidthUnit=WORD to prevent uint16_t overflow and transfer truncation.
Keywords: H7, STM32H7XX, HAL, DMA, cryp, HAL_CRYP_Decrypt_DMA, CRYP_DATAWIDTHUNIT_WORD, HAL_CRYP_Encrypt_DMA
Technical details: Includes code-level references and behavior evidence from stm32h7xx_hal_cryp.c and stm32h7xx_hal_cryp.h.
Key comments: Maintainer acknowledgement plus internal tracking decision.
```

Takeaway for this slide:
- docs_v2 keeps rich raw evidence.
- st_ready_issues converts that evidence into a stable, upload-compatible, and retrieval-friendly contract for the ST tool.

---

## Slide 0quinquies - Resolver Cases vs Diagnostic Cards: Inputs, Outputs, Value

Objective:
- Clarify what each artifact consumes, what it produces, and why it creates high operational value.

Resolver Cases - Inputs:
- issue_pr_commit_links_<repo>.json or issue_pr_commit_links_<repo>_linked_only.json
- raw_commits_<repo>.json (changed files and commit-level evidence)
- st_ready_files_<repo>.json (optional file-document enrichment when paths match)

Resolver Cases - Outputs:
- st_ready_resolver_cases_<repo>.json
- One card per linked issue with:
  - resolution_status (merged_fix / candidate_fix / commit_only_candidate / reference_only)
  - link_confidence and link_score
  - linked PRs and commits
  - files_evidence (changed files, match_rate with docs files, impacted modules/components)
  - resolver_card_text (Problem, Context, Resolver signal, Assessment, Constraints)

Diagnostic Cards - Inputs:
- st_ready_issues_<repo>.json (rescued issues by default, or all issues with --include-all-issues)
- st_ready_resolver_cases_<repo>.json (if available)

Diagnostic Cards - Outputs:
- st_ready_diagnostic_cards_<repo>.json
- One diagnostic card per issue key from issues/resolver union with:
  - query_aliases and query_anchor_tags
  - symptom_summary, likely_causes, confirmed_facts, plausible_diagnosis
  - response_blocks (facts_confirmed -> hypotheses -> checks)
  - clarification_questions (required)
  - debug_checks, possible_workarounds, constraints_or_limits
  - evidence_refs and st_ready_text for RAG consumption

Why this is important (high value):
- Resolver cases convert raw GitHub links into fix traceability signals for support teams.
- Diagnostic cards convert noisy issue text into structured troubleshooting logic the assistant can follow.
- Together, they reduce generic answers by improving both retrieval anchors and response structure.
- They make support behavior auditable: each answer can point back to issue/PR/commit evidence.
- They accelerate iteration: weak cards can be regenerated from pipeline rules instead of manual rewriting.

Concrete value snapshot (STM32CubeH7 current export):
- Resolver cases exported: 4/4 linked cases (candidate_fix=4).
- Diagnostic cards exported: 45 cards from 42 rescued issues + 4 resolver-linked entries.
- Net effect: broader troubleshooting coverage than resolver-only evidence, while keeping traceability to source artifacts.

---

## Slide 0sexies - Explication Facile (FR): Commit, Diff, et Linkage Fichiers

Objectif:
- Expliquer simplement ce que le pipeline fait aujourd'hui avec les commits et les fichiers modifies.

Q1) On prend le commit diff ou juste le message ?
- Les deux sont collectes.
- En pratique aujourd'hui, le linkage s'appuie surtout sur:
- le message de commit (references issue/fix/close),
- et des signaux de diff legers (fichiers modifies, additions, deletions, changes, PR mergee ou non).
- Le patch n'est pas encore exploite en analyse semantique profonde ligne par ligne.

Q2) "Actuellement", ca veut dire quoi concretement ?
- Le pipeline classe le lien en:
- merged_fix / candidate_fix / commit_only_candidate / reference_only.
- Cette decision vient d'un score base sur:
- PR explicites,
- commits significatifs,
- et evidence de fichiers modifies dans des PR mergees.

Q3) D'ou viennent les "diffs legers" ?
- Depuis l'API GitHub PR files: filename, status, additions, deletions, changes.
- Depuis l'API GitHub commit detail: files_changed + patch.
- Ces donnees sont stockees dans les fichiers bruts:
- data/raw_prs_<repo>.json
- data/raw_commits_<repo>.json

Q4) Comment se fait le linkage des fichiers modifies (depuis les donnees brutes) ?
1) Lier issue <-> PR via linked_issue_numbers.
2) Lier issue <-> commit via references explicites + inference depuis message.
3) Recuperer files_changed des commits lies.
4) Agreger par chemin normalise (path), cumuler additions/deletions/changes.
5) Tenter un match exact avec st_ready_files_<repo>.json.
6) Si match: enrichir (file_doc_id, component, board, file_type).
7) Sinon: garder source_match=commit_only.
8) Calculer match_rate et impacted_modules pour la carte resolver.

Takeaway simple:
- Oui, le linkage utilise des donnees brutes GitHub.
- Oui, il utilise des indices de diff.
- Non, il ne valide pas encore la correction par lecture technique complete du patch.

## Slide 1 - Why Evaluation in this PFE

Title:
- Evaluation Protocols for STM32Cube Support Persona

Message:
- Goal is not only answer quality, but also controlled behavior:
  - less hallucination
  - less out-of-context responses
  - better evidence traceability (issue/PR/commit/file)
- We evaluate both retrieval quality and live chatbot behavior.

Speaker note:
- "Our protocol validates the pipeline before and after KB upload, then monitors production stability with recurring 50Q campaigns."

---

## Slide 2 - 3-Step Evaluation Protocol

1) Benchmark creation
- Manual benchmark sets:
  - 30Q controlled set (issues/files/mixed)
  - 50Q operational set (ST Quality Index style)

2) Offline retrieval tests (TF-IDF)
- Check lexical retrievability before upload.
- Evaluate whether top retrieved chunks/docs are relevant.

3) Live ST platform run
- Upload Excel/CSV test suite.
- Compare expected answer vs persona answer.
- Track returned answer vs generic abstention vs exception.

Sources:
- pipeline/evaluation/test_tfidf_search_issues_v2.py
- pipeline/evaluation/test_tfidf_search_files_v2.py
- datasets/07_delivery/st_ready/run_h7_50q_ab_test.ps1

---

## Slide 3 - Step 1: Benchmark Creation

30Q reference set:
- File: datasets/06_eval_outputs/h7_eval_30q_questions.md
- Split by intent:
  - Q01-Q10: issues-centric
  - Q11-Q20: files-centric
  - Q21-Q30: mixed issues+files

50Q reference set:
- File: datasets/07_delivery/st_ready/h7_test_suite_excel_ready.csv
- Real support-like coverage:
  - DMA, UART, I2C, USB, ADC, FDCAN, Ethernet, CRYP
  - dual-core, cache/MPU, RTOS, uncertainty handling, evidence policy

Key point:
- Questions are manually authored to avoid synthetic benchmark bias.

---

## Slide 4 - Step 2: Offline TF-IDF Protocol

What is implemented:
- Vectorization with TfidfVectorizer.
- Similarity with cosine similarity.
- Search over valid docs only (is_valid=true).
- Top-k inspection for relevance.

Similarity linking between issues:
- File: pipeline/similarity/compute_issue_similarity_v2.py
- Current code uses:
  - top_k = 3
  - min_sim = 0.40

Important clarification for presentation:
- If you present threshold 0.30, position it as a candidate tuning scenario.
- Current repository truth is 0.40 in active script.

---

## Slide 5 - Step 3: Live ST Quality Index Run

Execution flow:
- Test suite CSV (Question, Expected answer, Tags).
- Script sends each question to persona API.
- Raw outputs stored to datasets/06_eval_outputs/run50_*.csv.

Automation:
- datasets/07_delivery/st_ready/run_h7_50q_ab_test.ps1
- pipeline_Automation/Chat_With_Persona_KB.py

Per question captured fields:
- QID, Question, GoldAnswer, Tags
- AssistantAnswer, Mode, ExitCode

Operational metrics:
- Answer returned
- Generic answer (I DO NOT KNOW / low confidence template)
- Exception (runner/API failure)

---

## Slide 6 - Benchmark Results (30Q A/B)

Source:
- datasets/06_eval_outputs/h7_eval_30q_scored_summary.csv

Global score (/7):
- A (issues_only): 2.93
- B (issues_plus_files): 5.33
- Gain: +2.40 points (~+81.9% relative)

By block:
- Issues block: 6.70 -> 6.20 (slight regression)
- Files block: 1.20 -> 6.00 (major gain)
- Mixed block: 1.30 -> 4.10 (strong gain)

Interpretation:
- Adding files JSON dramatically reduces missing-context responses on files and mixed prompts.

---

## Slide 7 - Benchmark Results (A/B/C on 10Q)

Source:
- datasets/06_eval_outputs/ab_test_scoring_template_h7_output_scored.csv

Average total (/9):
- A raw_issues_h7: 8.4
- B docs_issues_h7_v2: 8.7 (best)
- C st_ready_issues_h7: 6.9

Observed risk in C:
- One critical miss on Q7 (score 0/9, wrong topic retrieval).
- Some precision drops on Q4/Q5/Q9.

Takeaway:
- ST-ready format is useful for delivery, but needs retrieval hardening and alias anchoring to avoid topic drift.

---

## Slide 8 - 50Q Live Run Snapshot (API, CLI)

Sources:
- datasets/06_eval_outputs/run50_baseline_20260423_163941.csv
- datasets/06_eval_outputs/run50_candidate_20260423_163941.csv
- datasets/06_eval_outputs/run50_classic_20260428_162311.csv

Run quality snapshot:
- Baseline:
  - Exceptions: 20/50 (40%)
  - Generic answers: 16/50 (32%)
  - Informative non-generic non-exception: 14/50 (28%)
- Candidate:
  - Exceptions: 25/50 (50%)
  - Generic answers: 15/50 (30%)
  - Informative: 10/50 (20%)
- Classic:
  - Exceptions: 24/50 (48%)
  - Generic answers: 14/50 (28%)
  - Informative: 12/50 (24%)

Interpretation:
- Main bottleneck is runtime robustness (exceptions), not only retrieval precision.

---

## Slide 8bis - Offline vs Online Quality Index Difference

ST Quality Index online behavior:
- Upload spreadsheet with Question + Expected Answer + Tag
- Platform returns per-question score (/100)
- Includes details section and reason text (example: QUESTION #1 DETAILS -> 70)

Offline benchmark behavior in repository:
- Manual rubric scoring (/7 or /9) for controlled protocols
- Useful for deterministic A/B analysis by blocks

How we make scores comparable:
- Normalize offline /7 into /100
- offline_norm = (offline_total_0_to_7 / 7) * 100
- Compare with online score:
  - delta = online_score - offline_norm

Automation used:
- pipeline/evaluation/compare_offline_online_quality.py

Output:
- A/B summary by block (issues, files, mixed)
- global delta offline vs online

---

## Slide 9 - Incremental Evaluation Strategy (Anti-Hallucination)

Evaluation ladder (what we measure after each increment):
1. issues only
2. files added
3. issues + files
4. resolver cases added
5. diagnostic cards added
6. drivers/domain extension added

Why incremental:
- Isolate marginal gain of each datasource family.
- Detect when a new source increases noise or hallucination.
- Stop regressions before production rollout.

Upload automation confirms 4 active families in batch:
- issues_json
- files_json
- diagnostic_cards_json
- resolver_cases_json

Source:
- pipeline_Automation/Upload_STReady_New_Batch.ps1

---

## Slide 10 - Recommended KPIs for Next Iterations

Primary KPIs:
- Success rate = non-exception answers / total
- Useful answer rate = informative answers / total
- Generic abstention rate
- Source-grounded score (top1 + relevance + hallucination inverse)

Quality gates before each upload:
- Gate 1: stats scripts
- Gate 2: TF-IDF smoke tests
- Gate 3: schema validation
- Gate 4: 30Q controlled benchmark
- Gate 5: recurring 50Q ST Quality Index

Decision policy:
- Promote only if no severe regression on mixed queries and runtime exception rate trends down.

---

## Backup Slide - Commands (if jury asks "how did you run it?")

```bash
python -m pipeline.evaluation.test_stats_issues_v2
python -m pipeline.evaluation.test_stats_files_v2
python -m pipeline.evaluation.test_tfidf_search_issues_v2
python -m pipeline.evaluation.test_tfidf_search_files_v2
python -m pipeline.evaluation.validate_schemas
```

```powershell
./datasets/07_delivery/st_ready/run_h7_50q_ab_test.ps1
./pipeline_Automation/Upload_STReady_New_Batch.ps1 -RemoteUser your.name@st.com -Operation add
```
