# Rapport equipe - Integration d'une nouvelle serie STM32Cube

## 1) Objectif et niveau de detail
Ce document est un guide operatoire complet, redige pour une equipe qui decouvre le projet.
Il explique exactement:
1. Quoi modifier.
2. Ou le modifier.
3. Pourquoi le modifier.
4. Comment verifier que c'est correct.
5. Comment executer en local et via GitHub Actions.

Le scenario de reference est l'ajout d'une nouvelle serie, par exemple C5.

## 2) Architecture logique du pipeline
Le pipeline suit un flux fixe:
1. Ingestion GitHub (issues, commentaires, fichiers, liens PR/commits).
2. Nettoyage (clean_issues, clean_files).
3. Enrichissement (docs_issues_v2, docs_files_v2).
4. Similarite (issues reliees).
5. Export delivery ST-ready.
6. Split issues par composant (optionnel mais recommande).
7. Upload KB.

Le dossier de sortie principal est:
- datasets/07_delivery/st_ready/by_series/stm32cube<serie>

## 3) Fichiers critiques a connaitre

### 3.1 Configurations
1. shared/config/config_<serie>.json
2. shared/config/config_all_series.json

### 3.2 Workflows PowerShell
1. pipeline_Automation/workflow/Run_Single_Series_Full_Pipeline_And_Upload.ps1
2. pipeline_Automation/workflow/Split_Issues_By_Component.ps1
3. pipeline_Automation/workflow/Upload_Issues_By_Component.ps1
4. pipeline_Automation/workflow/Run_Full_Auto_Update_KB.ps1

### 3.3 Orchestrateur batch Python
1. pipeline_Automation/workflow/run_all_series.py

### 3.4 GitHub Actions
1. .github/workflows/auto_update_kb.yml
2. .github/workflows/manual_auto_update_kb.yml

## 4) Definition detaillee des champs de config

## 4.1 Fichier de serie: shared/config/config_<serie>.json

### owner
Organisation GitHub des depots sources.
Valeur attendue dans ce projet: STMicroelectronics.

### repos
Liste ordonnee des depots de la serie.
Regles:
1. Le premier element doit etre le repo parent: STM32Cube<Serie>.
2. Les elements suivants sont les depots relies (HAL, CMSIS, BSP, middleware).
3. Cette liste pilote l'ingestion et l'export.

### data_dir
Dossier interne des artefacts data.
Valeur standard: data.

### repos_dir
Dossier local contenant les clones.
Valeur standard: GitHub_repos.

### auto_clone_missing_repos
Si true, les repos manquants sont clones automatiquement.

### repo_clone_urls
Mapping depot -> URL git clone.
Exemple:
```json
"stm32c0xx-hal-driver": "https://github.com/STMicroelectronics/stm32c0xx-hal-driver.git"
```

### linked_repo_refs
Mapping depot -> SHA exact (commit) du sous-module sur la release cible.
Ce champ est essentiel pour la reproductibilite.

### commit_pr_scope
Regle de perimetre pour lier commits et PR.
Valeur utilisee: linked_or_merged.

### github_token_env
Nom de la variable d'environnement qui porte le token GitHub.
Valeur standard: GITHUB_TOKEN.

### rate_limits
Delais entre appels GitHub API.
Exemple:
1. issues_sleep
2. comments_sleep

### ingest_version
Version logique du format de config.
Valeur courante: v1.0.

## 4.2 Fichier global: shared/config/config_all_series.json

### all_series
Liste de toutes les series actives.

### series_config_files
Mapping entre nom de serie (ex: STM32CubeC5) et fichier local (ex: config_c5.json).

### kb_datasource_ids
Mapping par serie des datasource IDs deja crees dans la KB.
Champs usuels:
1. issues
2. files
3. diagnostic
4. resolver

### kb_id
Identifiant global de la KB cible.

### upload
Parametres globaux d'upload (utilisateur, split JSON, retries, etc.).

## 5) D'ou viennent repos, repo_clone_urls et linked_repo_refs

## 5.1 Source unique de verite
Le repo parent de la serie a la release cible (tag) est la reference.

## 5.2 Commandes d'extraction
Executer depuis un terminal:
```powershell
git clone --recursive https://github.com/STMicroelectronics/STM32CubeC5.git
cd STM32CubeC5
git checkout <tag_cible>
git submodule update --init --recursive

# URLs de submodules
git config -f .gitmodules --get-regexp "submodule\..*\.url"

# Paths de submodules
git config -f .gitmodules --get-regexp "submodule\..*\.path"

# SHAs reels de submodules
git submodule status --recursive
```

## 5.3 Regles de conversion en config
1. repos
Source: parent + noms de submodules.

2. repo_clone_urls
Source: sortie de la commande .gitmodules URL.

3. linked_repo_refs
Source: SHA de git submodule status.

