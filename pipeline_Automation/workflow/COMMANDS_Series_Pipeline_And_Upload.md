# Commandes pipeline + Alfred + upload KB par serie

Toutes les commandes se lancent depuis la racine du projet :

```powershell
cd "C:\Users\gharbiab\OneDrive - STMicroelectronics\Desktop\PFE_Chatbot_STM32Cube"
```

Le script principal est :

```powershell
.\pipeline_Automation\workflow\Run_Single_Series_Full_Pipeline_And_Upload.ps1
```

Il fait, pour une serie :

1. sync repos configures
2. audit/fix submodules manquants
3. pipeline preprocessing complet avec `--skip-chunking`
4. Alfred PDF figures pendant le preprocessing
5. exports ST-ready parent et subrepos : issues, resolver, diagnostic, issues avec image URLs
6. Alfred issues images sur tous les `st_ready_issues_with_images_*.json` sous la serie
7. export `files_json` V3 pour tous les repos de la config, y compris subrepos/drivers
8. patch PDF descriptions dans les fichiers racine et `drivers/*/files_json`
9. validation schema + placeholders
10. creation des datasources KB avec `operation new`, ou ajout dans des IDs existants si fournis
11. upload des drivers/subrepos dans les datasources parent correspondantes avec `operation add` : `issues`, `files`, `diagnostic_cards`, `resolver_cases`
12. sauvegarde des IDs dans `upload_datasource_ids_<serie>.json`

## Commandes completes

### G4

```powershell
.\pipeline_Automation\workflow\Run_Single_Series_Full_Pipeline_And_Upload.ps1 -Series G4
```

### L0

```powershell
.\pipeline_Automation\workflow\Run_Single_Series_Full_Pipeline_And_Upload.ps1 -Series L0
```

### L1

```powershell
.\pipeline_Automation\workflow\Run_Single_Series_Full_Pipeline_And_Upload.ps1 -Series L1
```

### L4

```powershell
.\pipeline_Automation\workflow\Run_Single_Series_Full_Pipeline_And_Upload.ps1 -Series L4
```

### L5

```powershell
.\pipeline_Automation\workflow\Run_Single_Series_Full_Pipeline_And_Upload.ps1 -Series L5
```

### N6

```powershell
.\pipeline_Automation\workflow\Run_Single_Series_Full_Pipeline_And_Upload.ps1 -Series N6
```

### U0

```powershell
.\pipeline_Automation\workflow\Run_Single_Series_Full_Pipeline_And_Upload.ps1 -Series U0
```

### U3

```powershell
.\pipeline_Automation\workflow\Run_Single_Series_Full_Pipeline_And_Upload.ps1 -Series U3
```

## Debug et execution separee

Pour preparer seulement les artefacts locaux sans upload KB :

```powershell
.\pipeline_Automation\workflow\Run_Single_Series_Full_Pipeline_And_Upload.ps1 -Series G4 -Mode Prepare
```

Pour uploader seulement une serie deja preparee :

```powershell
.\pipeline_Automation\workflow\Run_Single_Series_Full_Pipeline_And_Upload.ps1 -Series G4 -Mode Upload
```

Pour uploader une serie vers des datasources deja creees, passer les IDs existants. Exemple G4 :

```powershell
.\pipeline_Automation\workflow\Run_Single_Series_Full_Pipeline_And_Upload.ps1 `
	-Series G4 `
	-Mode Upload `
	-IssuesDatasourceId 29611 `
	-FilesDatasourceId 29612 `
	-DiagnosticDatasourceId 29614
