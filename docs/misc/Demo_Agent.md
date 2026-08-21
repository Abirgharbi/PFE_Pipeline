# Demo Reelle - STM32Cube Preprocessing Agent

## Objectif

Cette demo montre que l'agent n'est pas un assistant generique: il sait lire les artefacts reels du pipeline STM32Cube, les interpreter, et produire une sortie exploitable pour la documentation, l'evaluation et la preparation d'un RAG.

## Format recommande

- Duree: 10 a 15 minutes
- Mode: ouvrir l'agent STM32Cube Preprocessing Agent dans VS Code
- Resultat attendu: montrer 3 usages complementaires des skills

## Fichiers a garder ouverts

- `.github/agents/STM32CubePreprocessing.agent.md`
- `.github/skills/analyze-stats/SKILL.md`
- `.github/skills/document-json-schema/SKILL.md`
- `.github/skills/chunking-strategies/SKILL.md`
- `data/docs_issues_stm32cubeh7_v2.json`
- `data/docs_files_stm32cubeh7_v2.json`
- `data/chunks_issues_stm32cubeh7_v2.json`

## Demo 1 - Montrer la comprehension metier d'un document V2

### Artefact reel utilise

Source: `data/docs_issues_stm32cubeh7_v2.json`

Objet reel a montrer: `stm32cubeh7-issue-339`

Extrait utile:

```json
{
  "id": "stm32cubeh7-issue-339",
  "repo": "STM32CubeH7",
  "component": "UART",
  "issue_number": 339,
  "issue_title": "[Bug]: USART with a single line",
  "state": "open",
  "is_confirmed_bug": true,
  "is_valid": true,
  "layer": "CubeMX",
  "severity": "medium",
  "issue_kind": "bug_report"
}
```

### Prompt a copier dans l'agent

```text
Analyse cet objet provenant de docs_issues_stm32cubeh7_v2.json.
Explique en termes STM32Cube ce que signifie chaque champ metier important, puis donne:
1. un resume fonctionnel de l'issue,
2. pourquoi is_valid=true est coherent ici,
3. comment ce document peut etre exploite dans un pipeline RAG technique.

Objet:
{
  "id": "stm32cubeh7-issue-339",
  "repo": "STM32CubeH7",
  "component": "UART",
  "issue_number": 339,
  "issue_title": "[Bug]: USART with a single line",
  "state": "open",
  "is_confirmed_bug": true,
  "is_valid": true,
  "layer": "CubeMX",
  "severity": "medium",
  "issue_kind": "bug_report"
}
```

### Valeur a verbaliser

- L'agent ne fait pas qu'expliquer du JSON.
- Il reconnecte les champs a la logique STM32Cube: couche logicielle, severite, validite, usage RAG.
- Il transforme un document technique en connaissance interpretable.

## Demo 2 - Montrer le skill document-json-schema

### Artefact reel utilise

Source: `data/docs_files_stm32cubeh7_v2.json`

Objet reel a montrer: `stm32cubeh7-file-3796368010915485190`

Extrait utile:

```json
{
  "id": "stm32cubeh7-file-3796368010915485190",
  "source_kind": "file",
  "repo": "STM32CubeH7",
  "path": "README.md",
  "file_type": "root_readme",
  "board": "NUCLEO-H7A3ZI",
  "component": "USB",
  "example_name": null,
  "ingest_version": "v2.0",
  "is_valid": true
}
```

### Prompt a copier dans l'agent

```text
A partir de cet exemple provenant de docs_files_stm32cubeh7_v2.json, genere une mini documentation de schema orientee projet STM32Cube.
Je veux un resultat sous forme de tableau Markdown avec:
- champ,
- type probable,
- signification dans le pipeline,
- obligatoire ou optionnel.

Exemple:
{
  "id": "stm32cubeh7-file-3796368010915485190",
  "source_kind": "file",
  "repo": "STM32CubeH7",
  "path": "README.md",
  "file_type": "root_readme",
  "board": "NUCLEO-H7A3ZI",
  "component": "USB",
  "example_name": null,
  "ingest_version": "v2.0",
  "is_valid": true
}
```

### Valeur a verbaliser

- Le skill document-json-schema reduit l'ambiguite entre data engineering, evaluation et integration RAG.
- Il permet de formaliser rapidement un contrat de donnees lisible.

## Demo 3 - Montrer la valeur du chunking sur un cas reel

### Artefacts reels utilises

Source 1: `data/docs_issues_stm32cubeh7_v2.json`

Issue reelle: `stm32cubeh7-issue-338`

Source 2: `data/chunks_issues_stm32cubeh7_v2.json`

Chunks reels: `stm32cubeh7-issue-338-0` et `stm32cubeh7-issue-338-1`