4. Controle qualite
Tous les repos declares dans linked_repo_refs doivent exister dans repos.

## 6) Procedure complete d'ajout d'une serie C5

## 6.1 Creer le fichier de config serie
1. Copier un modele proche:
- shared/config/config_c0.json ou shared/config/config_g4.json
2. Renommer en shared/config/config_c5.json
3. Remplir repos, repo_clone_urls, linked_repo_refs depuis les commandes de la section 5.

## 6.2 Declarer C5 globalement
Modifier shared/config/config_all_series.json:
1. Ajouter STM32CubeC5 dans all_series.
2. Ajouter mapping dans series_config_files:
- STM32CubeC5: config_c5.json
3. Ajouter entree kb_datasource_ids pour STM32CubeC5.

Valeur initiale recommandee:
```json
"STM32CubeC5": {
  "issues": null,
  "files": null,
  "diagnostic": null,
  "resolver": null
}
```

## 6.3 Mettre a jour les scripts de workflow
Ajouter C5 dans chaque ValidateSet et seriesMap:
1. pipeline_Automation/workflow/Run_Single_Series_Full_Pipeline_And_Upload.ps1
2. pipeline_Automation/workflow/Split_Issues_By_Component.ps1
3. pipeline_Automation/workflow/Upload_Issues_By_Component.ps1
4. pipeline_Automation/workflow/Run_Full_Auto_Update_KB.ps1

Mapping attendu:
1. code serie: C5
2. slug: stm32cubec5
3. repo parent: STM32CubeC5
4. config: shared/config/config_c5.json

## 6.4 Mettre a jour l'orchestrateur Python
Dans pipeline_Automation/workflow/run_all_series.py, ajouter:
1. c5 dans SERIES_CONFIGS

## 6.5 Mettre a jour GitHub Actions
Modifier:
1. .github/workflows/auto_update_kb.yml
2. .github/workflows/manual_auto_update_kb.yml

Ajouter C5 dans:
1. input series (description/listes autorisees)
2. bloc de normalisation allowed
3. liste par defaut si necessaire

## 7) Mise en place complete sur un nouveau PC

## 7.1 Prerequis systeme
1. Windows 10/11
2. Git installe
3. Python 3.12+
4. Acces reseau GitHub + endpoint ST
5. Droits d'administration pour service runner

## 7.2 Creer le repo GitHub de travail
Deux options standards:
1. Fork du repo original sur le compte/organisation equipe.
2. Nouveau repo + push miroir depuis clone local.

Option fork recommandee (plus simple pour conserver historique et PR).

## 7.3 Cloner le projet sur le PC
```powershell
git clone https://github.com/<org-ou-user>/PFE_Chatbot_STM32Cube.git
cd PFE_Chatbot_STM32Cube
```

## 7.4 Configurer git local
```powershell
git config --global user.name "<Nom Equipe>"
git config --global user.email "<email>"
git config --system core.longpaths true
```

## 7.5 Creer l'environnement Python
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 7.6 Variables et secrets
Dans GitHub repository secrets (Settings > Secrets and variables > Actions > onglet Secrets):
1. RUNNER_CHECK_TOKEN
2. ST_GITHUB_ANALYZER_API_KEY
3. ST_CHATGPT_API_KEY
4. ST_REMOTE_USER

En local si besoin de test hors Actions:
```powershell
setx ST_CHATGPT_API_KEY "<value>"
setx ST_REMOTE_USER "<email_st>"
```

## 7.7 Installer / reconfigurer le self-hosted runner
Documentation officielle GitHub a suivre pour la creation initiale:
https://docs.github.com/en/actions/how-tos/manage-runners/self-hosted-runners/add-runners

Procedure depuis GitHub:
1. Settings
2. Actions
3. Runners
4. New self-hosted runner (Windows)
5. Copier les commandes configure et run

Bonnes pratiques:
1. Installer en service.
2. Conserver le label self-hosted.
3. Verifier que le runner apparait online dans GitHub.

**Important - clone du depot vs reconfiguration du runner.**
Quand une nouvelle machine clone ce depot, une partie du travail est deja faite (scripts,
configuration pipeline, dossier `actions-runner` present dans le clone). Le runner
self-hosted lui-meme n'est toutefois PAS reutilisable tel quel: il doit etre
reconfigure sur la nouvelle machine.

