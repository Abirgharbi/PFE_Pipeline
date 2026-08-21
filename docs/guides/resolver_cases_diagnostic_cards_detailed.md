# Resolver Cases et Diagnostic Cards - Documentation Detaillee

## 1. Objectif et valeur ajoutee

Cette documentation explique en detail:

- pourquoi on a 2 couches (Resolver Cases puis Diagnostic Cards),
- de quelles donnees chaque couche depend,
- comment chaque champ important est construit,
- pourquoi ces couches permettent de sortir des reponses plus pertinentes et actionnables.

Message central:

- Resolver Case = preuve technique de resolution (trace issue -> PR/commit -> fichiers impactes).
- Diagnostic Card = plan de diagnostic exploitable (facts -> hypotheses -> checks -> questions de clarification).


## 2. Ou ces couches se placent dans le pipeline

Etapes pipeline (orchestrateur):

- Ingestion issue-pr-commit links: [pipeline/run_full_workflow.py](../pipeline/run_full_workflow.py#L71)
- Cleaning issues: [pipeline/run_full_workflow.py](../pipeline/run_full_workflow.py#L74)
- Enrichment issues V2: [pipeline/run_full_workflow.py](../pipeline/run_full_workflow.py#L76)
- Delivery ST-ready resolver cases: [pipeline/run_full_workflow.py](../pipeline/run_full_workflow.py#L95)
- Delivery ST-ready diagnostic cards: [pipeline/run_full_workflow.py](../pipeline/run_full_workflow.py#L96)


## 3. Besoins pour generer chaque couche

### 3.1 Resolver Cases - prerequis

Inputs utilises:

- issue_pr_commit_links_<repo>_linked_only.json (ou fallback issue_pr_commit_links_<repo>.json): [pipeline/delivery/export_st_ready_resolver_cases.py](../pipeline/delivery/export_st_ready_resolver_cases.py#L322)
- raw_commits_<repo>.json pour reconstruire les fichiers modifies: [pipeline/delivery/export_st_ready_resolver_cases.py](../pipeline/delivery/export_st_ready_resolver_cases.py#L60)
- st_ready_files_<repo>.json pour enrichir les fichiers impactes quand match exact: [pipeline/delivery/export_st_ready_resolver_cases.py](../pipeline/delivery/export_st_ready_resolver_cases.py#L73)

Generation amont des links issue/PR/commit:

- build_links_for_repo: [pipeline/ingestion/fetch_issue_pr_commit_links.py](../pipeline/ingestion/fetch_issue_pr_commit_links.py#L123)
- extraction references issues depuis commit message: [pipeline/ingestion/fetch_issue_pr_commit_links.py](../pipeline/ingestion/fetch_issue_pr_commit_links.py#L41)

### 3.2 Diagnostic Cards - prerequis

Inputs utilises:

- st_ready_issues_<repo>.json: [pipeline/delivery/export_st_ready_diagnostic_cards.py](../pipeline/delivery/export_st_ready_diagnostic_cards.py#L664)
- st_ready_resolver_cases_<repo>.json: [pipeline/delivery/export_st_ready_diagnostic_cards.py](../pipeline/delivery/export_st_ready_diagnostic_cards.py#L665)

Comportement de selection important:

- par defaut, on ne prend que les rescued issues: [pipeline/delivery/export_st_ready_diagnostic_cards.py](../pipeline/delivery/export_st_ready_diagnostic_cards.py#L675)


## 4. Resolver Cases - comment les champs sont construits

Point d entree principal:

- to_st_ready_case: [pipeline/delivery/export_st_ready_resolver_cases.py](../pipeline/delivery/export_st_ready_resolver_cases.py#L201)

### 4.1 D ou vient exactement Problem/Context/Resolver signal/Assessment/Constraints

Le texte resolver est fabrique dans build_resolver_card_text:

- fonction source: [pipeline/delivery/export_st_ready_resolver_cases.py](../pipeline/delivery/export_st_ready_resolver_cases.py#L158)
- Problem: construit depuis issue_number + issue_title du case linkage
- Context: construit depuis repo + labels + issue_state
- Resolver signal: construit depuis resolution_status + link_confidence + link_score
- Assessment: choisi via un mapping resolution_status -> phrase d evaluation: [pipeline/delivery/export_st_ready_resolver_cases.py](../pipeline/delivery/export_st_ready_resolver_cases.py#L175)
- Constraints: phrase fixe ajoutee dans le resolver text: [pipeline/delivery/export_st_ready_resolver_cases.py](../pipeline/delivery/export_st_ready_resolver_cases.py#L197)

Les statuts possibles et leur interpretation de base:

- merged_fix: fix probablement integre en mainline
- candidate_fix: fix potentiel detecte mais integration incertaine
- commit_only_candidate: evidence commit sans trace PR solide
- reference_only: reference sans preuve technique forte
- unlinked: pas de linkage exploitable

Mapping texte de ces statuts: [pipeline/delivery/export_st_ready_resolver_cases.py](../pipeline/delivery/export_st_ready_resolver_cases.py#L176)    

### 4.2 D ou viennent resolution_status, link_confidence, link_score

Ces champs ne sont pas inventes dans delivery; ils viennent du linkage ingestion:

- score/confiance: [pipeline/ingestion/fetch_issue_pr_commit_links.py](../pipeline/ingestion/fetch_issue_pr_commit_links.py#L69)
- statut de resolution: [pipeline/ingestion/fetch_issue_pr_commit_links.py](../pipeline/ingestion/fetch_issue_pr_commit_links.py#L106)
- regles status explicites: merged_fix/candidate_fix/commit_only_candidate/reference_only/unlinked
	- [pipeline/ingestion/fetch_issue_pr_commit_links.py](../pipeline/ingestion/fetch_issue_pr_commit_links.py#L113)
	- [pipeline/ingestion/fetch_issue_pr_commit_links.py](../pipeline/ingestion/fetch_issue_pr_commit_links.py#L115)
	- [pipeline/ingestion/fetch_issue_pr_commit_links.py](../pipeline/ingestion/fetch_issue_pr_commit_links.py#L117)
	- [pipeline/ingestion/fetch_issue_pr_commit_links.py](../pipeline/ingestion/fetch_issue_pr_commit_links.py#L119)
	- [pipeline/ingestion/fetch_issue_pr_commit_links.py](../pipeline/ingestion/fetch_issue_pr_commit_links.py#L120)
- projection vers le JSON linkage final: [pipeline/ingestion/fetch_issue_pr_commit_links.py](../pipeline/ingestion/fetch_issue_pr_commit_links.py#L277)

Puis ces champs sont repris tels quels dans resolver export:

- resolution_status: [pipeline/delivery/export_st_ready_resolver_cases.py](../pipeline/delivery/export_st_ready_resolver_cases.py#L292)
- link_confidence: [pipeline/delivery/export_st_ready_resolver_cases.py](../pipeline/delivery/export_st_ready_resolver_cases.py#L301)
- link_score: [pipeline/delivery/export_st_ready_resolver_cases.py](../pipeline/delivery/export_st_ready_resolver_cases.py#L302)

### 4.3 match docs_files_exact vs commit_only

Le mecanisme est le suivant:

1. Charger les commits bruts: [pipeline/delivery/export_st_ready_resolver_cases.py](../pipeline/delivery/export_st_ready_resolver_cases.py#L60)
2. Charger l index des fichiers ST-ready files: [pipeline/delivery/export_st_ready_resolver_cases.py](../pipeline/delivery/export_st_ready_resolver_cases.py#L73)
3. Reconstituer les changed files depuis raw_commits: [pipeline/delivery/export_st_ready_resolver_cases.py](../pipeline/delivery/export_st_ready_resolver_cases.py#L102)
4. Si path exact trouve dans files_json -> source_match=docs_files_exact: [pipeline/delivery/export_st_ready_resolver_cases.py](../pipeline/delivery/export_st_ready_resolver_cases.py#L234)
5. Sinon -> source_match=commit_only: [pipeline/delivery/export_st_ready_resolver_cases.py](../pipeline/delivery/export_st_ready_resolver_cases.py#L252)

Impact direct:

- remplit linked_file_ids/linked_file_paths quand match exact: [pipeline/delivery/export_st_ready_resolver_cases.py](../pipeline/delivery/export_st_ready_resolver_cases.py#L305)
- enrichit files_evidence + impacted_modules/components/boards/file_types: [pipeline/delivery/export_st_ready_resolver_cases.py](../pipeline/delivery/export_st_ready_resolver_cases.py#L307)

### 4.4 Filtrage des cas exportes

- unlinked exclu
- reference_only exclu sauf option include_reference_only
- logique: [pipeline/delivery/export_st_ready_resolver_cases.py](../pipeline/delivery/export_st_ready_resolver_cases.py#L343)


## 5. Diagnostic Cards - generation detaillee des champs demandes

Point d entree principal:

- build_diagnostic_card: [pipeline/delivery/export_st_ready_diagnostic_cards.py](../pipeline/delivery/export_st_ready_diagnostic_cards.py#L539)

### 5.1 Quels textes sont lus cote issue et cote resolver

Texte cote issue (st_ready_text):

- genere dans compose_st_ready_text: [pipeline/delivery/export_st_ready_issues.py](../pipeline/delivery/export_st_ready_issues.py#L110)
- lignes Problem/Context/Root cause/Fix/Constraints/Keywords construites explicitement:
	- [pipeline/delivery/export_st_ready_issues.py](../pipeline/delivery/export_st_ready_issues.py#L141)
	- [pipeline/delivery/export_st_ready_issues.py](../pipeline/delivery/export_st_ready_issues.py#L142)
	- [pipeline/delivery/export_st_ready_issues.py](../pipeline/delivery/export_st_ready_issues.py#L143)
	- [pipeline/delivery/export_st_ready_issues.py](../pipeline/delivery/export_st_ready_issues.py#L144)
	- [pipeline/delivery/export_st_ready_issues.py](../pipeline/delivery/export_st_ready_issues.py#L145)
	- [pipeline/delivery/export_st_ready_issues.py](../pipeline/delivery/export_st_ready_issues.py#L146)

Texte cote resolver (resolver_card_text):

- genere dans build_resolver_card_text: [pipeline/delivery/export_st_ready_resolver_cases.py](../pipeline/delivery/export_st_ready_resolver_cases.py#L158)

Extraction des sections pour diagnostic:

- parse utilitaire: [pipeline/delivery/export_st_ready_diagnostic_cards.py](../pipeline/delivery/export_st_ready_diagnostic_cards.py#L86)
- issue_fields = Problem/Context/Root cause/Fix/Constraints/Keywords: [pipeline/delivery/export_st_ready_diagnostic_cards.py](../pipeline/delivery/export_st_ready_diagnostic_cards.py#L544)
- resolver_fields = Problem/Context/Resolver signal/Assessment/Candidate PRs/Commit evidence/Constraints: [pipeline/delivery/export_st_ready_diagnostic_cards.py](../pipeline/delivery/export_st_ready_diagnostic_cards.py#L548)

Important pour la detection:

- issue_body est extrait depuis le bloc Technical details du st_ready_text: [pipeline/delivery/export_st_ready_diagnostic_cards.py](../pipeline/delivery/export_st_ready_diagnostic_cards.py#L53)

### 5.2 Detection des patterns techniques (compile, timeout, dma, callback...)

La detection est regex-based via build_pattern_tags:

- fonction: [pipeline/delivery/export_st_ready_diagnostic_cards.py](../pipeline/delivery/export_st_ready_diagnostic_cards.py#L145)
- exemples de mapping:
	- callback -> callback_not_reached: [pipeline/delivery/export_st_ready_diagnostic_cards.py](../pipeline/delivery/export_st_ready_diagnostic_cards.py#L148)
	- timeout|timed out -> timeout: [pipeline/delivery/export_st_ready_diagnostic_cards.py](../pipeline/delivery/export_st_ready_diagnostic_cards.py#L150)
	- block|blocking -> blocking_behavior: [pipeline/delivery/export_st_ready_diagnostic_cards.py](../pipeline/delivery/export_st_ready_diagnostic_cards.py#L151)
	- dma -> dma_path: [pipeline/delivery/export_st_ready_diagnostic_cards.py](../pipeline/delivery/export_st_ready_diagnostic_cards.py#L152)
	- compile|build -> compile_error: [pipeline/delivery/export_st_ready_diagnostic_cards.py](../pipeline/delivery/export_st_ready_diagnostic_cards.py#L153)

Les textes analyses pour les patterns sont cumules dans build_diagnostic_card:

- title
- issue_fields Root cause
- issue_fields Fix
- issue_body (technical details)
- st_ready_text complet issue
- resolver_card_text
- appel: [pipeline/delivery/export_st_ready_diagnostic_cards.py](../pipeline/delivery/export_st_ready_diagnostic_cards.py#L566)

### 5.3 Extraction des versions (comment exact)

Fonction:

- extract_version_tags: [pipeline/delivery/export_st_ready_diagnostic_cards.py](../pipeline/delivery/export_st_ready_diagnostic_cards.py#L168)

Regex utilisees:

- STM32Cube repo + version semver (ex STM32CubeH7 v1.13.0): [pipeline/delivery/export_st_ready_diagnostic_cards.py](../pipeline/delivery/export_st_ready_diagnostic_cards.py#L172)
- CubeMX/CubeIDE + version: [pipeline/delivery/export_st_ready_diagnostic_cards.py](../pipeline/delivery/export_st_ready_diagnostic_cards.py#L174)
- HAL/LL/CMSIS + version: [pipeline/delivery/export_st_ready_diagnostic_cards.py](../pipeline/delivery/export_st_ready_diagnostic_cards.py#L176)

### 5.4 Generation des query_aliases (retrieval-ready)

Fonctions:

- build_query_aliases: [pipeline/delivery/export_st_ready_diagnostic_cards.py](../pipeline/delivery/export_st_ready_diagnostic_cards.py#L218)
- fallbacks generiques: [pipeline/delivery/export_st_ready_diagnostic_cards.py](../pipeline/delivery/export_st_ready_diagnostic_cards.py#L182)

Logique concrete:

1. Cas special HAL_SPI + DMA: [pipeline/delivery/export_st_ready_diagnostic_cards.py](../pipeline/delivery/export_st_ready_diagnostic_cards.py#L229)
2. Si pattern blocage/callback: ajoute "blocking function", "callback not reached", etc.: [pipeline/delivery/export_st_ready_diagnostic_cards.py](../pipeline/delivery/export_st_ready_diagnostic_cards.py#L245)
3. Extrait tailles en bytes dans le texte (ex "2 bytes"): [pipeline/delivery/export_st_ready_diagnostic_cards.py](../pipeline/delivery/export_st_ready_diagnostic_cards.py#L257)
4. Ajoute fallback component/board/API/version/title: [pipeline/delivery/export_st_ready_diagnostic_cards.py](../pipeline/delivery/export_st_ready_diagnostic_cards.py#L262)
5. Dedupe + limite 16: [pipeline/delivery/export_st_ready_diagnostic_cards.py](../pipeline/delivery/export_st_ready_diagnostic_cards.py#L274)

Puis query_anchor_tags fusionne aliases + API + patterns + versions (limite 24):

- [pipeline/delivery/export_st_ready_diagnostic_cards.py](../pipeline/delivery/export_st_ready_diagnostic_cards.py#L600)

### 5.5 likely_causes vs plausible_diagnosis vs hypotheses (diff exacte)

likely_causes:

- source: phrase courte de Root cause (issue_fields) + Assessment + Resolver signal (resolver_fields)
- fonction: [pipeline/delivery/export_st_ready_diagnostic_cards.py](../pipeline/delivery/export_st_ready_diagnostic_cards.py#L444)
- fallback si vide: "Root cause is not explicit...": [pipeline/delivery/export_st_ready_diagnostic_cards.py](../pipeline/delivery/export_st_ready_diagnostic_cards.py#L455)

plausible_diagnosis:

- source: metadata issue (layer/component/issue_kind) + resolution_status + patterns
- fonction: [pipeline/delivery/export_st_ready_diagnostic_cards.py](../pipeline/delivery/export_st_ready_diagnostic_cards.py#L416)
- branche status candidate_fix: [pipeline/delivery/export_st_ready_diagnostic_cards.py](../pipeline/delivery/export_st_ready_diagnostic_cards.py#L433)
- fallback si vide: [pipeline/delivery/export_st_ready_diagnostic_cards.py](../pipeline/delivery/export_st_ready_diagnostic_cards.py#L441)

hypotheses:

- fusion dedupe(plausible_diagnosis + likely_causes)
- fonction: [pipeline/delivery/export_st_ready_diagnostic_cards.py](../pipeline/delivery/export_st_ready_diagnostic_cards.py#L458)
- fallback si vide: "No strong hypothesis yet...": [pipeline/delivery/export_st_ready_diagnostic_cards.py](../pipeline/delivery/export_st_ready_diagnostic_cards.py#L460)

Note importante sur la chaine "resolution_status=candidate_fix, confidence=medium, score=0.":

- le texte vient de Resolver signal dans resolver_card_text
- il est raccourci via clean_signal_sentence -> first_sentence
- first_sentence coupe a la premiere ponctuation [.!?], ce qui peut tronquer un decimal comme 0.8 en 0.
	- [pipeline/delivery/export_st_ready_diagnostic_cards.py](../pipeline/delivery/export_st_ready_diagnostic_cards.py#L20)
	- [pipeline/delivery/export_st_ready_diagnostic_cards.py](../pipeline/delivery/export_st_ready_diagnostic_cards.py#L24)

### 5.6 debug_checks (comment elles sont redigees)

Fonction:

- build_debug_checks: [pipeline/delivery/export_st_ready_diagnostic_cards.py](../pipeline/delivery/export_st_ready_diagnostic_cards.py#L299)

Regles de redaction:

- callback/stuck busy -> instrumentation callbacks + etats READY: [pipeline/delivery/export_st_ready_diagnostic_cards.py](../pipeline/delivery/export_st_ready_diagnostic_cards.py#L305)
- compile_error -> rebuild exact toolchain/version: [pipeline/delivery/export_st_ready_diagnostic_cards.py](../pipeline/delivery/export_st_ready_diagnostic_cards.py#L312)
- timeout -> check timing/clock/interrupt: [pipeline/delivery/export_st_ready_diagnostic_cards.py](../pipeline/delivery/export_st_ready_diagnostic_cards.py#L314)
- si resolver linked_file_paths existe -> check path du fix: [pipeline/delivery/export_st_ready_diagnostic_cards.py](../pipeline/delivery/export_st_ready_diagnostic_cards.py#L316)
- ajoute verification component + check minimal reproducer
- dedupe + limite 5

### 5.7 clarification_questions (comment elles sont redigees)

Fonction:

- build_clarification_questions: [pipeline/delivery/export_st_ready_diagnostic_cards.py](../pipeline/delivery/export_st_ready_diagnostic_cards.py#L326)

Regles:

- toujours demander MCU/board exact
- ajoute question series si mcu_series present
- ajoute question versions si version_tags non vide
- ajoute question component si present
- ajoute question DMA/cache si pattern dma_path/cache_dma: [pipeline/delivery/export_st_ready_diagnostic_cards.py](../pipeline/delivery/export_st_ready_diagnostic_cards.py#L344)
- ajoute question IRQ/callback si pattern interrupt_path/callback: [pipeline/delivery/export_st_ready_diagnostic_cards.py](../pipeline/delivery/export_st_ready_diagnostic_cards.py#L346)
- ajoute demande de reproducer API si api_tags present
- dedupe + limite 6

### 5.8 response_blocks (comment ils sont rediges exactement)

Ce n est pas genere par template externe: c est un mapping direct dans card JSON:

- facts_confirmed = confirmed_facts
- hypotheses = hypotheses (fusion plausible + likely)
- checks = debug_checks

Code exact:

- response_blocks: [pipeline/delivery/export_st_ready_diagnostic_cards.py](../pipeline/delivery/export_st_ready_diagnostic_cards.py#L647)
- response_format fixe: [pipeline/delivery/export_st_ready_diagnostic_cards.py](../pipeline/delivery/export_st_ready_diagnostic_cards.py#L652)
- clarification_questions_required=true: [pipeline/delivery/export_st_ready_diagnostic_cards.py](../pipeline/delivery/export_st_ready_diagnostic_cards.py#L640)

### 5.9 constraints_or_limits et garde-fous

Construction des contraintes:

- fonction: build_constraints: [pipeline/delivery/export_st_ready_diagnostic_cards.py](../pipeline/delivery/export_st_ready_diagnostic_cards.py#L399)
- reprend la phrase issue_fields[Constraints] quand disponible: [pipeline/delivery/export_st_ready_diagnostic_cards.py](../pipeline/delivery/export_st_ready_diagnostic_cards.py#L405)
- ajoute limite rescued issue si rescue_applied=true: [pipeline/delivery/export_st_ready_diagnostic_cards.py](../pipeline/delivery/export_st_ready_diagnostic_cards.py#L408)
- ajoute explicitement la limite si link_confidence low/medium: [pipeline/delivery/export_st_ready_diagnostic_cards.py](../pipeline/delivery/export_st_ready_diagnostic_cards.py#L411)

Interpretation metier de cette limite:

- "la preuve fix n est pas universelle" = un lien existe vers PR/commit, mais pas assez fort pour conclure que la correction est applicable a tous les contextes board/version/integration.

### 5.10 Pourquoi source_types=resolver_case (et pas rescued_issue) pour issue 43

Logique source_types:

- source_types prend rescued_issue seulement si issue_doc.rescue_applied=true
- source_types prend resolver_case si resolver_doc existe
- code: [pipeline/delivery/export_st_ready_diagnostic_cards.py](../pipeline/delivery/export_st_ready_diagnostic_cards.py#L603)

Filtrage amont des issues pour diagnostic:

- par defaut include_all_issues=false, donc les issues non rescued sont exclues: [pipeline/delivery/export_st_ready_diagnostic_cards.py](../pipeline/delivery/export_st_ready_diagnostic_cards.py#L675)

Consequence pour issue 43:

- issue 43 dans issues_json a rescue_applied=false: [datasets/07_delivery/st_ready/issues_json/st_ready_issues_stm32cubeh7.json](../datasets/07_delivery/st_ready/issues_json/st_ready_issues_stm32cubeh7.json#L5887)
- mais resolver case existe pour issue 43: [datasets/07_delivery/st_ready/resolver_cases_json/st_ready_resolver_cases_stm32cubeh7.json](../datasets/07_delivery/st_ready/resolver_cases_json/st_ready_resolver_cases_stm32cubeh7.json#L21)
- donc diagnostic card 43 est resolver-driven, avec source_types=[resolver_case] et resolution_status=candidate_fix: [datasets/07_delivery/st_ready/diagnostic_cards_json/st_ready_diagnostic_cards_stm32cubeh7.json](../datasets/07_delivery/st_ready/diagnostic_cards_json/st_ready_diagnostic_cards_stm32cubeh7.json#L453)

### 5.11 Definition des flux

Flux resolver-driven:

- card construite principalement depuis resolver_doc
- typiquement source_types contient resolver_case
- cas example: issue 43

Flux issue-rescued sans resolver:

- card construite depuis issue_doc rescued, resolver_doc absent
- source_types=rescued_issue et resolution_status=null
- cas example: issue 50


## 6. Exemples concrets champ par champ

### 6.1 Exemple A - issue 43 (resolver-driven)

Resolver case:

- issue_number=43: [datasets/07_delivery/st_ready/resolver_cases_json/st_ready_resolver_cases_stm32cubeh7.json](../datasets/07_delivery/st_ready/resolver_cases_json/st_ready_resolver_cases_stm32cubeh7.json#L21)
- resolution_status=candidate_fix: [datasets/07_delivery/st_ready/resolver_cases_json/st_ready_resolver_cases_stm32cubeh7.json](../datasets/07_delivery/st_ready/resolver_cases_json/st_ready_resolver_cases_stm32cubeh7.json#L44)
- link_confidence=medium: [datasets/07_delivery/st_ready/resolver_cases_json/st_ready_resolver_cases_stm32cubeh7.json](../datasets/07_delivery/st_ready/resolver_cases_json/st_ready_resolver_cases_stm32cubeh7.json#L48)
- link_score=0.8: [datasets/07_delivery/st_ready/resolver_cases_json/st_ready_resolver_cases_stm32cubeh7.json](../datasets/07_delivery/st_ready/resolver_cases_json/st_ready_resolver_cases_stm32cubeh7.json#L49)

Diagnostic card:

- card issue 43: [datasets/07_delivery/st_ready/diagnostic_cards_json/st_ready_diagnostic_cards_stm32cubeh7.json](../datasets/07_delivery/st_ready/diagnostic_cards_json/st_ready_diagnostic_cards_stm32cubeh7.json#L442)
- source_types=[resolver_case]: [datasets/07_delivery/st_ready/diagnostic_cards_json/st_ready_diagnostic_cards_stm32cubeh7.json](../datasets/07_delivery/st_ready/diagnostic_cards_json/st_ready_diagnostic_cards_stm32cubeh7.json#L453)
- response_blocks construits exactement depuis facts/hypotheses/checks: [datasets/07_delivery/st_ready/diagnostic_cards_json/st_ready_diagnostic_cards_stm32cubeh7.json](../datasets/07_delivery/st_ready/diagnostic_cards_json/st_ready_diagnostic_cards_stm32cubeh7.json#L492)
- contrainte explicite "Linked fix evidence is not strong enough...": [datasets/07_delivery/st_ready/diagnostic_cards_json/st_ready_diagnostic_cards_stm32cubeh7.json](../datasets/07_delivery/st_ready/diagnostic_cards_json/st_ready_diagnostic_cards_stm32cubeh7.json#L517)

### 6.2 Exemple B - issue 50 (issue-rescued sans resolver)

Issue source:

- issue 50, rescue_applied=true: [datasets/07_delivery/st_ready/issues_json/st_ready_issues_stm32cubeh7.json](../datasets/07_delivery/st_ready/issues_json/st_ready_issues_stm32cubeh7.json#L5787)
- st_ready_text contient explicitement Problem/Context/Root cause/Fix/Constraints/Keywords

Diagnostic card:

- card issue 50: [datasets/07_delivery/st_ready/diagnostic_cards_json/st_ready_diagnostic_cards_stm32cubeh7.json](../datasets/07_delivery/st_ready/diagnostic_cards_json/st_ready_diagnostic_cards_stm32cubeh7.json#L552)
- source_types=[rescued_issue]: [datasets/07_delivery/st_ready/diagnostic_cards_json/st_ready_diagnostic_cards_stm32cubeh7.json](../datasets/07_delivery/st_ready/diagnostic_cards_json/st_ready_diagnostic_cards_stm32cubeh7.json#L563)
- resolution_status=null (pas de resolver): [datasets/07_delivery/st_ready/diagnostic_cards_json/st_ready_diagnostic_cards_stm32cubeh7.json](../datasets/07_delivery/st_ready/diagnostic_cards_json/st_ready_diagnostic_cards_stm32cubeh7.json#L568)
- patterns detectes (callback_not_reached, dma_path, ...), aliases et checks derives du texte issue

### 6.3 Exemple C - issue 316 (match docs_files_exact)

Resolver case:

- issue 316: [datasets/07_delivery/st_ready/resolver_cases_json/st_ready_resolver_cases_stm32cubeh7.json](../datasets/07_delivery/st_ready/resolver_cases_json/st_ready_resolver_cases_stm32cubeh7.json#L385)
- linked_file_paths inclut README.md via match exact docs_files: [datasets/07_delivery/st_ready/resolver_cases_json/st_ready_resolver_cases_stm32cubeh7.json](../datasets/07_delivery/st_ready/resolver_cases_json/st_ready_resolver_cases_stm32cubeh7.json#L449)
- preuve directe source_match=docs_files_exact sur README.md: [datasets/07_delivery/st_ready/resolver_cases_json/st_ready_resolver_cases_stm32cubeh7.json](../datasets/07_delivery/st_ready/resolver_cases_json/st_ready_resolver_cases_stm32cubeh7.json#L766)

Interpretation:

- docs_files_exact ajoute des metadonnees file_type/component/board et augmente la qualite de contextualisation par rapport a commit_only.


## 7. KPI actuels STM32CubeH7 (preuve de valeur)

Linkage global:

- issues_total = 296
- linked_issues = 4
- link_rate = 0.0135
- source: [data/issue_pr_commit_links_stm32cubeh7_summary.json](../data/issue_pr_commit_links_stm32cubeh7_summary.json#L1)

Resolver export:

- exported_cases = 4
- source: [datasets/07_delivery/st_ready/resolver_cases_json/summary_resolver_cases_stm32cubeh7.json](../datasets/07_delivery/st_ready/resolver_cases_json/summary_resolver_cases_stm32cubeh7.json#L1)

Diagnostic export:

- rescued_issues_considered = 42
- resolver_cases_considered = 4
- exported_cards = 45
- include_all_issues = false
- source: [datasets/07_delivery/st_ready/diagnostic_cards_json/summary_diagnostic_cards_stm32cubeh7.json](../datasets/07_delivery/st_ready/diagnostic_cards_json/summary_diagnostic_cards_stm32cubeh7.json#L1)

Lecture metier:

- resolver conserve la preuve de fix quand elle existe
- diagnostic maintient la couverture quand le fix-link est rare
- garde-fous actifs pour limiter les sur-conclusions


## 8. Commandes utiles pour reproduire

Execution ciblee Resolver Cases:

- python -m pipeline.delivery.export_st_ready_resolver_cases --repo STM32CubeH7

Execution ciblee Diagnostic Cards:

- python -m pipeline.delivery.export_st_ready_diagnostic_cards --repo STM32CubeH7

Execution all repos (automation PowerShell):

- [pipeline_Automation/Generate_Diagnostic_Cards_For_All_Repos.ps1](../pipeline_Automation/Generate_Diagnostic_Cards_For_All_Repos.ps1#L1)

Workflow complet avec export ST-ready:

- python -m pipeline.run_full_workflow --export-st-ready


## 9. Checklist de validation avant publication KB

1. Verifier coherence des summaries (counts input/output).
2. Verifier que chaque Diagnostic Card a un response_blocks complet et exploitable.
3. Verifier que evidence_refs pointe vers issue/PR/commit valides.
4. Verifier que low/medium confidence ajoute bien des limites explicites.
5. Verifier que les alias et pattern_tags couvrent les ancres reelles des requetes user.
6. Verifier la coherence des flux source_types (rescued_issue/resolver_case).


## 10. Resume executif (pour slide)

- Resolver Cases fournissent la preuve technique et la tracabilite du fix.
- Diagnostic Cards transforment cette preuve (ou les signaux issue) en plan de diagnostic actionnable.
- Les champs critiques sont construits par regles explicites, verifiables dans le code et dans les exports.
- En cas de preuve faible, le design force contraintes + clarification, au lieu de presenter un fix comme universel.


## 11. Note SHA (rappel court)

Le SHA n est pas devine, il est lu depuis GitHub API:

- route PR commits: [pipeline/ingestion/github_service.py](../pipeline/ingestion/github_service.py#L308)
- boucle de collecte commits pour PR: [pipeline/ingestion/github_service.py](../pipeline/ingestion/github_service.py#L375)
- lecture sha depuis le resume commit: [pipeline/ingestion/github_service.py](../pipeline/ingestion/github_service.py#L391)
- appel du detail commit par sha: [pipeline/ingestion/github_service.py](../pipeline/ingestion/github_service.py#L333)
- stockage de sha dans payload commit detail: [pipeline/ingestion/github_service.py](../pipeline/ingestion/github_service.py#L347)

Donc: SHA = valeur officielle API GitHub, pas une inference.