Constat reel: l'issue ADC avec DMA a ete coupee en 2 chunks, un pour la description, un pour les commentaires.

### Prompt a copier dans l'agent

```text
Compare ce document source et ses chunks V2.
Explique si la strategie de chunking est adaptee a un usage RAG technique STM32Cube.
Je veux:
1. les benefices du decoupage actuel,
2. les risques potentiels de perte de contexte,
3. une recommandation concrete entre garder ce decoupage ou le modifier.

Document source:
- issue_title: [Bug]: CubeMx allows an invalid combination of parameters for ADC with DMA
- layer: CubeMX
- component: ADC
- severity: low
- issue_kind: bug_report

Chunk 0 resume:
- contient le Bug Summary, la Detailed Description et l'environnement

Chunk 1 resume:
- contient les commentaires et la reference interne ST
```

### Valeur a verbaliser

- Ici on montre que le chunking n'est pas juste un detail technique.
- L'agent peut juger si la segmentation preserve la recuperation d'information utile.
- C'est directement lie a la qualite future du RAG.

## Demo 4 - Montrer le skill analyze-stats sur la vraie pipeline

### Commande a lancer avant ou pendant la reunion

```bash
python -m pipeline.evaluation.test_stats_issues_v2
```

### Prompt a copier apres execution

```text
Analyse cette sortie de test_stats_issues_v2.py.
Je veux une synthese orientee evaluation qualite avec:
1. les distributions importantes,
2. les biais potentiels de preprocessing,
3. les 3 actions prioritaires a mener.

Voici la sortie console:
[COLLER ICI LA SORTIE]
```

### Valeur a verbaliser

- Le skill analyze-stats convertit un simple affichage console en decisions actionnables.
- On passe de la mesure brute a l'interpretation qualite.

## Slide de conclusion

Message final a dire:

> Le pipeline produit des artefacts. L'agent, lui, transforme ces artefacts en comprehension, en documentation et en recommandations. C'est cette couche d'exploitation intelligente qui apporte la valeur.

## Version tres courte si tu n'as que 5 minutes

1. Demo 1 pour montrer la comprehension metier.
2. Demo 2 pour montrer la generation de schema.
3. Demo 3 pour montrer l'impact sur la qualite RAG.

## Resultat attendu en reunion

- Les personnes techniques voient que l'agent comprend la structure du pipeline.
- Les encadrants voient un gain concret en analyse et en documentation.
- La valeur des skills apparait comme modulaire, specialisee et directement exploitable.


________________________________________

Version claire et facile à présenter (prête pour le project overview)

1. Objectif global de la Delivery  
La Delivery transforme des données techniques brutes en connaissances directement utilisables dans une KB support.  
L’objectif est triple :  
- Donner des réponses actionnables pour le troubleshooting.  
- Garder une traçabilité complète vers GitHub.  
- Fournir un format stable pour l’ingestion côté ST.

2. Pourquoi on en avait besoin  
On a observé un écart entre la donnée disponible et l’usage réel support :  
- Les issues brutes expliquent le problème, mais ne donnent pas un parcours de diagnostic clair.  
- Les utilisateurs posent des questions orientées symptôme, pas orientées numéro d’issue.  
- Les résultats pouvaient être corrects sur la source, mais faibles sur les actions concrètes à faire.  
- Sans standard de delivery, les liens et labels deviennent incohérents entre exports.  
Conclusion : le contenu existait, mais la couche opérationnelle manquait.

3. Resolver Cases : ce qu’on a construit et comment  
Un Resolver Case répond à : existe-t-il une piste de fix crédible et vérifiable ?  
Construction :  
- On part d’une issue.  
- On relie cette issue aux PR, commits et fichiers modifiés quand ils existent.  
- On calcule un niveau de confiance et un statut de résolution.  
- On génère une synthèse orientée décision technique.  
Exemple utile : USART fails to compile.  
Le Resolver Case montre la chaîne issue -> PR -> commit -> fichier impacté, avec un statut candidate fix.  
Valeur : on passe d’un fil GitHub à une piste de correction exploitable.

4. Diagnostic Cards : ce qu’on a construit et comment  
Une Diagnostic Card répond à : que dois-je vérifier maintenant sur mon cas terrain ?  
Construction :  
- On structure le contenu autour des symptômes.  
- On ajoute causes probables, checks techniques, workarounds, contraintes, preuves.  
- On produit une carte lisible comme checklist de debug.  
Exemple utile : USB HS avec ULPI ne démarre pas.  
La carte guide les vérifications clock, reset PHY, pinmux, séquence init, DMA/cache.  
Valeur : l’ingénieur gagne un plan d’action concret, pas seulement un historique de discussion.

