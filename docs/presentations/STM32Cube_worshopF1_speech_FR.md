# Speech complet (FR) — STM32Cube_worshopF1.pptx
## Présentation en ligne — script de l'orateur

> Note méthodologique : ce speech a été reconstitué à partir des diagrammes sources de la présentation (`docs/diagrams/presentation/*.drawio`), du script de mise à jour du deck (`docs/scripts/update_stm32cube_workshopf1_pptx.py`) et des guides d'évaluation existants (`docs/presentations/evaluation_slides_formulas_speaker_guide.md`, `docs/presentations/presentation_evaluation_protocol_benchmark_slides.md`). L'ordre suit la narration logique du pipeline (vue d'ensemble → flux de données → échelle → delivery/KB → Alfred Vision → automatisation CI/CD → évaluation → conclusion). Si l'ordre réel de vos slides diffère légèrement, les blocs ci-dessous restent réutilisables tels quels : dites-moi l'ordre exact et je réajuste le mapping section/slide.

**Durée cible suggérée** : 20–25 minutes de speech + 5–10 minutes de questions.
**Conseil présentation en ligne** : partagez l'écran avant de commencer à parler, vérifiez que le mode présentateur n'affiche pas vos notes aux autres, et marquez une courte pause après chaque section pour laisser la place aux questions dans le chat.

---

## 0. Introduction et accroche (1–2 min)

*(Slide de titre)*

Bonjour à tous, merci d'être présents pour cet atelier sur le pipeline de prétraitement STM32Cube.

Aujourd'hui, je vais vous présenter un projet qui répond à un problème très concret : comment transformer des milliers d'issues GitHub, de pull requests, de commits et de fichiers techniques dispersés sur les dépôts STMicroelectronics, en une base de connaissances fiable, exploitable par un assistant conversationnel pour répondre aux questions techniques des utilisateurs STM32Cube.

Le fil conducteur de cette présentation est simple : je vais vous montrer, étape par étape, comment on part d'une donnée brute et bruitée sur GitHub, jusqu'à une réponse fiable et traçable donnée à un ingénieur qui rencontre un bug sur sa carte STM32.

Je vais structurer mon intervention en quatre grandes parties :
1. Le contexte et les objectifs du projet,
2. L'architecture du pipeline de bout en bout,
3. L'automatisation et la mise à jour continue de la base de connaissances,
4. L'évaluation de la qualité et les résultats obtenus.

---

## 1. Contexte et objectifs (2 min)

*(Slide contexte / objectifs)*

Avant d'entrer dans le détail technique, mettons-nous d'accord sur le point de départ.

Historiquement, la connaissance de support STM32 était éclatée : des issues GitHub, des pull requests, des commits, des fichiers README, des notes de version, des exemples de code — le tout hétérogène, avec des formats différents, des liens faibles entre les documents, et une qualité technique inégale. Sans structuration, la qualité de recherche et la cohérence des réponses restaient instables.

Ce que nous faisons aujourd'hui, c'est construire un pipeline de bout en bout qui transforme ces signaux GitHub bruts en preuves de support fiables. Concrètement, cela veut dire :

- Générer des artefacts de support intelligents : des **cas de résolution** qui tracent la correction d'un bug depuis l'issue jusqu'au commit, et des **fiches de diagnostic** qui structurent la logique de dépannage pour l'assistant.
- Exporter ces artefacts dans un format prêt à être ingéré par l'outil ST, ce qu'on appelle le format **ST-ready**.
- Évaluer en continu, en offline et en ligne, et régénérer les artefacts dès qu'un écart de qualité est détecté.

Pourquoi ce projet compte : on réduit les réponses génériques et peu utiles en support, on augmente la traçabilité technique — chaque réponse peut être reliée à une preuve — et on rend le comportement de l'assistant plus stable, plus explicable, et prêt pour la production.

Aujourd'hui, la base de connaissances est opérationnelle mais continue de s'améliorer par cycles itératifs. La priorité n'est pas seulement d'augmenter un score, mais d'obtenir un comportement robuste, auditable et reproductible.

---

## 1bis. Le vrai problème de départ : le temps perdu à analyser manuellement les issues (2–3 min)

*(Slide problématique)*

Je veux m'arrêter un instant sur le problème concret qui justifie tout ce projet, parce que c'est le point de départ métier, pas seulement une contrainte technique.

Aujourd'hui, un ingénieur STM32 — interne à ST ou client — qui rencontre un bug firmware doit **parcourir manuellement** les ressources disponibles pour trouver une réponse. Et ce processus manuel souffre de quatre limitations majeures qui font perdre énormément de temps.

**Premièrement, le volume et la dispersion.** Les données sont réparties sur plus de **200 dépôts GitHub**, ce qui représente des milliers d'issues, des centaines de pull requests et des dizaines de milliers de fichiers source. Chercher l'information pertinente revient littéralement à chercher une aiguille dans une botte de foin numérique.

**Deuxièmement, le bruit et l'hétérogénéité.** Le contenu des issues mélange du texte technique utile avec énormément de bruit : templates vides, messages automatiques de bots GitHub, discussions hors-sujet, doublons, markdown mal formé. Et côté fichiers, certains contiennent jusqu'à **30 % de licence** dans le texte, et les headers CMSIS dépassent **1,7 Mo** de définitions bit-à-bit qui n'apportent rien au diagnostic. Un ingénieur qui lit ça manuellement perd un temps considérable avant même d'atteindre l'information utile.

**Troisièmement, la fragmentation des connaissances.** Résoudre un bug implique souvent de recouper une issue, la discussion d'une pull request, un commit dans un sous-dépôt différent, et une note de version qui documente le correctif. Ces liens ne sont pas toujours explicites dans GitHub : il faut les reconstituer à la main, ce qui est une investigation manuelle fastidieuse.

**Quatrièmement, l'opacité du contenu visuel.** De nombreuses issues contiennent des captures d'écran — erreurs STM32CubeIDE, oscillogrammes, configurations CubeMX, schémas de câblage — qui portent une information de diagnostic critique, mais qui sont **invisibles** pour une recherche textuelle classique. C'est exactement le problème qu'on a résolu avec Alfred Vision, dont je parlerai plus loin.

*Et ce n'est pas qu'un problème de confort :* avec les canaux de support existants, le temps de réponse va **de 48 heures à 2 semaines**, ce qui bloque concrètement l'avancement du développement client. Les alternatives existantes ne suffisent pas non plus : la recherche GitHub native ne filtre ni par composant, ni par sévérité, ni par couche logicielle, et l'ingénieur doit parcourir 50 issues ou plus sans garantie de trouver la bonne ; Alfred générique donne des conseils génériques sans accès aux issues spécifiques ; Stack Overflow n'est pas spécifique à ST et n'a pas de traçabilité vers les correctifs officiels ; la documentation PDF n'est pas indexable et ses figures restent opaques.

*Le chiffre à retenir :* sur un benchmark de 20 questions techniques couvrant 5 séries MCU, Alfred générique obtient un score de **116/200, soit 58 %**, contre **161/200, soit 80,5 %** pour notre solution avec base de connaissances — un **gain de +39 %** en pertinence, en actionnabilité et en traçabilité.

*Ce que je dis à l'oral :* "Ce n'est pas un problème abstrait : c'est du temps d'ingénieur perdu, chaque jour, à recouper manuellement des issues, des PR, des commits et des captures d'écran dispersés sur plus de 200 dépôts. Notre pipeline ne remplace pas l'expertise humaine, il élimine ce temps de recherche manuelle pour se concentrer directement sur le diagnostic."

---

## 2. Vue d'ensemble du pipeline — architecture de bout en bout (3–4 min)

*(Slide "Pipeline Overview — End-to-End Architecture")*

Voici la vue d'ensemble de l'architecture. On part de la source, à gauche, jusqu'à la réponse client, à droite.

La source, c'est GitHub, avec les dépôts STMicroelectronics : STM32CubeH7, STM32CubeF4, STM32CubeH5, STM32CubeU5, STM32CubeWL, et leurs sous-dépôts — pilotes HAL, CMSIS, BSP.

Le pipeline se décompose en sept étapes :

**Étape 1 — Ingestion.** On récupère les issues et leurs commentaires, les pull requests, les commits, les liens issue-PR-commit, les fichiers du dépôt (README, notes de version, exemples), et on fait une synchronisation locale des dépôts.

**Étape 2 — Cleaning.** On normalise les champs, on filtre les contenus invalides, on déduplique, on structure les métadonnées.

**Étape 3 — Enrichment V2.** C'est ici qu'on ajoute de l'intelligence : classification du type d'issue, scoring de sévérité, détection de la carte et du composant concernés, détection de la couche logicielle — HAL, BSP, CMSIS —, extraction de mots-clés.

**Étape 4 — Similarity.** On calcule des vecteurs TF-IDF et une similarité cosinus pour lier les issues entre elles — le champ `related_issue_ids` — et détecter des liens inter-dépôts.

**Étape 5 — Chunking V2.** On découpe les documents pour l'évaluation offline, avec différentes stratégies : découpage par paragraphe, par section, avec des tailles bornées et une stratégie de recouvrement. J'y reviendrai dans la partie évaluation.

**Étape 6 — Evaluation.** Des scripts de statistiques, des tests de recherche TF-IDF, une validation de schéma, des métriques de qualité — c'est notre porte de qualité avant publication.

**Étape 7 — ST-Ready Delivery.** On génère les fichiers Issues JSON, Files JSON, Resolver Cases, Diagnostic Cards, et on enrichit les images avec Alfred.

Le tout est ensuite uploadé vers la base de connaissances **ST AI Bridge, KB numéro 793**, qui alimente la persona **ST GitHub Analyzer**, le chatbot final vu par l'utilisateur.

Un point important à retenir : ce pipeline est actif sur cinq séries — H7, F4, H5, U5, WL — plus les dépôts pilotes HAL, CMSIS et BSP associés à chaque série.

---

## 3. Flux de données : de la source à la réponse client (2–3 min)

*(Slide "Data Flow: From GitHub to Customer Answer")*

Pour rendre ça plus concret, suivons le parcours complet d'une donnée.

En haut, quatre types de sources : les issues GitHub — questions et rapports de bug —, les pull requests — corrections de code —, les commits — preuves de changement —, et les fichiers du dépôt — README, documentation, BSP.

Ces quatre flux entrent dans le pipeline de prétraitement : nettoyage, enrichissement, liaison, découpage, validation.

En sortie, quatre familles d'artefacts de livraison : les fiches d'issues — des questions-réponses structurées —, la documentation de fichiers — référence technique —, les cas de résolution — traçabilité de correction —, et les fiches de diagnostic — analyse de panne.

Ces quatre artefacts remontent vers la base de connaissances ST AI Bridge, numéro 793, qui fait une recherche hybride, sémantique et plein texte.

Et en bas de la chaîne, l'utilisateur final : un ingénieur qui tape par exemple *"le bus I2C sur STM32F446 se bloque de façon aléatoire, le flag busy reste actif"* — et c'est cette chaîne complète, de la source brute jusqu'à cette question, qui doit produire une réponse pertinente et sourcée.

---

## 4. Passage à l'échelle : couverture des séries (2 min)

*(Slide "STM32Cube KB Coverage — 5 Series, 47 Repos")*

Ce pipeline n'est pas un prototype limité à une seule série. Voici l'échelle réelle du projet.

- **STM32H7** : 12 dépôts, environ 500 issues, 3000 fichiers, 100 cas de résolution — c'est notre série pilote.
- **STM32F4** : 16 dépôts, environ 800 issues, 5400 fichiers — c'est la série la plus volumineuse.
- **STM32H5** : 6 dépôts, environ 200 issues — la série la plus récente.
- **STM32U5** : 8 dépôts, environ 350 issues — la gamme ultra basse consommation.
- **STM32WL** : 5 dépôts, environ 150 issues — la gamme LoRa et LPWAN.

Au total, cela représente **47 dépôts**, **20 datasources** dans la base de connaissances — quatre types d'artefacts multipliés par cinq séries — et environ **14 400 documents indexés**, interrogeables par recherche hybride sémantique et plein texte.

---

## 5. Livraison ST-Ready et upload vers la base de connaissances (3 min)

*(Slide "ST-Ready Delivery & KB Upload Architecture")*

Entrons maintenant dans le détail de la livraison, l'étape charnière entre notre pipeline et l'outil ST.

Pour chaque série, on génère quatre familles de fichiers :

- **Issues JSON** : des fiches d'issue structurées — problème, cause racine, correctif, contraintes, mots-clés, sévérité.
- **Files JSON** : README, notes de version, contenu technique découpé, métadonnées carte et composant.
- **Resolver Cases JSON** : la chaîne issue → pull request → commit, avec les fichiers modifiés en preuve, et un score de confiance de résolution.
- **Diagnostic Cards JSON** : des alias de requête, des ancrages par mots-clés, des références de preuve, un diagnostic structuré.

Toutes ces images passées par les issues sont enrichies par **Alfred Vision AI**, qui convertit l'image en texte.

Ces fichiers sont organisés par série, sous `datasets/07_delivery/st_ready/by_series/`, avec une structure identique pour chaque série : `issues_json`, `files_json`, `resolver_cases_json`, `diagnostic_cards_json`, et un dossier `drivers` pour les sous-dépôts.

L'upload se fait via le script `Add_Data_Source_Files.py`, qui parle à l'API **ST AI Bridge**, sur la base de connaissances numéro 793. Quelques points techniques à retenir :
- la découpe automatique des fichiers de plus de 25 Mo, avec `--json-split-size 1000`,
- une politique de gestion des fichiers JSON vides,
- une authentification dédiée au client applicatif.

Et côté persona, la configuration cible une **recherche hybride**, avec un seuil sémantique de 0.55, jusqu'à 20 documents en recherche sémantique et 12 en plein texte.

---

## 6. Alfred Vision AI : rendre les images cherchables (3 min)

*(Slide "Alfred Vision AI — Image-to-Text Enrichment")*

Un problème très concret que nous avons rencontré : une grande partie des issues GitHub contiennent des **images** — captures d'erreur, captures d'analyseur logique, captures de configuration CubeMX, traces d'oscilloscope. Or, un moteur de recherche RAG classique, basé sur du texte, est **aveugle** à ces images.

La solution : **Alfred Vision API**, un service multimodal qui fait de l'analyse d'image sémantique et de l'extraction de texte par OCR, avec une sensibilité au contexte spécifique ST.

Concrètement, le script `enrich_json_images_with_alfred.py` :
1. scanne le JSON pour trouver les URLs d'image,
2. envoie chaque image à l'API Alfred Vision,
3. récupère une description et le texte OCR extrait,
4. ajoute ce texte au corps de l'issue.

Un exemple concret de transformation : une issue qui dit *"voir la capture d'écran ci-jointe montrant l'erreur"* avec une image attachée devient, après enrichissement, la même phrase **plus** une section `[IMAGE DESCRIPTION]` qui décrit : *"boîte de dialogue d'erreur STM32CubeIDE affichant HAL_SPI_ERROR_OVR, erreur de dépassement pendant un transfert DMA, avec la configuration SPI1 visible en arrière-plan"*, et une section `[IMAGE TEXT]` avec le texte OCR brut de l'erreur.

Résultat : ce contenu devient désormais **interrogeable** par le moteur RAG, et les messages d'erreur deviennent une source de recherche à part entière.

Un point de robustesse important, que nous avons corrigé : la fonction `first_sentence()` retire désormais le marqueur `[IMAGE ATTACHED]` du `root_cause_hint`, pour éviter une duplication. Sans ce correctif, quand une image de commentaire est citée à la fois dans "Root cause" et dans "Key comments", Alfred épuisait ses appels sur la copie et produisait `UNAVAILABLE` sur les images originales.

---

## 7. Automatisation CI/CD : la mise à jour continue de la KB (4 min)

*(Slides "GitHub Actions CI/CD" et "Automation Pipeline — Run_Single_Series_Full_Pipeline_And_Upload.ps1")*

Passons maintenant à la partie automatisation, qui garantit que cette base de connaissances reste à jour sans intervention manuelle constante.

Le workflow GitHub Actions se déclenche de deux façons : automatiquement, le 1er et le 15 de chaque mois à 3h du matin UTC, ou manuellement, avec des paramètres — série, skip ingestion, skip upload.

Il s'exécute en deux jobs :

**Job 1 — Pipeline**, sur runner cloud : checkout du dépôt, installation des dépendances, exécution du pipeline complet par série — ingestion, nettoyage, enrichissement, similarité, export —, puis une **porte de qualité obligatoire** : `validate_schemas.py`. Si elle échoue, le workflow s'arrête ; si elle passe, les artefacts sont publiés.

**Job 2 — Upload vers la KB**, sur un runner self-hosted, en local sur le réseau ST : téléchargement des artefacts du job 1, puis un motif **suppression puis réinsertion** — on supprime l'ancien contenu de chaque datasource avant de republier le nouveau, ce qui évite les erreurs de type "fichier déjà existant".

Et pour l'exécution manuelle ou l'atelier pratique, nous avons un script central : `Run_Single_Series_Full_Pipeline_And_Upload.ps1`, avec trois modes :
- **Mode Full** (par défaut) : prepare + upload,
- **Mode Prepare** : génère les artefacts locaux sans upload,
- **Mode Upload** : rejoue uniquement la phase d'upload, utile pour une reprise rapide après incident.

Ce script exécute huit étapes, en deux phases :

*Phase Prepare* :
1. Synchronisation du dépôt et audit des sous-modules,
2. Prétraitement complet avec conversion Alfred des figures PDF pendant le run,
3. Export ST-ready pour le dépôt parent et les sous-dépôts,
4. Enrichissement Alfred des images d'issues,
5. Patch des descriptions PDF dans les fichiers de livraison,
6. Validation de schéma et contrôle des placeholders non résolus.

*Phase Upload* :
7. Création ou ajout des datasources dans la KB, avec sauvegarde des identifiants dans `upload_datasource_ids_<série>.json`,
8. Upload des sous-dépôts et pilotes dans les datasources parentes, avec découpage automatique des gros fichiers.

Un mécanisme de robustesse important : si un identifiant de datasource sauvegardé est périmé, on recrée automatiquement la datasource — cela corrige un cas réel observé, `KbDataSourceEntity not found`, rencontré sur la série WB. Et à la fin, les identifiants uploadés sont resynchronisés automatiquement dans `shared/config/config_all_series.json`, pour éviter tout écart entre les snapshots de série et la configuration globale.

---

## 8. Évaluation : mesurer la qualité, pas seulement la disponibilité (5 min)

*(Slide "Alfred and ST GitHub Analyzer Persona Evaluation — Metrics and Formulas")*

C'est la partie que je veux mettre en avant particulièrement, car elle répond à une question essentielle : comment sait-on que ce qu'on livre est réellement de qualité, et pas seulement "disponible" ?

### 8.1 Confiance contextuelle d'Alfred Vision

L'objectif de cette formule : montrer que le succès ne se mesure pas seulement à la disponibilité de l'API, mais à la **qualité de l'ancrage contextuel** du texte généré.

La formule de confiance contextuelle :

> Confiance contextuelle (%) = (nombre d'éléments évalués avec un score de cohérence C ≥ seuil τ) / N évalués × 100

où :
- **N évalués** est le nombre d'images ou de figures évaluées,
- **C** est le score de cohérence calculé par `validate_alfred_coherence.py`,
- **τ** (tau) est le seuil d'alerte, fixé à 0.12, en dessous duquel le texte est considéré comme faiblement ancré.

Les chiffres à présenter : pour les captures d'écran d'issues, (200 − 3) / 200 = **98,5 %**. Pour les figures extraites de PDF, (242 − 141) / 242 = **41,7 %**.

*Ce que je dis à l'oral :* "Nous ne mesurons pas seulement si Alfred renvoie du texte, mais si ce texte est ancré dans un contexte technique réel. Avec un seuil de cohérence à 0.12, on obtient 98,5 % pour les captures d'écran d'issues, contre 41,7 % pour les figures PDF — ce qui confirme que le contexte d'une capture d'écran dans une issue est beaucoup plus riche que celui d'une figure isolée dans un PDF."

### 8.2 Étude comparative : LLM générique vs Persona KB

L'objectif ici : quantifier le gain de qualité apporté par une persona qui s'appuie d'abord sur la base de connaissances, comparée à un usage direct et générique d'Alfred.

La formule de gain relatif :

> Gain (%) = (Score persona − Score Alfred générique) / Score Alfred générique × 100

Avec Score Alfred générique = 5,8/10 et Score persona = 8,1/10 :

> Gain = (8,1 − 5,8) / 5,8 × 100 = 39,7 %, arrondi à **+39 %**

*Point important à ne pas oublier de dire :* ce +39 % est un **gain relatif** par rapport au score de référence, pas un gain absolu en points. Et ce gain ne se limite pas au score : la traçabilité augmente aussi fortement, avec des citations vérifiables qui passent de 0 % à 87 %.

### 8.3 Score de stratégie KB (score pondéré multi-facteurs)

Pour choisir la meilleure configuration de recherche, nous utilisons un score pondéré :

> S = 0,40 × R_top1 + 0,20 × R_top3 + 0,35 × R_réponse − 0,15 × R_hallucination − 0,05 × (1 − Bonus_latence)

La pertinence en première position et la justesse de la réponse finale portent les poids les plus importants ; l'hallucination est pénalisée ; la latence intervient comme critère secondaire d'optimisation.

### 8.4 Indice de qualité — offline vs online

Enfin, pour comparer un scoring manuel expert et le score de la plateforme en production :

> QI_offline = (total noté sur 7) / 7 × 100
> Delta = QI_online − QI_offline

*Ce que je dis à l'oral :* "En offline, on note chaque réponse avec une grille experte, puis on normalise sur 100. En ligne, on utilise l'indice de qualité de la plateforme. Le delta nous indique si le comportement en production dépasse ou reste en dessous de nos attentes issues du benchmark manuel."

### 8.5 Résultats de benchmark à retenir

- Sur le test A/B à 30 questions : ajouter les fichiers JSON aux issues fait passer le score global de 2,93 à 5,33 sur 7, soit un gain d'environ **+82 % relatif**. Le gain est particulièrement fort sur les questions mixtes et sur les questions liées aux fichiers.
- Sur les runs en ligne à 50 questions, le principal facteur limitant n'est pas la précision de la recherche mais la **robustesse d'exécution** : entre 40 % et 50 % d'exceptions selon les runs, ce qui oriente nos priorités d'amélioration vers la fiabilité du runtime autant que vers la qualité de la recherche.

---

## 9. Conclusion et feuille de route (2 min)

*(Slide de conclusion)*

Pour conclure, trois messages à retenir :

1. **Le pipeline est industrialisé** : traçable, reprenable en cas d'échec, gouvernable via des modes Full, Prepare et Upload, avec des portes de qualité à chaque étape.
2. **La qualité est mesurée, pas supposée** : nous avons des formules explicites de confiance contextuelle, de gain comparatif, et d'indice de qualité offline versus online — pas seulement un ressenti qualitatif.
3. **L'amélioration est continue** : chaque écart détecté en évaluation déclenche une correction dans le générateur, pas un correctif manuel ponctuel — c'est ce qui rend le système durable.

Prochaine étape d'infrastructure : disposer d'un runner self-hosted dédié et toujours actif, pour fiabiliser encore davantage le job d'upload vers la base de connaissances.

Merci pour votre attention, je suis maintenant disponible pour vos questions.

---

## Annexe — Questions probables et éléments de réponse rapide

- **"Pourquoi Add vs Replace pour l'upload ?"** → Add ajoute des fichiers dans une datasource existante ; Replace nettoie puis republie pour éviter les doublons en production. Le motif utilisé en CI/CD est suppression puis réinsertion (delete + re-add).
- **"Pourquoi les issues 'invalides' sont-elles exclues ?"** → Textes trop courts, labels dupliqués ou wontfix sont filtrés par défaut ; un mécanisme de "rescue" récupère les faux négatifs techniquement intéressants.
- **"Le patch de commit est-il analysé en profondeur ?"** → Non, pas encore d'analyse sémantique ligne par ligne du patch ; le linkage s'appuie sur le message de commit et des signaux de diff légers (fichiers modifiés, additions/suppressions).
- **"Comment évitez-vous que les images épuisent les appels Alfred ?"** → Correctif `first_sentence()` qui retire `[IMAGE ATTACHED]` du `root_cause_hint` pour éviter la duplication d'URL entre "Root cause" et "Key comments".
- **"Quel est le prochain levier d'amélioration prioritaire ?"** → Réduire le taux d'exceptions runtime (40–50 % observé), qui est aujourd'hui le facteur limitant principal devant la précision de recherche.

---

## Repères de timing (pour un atelier de ~25 minutes)

| Section | Durée |
|---|---|
| 0. Introduction | 1–2 min |
| 1. Contexte et objectifs | 2 min |
| 1bis. Problème du temps d'analyse manuel des issues | 2–3 min |
| 2. Vue d'ensemble du pipeline | 3–4 min |
| 3. Flux de données | 2–3 min |
| 4. Couverture des séries | 2 min |
| 5. Delivery ST-ready & upload KB | 3 min |
| 6. Alfred Vision AI | 3 min |
| 7. Automatisation CI/CD | 4 min |
| 8. Évaluation et formules | 5 min |
| 9. Conclusion | 2 min |
| **Total** | **~29–33 min + Q&A** |
