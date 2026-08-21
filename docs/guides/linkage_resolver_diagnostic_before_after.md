# Linkage / Resolver / Diagnostic Cards - Avant vs Apres

## 1) Objectif
Documenter:
- ce qui posait probleme avant,
- les modifications implementees,
- pourquoi ces modifications ont ete faites,
- la valeur ajoutee attendue,
- l'etat actuel observe sur STM32CubeH7,
- les prochaines etapes d'execution et de validation.

## 2) Perimetre
Cette note couvre la chaine suivante:
1. regeneration des liens issue/PR/commit,
2. regeneration des resolver cases ST-ready,
3. regeneration des diagnostic cards ST-ready,
4. audit de coherence et suivi des cas unlinked.

Scripts principaux:
- pipeline/ingestion/fetch_issue_pr_commit_links.py
- pipeline/delivery/export_st_ready_resolver_cases.py
- pipeline/delivery/export_st_ready_diagnostic_cards.py
- pipeline/evaluation/run_linkage_delivery_audit.py

## 3) Avant (problemes identifies)

### A. Des liens utiles passaient sous le radar
Cas typique: un commit mentionne un issue, mais sans PR explicite ou sans pattern strict.
Resultat: le cas restait unlinked alors qu'il existait un signal de correction.

### B. Historique merge-heavy sous-evalue
Certains historiques contiennent surtout des merges; le signal de correction peut etre reel mais moins visible.
Resultat: risque de sous-estimer la qualite du lien vers un correctif.

### C. Niveau de preuve pas assez explicite
Les consumers aval avaient besoin d'une distinction claire entre:
- candidate_fix,
- commit_only_candidate,
- reference_only,
- unlinked.

Sans cette distinction, les cartes resolver/diagnostic pouvaient paraitre trop affirmatives ou trop vagues.

### D. Tracabilite fichiers changes insuffisante
Il manquait une vue claire des fichiers reellement touches pour justifier une action technique.

### E. Cartes diagnostic insuffisamment robustes pour nouveaux bugs
Il fallait renforcer:
- fallback aliases/query anchors,
- tags techniques et tags de version,
- format de reponse stable en 3 blocs,
- questions de clarification obligatoires.

## 4) Modifications implementees

### 4.1 Ingestion links (issue/PR/commit)
Fichier: pipeline/ingestion/fetch_issue_pr_commit_links.py

Modifs:
- extension des signaux commit message (issue, issue 123, /issues/123),
- extraction des issue IDs via regex dediees,
- garde-fou pour eviter le bruit des references #123 hors contexte,
- scoring et statut enrichis deja en place (commit_only_candidate, merged_pr_with_file_evidence).

Pourquoi:
- reduire les faux unlinked,
- mieux capter les corrections portees au niveau commit.

### 4.2 Export resolver cases
Fichier: pipeline/delivery/export_st_ready_resolver_cases.py

Modifs:
- propagation explicite du niveau de preuve (dont commit_only_candidate),
- propagation des signaux merged_pr_with_file_evidence,
- enrichissement files_evidence (fichiers changes, module, score, match docs).

Pourquoi:
- fournir une carte resolver plus actionnable,
- rendre explicite la qualite de preuve et le scope technique.

### 4.3 Export diagnostic cards
Fichier: pipeline/delivery/export_st_ready_diagnostic_cards.py