5. Exports ST-ready : rôle et nécessité  
Les exports ST-ready sont la couche de standardisation finale.  
Ils assurent :  
- Un format homogène prêt à l’ingestion KB.  
- Des champs de lien et label cohérents.  
- Une séparation claire des objets selon leur usage : résolution, diagnostic, contenu général.  
- Une traçabilité entre la réponse affichée et la source technique d’origine.  
Valeur : ingestion plus robuste, moins d’erreurs de parsing, meilleure qualité de restitution.

6. Message clé à dire en conclusion  
Nous n’avons pas seulement ajouté des artefacts.  
Nous avons ajouté trois niveaux de valeur complémentaires :  
- Resolver Cases : transformer des signaux de code en pistes de fix fiables.  
- Diagnostic Cards : transformer des symptômes en plan de debug actionnable.  
- Exports ST-ready : garantir une ingestion robuste, cohérente et traçable.

Version courte à dire à l’oral (30 secondes)  
La Delivery comble le gap entre données GitHub et usage support réel. Les Resolver Cases donnent des pistes de fix vérifiables, les Diagnostic Cards donnent une checklist de diagnostic immédiatement utilisable, et les exports ST-ready garantissent une ingestion stable et traçable dans la KB ST.
___________________________________________________
Tu peux présenter la partie Delivery avec une narration plus forte, orientée problème puis solution.

**1) Objectif global de la Delivery**
La Delivery a été créée pour transformer des données techniques brutes en connaissances directement utilisables par une KB de support.  
Le but n’était pas seulement d’exporter du JSON, mais de produire des contenus:
1. actionnables pour le troubleshooting,
2. traçables vers GitHub,
3. suffisamment structurés pour une ingestion stable côté ST.

**2) Pourquoi on en avait besoin**
On a identifié un vrai gap entre données disponibles et usage support:
1. Les issues brutes donnent de l’information, mais pas un parcours de diagnostic.
2. Les questions utilisateurs sont souvent symptom-driven, par exemple USB HS ne démarre pas, pas issue-driven.
3. Les réponses de récupération étaient parfois correctes sur la source, mais faibles sur l’action concrète.
4. Sans standard de livraison, les liens et labels deviennent incohérents selon les exports.

En résumé: le corpus existait, mais il manquait la couche opérationnelle pour aider un ingénieur à décider quoi tester ensuite.

**3) Comment les Resolver Cases ont été construits**
Les Resolver Cases répondent à la question: y a-t-il une piste de fix crédible et vérifiable ?
Leur construction suit une logique de preuve:
1. Point de départ: une issue.
2. Enrichissement avec ses liens PR/commit quand ils existent.
3. Qualification du niveau de confiance avec un statut de résolution.
4. Ajout de l’impact technique via fichiers touchés et modules concernés.
5. Génération d’un texte de synthèse orienté résolution.

Exemple utile:
Issue USART fails to compile.  
Le Resolver Case montre le PR lié, le commit associé, le fichier modifié, puis classe le cas comme candidate fix.  
Résultat: on passe de simple discussion GitHub à une piste de correction exploitable.

**4) Comment les Diagnostic Cards ont été construites**
Les Diagnostic Cards répondent à la question: que dois-je vérifier maintenant sur mon cas terrain ?
Elles sont construites pour le raisonnement de debug:
1. Symptômes observables.
2. Causes probables.
3. Checks techniques ordonnés.
4. Workarounds possibles.
5. Contraintes et limites.
6. Références de preuve.

Exemple utile:
USB HS avec ULPI ne démarre pas.  
La carte structure les vérifications clock, reset PHY, pinmux, init sequence, DMA/cache.  
Résultat: l’utilisateur gagne une checklist concrète au lieu d’un long fil d’issue difficile à exploiter.

**5) Rôle des exports ST-ready**
Les exports ST-ready sont la couche de standardisation finale:
1. Format de sortie stable et homogène pour ingestion KB.
2. Champs de lien et de label cohérents.
3. Séparation claire des objets selon leur usage: résolution, diagnostic, contenu général.
4. Traçabilité maintenue entre carte affichée et source technique d’origine.

**6) Message clé à mettre dans la présentation**
Nous n’avons pas juste ajouté des artefacts.  
Nous avons ajouté trois niveaux complémentaires de valeur:
1. Resolver Cases: transformer des signaux de code en pistes de fix fiables.
2. Diagnostic Cards: transformer des symptômes en plan de debug actionnable.
3. ST-ready exports: garantir une ingestion robuste, cohérente et traçable.

Si tu veux, je peux te préparer une version slide par slide en format 6 diapositives avec texte court oral-ready.
_________________________________________
Overview of the ST solution of AI persona
Overview of the knowledge base construction process
Short demo
Status of the work
Objective of the project
Current progress
What is still to do
Q&A and discussion 
______________________
Oui, une vue sommaire et comment cela t'a servi à mieux comprendre comment fonctionne la solution ST