```

Cette commande ajoute tout ce qui existe localement pour G4 :

- issues racine + `drivers/*/issues_json` dans `DB_STready_G4_Issues`
- files racine + `drivers/*/files_json` dans `DB_STready_G4_Files`
- diagnostic racine + `drivers/*/diagnostic_cards_json` dans `DB_STready_G4_Diagnostic`
- resolver racine + `drivers/*/resolver_cases_json` si une datasource resolver existe ou si des resolver cases sont presentes

Pour creer/uploader seulement les fichiers racine, sans drivers :

```powershell
.\pipeline_Automation\workflow\Run_Single_Series_Full_Pipeline_And_Upload.ps1 -Series G4 -Mode Upload -SkipDrivers
```

## Reprise/debug si G4 a ete lance partiellement

Si les fichiers locaux existent mais que les IDs KB ne sont pas sauvegardes, ou si les drivers missed ne sont pas tous presents, reprendre en deux temps.

### 1. Regenerer et verifier G4 localement

```powershell
.\pipeline_Automation\workflow\Run_Single_Series_Full_Pipeline_And_Upload.ps1 -Series G4 -Mode Prepare
```

Verifier les fichiers racine :

```powershell
Test-Path "datasets/07_delivery/st_ready/by_series/stm32cubeg4/issues_json/st_ready_issues_with_images_stm32cubeg4.json"
Test-Path "datasets/07_delivery/st_ready/by_series/stm32cubeg4/files_json/st_ready_files_stm32cubeg4_v3.json"
Test-Path "datasets/07_delivery/st_ready/by_series/stm32cubeg4/diagnostic_cards_json/st_ready_diagnostic_cards_stm32cubeg4.json"
Test-Path "datasets/07_delivery/st_ready/by_series/stm32cubeg4/resolver_cases_json/st_ready_resolver_cases_stm32cubeg4.json"
```

Verifier les drivers/subrepos missed :

```powershell
Get-ChildItem "datasets/07_delivery/st_ready/by_series/stm32cubeg4/drivers" -Directory
```

Verifier Alfred issues :

```powershell
Get-Content "datasets/07_delivery/st_ready/by_series/stm32cubeg4/issues_json/st_ready_issues_with_images_stm32cubeg4__alfred_summary.json" -Raw
Get-ChildItem "datasets/07_delivery/st_ready/by_series/stm32cubeg4/drivers/*/issues_json/*__alfred_summary.json"
```

Verifier qu'il ne reste aucun placeholder Alfred/PDF :

```powershell
Select-String -Path "datasets/07_delivery/st_ready/by_series/stm32cubeg4/**/*.json" `
	-Pattern "IMAGE DESCRIPTION UNAVAILABLE|\[FIGURE DETECTED\]|Figure detected on page"
```

### 2. Uploader G4 apres verification locale

```powershell
.\pipeline_Automation\workflow\Run_Single_Series_Full_Pipeline_And_Upload.ps1 -Series G4 -Mode Upload
```

Le script sauvegarde les IDs crees ici :

```text
datasets/07_delivery/st_ready/by_series/stm32cubeg4/upload_datasource_ids_stm32cubeg4.json
```

## Fichiers d'IDs crees

Apres l'upload, les IDs sont sauvegardes ici :

```text
datasets/07_delivery/st_ready/by_series/<serie>/upload_datasource_ids_<serie>.json
```

Exemples :

```text
datasets/07_delivery/st_ready/by_series/stm32cubeg4/upload_datasource_ids_stm32cubeg4.json
datasets/07_delivery/st_ready/by_series/stm32cubel0/upload_datasource_ids_stm32cubel0.json
```

Ces IDs doivent ensuite etre reportes dans `shared/config/config_all_series.json`.

## Notes importantes

- Les datasources racine `Issues`, `Files`, `Diagnostic`, `Resolver` sont creees avec `operation new`, sauf si un ID est fourni en parametre.
- Les sorties `drivers/*/issues_json`, `drivers/*/files_json`, `drivers/*/diagnostic_cards_json` et `drivers/*/resolver_cases_json` sont ajoutees avec `operation add` dans la datasource parent correspondante.
- Si `resolver_cases` est vide, le script saute la datasource resolver.
- Le script echoue si un placeholder Alfred/PDF reste non resolu.