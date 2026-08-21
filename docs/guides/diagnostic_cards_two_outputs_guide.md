# Diagnostic Cards H7 - Guide compare des 2 sorties

## 1) Objectif

Ce document explique clairement la difference entre les 2 fichiers suivants:

- `datasets/07_delivery/st_ready/diagnostic_cards_json/st_ready_diagnostic_cards_stm32cubeh7.json`
- `datasets/07_delivery/st_ready/diagnostic_cards_json/st_ready_diagnostic_cards_stm32cubeh7_from_resolver.json`

Il precise:

- lequel est la sortie officielle a consommer
- pourquoi `query_aliases` peut sembler manquant
- comment lire les champs de confiance dans les cartes

---

## 2) Resume executif

- `st_ready_diagnostic_cards_stm32cubeh7.json` est la sortie diagnostic officielle (finale, support-ready).
- `st_ready_diagnostic_cards_stm32cubeh7_from_resolver.json` est une sortie resolver-like (intermediaire/legacy), pas la sortie diagnostic finale.
- `query_aliases` est un champ des diagnostics finaux; il n apparait pas dans `_from_resolver`.

---

## 3) Preuves verifiees (etat actuel)

### 3.1 Sortie officielle et compte

Le fichier summary officiel confirme:

- `output_file`: `.../st_ready_diagnostic_cards_stm32cubeh7.json`
- `format`: `json-array`
- `exported_cards`: `45`

Source:

- `datasets/07_delivery/st_ready/diagnostic_cards_json/summary_diagnostic_cards_stm32cubeh7.json`

### 3.2 Compte de la sortie `_from_resolver`

Le fichier `_from_resolver` contient 18 entrees resolver-style.

### 3.3 Workflow actif

Le workflow principal exporte les diagnostic cards via:

- `pipeline/run_full_workflow.py`
- `pipeline/delivery/export_st_ready_diagnostic_cards.py`

Aucune reference pipeline active a `from_resolver` n a ete trouvee.

---

## 4) Comparaison directe des 2 fichiers

| Aspect | `..._from_resolver.json` | `...stm32cubeh7.json` |
|---|---|---|
| Statut | Intermediaire (resolver-like) | Officiel (diagnostic final) |
| Racine JSON | Objet avec cle `diagnostic_cards` | Tableau JSON racine |
| Nombre d entrees observe | 18 | 45 |
| Template dominant | `st_v1_resolver_case` | `st_v1_diagnostic_card` |
| Champs resolver (`linked_pr_numbers`, `linked_commit_shas`, `files_evidence`, `resolver_card_text`) | Oui | Partiellement derives, mais pas format resolver brut |
| Champs diagnostic (`query_aliases`, `plausible_diagnosis`, `debug_checks`, `possible_workarounds`) | Non | Oui |
| Usage recommande pour persona KB | Non | Oui |

---

## 5) Pourquoi `query_aliases` semble absent

### Cas A - Fichier `_from_resolver`

C est normal: ce fichier ne suit pas le schema diagnostic final. Il suit une logique resolver-case.

### Cas B - Fichier officiel

`query_aliases` existe dans la structure officielle, mais il peut etre vide (`[]`) sur certaines cartes.

Cause:

- generation heuristique/conditionnelle dans `pipeline/delivery/export_st_ready_diagnostic_cards.py`
- alias enrichis surtout quand des patterns techniques clairs sont detectes

---

## 6) Note importante sur la confidence des Diagnostic Cards

Dans les diagnostic cards, il n existe pas de champ/fonction nomme `diagnosis_confidence`.

La confiance exploitee vient de:

- `evidence_strength` cote issue (prioritaire)
- fallback sur `link_confidence` cote resolver

Assignation dans la carte:

- `pipeline/delivery/export_st_ready_diagnostic_cards.py` (champ `evidence_strength` dans `build_diagnostic_card`)

### 6.1 Source prioritaire: `evidence_strength` (issues)

Calcule amont dans:

- `pipeline/enrichment/preprocessing_model.py` (`compute_issue_evidence_strength`)

Regles:

- issue invalide => `low`
- confirmed bug + signaux techniques suffisants => `high`
- sinon si signaux techniques suffisants => `medium`
- sinon => `low`

### 6.2 Source fallback: `link_confidence` (resolver)

Calcule amont dans:

- `pipeline/ingestion/fetch_issue_pr_commit_links.py` (`score_and_confidence`)

Le score depend de:

- PR explicite
- PR merge
- commit significatif (les commits merge-like sont filtres)

Mapping:

- `high` si score >= 0.9
- `medium` si score >= 0.5
- `low` si score > 0
- `none` sinon

Impact pratique dans la carte:

- `evidence_refs` reprend la confidence des refs issue/PR/commit
- si `link_confidence` est `low` ou `medium`, une contrainte de prudence est ajoutee

---

## 7) Recommandation de consommation

Pour la KB persona et les usages support:

- utiliser `datasets/07_delivery/st_ready/diagnostic_cards_json/st_ready_diagnostic_cards_stm32cubeh7.json`

Ne pas utiliser comme source principale diagnostic:

- `datasets/07_delivery/st_ready/diagnostic_cards_json/st_ready_diagnostic_cards_stm32cubeh7_from_resolver.json`

Ce dernier reste utile uniquement comme artefact d analyse resolver.

---

## 8) Checklist avant upload

1. Verifier le summary officiel du repo cible.
2. Verifier que la sortie cible contient bien les champs diagnostics (`query_aliases`, `debug_checks`, `plausible_diagnosis`, `possible_workarounds`).
3. Verifier la presence de `evidence_refs` pour la tracabilite.
4. Accepter que `query_aliases` puisse etre vide sur une partie des cartes (comportement attendu avec heuristiques actuelles).

---

## 9) Ameliorations conseillees

1. Ajouter un fallback d alias si `query_aliases` est vide (titre + composant + API anchors).
2. Ajouter un indicateur de couverture alias dans les summary diagnostics.
3. Ajouter un garde-fou de validation si trop de cartes ont `query_aliases = []`.
4. Renommer/deprecier les artefacts `_from_resolver` pour eviter les confusions de livraison.

---

## 10) Conclusion

Les 2 fichiers ne representent pas le meme niveau de transformation:

- `_from_resolver`: signal de resolution (resolver-centric)
- `st_ready_diagnostic_cards_stm32cubeh7.json`: carte diagnostic finale (support-centric)

Pour les usages operationnels (persona KB, support, quality index), la reference est le fichier diagnostic officiel.