Pour reconfigurer le runner:
1. Supprimer le contenu du dossier `actions-runner` (il contient une
   configuration/registration propre a la machine d'origine).
2. Reprendre les instructions a partir de l'etape 6 du document GitHub officiel
   ci-dessus (telechargement et configuration du runner).
3. Executer ces commandes depuis une console PowerShell ou CMD Windows, et non
   depuis Git Bash (le script de configuration du runner n'est pas garanti de
   fonctionner correctement sous Git Bash).
4. Lors de la (re)configuration (`config.cmd`), il est recommande de conserver
   les options par defaut proposees (nom de runner, groupe, labels, dossier de
   travail), sauf besoin explicite de les modifier.

## 7.8 Check reseau runner
Verifier connectivite:
1. api.github.com
2. api-ai-bridge.st.com

## 8) Execution locale de validation (avant CI)

## 8.1 Prepare
```powershell
powershell -ExecutionPolicy Bypass -File .\pipeline_Automation\workflow\Run_Single_Series_Full_Pipeline_And_Upload.ps1 -Series C5 -Mode Prepare
```

Succes attendu:
1. livraison ST-ready generee sous datasets/07_delivery/st_ready/by_series/stm32cubec5
2. pas d'erreur schema (sauf si volontairement skip)

## 8.2 Split par composant
```powershell
powershell -ExecutionPolicy Bypass -File .\pipeline_Automation\workflow\Split_Issues_By_Component.ps1 -Series C5
```

Succes attendu:
1. dossier by_component present
2. summary_by_component_c5.json present

## 8.3 Verification anti-doublons
```powershell
python -m pipeline.delivery.validate_issues_by_component_split --summary "datasets/07_delivery/st_ready/by_series/stm32cubec5/issues_json/by_component/summary_by_component_c5.json"
```

Succes attendu:
1. no duplicates
2. full coverage

## 8.4 Upload composant dry-run
```powershell
powershell -ExecutionPolicy Bypass -File .\pipeline_Automation\workflow\Upload_Issues_By_Component.ps1 -Series C5 -DryRun -RemoteUser "<email_st>"
```

## 8.5 Upload composant reel
```powershell
powershell -ExecutionPolicy Bypass -File .\pipeline_Automation\workflow\Upload_Issues_By_Component.ps1 -Series C5 -RemoteUser "<email_st>"
```

## 8.6 Reporter les IDs datasource
Apres upload reussi, renseigner shared/config/config_all_series.json:
1. kb_datasource_ids.STM32CubeC5.issues
2. kb_datasource_ids.STM32CubeC5.files
3. kb_datasource_ids.STM32CubeC5.diagnostic
4. kb_datasource_ids.STM32CubeC5.resolver

## 9) Execution via GitHub Actions

## 9.1 Workflow manuel
Utiliser .github/workflows/manual_auto_update_kb.yml

Inputs recommandees pour migration composant:
1. mode = Full ou Upload
2. enable_issues_by_component_flow = true
3. component_issues_only = true

## 9.2 Workflow planifie
Utiliser .github/workflows/auto_update_kb.yml

Verifier:
1. C5 present dans listes allowed
2. C5 present dans DEFAULT_SERIES si activation automatique desiree

## 9.3 Critere de succes CI
1. job preprocess-series = success
2. job upload-series = success
3. step summary sans erreurs bloquantes

## 10) Mode composant vs datasource global

## 10.1 Signification des switches
1. EnableIssuesByComponentFlow
- active split + upload datasources issues par composant.

2. ComponentIssuesOnly
- desactive l'upload du gros datasource issues global.
- conserve uniquement issues_SERIE_COMPONENT (plus issues_SERIE pour null component).

## 10.2 Commande type migration
```powershell
powershell -ExecutionPolicy Bypass -File .\pipeline_Automation\workflow\Run_Single_Series_Full_Pipeline_And_Upload.ps1 -Series C5 -Mode Upload -EnableIssuesByComponentFlow -ComponentIssuesOnly -RemoteUser "<email_st>"
```

## 11) Checklist finale Go/No-Go
1. config_c5.json cree et complete
2. config_all_series.json mis a jour
3. C5 ajoutee dans scripts PS + run_all_series.py
4. C5 ajoutee dans workflows GH
5. Prepare local passe
6. Split by_component passe
7. Validation anti-doublons passe
8. Upload dry-run passe
9. Upload reel passe
10. IDs KB traces dans config_all_series.json

## 12) Erreurs frequentes et correction

## C5 non reconnue
Cause: oublie ValidateSet ou seriesMap.
Correction: ajouter C5 dans tous les scripts concernes.

## linked_repo_refs incomplet
Cause: extraction partielle des submodules.
Correction: refaire git submodule update --init --recursive puis git submodule status --recursive.

## Fichiers by_component absents
Cause: split non execute.
Correction: executer Split_Issues_By_Component.ps1 avant upload composant.

## Echec upload KB
Cause probable:
1. secret ST_CHATGPT_API_KEY absent
2. remote user incorrect
3. endpoint ST inaccessible

Correction:
1. verifier secrets
2. verifier connectivite reseau/proxy
3. relancer en dry-run puis reel

## Doublons detectes apres split
Cause: ancien resultat melange avec nouveau.
Correction:
1. nettoyer le dossier by_component
2. regenarer split
3. reexecuter validateur
