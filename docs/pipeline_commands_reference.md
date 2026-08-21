# Pipeline Commands Reference — STM32Cube Preprocessing

> Toutes les commandes sont à exécuter depuis la racine du projet.
> Remplacer `STM32CubeH7` par le repo cible si besoin.

---

## 1. Full Workflow (toutes les étapes)

```powershell
python -m pipeline.run_full_workflow
```

Avec export ST-ready :
```powershell
python -m pipeline.run_full_workflow --export-st-ready
```

Options utiles :
```powershell
python -m pipeline.run_full_workflow --skip-ingestion --continue-on-error
python -m pipeline.run_full_workflow --export-st-ready --skip-chunking --continue-on-error
```

Pour une série spécifique (via variable d'environnement) :
```powershell
$env:STM32CUBE_CONFIG = "shared/config/config_f4.json"
python -m pipeline.run_full_workflow --export-st-ready --skip-chunking --continue-on-error
```

Pipeline batch multi-séries :
```powershell
$series = @("g4", "l0", "l1", "l4")
foreach ($s in $series) {
    $env:STM32CUBE_CONFIG = "shared/config/config_$s.json"
    python -m pipeline.run_full_workflow --export-st-ready --skip-chunking --continue-on-error
}
```

---

## 2. Ingestion (fetch depuis GitHub)

```powershell
python -m pipeline.ingestion.fetch_issues --repo STM32CubeH7
python -m pipeline.ingestion.fetch_prs --repo STM32CubeH7
python -m pipeline.ingestion.fetch_commits --repo STM32CubeH7
python -m pipeline.ingestion.fetch_files --repo STM32CubeH7
python -m pipeline.ingestion.fetch_issue_pr_commit_links --repo STM32CubeH7
```

---

## 3. Cleaning

```powershell
# V1 — Basic normalization
python -m pipeline.cleaning.clean_issues
python -m pipeline.cleaning.clean_files

# V3 — Type-aware cleaning (HTML strip, CMSIS filter, license removal)
python -m pipeline.cleaning.clean_files_v3
```

---

## 4. Enrichment (V2)

```powershell
python -m pipeline.enrichment.issues_to_docs_v2
python -m pipeline.enrichment.files_to_docs_v2
```

---

## 5. Similarity

```powershell
python -m pipeline.similarity.compute_issue_similarity_v2
```

---

## 6. Chunking

```powershell
python -m pipeline.chunking.docs_to_chunks_issues_v2
python -m pipeline.chunking.docs_to_chunks_files_v2
```

---

## 7. Delivery (Export ST-Ready)

### Issues (avec champ image_urls)
```powershell
python -m pipeline.delivery.export_st_ready_issues_with_images --repo STM32CubeH7
```

### Issues (standard sans images)
```powershell
python -m pipeline.delivery.export_st_ready_issues --repo STM32CubeH7
```

### Files
```powershell
python -m pipeline.delivery.export_st_ready_files --repo STM32CubeH7
```

### Resolver Cases
```powershell
python -m pipeline.delivery.export_st_ready_resolver_cases --repo STM32CubeH7
```

### Diagnostic Cards
```powershell
python -m pipeline.delivery.export_st_ready_diagnostic_cards --repo STM32CubeH7
```

---

## 8. Alfred — Enrichissement images

### Images d'issues
```powershell
python pipeline_Automation/alfred/enrich_json_images_with_alfred.py --input "datasets/07_delivery/st_ready/by_series/stm32cubeh7/issues_json/st_ready_issues_with_images_stm32cubeh7.json" --inplace
```

### Figures PDF
```powershell
python pipeline_Automation/alfred/enrich_pdf_figures_with_alfred.py
python pipeline_Automation/alfred/enrich_pdf_figures_with_alfred.py --repo STM32CubeH7
python pipeline_Automation/alfred/enrich_pdf_figures_with_alfred.py --max-figures 50
```

### Patch PDF descriptions dans les delivery files
```powershell
python pipeline_Automation/patch_pdf_descriptions_in_delivery.py --dry-run
python pipeline_Automation/patch_pdf_descriptions_in_delivery.py
```

### Fix JSON corrompus (control characters)
```powershell
python pipeline_Automation/fix_corrupted_json_files.py
python pipeline_Automation/fix_corrupted_json_deep.py
```

Options Alfred :
- `--use-proxy` : utiliser le proxy ST (185.46.212.88:80)
- `--no-replace-text` : ne pas remplacer [IMAGE ATTACHED] dans le texte
- `--max-records N` : limiter à N records
- `--strip-analyses` : retirer les analyses détaillées

---

## 9. Upload vers KB (datasource)

### Commande générique
```powershell
$params = '{"label": "{{repo}} issue #{{issue_number}} - {{issue_title}}", "externalURL": "https://github.com/STMicroelectronics/{{repo}}/issues/{{issue_number}}", "rootTagPath": "issues"}'
$b64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($params))
python pipeline_Automation/upload/Add_Data_Source_Files.py --kb 793 --operation add --datasource-id <ID> --remote-user "abir.gharbi@st.com" --processor JSON --processor-params "base64:$b64" --json-split-size 1000 --files "<chemin_fichier.json>"
```

### H7 Issues (datasource #24406)
```powershell
$params = '{"label": "{{repo}} issue #{{issue_number}} - {{issue_title}}", "externalURL": "https://github.com/STMicroelectronics/{{repo}}/issues/{{issue_number}}", "rootTagPath": "issues"}'
$b64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($params))
python pipeline_Automation/upload/Add_Data_Source_Files.py --kb 793 --operation add --datasource-id 24406 --remote-user "abir.gharbi@st.com" --processor JSON --processor-params "base64:$b64" --json-split-size 1000 --files "datasets/07_delivery/st_ready/by_series/stm32cubeh7/issues_json/st_ready_issues_with_images_stm32cubeh7.json"
```

### Params pour Files
```powershell
$params = '{"label": "{{repo}} - {{file_type}} - {{path}}", "externalURL": "{{github_url}}", "rootTagPath": "files"}'
```

### Erreur ST Platform: `embedDocuments return EMPTY vectors`

Cette erreur signifie que le backend ST a lance l'activation du datasource, mais que le processeur JSON n'a produit aucun texte a vectoriser. Le datasource reste alors bloque ou inactif apres rollback.

Verifier en priorite :
- Le fichier doit avoir une racine objet correspondant au processor param, par exemple `{"files": [...]}` pour les exports files.
- Chaque element doit contenir un champ texte non vide, normalement `st_ready_text` dans les exports `st_ready_files_*`.
- Les params doivent etre encodes en base64 dans PowerShell, surtout avec les templates `{{...}}`.
- Si le datasource est deja bloque apres rollback, recreer un datasource JSON propre avec `--operation new`, puis refaire l'upload. Relancer `add` sur le meme datasource bloque repete souvent le rollback.

Commande files recommandee :
```powershell
$params = '{"label": "{{repo}} - {{file_type}} - {{path}}", "externalURL": "{{github_url}}", "rootTagPath": "files"}'
$b64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($params))
python pipeline_Automation/upload/Add_Data_Source_Files.py --kb 793 --operation add --datasource-id <FILES_DATASOURCE_ID> --remote-user "abir.gharbi@st.com" --processor JSON --processor-params "base64:$b64" --json-root-mode auto --empty-json-policy skip --json-split-size 1000 --files "datasets/07_delivery/st_ready/files_json/st_ready_files_<repo>.json"
```

Si l'activation reste bloquee apres l'erreur, creer un nouveau datasource :
```powershell
python pipeline_Automation/upload/Add_Data_Source_Files.py --kb 793 --operation new --datasource-name "STready_<SERIES>_Files_JSON" --remote-user "abir.gharbi@st.com" --processor JSON --processor-params "base64:$b64" --json-root-mode auto --empty-json-policy skip --json-split-size 1000 --files "datasets/07_delivery/st_ready/files_json/st_ready_files_<repo>.json"
```

### Params pour Resolver Cases
```powershell
$params = '{"label": "{{repo}} resolver #{{issue_number}} - {{issue_title}}", "externalURL": "https://github.com/STMicroelectronics/{{repo}}/issues/{{issue_number}}", "rootTagPath": "resolver_cases"}'
```

### Params pour Diagnostic Cards
```powershell
$params = '{"label": "{{card_id}} - {{card_title}}", "externalURL": "{{primary_issue_url}}", "rootTagPath": "diagnostic_cards"}'
```

---

## 10. Evaluation

### Rapport d'évaluation (avec PDF)
```powershell
python -m pipeline.evaluation.generate_evaluation_report --repo STM32CubeH7 --pdf
```

### Stats issues
```powershell
python -m pipeline.evaluation.test_stats_issues_v2
```

### Stats files
```powershell
python -m pipeline.evaluation.test_stats_files_v2
```

### TF-IDF search test (issues)
```powershell
python -m pipeline.evaluation.test_tfidf_search_issues_v2
```

### TF-IDF search test (files)
```powershell
python -m pipeline.evaluation.test_tfidf_search_files_v2
```

### Validation schemas
```powershell
python -m pipeline.evaluation.validate_schemas
```

---

## 11. Automation Scripts (PowerShell)

### Pipeline complet pour tous les repos
```powershell
.\pipeline_Automation\workflow\Run_Issues_Pipeline_For_All_Repos.ps1
```

### Diagnostic cards pour tous les repos
```powershell
.\pipeline_Automation\workflow\Generate_Diagnostic_Cards_For_All_Repos.ps1
```

### Upload batch ST-Ready
```powershell
.\pipeline_Automation\upload\Upload_STReady_New_Batch.ps1
```

### Full auto-update KB
```powershell
.\pipeline_Automation\workflow\Run_Full_Auto_Update_KB.ps1
```

---

## 12. Upload Scripts Automatisés

### Upload issues Alfred-enrichies (13 séries)
```powershell
python pipeline_Automation/upload/upload_alfred_issues_all_series.py --dry-run
python pipeline_Automation/upload/upload_alfred_issues_all_series.py
```

### Upload files PDF-enrichies (13 séries)
```powershell
python pipeline_Automation/upload/upload_pdf_enriched_files_all_series.py --dry-run
python pipeline_Automation/upload/upload_pdf_enriched_files_all_series.py
```

Retry prudent pour une seule serie apres rollback backend ST (`Cannot read properties of undefined (reading 'status')`) :
```powershell
python pipeline_Automation/upload/upload_pdf_enriched_files_all_series.py --only-series stm32cubef0 --json-split-size 200 --verbose
```

Si le datasource reste bloque apres plusieurs rollbacks, creer un nouveau datasource Files JSON pour la serie puis relancer l'upload vers ce nouvel ID. Cette erreur vient du backend async ST pendant le traitement/rollback, pas d'une erreur Python locale.

### Upload drivers sous-repos (8 nouvelles séries)
```powershell
.\pipeline_Automation\upload\Upload_All_Drivers.ps1
```

---

## Datasources IDs connus

| Série | Issues | Files | Diagnostic | Resolver |
|-------|:------:|:-----:|:----------:|:--------:|
| STM32CubeC0 | 29193 | 29192 | 29212 | — |
| STM32CubeF0 | 29195 | 29196 | 29213 | — |
| STM32CubeF1 | 29197 | 29198 | 29214 | 29211 |
| STM32CubeF2 | 29199 | 29200 | 29215 | — |
| STM32CubeF3 | 29282 | 29283 | 29284 | — |
| STM32CubeF4 | 28099 | 29042 (V3) | 28122 | 28118 |
| STM32CubeF7 | 29276 | 29277 | 29278 | 29279 |
| STM32CubeG0 | 29273 | 29274 | 29275 | — |
| STM32CubeH5 | 28158 | 29043 (V3) | 28165 | 28164 |
| STM32CubeH7 | 24406 | 29041 (V3) | 24408 | 24410 |
| STM32CubeH7RS | 29270 | 29271 | 29272 | — |
| STM32CubeU5 | 28167 | 29044 (V3) | 28170 | 28244 |
| STM32CubeWL | 28171 | 29045 (V3) | 28173 | 28245 |

> KB #793 = ST GitHub Analyzer_Unstructured
> Master config: `shared/config/config_all_series.json`

---

## 13. Configs Disponibles

| Série | Config File |
|-------|-------------|
| H7 (default) | `shared/config/config.json` |
| C0, F0–F7, G0 | `shared/config/config_<série>.json` |
| H5, H7RS, U5, WL | `shared/config/config_<série>.json` |
| G4, L0, L1, L4, L5 | `shared/config/config_<série>.json` (nouvelles) |
| N6, U0, U3 | `shared/config/config_<série>.json` (nouvelles) |
| WB, WB0, WBA, WL3 | `shared/config/config_<série>.json` (nouvelles) |

**25 séries au total** — 13 en production, 12 configurées.

---

## 14. GitHub Actions Automation (Dual Upload Target)

Workflows principaux :
- `.github/workflows/auto_update_kb.yml`
- `.github/workflows/manual_auto_update_kb.yml`

Le workflow exécute, pour chaque série, le script :

```powershell
.\pipeline_Automation\workflow\Run_Single_Series_Full_Pipeline_And_Upload.ps1
```

### Architecture disponible

- **Chemin 1 (défaut, stable prod)** : upload sur runner `self-hosted`
- **Chemin 2 (test cloud)** : upload sur runner `github-hosted` (`windows-latest`)

La sélection se fait avec l'input workflow :
- `upload_execution_target`: `self-hosted` | `github-hosted`

Valeur par défaut : `self-hosted`.

### Prérequis

- Runner self-hosted Windows `online` dans le repo GitHub (obligatoire pour le mode `self-hosted`)
- Secrets GitHub Actions configurés :
    - `ST_GITHUB_ANALYZER_API_KEY`
    - `ST_CHATGPT_API_KEY` (ou `ST_AI_BRIDGE_API_KEY` / `ST_API_KEY`)
    - `ST_REMOTE_USER`

### Trigger automatique

- Cron bi-mensuel : 1er et 15 du mois à 03:00 UTC
- Exécution par défaut en `self-hosted`

### Trigger manuel (GitHub UI)

Dans **Actions > Auto Update KB > Run workflow** :

- `series`: `G4,L0,L1,L4,L5,N6,U0,U3,WB,WB0,WBA,WL3` (ou sous-ensemble)
- `mode`: `Full` | `Prepare` | `Upload`
- `existing_datasource_mode`: `Replace` | `Add`
- `upload_execution_target`: `self-hosted` | `github-hosted`
- `skip_drivers`: `true/false`
- `skip_schema_validation`: `true/false`
- `continue_on_workflow_error`: `true/false`
- `placeholder_policy`: `Fail` | `Warn` | `Off`
- `max_parallel`: `1` (recommandé avec un seul runner)

### Mode d'utilisation sans risque

1. **Production normale** : laisser `upload_execution_target=self-hosted`.
2. **Test cloud organisation interne** : lancer une seule série avec `upload_execution_target=github-hosted`.
3. **Si pas d'accès réseau ST côté cloud** : relancer immédiatement avec `upload_execution_target=self-hosted` (aucune modification de code nécessaire).

### Vérification rapide runner local (mode self-hosted)

```powershell
cd .\actions-runner
.\run.cmd
```

Le runner doit afficher `Listening for Jobs`.
