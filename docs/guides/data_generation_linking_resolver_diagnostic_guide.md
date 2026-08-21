# Data Generation, Issue-PR-Commit Linking, Resolver Cases, Diagnostic Cards

## 1) Big picture

This note explains, step by step, how the STM32Cube preprocessing pipeline builds technical knowledge and then turns it into troubleshooting-ready outputs.

High-level flow:

1. Ingestion
2. Cleaning
3. Enrichment
4. Similarity
5. Chunking
6. Delivery

Main orchestrator:

- pipeline/run_full_workflow.py


## 2) Data Generation objective and boundary

### Data Generation objective

Data Generation is the key step that turns processed data into useful knowledge, so the assistant can find the right answer.

### Practical meaning

Data Generation builds reliable, structured, RAG-ready knowledge from:

- cleaned issue/file text,
- enriched metadata,
- similarity signals,
- chunked retrieval units.

### Boundary with Delivery

- Data Generation builds the knowledge.
- Delivery packages and publishes that knowledge in final ST-ready formats.


## 3) How Issue-PR-Commit linking is designed (step by step)

Primary scripts:

- pipeline/ingestion/fetch_prs.py
- pipeline/ingestion/fetch_commits.py
- pipeline/ingestion/github_service.py
- pipeline/ingestion/fetch_issue_pr_commit_links.py

### Step 1: Pull requests are ingested with issue references

In pipeline/ingestion/github_service.py, each PR detail includes:

- pr_number
- title/body
- linked_issue_numbers extracted from PR title/body
- changed_files_count and files_changed

### Step 2: Commits are ingested from selected PRs

In pipeline/ingestion/fetch_commits.py:

- the script selects PRs (default linked_or_merged scope),
- fetches all commits for those PRs,
- stores commit details with pr_numbers, linked_issue_numbers, stats, and files_changed.

Commit detail in pipeline/ingestion/github_service.py includes:

- sha, message, committed_at,
- files_changed with filename/status/additions/deletions/changes/patch,
- linked_issue_numbers extracted from commit message.

### Step 3: Link builder merges explicit and inferred signals

In pipeline/ingestion/fetch_issue_pr_commit_links.py, for each issue:

1. collect explicit PR links (PR linked_issue_numbers),
2. collect explicit commit links (commit linked_issue_numbers),
3. infer extra links from commit messages using regex patterns.

Regex logic catches patterns like:

- fix/close/resolve/ref,
- issue #123,
- /issues/123 URLs,
- bare #123 only when context is strong enough.

### Step 4: Merge-like commits are separated

The script detects merge-like commit messages and separates them from meaningful commits to reduce noisy evidence.

### Step 5: Score, confidence, and status are assigned

For each issue linkage, the script computes:

- link_score
- link_confidence (high/medium/low/none)
- resolution_status among:
  - merged_fix
  - candidate_fix
  - commit_only_candidate
  - reference_only
  - unlinked

### Step 6: Two output files are produced

- Full output: data/issue_pr_commit_links_<repo>.json
- Filtered output: data/issue_pr_commit_links_<repo>_linked_only.json


## 4) How Resolver Cases are designed (step by step)

Primary script:

- pipeline/delivery/export_st_ready_resolver_cases.py

### Step 1: Start from linkage outputs

Input is loaded from:

- data/issue_pr_commit_links_<repo>_linked_only.json (preferred)
- fallback to data/issue_pr_commit_links_<repo>.json

### Step 2: Keep only actionable statuses

By default:

- unlinked is excluded,
- reference_only is excluded unless include_reference_only is enabled.

### Step 3: Build changed-file evidence from raw commits

The exporter loads raw_commits_<repo>.json, aggregates files_changed across linked commits, and computes:

- changed_files_total
- per-file changes/additions/deletions
- touched_by_commits
- module inference (HAL_Driver, CMSIS, Middlewares, etc.)

### Step 4: Try exact join with ST-ready files knowledge

For each changed path, it tries to match st_ready_files_<repo>.json to enrich with:

- file_doc_id
- file_type
- component
- board
- example_name

If no match, source_match is commit_only.

### Step 5: Build resolver card

Each resolver case includes:

- linked PR and commit URLs,
- resolution_status, link_confidence, link_score,
- resolver_card_text (problem/context/signal/assessment/constraints),
- files_evidence and impacted_* fields.

Output:

- datasets/07_delivery/st_ready/resolver_cases_json/st_ready_resolver_cases_<repo>.json
- datasets/07_delivery/st_ready/resolver_cases_json/summary_resolver_cases_<repo>.json


## 5) How Diagnostic Cards are designed (step by step)

Primary script:

- pipeline/delivery/export_st_ready_diagnostic_cards.py

### Step 1: Load ST-ready issue and resolver sources

Inputs:

- datasets/07_delivery/st_ready/issues_json/st_ready_issues_<repo>.json
- datasets/07_delivery/st_ready/resolver_cases_json/st_ready_resolver_cases_<repo>.json

### Step 2: Select issue subset

Default behavior:

- uses rescued issues only (unless include_all_issues is enabled),
- keeps resolver cases by issue number.

### Step 3: Merge issue and resolver by issue_number

For each key, build one diagnostic card from:

- issue evidence (when available),
- resolver evidence (when available),
- or both.

### Step 4: Extract troubleshooting signals

The builder parses prefixed fields from st_ready_text and resolver_card_text, then derives:

- technical_pattern_tags
- api_family_tags
- version_tags
- query_aliases
- clarification_questions
- debug_checks
- likely_causes, confirmed_facts, plausible_diagnosis

### Step 5: Enforce assistant response structure

Cards include response_blocks in this order:

- facts_confirmed
- hypotheses
- checks

This is why Diagnostic Cards are conversation-ready, not only evidence records.

### Step 6: Export final cards

Output:

- datasets/07_delivery/st_ready/diagnostic_cards_json/st_ready_diagnostic_cards_<repo>.json
- datasets/07_delivery/st_ready/diagnostic_cards_json/summary_diagnostic_cards_<repo>.json


## 6) Concrete examples

### Example A: Issue knowledge card (#343)

File:

- datasets/07_delivery/st_ready/issues_json/st_ready_issues_stm32cubeh7.json

Observed content for issue 343:

- issue_title about HAL_CRYP_Decrypt_DMA over 65535 bytes,
- layer HAL, component DMA,
- evidence_strength high,
- technical anchors preserved in st_ready_text.

### Example B: Resolver case (#43)

File:

- datasets/07_delivery/st_ready/resolver_cases_json/st_ready_resolver_cases_stm32cubeh7.json

Observed content for issue 43:

- linked_pr_numbers: [44]
- linked_commit_shas contains commit 4741000f...
- resolution_status: candidate_fix
- link_confidence: medium
- link_score: 0.8
- files_evidence points to Drivers/STM32H7xx_HAL_Driver/Src/stm32h7xx_hal_usart.c

### Example C: Diagnostic card (#43)

File:

- datasets/07_delivery/st_ready/diagnostic_cards_json/st_ready_diagnostic_cards_stm32cubeh7.json

Observed content for issue 43:

- source_types includes resolver_case,
- response_blocks provide facts -> hypotheses -> checks,
- evidence_refs include PR and commit links,
- constraints warn that fix confidence is not enough for universal applicability.


## 7) Difference summary (simple)

### Issue-PR-Commit linking

Purpose: build traceable fix evidence from GitHub graph and messages.

### Resolver Cases

Purpose: package fix evidence into actionable technical resolution cases.

### Diagnostic Cards

Purpose: convert evidence into guided troubleshooting dialogue blocks.


## 8) One-line presentation version

Issue-PR-Commit linking reconstructs technical resolution evidence, Resolver Cases package that evidence as fix candidates, and Diagnostic Cards transform it into assistant-ready troubleshooting guidance.
_____________________________________
Oui — ce schéma raconte une idée intéressante, mais il est **trop détaillé** pour une slide de présentation, surtout si tu dois le commenter oralement devant une audience qui ne connaît pas déjà la logique interne.

Il montre bien :
- fusion issue + resolver
- extraction de faits
- extraction d’indices de fix
- calcul de confiance
- génération d’une carte actionnable

Mais à l’oral, si tu n’as pas un message simple, l’audience va se perdre.

Donc je vais te donner :

1. **comment présenter ce schéma**
2. **un speech clair et fluide**
3. **une version plus courte si tu veux**

