# Atelier Pratique — Pipeline de Prétraitement STM32Cube

## Guide rapide commandes (copier-coller)

Pour une version courte et accessible des commandes atelier, voir:

- `docs/presentations/README_Atelier_Quick_Commands.md`

## Génération de la présentation PPTX (après modifications)

Pour régénérer la version PowerPoint à jour :

```powershell
python docs/scripts/generate_atelier_pratique_pptx.py --output docs/Atelier_Pratique_Pipeline_STM32Cube.pptx
```

Sortie attendue :
`docs/Atelier_Pratique_Pipeline_STM32Cube.pptx`

Pour mettre a jour directement la presentation atelier F1 avec les nouvelles slides
automation + formules d'evaluation Alfred/persona :

```powershell
python docs/scripts/update_stm32cube_workshopf1_pptx.py --input docs/STM32Cube_worshopF1.pptx --output docs/STM32Cube_worshopF1.pptx
```

Ce script fait une finalisation "in-place" de la presentation existante :
- remplit la diapo automation existante (au lieu d'ajouter une nouvelle diapo),
- ajoute des encadres de reference formules en bas des diapos evaluation/persona,
- supprime les anciennes diapos auto-ajoutees (Plan mise a jour / Formules globales) si presentes.

Optionnel : si le schema automation a ete exporte en PNG, placez-le sous
`docs/diagrams/presentation/exported/07_automation_series_pipeline.png`.

## Objectif

Ce guide permet à l'équipe de **lancer, comprendre et maintenir** le pipeline de prétraitement de bout en bout :  
**Ingestion → Cleaning → Enrichment → Similarity → Delivery → Alfred → Upload KB**

---

## 0. Mode Présentation (Comité / Direction)

Si l'objectif est de présenter devant un public important, utiliser ce fil narratif court (10-15 min) :

### 0.1 Message clé en 30 secondes

Le pipeline transforme des signaux GitHub bruts et hétérogènes en artefacts support exploitables, traçables et uploadables dans la KB ST.

### 0.2 Storyline recommandée (ordre des slides)

1. **Vue d'ensemble** : le pipeline en une image (7 blocs, entrée GitHub, sortie KB).
2. **Le problème des images** : captures opaques → solution Alfred Vision.
3. **Connexion Alfred + NovaX** : architecture multi-agents KB-first.
4. **Zoom Cleaning → Enrichment** : d'où viennent les fichiers `docs_*`, V3 type-aware.
5. **Preuve** : gates qualité + exemples concrets avant/après.
6. **Impact** : Quality Index, confiance contextuelle, traçabilité.

### 0.3 Slide 1 — Vue d'Ensemble du Pipeline (3 min)

**Message clé** : Le pipeline transforme des données brutes GitHub en artefacts structurés pour un chatbot IA spécialisé STM32.

**Schéma à montrer** :

```
┌─────────────┐    ┌───────────┐    ┌──────────────┐    ┌────────────┐    ┌──────────┐    ┌────────────┐    ┌──────────┐
│ 1. Ingestion│───▶│2. Cleaning│───▶│3. Enrichment │───▶│4. Similarité│───▶│5. Chunking│───▶│6. Validation│───▶│7. Delivery│
│ fetch_*     │    │ V1 + V3   │    │ NLP + Alfred │    │ TF-IDF     │    │ 512 tok   │    │ JSON Schema│    │ 4 types  │
└─────────────┘    └───────────┘    └──────────────┘    └────────────┘    └──────────┘    └────────────┘    └──────────┘
      ▲                                                                                                          │
      │                                                                                                          ▼
 GitHub API                                                                                                 KB #793
 25 séries                                                                                             ST ChatGPT
 200+ repos                                                                                            GPT-5.1
```

**Points à dire** :
- 25 séries STM32 (13 en production, 12 configurées)
- 4 types d'artefacts produits : Issues, Files, Resolver Cases, Diagnostic Cards
- Pipeline modulaire : chaque stage rejouable indépendamment (`--skip-ingestion`, `--skip-chunking`)
- Artefacts traçables : chaque document final cite sa source GitHub

**Chiffres à afficher** :
| Donnée | Valeur |
|--------|--------|
| Séries couvertes | 25 (13 prod, 12 config) |
| Repos GitHub | 200+ |
| Issues traitées | ~3 350 |
| Files documentés | ~14 000 |
| Diagnostic Cards | ~157 |
| Resolver Cases | ~390 |
| KB Datasources | 38 |

### 0.4 Slide 2 — Le Problème des Images et la Solution Alfred (3 min)

**Message clé** : Les captures d'écran dans les issues sont invisibles pour la recherche textuelle. Alfred Vision les rend cherchables.

**Avant/Après** :

```
AVANT (opaque pour le RAG) :
─────────────────────────────
Issue #42: "HAL_SPI fails on H743"
Body: "See screenshot below"
[IMAGE ATTACHED: screenshot_debugger.png]    ← invisible pour la recherche !

APRÈS (cherchable par le RAG) :
─────────────────────────────
Issue #42: "HAL_SPI fails on H743"  
Body: "See screenshot below"
[IMAGE DESCRIPTION] The screenshot shows STM32CubeIDE debugger with a hard fault
at address 0x08001234 in HAL_SPI_TxRxCpltCallback. The call stack shows DMA IRQ
handler triggered from SPI1 peripheral. D-cache is enabled in MPU config panel.
```

**Résultats mesurés** :
| Source | Évalués | Confiance contextuelle |
|--------|---------|----------------------|
| Images d'issues GitHub | 200 | **98.5%** |
| Figures PDF | 242 | **41.7%** |
| Total Alfred | 442 | **67.4%** |

**Explication** : la confiance des images d'issues est très élevée car le texte de l'issue mentionne les mêmes erreurs/logs que la capture. Les figures PDF sont plus difficiles car le contexte de page est souvent insuffisant.

**Fiabilité opérationnelle** : 99.1% de succès sur les séries stabilisées (H7, F4, WL, F7).

### 0.5 Slide 3 — Architecture Multi-Agents : Alfred + NovaX (2 min)

**Message clé** : L'architecture est KB-first. La Knowledge Base est TOUJOURS interrogée en premier.

**Schéma** :

```
                    ┌─────────────────────────────────┐
                    │  Persona: ST GitHub Analyzer     │
     Question      │  (GPT-5.1 via Azure OpenAI)      │
  ──────────────▶  │                                   │
  Ingénieur STM32  └─────────┬───────────────┬─────────┘
                             │               │
                    ALWAYS   │               │  ONLY if KB empty
                    FIRST    ▼               ▼
              ┌──────────────────┐    ┌──────────────────┐
              │ Tool KB #793     │    │ Tool NovaX       │
              │ Unstructured     │    │ Fallback         │
              │ Hybrid Search    │    │ Bugzilla +       │
              │ (Semantic + FT)  │    │ STCommunity      │
              └──────────────────┘    └──────────────────┘
                       ▲
                       │ Upload JSON (pipeline)
              ┌──────────────────┐
              │ Pipeline 7 stages│
              │ Agent maintenance│
              └──────────────────┘
```

**Points à dire** :
- **KB Tool** : recherche hybride (semantic 0.55 threshold + full-text) dans 38 datasources
- **NovaX Tool** : fallback UNIQUEMENT quand la KB ne retourne rien de pertinent
- **Leçon critique** : une description NovaX trop permissive → QI chute de 10 points (la persona court-circuite la KB)
- **Solution** : description restrictive qui force la priorité KB

**Paramètres KB retenus** :
| Paramètre | Valeur |
|-----------|--------|
| Search Type | Hybrid (Semantic + Full-text) |
| Semantic Threshold | 0.55 |
| Semantic Max Docs | 25 |
| Full-text Max Docs | 12 |
| Modèle LLM | GPT-5.1 |

### 0.6 Slide 4 — Zoom : Cleaning → Enrichment (le cœur du pipeline) (5 min)

**Message clé** : C'est entre le nettoyage et l'enrichissement que la donnée brute devient exploitable par le RAG. Le V3 adapte la stratégie au type de fichier.

#### Partie A : Cleaning V3 — Nettoyage Type-Aware

**Le problème** : un fichier Release Notes HTML et un header CMSIS de 1.7 Mo ne se nettoient pas de la même façon.

**Arbre de décision V3** :

```
raw_files_*.json
       │
       ▼
┌──────────────────┐
│ detect_file_type()│
└────────┬─────────┘
         │
    ┌────┼────────────────┬──────────────────┬────────────────────┐
    ▼    ▼                ▼                  ▼                    ▼
Release  README          Source             CMSIS > 100Ko        Autre
Notes    (.md)           (.c/.h)            (stm32*xx.h)
    │    │                │                  │                    │
    ▼    ▼                ▼                  ▼                    ▼
strip_   clean_          strip_             filter_cmsis()       passthrough
html()   markdown()      license()          (IRQ + base addr     (inchangé)
(-33%)   (-15%)          (-10%)             + TypeDef only)
                                            (-96% !)
```

**Exemple concret CMSIS** :
```
stm32h743xx.h : 1 458 301 caractères → 52 140 caractères (-96.4%)
Ne conserve que : IRQn_Type enum, PERIPH_BASE defines, TypeDef structs
```

**Résultat** : `clean_files_<repo>_v3.json` (+31% de densité signal/chunk)

#### Partie B : Enrichissement — D'où viennent les `docs_*`

**Pour les issues** (`issues_to_docs_v2.py`) :

```
clean_issues_<repo>.json
         │
         ▼
┌─────────────────────────────────────────────────┐
│ Heuristiques NLP (regex domain-specific STM32)  │
│                                                  │
│  • layer      → HAL / BSP / CMSIS / MW / APP   │
│  • component  → SPI / I2C / UART / DMA / USB   │
│  • severity   → high / medium / low            │
│  • board      → NUCLEO-H743ZI / STM32H750B-DK  │
│  • issue_kind → bug_report / question / feature │
│  • is_valid   → true/false (filtrage spam)      │
└─────────────────────────────────────────────────┘
         │
         ▼
docs_issues_<repo>_v2.json
```

**Couverture mesurée (H7, 296 docs)** :
| Champ | Score | Seuil | Verdict |
|-------|-------|-------|---------|
| Validité | 86.4% | ≥85% | BON |
| Layer | 88.2% | ≥85% | BON |
| Severity | 100% | ≥90% | EXCELLENT |
| Component | 72.6% | ≥70% | ACCEPTABLE |
| Board | 45.3% | ≥60% | INSUFFISANT (signal absent des données) |

**Pour les fichiers** (`files_to_docs_v2.py`) :

```
clean_files_<repo>_v3.json
         │
         ▼
┌─────────────────────────────────────────────────┐
│ Classification par type + extraction métadonnées│
│                                                  │
│  • file_type  → source_code / release_notes /   │
│                 readme / cmsis_device_header /   │
│                 documentation_pdf               │
│  • board      → détecté depuis le path BSP     │
│  • component  → détecté depuis le nom fichier  │
│  • example_name → nom du projet exemple        │
│  • is_valid   → true si clean_text > 100 car.  │
└─────────────────────────────────────────────────┘
         │
         ▼
docs_files_<repo>_v3.json
```

**Puis la similarité** : `compute_issue_similarity_v2.py` ajoute les voisins TF-IDF → `docs_issues_<repo>_v2_sim.json`

**Puis la delivery** : les `docs_*` sont transformés en 4 types d'artefacts ST-ready avec texte structuré, métadonnées, et URLs GitHub.

### 0.3 KPI à afficher (lisibles, non ambigus)

| KPI | Définition | Pourquoi c'est important |
|-----|------------|--------------------------|
| Ingestion completeness | `% issues/files non vides` | Vérifie que la matière d'entrée existe |
| Enrichment coverage | `% docs avec layer/component/board` | Mesure la valeur ajoutée du preprocessing |
| Alfred success rate | `images décrites / images détectées` | Mesure la fiabilité multimodale |
| Placeholder rate | `placeholders non résolus / figures détectées` | Détecte les trous de connaissance visuelle |
| Quality Index | Score end-to-end sur jeu de questions | Mesure le niveau de service perçu |

### 0.4 Go / No-Go opérationnel avant démo

| Check | Critère Go |
|-------|------------|
| Schémas JSON | 100% valide |
| Upload | Aucun échec bloquant |
| Placeholders Alfred | 0 en mode strict (ou rapport explicite en mode Warn) |
| Questions smoke test | Réponses cohérentes et sourcées |

### 0.5 Script démo live (5 min)

1. Lancer une série en `Prepare`.
2. Montrer les artefacts `st_ready` générés.
3. Lancer `Upload` et afficher les IDs datasource.
4. Montrer 1 question technique et la source citée.
5. Montrer 1 cas de garde-fou (placeholder/report) et la mitigation.

---

## 1. Prérequis

### 1.1 Environnement

```powershell
# Cloner le repo
git clone https://github.com/abirGharbi-st/PFE_Chatbot_STM32Cube.git
cd PFE_Chatbot_STM32Cube

# Créer le venv Python 3.11+
python -m venv .venv
.venv\Scripts\Activate.ps1

# Installer les dépendances
pip install -r requirements.txt
```

### 1.2 Variables d'environnement

| Variable | Description | Exemple |
|----------|-------------|---------|
| `GITHUB_TOKEN` | Token GitHub avec accès aux repos STMicroelectronics | `ghp_xxxx...` |
| `STM32CUBE_CONFIG` | (Optionnel) Chemin vers un config spécifique | `shared/config/config_f7.json` |

```powershell
$env:GITHUB_TOKEN = "ghp_votre_token"
```

### 1.3 Structure du projet

```
PFE_Chatbot_STM32Cube/
├── shared/config/          # Fichiers de config par série (config_h7.json, config_f4.json...)
├── pipeline/               # Code du pipeline (ingestion, cleaning, enrichment, etc.)
├── pipeline_Automation/    # Scripts Alfred + Upload KB
├── data/                   # Fichiers intermédiaires (raw, clean, docs, chunks)
├── datasets/07_delivery/   # Outputs finaux ST-ready
└── GitHub_repos/           # Clones locaux des repos (auto-créés)
```

---

## 2. Configuration d'une série

Chaque série STM32 a un fichier de config sous `shared/config/config_<serie>.json` :

```json
{
  "owner": "STMicroelectronics",
  "repos": [
    "STM32CubeH7",           // Repo principal
    "stm32h7xx-hal-driver",  // Sous-repos (drivers)
    "cmsis_device_h7",
    "stm32h7xx-nucleo-bsp"
  ],
  "data_dir": "data",
  "repos_dir": "GitHub_repos",
  "auto_clone_missing_repos": true,
  "repo_clone_urls": { ... },
  "github_token_env": "GITHUB_TOKEN",
  "rate_limits": {
    "issues_sleep": 0.2,
    "comments_sleep": 0.1
  }
}
```

**Pour ajouter une nouvelle série :**
1. Créer `shared/config/config_<serie>.json` avec la liste des repos
2. Ajouter le mapping des sous-repos dans `pipeline/delivery/delivery_paths.py`
3. Lancer le pipeline

---

## 3. Exécution du Pipeline

### 3.1 Workflow complet (une série)

Commande recommandée atelier (pipeline + Alfred + upload KB en one-shot) :

```powershell
.\pipeline_Automation\workflow\Run_Single_Series_Full_Pipeline_And_Upload.ps1 -Series H7
```

Commande démo recommandée (ne bloque pas la présentation si un placeholder subsiste, tout en gardant la traçabilité) :

```powershell
.\pipeline_Automation\workflow\Run_Single_Series_Full_Pipeline_And_Upload.ps1 -Series H7 -Mode Full -PlaceholderPolicy Warn
```

Mode debug en 2 temps :

```powershell
# 1) Préparer tous les artefacts localement
.\pipeline_Automation\workflow\Run_Single_Series_Full_Pipeline_And_Upload.ps1 -Series H7 -Mode Prepare

# 2) Uploader vers KB après validation locale
.\pipeline_Automation\workflow\Run_Single_Series_Full_Pipeline_And_Upload.ps1 -Series H7 -Mode Upload
```

Workflow Python direct (utile pour debug d'un stage précis) :

```powershell
$env:STM32CUBE_CONFIG = "shared/config/config_h7.json"
python -m pipeline.run_full_workflow --export-st-ready --continue-on-error
```

**Options :**
| Flag | Effet |
|------|-------|
| `--export-st-ready` | Génère les JSON de delivery après le pipeline |
| `--continue-on-error` | Ne s'arrête pas si un step échoue |
| `--skip-ingestion` | Saute l'ingestion (utilise les raw existants) |
| `--skip-chunking` | Saute le chunking local |
| `--no-enrich-pdf` | Saute l'enrichissement Alfred des figures PDF |

### 3.2 Étapes du pipeline (dans l'ordre)

| # | Étape | Script | Input → Output |
|---|-------|--------|----------------|
| 1 | Ingestion Issues | `fetch_issues.py` | GitHub API → `data/raw_issues_<repo>.json` |
| 2 | Ingestion PRs | `fetch_prs.py` | GitHub API → `data/raw_prs_<repo>.json` |
| 3 | Ingestion Commits | `fetch_commits.py` | GitHub API → `data/raw_commits_<repo>.json` |
| 4 | Ingestion Links | `fetch_issue_pr_commit_links.py` | Croisement issues/PRs/commits |
| 5 | Sync repos | `repo_sync_service.py` | Clone/pull les repos localement |
| 6 | Ingestion Files | `fetch_files.py` | Repos locaux → `data/raw_files_<repo>.json` |
| 7 | Alfred PDF | `enrich_pdf_figures_with_alfred.py` | Figures PDF → descriptions texte |
| 8 | Cleaning Issues | `clean_issues.py` | raw → `data/clean_issues_<repo>.json` |
| 9 | Cleaning Files | `clean_files.py` | raw → `data/clean_files_<repo>.json` |
| 10 | Enrichment Issues | `issues_to_docs_v2.py` | clean → `data/docs_issues_<repo>_v2.json` |
| 11 | Enrichment Files | `files_to_docs_v2.py` | clean → `data/docs_files_<repo>_v2.json` |
| 12 | Similarity | `compute_issue_similarity_v2.py` | docs → `data/docs_issues_<repo>_v2_sim.json` |
| 13 | Chunking Issues | `docs_to_chunks_issues_v2.py` | docs → `data/chunks_issues_<repo>_v2.json` |
| 14 | Chunking Files | `docs_to_chunks_files_v2.py` | docs → `data/chunks_files_<repo>_v2.json` |
| 15 | Stats + Validation | `test_stats_*.py` + `validate_schemas.py` | Vérification qualité |
| 16 | Delivery | `export_st_ready_*.py` | → `datasets/07_delivery/st_ready/by_series/` |

### 3.3 Lancer plusieurs séries

```powershell
foreach ($serie in @("config_c0", "config_f0", "config_f1", "config_f2", "config_f3", "config_f7", "config_g0", "config_h7rs")) {
    Write-Host "=== Processing $serie ===" -ForegroundColor Cyan
    $env:STM32CUBE_CONFIG = "shared/config/$serie.json"
    python -m pipeline.run_full_workflow --export-st-ready --continue-on-error --no-enrich-pdf
}
```

---

## 4. Enrichissement Alfred (Images)

### 4.1 Images dans les issues (captures d'écran)

Alfred Vision analyse les captures d'écran attachées aux issues et remplace `[IMAGE ATTACHED]` par `[IMAGE DESCRIPTION] ...`

```powershell
python pipeline_Automation/alfred/enrich_json_images_with_alfred.py `
  --input "datasets/07_delivery/st_ready/by_series/stm32cubeh7/issues_json/st_ready_issues_with_images_stm32cubeh7.json" `
  --inplace --use-proxy
```

**Le fichier résultant (version finale)** :
`datasets/07_delivery/st_ready/by_series/stm32cubeh7/issues_json/st_ready_issues_with_images_stm32cubeh7.json`

**Résumé Alfred généré** :
`datasets/07_delivery/st_ready/by_series/stm32cubeh7/issues_json/st_ready_issues_with_images_stm32cubeh7__alfred_summary.json`

> ⚠️ Seules les séries avec des images dans les issues ont un fichier `with_images`. Si le fichier n'existe pas, la série n'a pas d'images → pas besoin d'Alfred.

### 4.2 Figures PDF

Alfred Vision décrit les figures extraites des PDFs techniques :

```powershell
python pipeline_Automation/alfred/enrich_pdf_figures_with_alfred.py --repo STM32CubeH7 --use-proxy
```

### 4.3 Séries avec images (à ce jour)

| Série | Issues avec images | Alfred requis |
|-------|:--:|:--:|
| H7 | 53 | ✅ |
| F4 | 34 | ✅ |
| WL | 23 | ✅ |
| U5 | 6 | ✅ |
| H5 | 3 | ✅ |
| C0, F0-F3, F7, G0, H7RS | 0 | ❌ |

---

## 5. Upload vers la Knowledge Base

### 5.0 Commande atelier recommandée (mise à jour)

Pour l'atelier pratique, utiliser en priorité le script workflow qui gère parent + drivers + validations + upload :

```powershell
.\pipeline_Automation\workflow\Run_Single_Series_Full_Pipeline_And_Upload.ps1 -Series H7
```

Le script sauvegarde automatiquement les IDs créés dans :
`datasets/07_delivery/st_ready/by_series/stm32cubeh7/upload_datasource_ids_stm32cubeh7.json`

### 5.1 Architecture de la KB

La KB **#793** (ST GitHub Analyzer) contient des **datasources séparées par série ET par type** :

```
KB #793
├── STM32H7 Issues (#24406)
├── STM32H7 Files (#29041)
├── STM32H7 Diagnostic Cards (#24408)
├── STM32H7 Resolver Cases (#24410)
├── STM32F4 Issues (#28099)
├── STM32F4 Files (#29042)
├── ...
```

### 5.2 Processor params (4 types)

| Type | rootTagPath | Label template |
|------|-------------|---------------|
| Issues | `issues` | `{{repo}} issue #{{issue_number}} - {{issue_title}}` |
| Files | `files` | `{{repo}} {{file_type}} - {{path}}` |
| Resolver Cases | `resolver_cases` | `{{label}}` |
| Diagnostic Cards | — | `{{label}}` |

### 5.3 Créer une nouvelle datasource

```powershell
$paramsIssues = '{"label": "{{repo}} issue #{{issue_number}} - {{issue_title}}", "externalURL": "https://github.com/STMicroelectronics/{{repo}}/issues/{{issue_number}}", "rootTagPath": "issues"}'
$b64 = [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($paramsIssues))

python pipeline_Automation/upload/Add_Data_Source_Files.py `
  --kb 793 --operation new `
  --datasource-name "STM32XX Issues" `
  --remote-user "votre.email@st.com" --processor JSON `
  --processor-params "base64:$b64" --json-split-size 1000 `
  --files "datasets/07_delivery/st_ready/by_series/stm32cubexx/issues_json/st_ready_issues_stm32cubexx.json"
```

### 5.4 Ajouter des fichiers à une datasource existante

```powershell
python pipeline_Automation/upload/Add_Data_Source_Files.py `
  --kb 793 --operation add --datasource-id <ID> `
  --remote-user "votre.email@st.com" --processor JSON `
  --processor-params "base64:$b64" --json-split-size 1000 `
  --files "chemin/vers/fichier.json"
```

### 5.5 Upload des drivers (automatisé)

```powershell
.\pipeline_Automation\upload\Upload_All_Drivers.ps1
```

Ce script :
- Scanne tous les `by_series/<serie>/drivers/` 
- Route chaque artifact vers la bonne datasource (issues → DS Issues, files → DS Files...)
- Ignore les fichiers vides
- Affiche un résumé

### 5.6 Vérifier le contenu de la KB

```powershell
python pipeline_Automation/upload/Get_Persona_KBs.py
```

---

## 6. Bonnes Pratiques

### 6.1 Exécution

| Règle | Pourquoi |
|-------|----------|
| Toujours utiliser `--continue-on-error` | Un sous-repo sans issues ne doit pas bloquer les autres |
| Vérifier les `summary_*.json` après delivery | Confirme les counts avant upload |
| Ne pas uploader les fichiers vides (`[]`) | L'API rejecte avec "empty JSON arrays" |
| Utiliser `--skip-ingestion` pour re-processer | Évite de re-télécharger les issues (rate limit GitHub) |

### 6.2 Organisation des datasources

| Règle | Pourquoi |
|-------|----------|
| 1 datasource = 1 série + 1 type d'artifact | Permet le remplacement ciblé |
| Les drivers vont dans la MÊME datasource que le repo principal | Même série = même contexte |
| Nommage : `STM32XX <Type>` | Lisibilité dans KB Management |

### 6.3 Alfred

| Règle | Pourquoi |
|-------|----------|
| `--use-proxy` sur le réseau ST | Proxy obligatoire pour api-ai-bridge.st.com |
| `--inplace` pour remplacer le fichier | Évite les doublons |
| Vérifier 0 `[IMAGE DESCRIPTION UNAVAILABLE]` | Si présent = URL expirée ou rate limit |

### 6.5 Présentation à fort enjeu (checklist)

| Action | Statut attendu |
|--------|----------------|
| Préparer un run `Prepare` la veille | ✅ |
| Générer les résumés `summary_*.json` | ✅ |
| Vérifier `validate_schemas` | ✅ |
| Préparer 3 exemples avant/après (raw → st_ready) | ✅ |
| Préparer 1 cas d'échec + mitigation (transparence) | ✅ |

### 6.4 Git

| Règle | Pourquoi |
|-------|----------|
| Ne JAMAIS commit les fichiers `data/*.json` | Dépassent 100 MB → push rejeté |
| Le `.gitignore` exclut `data/raw_*`, `data/clean_*`, `data/docs_*`, `data/chunks_*` | Protection automatique |
| Les `datasets/07_delivery/` sont committés | Ils sont plus petits et représentent le livrable |

---

## 7. Workflow complet — Nouvelle série (checklist)

```
□ 1. Créer shared/config/config_<serie>.json
□ 2. Ajouter le mapping sous-repos dans pipeline/delivery/delivery_paths.py
□ 3. Lancer: $env:STM32CUBE_CONFIG = "shared/config/config_<serie>.json"
             python -m pipeline.run_full_workflow --export-st-ready --continue-on-error
□ 4. Vérifier datasets/07_delivery/st_ready/by_series/stm32cube<serie>/
     - issues_json/ ✓

---

## 8. Annexes utiles pour la présentation

### 8.1 Exemple de comparaison “avant / après pipeline”

- **Avant** : issue brute, commentaires longs, image non interprétée.
- **Après** : card `st_ready` structurée avec contexte, contraintes, mots-clés, détails techniques.

### 8.2 Risques et mitigations à annoncer explicitement

| Risque | Effet | Mitigation |
|-------|-------|------------|
| Timeout API Alfred | Images non décrites | Re-run ciblé + cache + reporting |
| Placeholder PDF tronqué | Perte d'info visuelle | Patch ciblé + gate placeholder |
| Série peu documentée | Réponses incomplètes | Fallback Alfred + enrichissement continu |

### 8.3 Message de clôture conseillé

Le pipeline n'est pas seulement un ETL: c'est une chaîne qualité outillée, avec traçabilité des preuves, garde-fous explicites et boucle d'amélioration continue vers la production.
     - files_json/ ✓
     - diagnostic_cards_json/ ✓
     - resolver_cases_json/ ✓
     - drivers/ (si sous-repos) ✓
□ 5. Alfred (si images): 
     python pipeline_Automation/alfred/enrich_json_images_with_alfred.py --input <with_images.json> --inplace --use-proxy
□ 6. Upload repo principal (4 commandes: issues, files, diag, resolver)
□ 7. Upload drivers: .\pipeline_Automation\upload\Upload_All_Drivers.ps1
□ 8. Vérifier: python pipeline_Automation/upload/Get_Persona_KBs.py
```

---

## 8. Dépannage

| Problème | Cause | Solution |
|----------|-------|----------|
| `FileNotFoundError: st_ready_issues_with_images_*.json` | La série n'a pas d'images | Normal — skip Alfred images |
| `ValueError: All selected files are empty JSON arrays` | Pas de resolver cases | Normal — série sans fix documenté |
| `Datasource response: skipped_existing_files` | Fichier déjà uploadé | Supprimer le fichier dans KB Management puis re-uploader, ou créer un nouveau datasource |
| `error: File exceeds GitHub's file size limit` | Fichier `data/*.json` > 100 MB dans git | Vérifier `.gitignore` exclut bien `data/` |
| `rate limit` GitHub | Trop d'appels API | Attendre 1h ou augmenter `issues_sleep` dans config |
| Enrichment 0% pour un sous-repo | Pas de `docs_issues_*_v2.json` | Normal — les sous-repos BSP ont peu d'issues |

---

## 9. Contacts et Ressources

- **API Alfred Vision** : `api-ai-bridge.st.com` / client `mdrf_stgithub_analyzer_client`
- **KB Management** : Interface web ST ChatGPT → Knowledge Bases → #793
- **Persona** : "ST GitHub Analyzer" / client `mdrf_st_github_analyzer`
- **Repo GitHub** : `github.com/abirGharbi-st/PFE_Chatbot_STM32Cube`

---

## 10. Slide prête — Démo Alfred (2 exemples H7)

### Slide A — Exemple 1 (Issue #335)

- Issue: How to resolve observed warning when -Wcast-align flag is used during compile time
- Avant intégration: texte issue avec capture d'écran attachée
- Après intégration dans `st_ready_text`:
  `[IMAGE DESCRIPTION] Screenshot of an Eclipse/STM32CubeIDE project properties window on the Tool Settings tab...`
- Description Alfred stockée en structuré (`image_analyses[0].description`):
  `Screenshot of an Eclipse/STM32CubeIDE project properties or tool settings page focused on MCU/MPU GCC Linker > Miscellaneous...`
- Impact RAG:
  la capture devient searchable (flags, panneau Warnings/Miscellaneous, contexte build)

### Slide B — Exemple 2 (Issue #333)

- Issue: Fix compile time warnings without removing the set compiler flags
- Après intégration dans `st_ready_text`:
  `[IMAGE DESCRIPTION] Screenshot of the STM32CubeIDE "About" dialog window on Windows...`
- Description Alfred stockée en structuré (`image_analyses[0].description`):
  `Screenshot of the “About STM32CubeIDE” dialog on Windows. Visible details include Version 2.0.0 and Build 26820...`
- Impact RAG:
  la version exacte de l'outil devient récupérable dans la recherche (traceabilité du contexte)

### Message clé à dire en soutenance

Alfred enrichit deux niveaux:
1. **Texte intégré** dans `st_ready_text` via `[IMAGE DESCRIPTION] ...` (utile pour retrieval direct)
2. **Métadonnées détaillées** dans `image_analyses` (description + OCR + statut)

Résultat: les screenshots et boîtes de dialogue deviennent exploitables par la KB comme du texte technique.
