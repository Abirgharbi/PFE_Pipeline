# Upload des processorParams via API ST - Documentation detaillee

## Objectif
Expliquer precisement comment la solution envoie rootTagPath, externalURL et label a l API ST, sans ajout manuel dans l UI Persona.

Cette documentation est orientee Python-first.
Le script de reference est [pipeline_Automation/upload/Add_Data_Source_Files.py](../../pipeline_Automation/upload/Add_Data_Source_Files.py).

## Contrat ST et conformite
Selon la documentation ST New Data Source, la requete contient:
- type = kb-datasource-new
- service = kb
- datasource.processor
- datasource.processorParams
- fichiers en multipart sous le champ files

Notre implementation respecte ce contrat:
- creation datasource: type kb-datasource-new
- ajout fichiers: type kb-datasource-add
- suppression datasource: type kb-datasource-delete
- envoi des fichiers avec le nom multipart files

## Comment la solution a ete construite
1. Besoin metier: injecter rootTagPath, externalURL, label via API pour eviter la configuration manuelle UI.
2. Verification technique: l API ST accepte datasource.processorParams pour JSON.
3. Probleme terrain observe: erreurs frequentes de quoting des JSON CLI sous Windows.
4. Solution definitive:
   - parser robuste de processorParams dans le Python,
   - support JSON brut ou base64,
   - validations avant appel API,
   - precheck d authentification.
5. Industrialisation:
   - retries reseau,
   - fallback de formats payload,
   - hints explicites sur erreurs 2000/1000/3000.

## Mapping champ par champ

| Champ ST | Champ envoye par le script |
|---|---|
| version | version=1 |
| clientAppName | --client-app-name ou auto-resolution |
| timestamp | genere automatiquement (mode secondes par defaut) |
| remoteUser | --remote-user |
| service | --service (kb par defaut) |
| type | --operation mappe vers kb-datasource-add/new/delete |
| kb | --kb |
| datasource.id | --datasource-id (add/delete) |
| datasource.name | --datasource-name (new) |
| datasource.classification | --datasource-classification (new) |
| datasource.tags | --datasource-tags (new) |
| datasource.processor | --processor JSON |
| datasource.processorParams | --processor-params (JSON ou base64) |
| files (multipart) | --files ... |

## Flux interne du script Python
1. Parse arguments CLI.
2. Valide remote user email.
3. Resolve API key.
4. Resolve client app name.
5. Parse processor params:
   - accepte JSON standard,
   - accepte prefixe base64:,
   - tente un parsing relaxe pour des cas PowerShell deformes.
6. Construit datasource payload selon operation.
7. Lance auth precheck kb-list (sauf skip explicite).
8. Prepare upload JSON (normalisation root et split optionnel).
9. Envoie requete API avec auth token ST.
10. Traite erreurs API avec hints actionnables.

## Structure du payload envoye
Exemple conceptuel new datasource JSON:

{
  "version": 1,
  "clientAppName": "<client-app>",
  "timestamp": 1725996984,
  "remoteUser": "first.last@st.com",
  "service": "kb",
  "type": "kb-datasource-new",
  "kb": 793,
  "datasource": {
    "name": "DB_STready_Issues_Test",
    "classification": "PUBLIC",
    "processor": "JSON",
    "processorParams": {
      "rootTagPath": "issues",
      "externalURL": "{{github_url}}",
      "label": "{{repo}} issue #{{issue_number}} - {{issue_title}}"
    }
  }
}

Les fichiers sont ajoutes en multipart form-data avec la cle files.

## Valeurs recommandees de processorParams

Issues:
{
  "rootTagPath": "issues",
  "externalURL": "{{github_url}}",
  "label": "{{repo}} issue #{{issue_number}} - {{issue_title}}"
}

Files:
{
  "rootTagPath": "files",
  "externalURL": "https://github.com/STMicroelectronics/{{repo}}/search?q={{path}}&type=code",
  "label": "{{repo}} {{file_type}} - {{path}}"
}

Diagnostic cards:
{
  "rootTagPath": "diagnostic_cards",
  "externalURL": "{{externalURL}}",
  "label": "{{repo}} diagnostic #{{issue_number}} - {{title}}"
}

Resolver cases:
{
  "rootTagPath": "resolver_cases",
  "externalURL": "{{externalURL}}",
  "label": "{{repo}} resolver #{{issue_number}} - {{issue_title}}"
}

## Commandes Python de reference

Creation new datasource avec processorParams:

python pipeline_Automation/upload/Add_Data_Source_Files.py \
  --kb 793 \
  --operation new \
  --datasource-name DB_STready_Issues_Test \
  --datasource-classification PUBLIC \
  --remote-user first.last@st.com \
  --service kb \
  --processor JSON \
  --processor-params "{\"rootTagPath\":\"issues\",\"externalURL\":\"{{github_url}}\",\"label\":\"{{repo}} issue #{{issue_number}} - {{issue_title}}\"}" \
  --files datasets/07_delivery/st_ready/issues_json/st_ready_issues_STM32CubeH7.json

Ajout dans datasource existante:

python pipeline_Automation/upload/Add_Data_Source_Files.py \
  --kb 793 \
  --operation add \
  --datasource-id 24406 \
  --remote-user first.last@st.com \
  --service kb \
  --processor JSON \
  --processor-params "{\"rootTagPath\":\"issues\",\"externalURL\":\"{{github_url}}\",\"label\":\"{{repo}} issue #{{issue_number}} - {{issue_title}}\"}" \
  --files datasets/07_delivery/st_ready/issues_json/st_ready_issues_STM32CubeH7.json

Option plus robuste sous Windows: envoyer processorParams en base64.

## Pourquoi base64 existe dans la solution
processorParams contient souvent:
- doubles accolades,
- guillemets,
- URL avec caracteres speciaux.

Le format base64 elimine les erreurs d echappement CLI et garantit un payload stable.

Le script Python decode automatiquement si le parametre commence par base64:.

## Validation et garde-fous
- Verifie que processorParams est un objet JSON.
- Verifie les champs obligatoires selon operation.
- Verifie email remote-user.
- Auth precheck kb-list avant upload.
- Messages d aide en cas d echec auth:
  - invalid auth token,
  - invalid application name,
  - invalid timestamp.

## Erreurs frequentes et correction

Erreur: Invalid auth token
- Cause typique: api key invalide ou mauvaise paire api key/client app.
- Action: verifier --api-key, --client-app-name, et les secrets actifs.

Erreur: invalid application name
- Cause typique: client app ne correspond pas a la persona.
- Action: fournir le bon --client-app-name ou laisser auto-resolution.

Erreur: no documents found
- Cause typique: JSON vide.
- Action: utiliser --empty-json-policy skip ou corriger les fichiers source.

Erreur: datasource must be a number
- Cause typique: id datasource absent/invalide en delete/add.
- Action: verifier --datasource-id entier.

## Conclusion
La solution detaillee est implementee dans Python et envoie bien rootTagPath, externalURL et label via API.
Le processus est conforme a la doc ST, reproductible en CI, et ne depend pas de modifications manuelles dans l UI Persona.
