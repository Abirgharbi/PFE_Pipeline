# Guide Rapide Self-Hosted Runner (FR)

Objectif: installer et configurer une machine de test en 10 minutes.

## 1) Prérequis machine

1. Windows 10/11.
2. Git installé.
3. Python 3.12+ installé.
4. Machine sans veille (sleep/hibernate désactivé).
5. Internet stable.

## 2) Créer le runner GitHub

1. Ouvrir le repo GitHub.
2. Aller à Settings -> Actions -> Runners -> New self-hosted runner.
3. Choisir Windows x64.
4. Exécuter les commandes proposées par GitHub sur la machine.
5. Installer le runner en service et démarrer.

## 3) Secrets obligatoires (repo)

Aller à Settings -> Secrets and variables -> Actions.

Ajouter:
1. RUNNER_CHECK_TOKEN
2. ST_CHATGPT_API_KEY
3. ST_CHATGPT_API_KEY 

## 4) Préparer Python dans le projet

Depuis la racine du repo:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 5) Config Git Windows

```powershell
git config --system core.longpaths true
```

## 6) Lancer le test superviseur

1. Ouvrir GitHub Actions.
2. Lancer Manual Auto Update KB.
3. Choisir mode Full.
4. Choisir une seule série pour test.

## 7) Résultat attendu

Ordre des jobs:
1. Prepare matrix inputs
2. Check self-hosted runner availability
3. Preprocess <Series>
4. Upload <Series>

Contrôles:
1. runner_ready = true
2. Alfred API key preflight = OK
3. Upload terminé sans erreur

## 8) Si ça échoue

1. Erreur 403 runner check:
- vérifier RUNNER_CHECK_TOKEN

2. Missing Alfred API key:
- ajouter ST_CHATGPT_API_KEY (ou ST_AI_BRIDGE_API_KEY / ST_API_KEY)

3. Lost communication:
- redémarrer service runner
- vérifier réseau + RAM/CPU
- vérifier logs dans actions-runner/_diag