---

# Ce que montre ce schéma, en langage simple

Le message central est :

> A Diagnostic Card is not created from raw issue text only.  
> It combines:
> - issue context,
> - resolver evidence,
> - confirmed facts,
> - fix-related clues,
> - and a confidence estimation,
> to produce a structured support-oriented action card.

Donc, à l’oral, il faut guider l’audience en 4 temps :

## 1. Inputs
- issue
- resolver evidence
- linked PR / commit information

## 2. Extraction
- confirmed facts from issue/body/comments/evidence
- fix evidence from PR / commit links

## 3. Confidence
- combine these signals
- estimate diagnosis confidence

## 4. Output
- structured action card
- usable by support engineers

---

# Speech recommandé

## Version claire et professionnelle

> This diagram shows a more detailed view of how a Diagnostic Card is built.  
> We start from two main inputs: the ST-ready issue and the resolver case, which already contains fix-related evidence when available.  
> From the issue side, we extract confirmed facts from the issue body, comments, and evidence attachments.  
> In parallel, from the linked PRs and commits, we extract fix evidence, such as code changes, references to the issue number, or closing keywords.  
> These two streams are then combined to compute a diagnosis confidence.  
> Depending on the strength of the signals, the confidence can be high, medium, or low.  
> Finally, this information is transformed into a structured action card that can help support engineers more quickly understand the problem, assess the confidence level, and identify the next checks or actions to perform.

---

# Version un peu plus naturelle

> This slide gives a deeper look into the Diagnostic Card logic.  
> The card does not come only from the raw issue text.  
> It combines issue context with resolver evidence when available.  
> First, we extract confirmed facts from the issue body, comments, and supporting evidence.  
> Then, we look at linked PRs and commits to identify fix-related clues, such as code changes, references to the issue number, or closing patterns.  
> These signals are combined to estimate a diagnosis confidence.  
> Based on that confidence, the system generates a structured action card that is easier for support engineers to use during investigation.

---

# Version plus courte pour slide

> This diagram shows how a Diagnostic Card goes beyond raw issue text.  
> It combines confirmed facts from the issue with fix-related evidence from linked PRs and commits.  
> These signals are used to compute a confidence level, and the result is a structured action card for support engineers.

---

# Ce que tu peux dire sur la boîte rouge “Compute diagnosis confidence”

Comme elle est mise en évidence, tu dois absolument la commenter.

Tu peux dire :

> The highlighted step is important because it acts as the decision point between raw evidence and actionable support guidance. It is where issue facts and resolver clues are combined into a confidence signal before generating the final card.

---

# Si tu veux une phrase qui valorise la slide

Tu peux ajouter à l’oral :

> This is one of the key differences between storing raw issues and generating support-oriented knowledge: the system is not only collecting information, it is structuring it into a form that helps decision-making.

---

# Important
Ton schéma utilise :
- **support engineers**
- **structured action card**

C’est bien, mais si ta slide est censée parler strictement de **Diagnostic Cards**, alors à l’oral tu dois dire que :

> this structured action card is the Diagnostic Card output

sinon on peut croire qu’il s’agit d’un autre objet.

Tu peux donc dire :

> In this diagram, the “structured action card” corresponds to the Diagnostic Card used downstream.

---

# Ma recommandation orale finale

Je te conseille de dire ceci :

> This diagram gives a more detailed view of the Diagnostic Card construction.  
> We start from the ST-ready issue and the resolver case, which may already include fix-related evidence.  
> From the issue side, we extract confirmed facts from the body, comments, and supporting evidence.  
> From the linked PRs and commits, we extract fix clues such as code changes, issue references, and closing keywords.  
> These signals are combined in the highlighted step to compute a diagnosis confidence.  
> This confidence can be high, medium, or low, and it helps control how the final card is built.  
> The final result is a structured action card — in other words, the Diagnostic Card — designed to help support engineers understand the issue faster and decide what to check next.

---

# Si tu veux, je peux aussi te faire :

1. **une version encore plus simple pour audience non technique**
2. **une version beaucoup plus courte, 20 secondes**
3. **une reformulation du schéma pour qu’il soit visuellement plus cohérent avec les autres slides**
4. **une phrase de conclusion à mettre sous ce schéma**.