Modifs prioritaires implementees:
- fallback query aliases (meme quand peu d'aliases explicites),
- extraction et propagation de version_tags,
- ajout de query_anchor_tags,
- clarification_questions_required = true,
- generation de clarification_questions,
- format de reponse structure:
  - facts_confirmed,
  - hypotheses,
  - checks,
- ajout de response_format et response_blocks dans la carte.

Pourquoi:
- augmenter la robustesse sur les bugs nouveaux,
- forcer une reponse plus sure, explicable et orientee triage.

### 4.4 Validation schema
Fichier: shared/schemas/issue_pr_commit_links.schema.json

Modif:
- enum resolution_status inclut commit_only_candidate.

Pourquoi:
- aligner contrat de donnees et generation.

### 4.5 Batch execution + audit
Nouveau fichier: pipeline/evaluation/run_linkage_delivery_audit.py

Fonctions:
- export resolver + diagnostic pour tous les repos,
- validation schema des fichiers links,
- verification coherence summary vs payload,
- audit des cas unlinked (breakdown des raisons + echantillons).

Sorties:
- datasets/06_eval_outputs/linkage_delivery_batch_report.json
- datasets/06_eval_outputs/linkage_delivery_batch_report.md
- datasets/06_eval_outputs/unlinked_audit_<repo>.json
- datasets/06_eval_outputs/unlinked_audit_<repo>.md

## 5) Apres (etat observe sur STM32CubeH7)

Source: data/issue_pr_commit_links_stm32cubeh7_summary.json
- issues_total: 296
- linked_issues: 4
- unlinked_issues: 292
- link_rate: 0.0135
- status: 4 candidate_fix, 0 merged_fix, 0 commit_only_candidate, 0 reference_only

Source: datasets/07_delivery/st_ready/resolver_cases_json/summary_resolver_cases_stm32cubeh7.json
- total_cases_in_input: 4
- exported_cases: 4
- status_breakdown: 4 candidate_fix

Source: datasets/07_delivery/st_ready/diagnostic_cards_json/summary_diagnostic_cards_stm32cubeh7.json
- rescued_issues_considered: 42
- resolver_cases_considered: 4
- exported_cards: 45

Interpretation:
- la chaine est fonctionnelle et enrichie,
- la nouvelle logique est active,
- mais sur le snapshot H7 actuel, commit_only_candidate et merged_pr_with_file_evidence restent nuls,
- le gisement principal reste les 292 unlinked a analyser/ameliorer.

## 6) Exemples simples

### Exemple 1 - candidate_fix clair
Issue 43 (USART fails to compile):
- PR liee,
- commit technique explicite,
- resolver_status = candidate_fix,
- files_evidence montre le fichier HAL modifie.

Valeur:
- on peut tracer le probleme jusqu'au fichier impacte et proposer un triage concret.

### Exemple 2 - merge-like visible
Issue 181:
- evidence contient un commit merge-like dans l'historique,
- la trace est conservee au lieu d'etre perdue.

Valeur:
- meilleure lecture de la qualite de preuve et des limites d'interpretation.

## 7) Pourquoi ces modifs etaient necessaires
1. Eviter de perdre des signaux de correction reels.
2. Mieux qualifier le niveau de confiance avant recommandation.
3. Donner une trace technique exploitable (fichiers touches).
4. Standardiser la reponse diagnostic pour limiter l'hallucination et mieux cadrer le support.
5. Industrialiser le suivi avec un batch + audit reproductible.

## 8) Prochaines etapes recommandees

### Etape 1 - Regenerer links
python -m pipeline.ingestion.fetch_issue_pr_commit_links

### Etape 2 - Lancer batch export + audit tous repos
python -m pipeline.evaluation.run_linkage_delivery_audit --audit-repo STM32CubeH7

### Etape 3 - Verifier rapports
- datasets/06_eval_outputs/linkage_delivery_batch_report.md
- datasets/06_eval_outputs/unlinked_audit_stm32cubeh7.md

### Etape 4 - Cible corrective courte
- traiter les raisons dominantes dans unlinked_audit,
- enrichir encore les aliases/version anchors pour categories dominantes,
- rerun batch et comparer les deltas.

### Etape 5 - Cible corrective continue
- garder le format reponse facts/hypotheses/checks,
- maintenir les clarification questions obligatoires,
- monitorer impact sur runs live (generic/exception/useful).

## 9) Critere de succes
- baisse du volume unlinked,
- apparition de cas commit_only_candidate ou merged_pr_with_file_evidence quand justifie,
- cartes plus stables et exploitables en triage,
- meilleure coherence entre summaries et payloads exportes.
