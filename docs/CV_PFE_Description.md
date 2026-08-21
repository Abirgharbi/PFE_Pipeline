# Description PFE – Pipeline RAG & Agentic AI (STMicroelectronics)

> À utiliser pour CV, LinkedIn, lettre de motivation ou préparation d'entretien.

---

## Description unifiée complète

**Reverse-engineering d'un système RAG industriel, conception d'un pipeline de Data Generation et développement d'agents IA agentiques pour un chatbot de support technique — STMicroelectronics**

Stage de fin d'études (6 mois) au sein d'une équipe IA dans l'industrie des semiconducteurs. Mission : alimenter et optimiser un système de Retrieval-Augmented Generation (RAG) en production (black box interne) servant de chatbot de support technique pour des milliers d'utilisateurs.

**Analyse et reverse-engineering du RAG interne** : étude du comportement du système RAG propriétaire (stratégies de retrieval, scoring, chunking appliqué côté plateforme) afin d'identifier les bonnes pratiques, les limites de pertinence et les leviers d'amélioration exploitables depuis le preprocessing. Développement d'un second RAG hors domaine pour comparer les stratégies et en extraire les patterns efficaces transposables au RAG de production.

**Data Generation** : conception d'un pipeline Python modulaire multi-étapes (ingestion → cleaning → enrichment → chunking → delivery) générant des données structurées RAG-ready à partir de sources brutes hétérogènes non exploitables telles quelles (GitHub API, documentation technique, PDF, images, Markdown). Transformation de 20+ sources de données en base de connaissances optimisée pour le retrieval.

**Feature Engineering** : extraction automatique de features métier (couche logicielle, sévérité, composant, board, type de problème, mots-clés techniques) par heuristics NLP et règles expertes. Classification automatique des contenus, détection de composants/boards, calcul de scores de qualité et de pertinence pour filtrer et prioriser les données injectées dans la Knowledge Base.

**Agents IA agentiques** : développement d'agents autonomes orchestrant des appels à des LLM Vision pour l'enrichissement multimodal (analyse d'images techniques, génération de descriptions textuelles à partir de captures d'écran et schémas). Workflow agentique gérant les erreurs, les retries, et l'enrichissement incrémental de contenus multimodaux à grande échelle.

**Stratégies de chunking et similarité** : implémentation et comparaison de stratégies de découpage (paragraph-level, section-level, full-document) et calcul de similarité cosinus (TF-IDF) pour maximiser la pertinence du retrieval. Analyse de l'impact de chaque stratégie sur la qualité des réponses du chatbot.

**Framework d'évaluation end-to-end** : mise en place de tests automatisés (retrieval accuracy offline vs online, validation de schémas JSON, statistiques de couverture et qualité, comparaison avant/après chaque itération) pour mesurer l'impact de chaque modification du pipeline sur la qualité des réponses du chatbot. Boucle itérative data-driven : modifier le pipeline → regénérer les données → évaluer → mesurer l'impact sur le RAG.

**Automatisation CI/CD** : déploiement continu vers la Knowledge Base de production (GitHub Actions, PowerShell) avec mise à jour incrémentale de 20+ sources de données sans intervention manuelle.

**Technologies** : Python, NLP, RAG (Retrieval-Augmented Generation), LLM APIs (Vision), Agentic AI, Feature Engineering, Data Generation, TF-IDF, Cosine Similarity, JSON Schema, REST APIs, GitHub Actions, CI/CD, Git, PowerShell

---

## Versions condensées pour CV

### Version moyenne (4 lignes)

**Reverse-engineering d'un RAG industriel & pipeline de Data Generation pour chatbot IA — Semiconducteurs**

Analyse d'un système RAG de production (black box) pour en extraire les stratégies de retrieval et les contraintes d'ingestion. Conception d'un pipeline Python de data generation et feature engineering transformant 20+ sources hétérogènes (APIs, docs, images) en données RAG-ready. Développement d'agents IA agentiques (LLM Vision) pour l'enrichissement multimodal. Mise en place d'un framework d'évaluation (retrieval accuracy, quality metrics) et automatisation CI/CD du déploiement vers la Knowledge Base.

**Compétences** : RAG, Agentic AI, LLM, NLP, Feature Engineering, Data Generation, Évaluation IA, Python, CI/CD

### Version courte (2 lignes)

**Pipeline RAG & Agentic AI — Ingénieur IA stagiaire, industrie semiconducteurs**

Reverse-engineering d'un RAG de production pour en extraire les bonnes pratiques ; conception d'un pipeline de data generation et feature engineering (20+ sources, agents LLM Vision, évaluation retrieval) alimentant une Knowledge Base en production via CI/CD.

---

## Bullet points (format anglo-saxon / LinkedIn)

- Reverse-engineered a **production RAG system** (black box) to extract retrieval strategies, scoring behavior, and chunking constraints — then applied findings to optimize preprocessing
- Designed and implemented an end-to-end **data generation pipeline** (ingestion → cleaning → enrichment → chunking → delivery) processing 20+ heterogeneous data sources into RAG-ready knowledge
- Built **feature engineering** modules extracting structured metadata (software layer, severity, component, board, issue type) from unstructured technical content using NLP heuristics
- Developed **Agentic AI workflows** orchestrating LLM Vision API calls for automated multimodal data enrichment (image analysis, text generation from screenshots and schematics)
- Implemented a **retrieval evaluation framework** (TF-IDF search tests, offline vs online accuracy comparison, schema validation, quality statistics) enabling data-driven iteration
- Applied and compared **chunking strategies** (paragraph-level, section-level, full-document) and similarity computation (TF-IDF, cosine) to optimize retrieval relevance
- Automated the full **data generation lifecycle** with CI/CD (GitHub Actions, PowerShell), enabling continuous Knowledge Base updates without manual intervention across 20+ data sources

---

## Points clés à faire ressortir en entretien

| Thème | Ce que tu as fait concrètement |
|-------|-------------------------------|
| **Comprendre un RAG black box** | Étudié le comportement du RAG interne (scoring, chunking plateforme) pour adapter le preprocessing ; développé un RAG hors domaine pour comparer les stratégies |
| **Data Generation** | Créé des données structurées à partir de sources brutes non exploitables telles quelles (GitHub API, PDF, images, Markdown) |
| **Feature Engineering** | Extrait des features (layer, severity, board, component, issue_kind) par NLP + heuristics ; classification automatique ; scoring de qualité |
| **Agentic AI** | Agents autonomes appelant un LLM Vision pour enrichir des contenus multimodaux à grande échelle |
| **Évaluation** | Framework offline/online mesurant la retrieval accuracy et la qualité des réponses ; comparaison avant/après chaque itération |
| **Itération data-driven** | Boucle : modifier le pipeline → regénérer → évaluer → mesurer l'impact sur le RAG |
| **CI/CD & Production** | Déploiement automatisé continu vers KB de production, 20+ sources, zéro intervention manuelle |
