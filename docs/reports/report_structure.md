# Nouvelle structure du rapport PFE — 5 chapitres

> Rapport : *Conception et Implémentation d'un Pipeline de Prétraitement Intelligent pour la Base de Connaissances STM32Cube*
>
> Squelette de sommaire (chapitres + sections + sous-sections). Les 10 anciens chapitres sont réorganisés selon l'arc académique :
> **Contexte → État de l'art → Conception → Réalisation → Évaluation.**
>
> Un commentaire `(ex-X.Y)` indique l'origine dans l'ancien plan (fichier `PFE_Report_STM32Cube_Pipeline.tex` + `chapter_configuration.tex` + `chapter_evaluation.tex`).

```latex
% ---- Sections liminaires (non numérotées) ----
\chapter*{Remerciements}
\addcontentsline{toc}{chapter}{Remerciements}

\chapter*{Introduction Générale}
\addcontentsline{toc}{chapter}{Introduction Générale}


% =========================================================================
\chapter{Contexte Général du Projet}
% (fusion des ex-chapitres 1 et 2)
% =========================================================================

\section{Présentation de l'Entreprise}                        % (ex-1.1)
    \subsection{Présentation Générale}                        % (ex-1.1.1)
    \subsection{Vision et Marchés}                            % (ex-1.1.2)
    \subsection{STMicroelectronics Tunis}                     % (ex-1.1.3)

\section{Division Microcontrôleurs (MCD)}                     % (ex-1.2)

\section{Équipe d'Accueil : Technical Marketing and Application Support} % (ex-1.3)

\section{L'Écosystème STM32 et les Dépôts GitHub}             % (ex-2.1)
    \subsection{Les Dépôts GitHub STMicroelectronics}         % (ex-2.1.1)

\section{Problématique}                                       % (ex-2.2)
    \subsection{Critique de l'Existant}                       % (ex-2.2.1)

\section{Objectifs du Projet}                                 % (ex-2.8)

\section{Contributions Techniques Originales}                 % (ex-2.7)

\section{Enjeux Éthiques et Responsabilité}                   % (ex-2.9)

\section{Les 25 Séries STM32 Couvertes}                       % (ex-2.11)

\section{Plan du Rapport}                                     % (ex-2.10)


% =========================================================================
\chapter{État de l'Art et Fondements Théoriques}
% (partie théorique de l'ex-chapitre 2 + intégralité de l'ex-chapitre 4)
% =========================================================================

\section{Le Paradigme RAG}                                    % (ex-2.3.1)

\section{Preprocessing et Qualité de la Base de Connaissances} % (ex-2.3.2)

\section{TF-IDF pour la Similarité}                           % (ex-2.3.3)

\section{Alfred Vision pour la Description d'Images}          % (ex-2.3.4)

\section{Étude Comparative des Solutions Existantes}          % (ex-2.4)

\section{Synthèse de la Solution Proposée}                    % (ex-2.5)

\section{Positionnement par Rapport à l'État de l'Art}        % (ex-2.6)

\section{Qu'est-ce qu'un Pipeline de Preprocessing ?}         % (ex-4.1)
    \subsection{Principes Fondamentaux}                       % (ex-4.1.1)

\section{Enjeux du Preprocessing pour le RAG}                 % (ex-4.2)
    \subsection{Problème « Garbage In, Garbage Out »}         % (ex-4.2.1)
    \subsection{Exigences Spécifiques au Domaine Embedded}    % (ex-4.2.2)

\section{Étapes Canoniques d'un Pipeline NLP}                 % (ex-4.3)

\section{Métriques de Qualité d'un Pipeline}                  % (ex-4.5)

\section{Patterns d'Architecture Pipeline}                    % (ex-4.6)
    \subsection{Pattern Batch vs Streaming}                   % (ex-4.6.1)
    \subsection{Pattern « Rejouable par Stage »}              % (ex-4.6.2)
    \subsection{Pattern « Gate de Qualité »}                  % (ex-4.6.3)


% =========================================================================
\chapter{Analyse des Besoins et Conception}
% (fusion des ex-chapitres 3 et 5, + ex-4.4)
% =========================================================================

\section{Identification des Acteurs}                          % (ex-3.1)

\section{Besoins Fonctionnels}                                % (ex-3.2)

\section{Besoins Non Fonctionnels}                            % (ex-3.3)

\section{Contraintes et Décisions de Conception}             % (ex-3.4)

\section{Approche Méthodologique}                             % (ex-5.1)
    \subsection{Sélection de la Méthodologie : Scrum Adapté}  % (ex-3.5)
        % Organisation en Sprints (ex-3.5.1)
        % Artefacts Scrum Utilisés (ex-3.5.2)
    \subsection{Pourquoi CRISP-DM ? Choix et Justification Méthodologique} % (NOUVEAU)
        % Comparaison CRISP-DM vs KDD, SEMMA, TDSP, Agile pur
        % Argumentaire : pourquoi CRISP-DM est le meilleur choix pour ce projet
    \subsection{Adaptation de CRISP-DM au Projet}            % (ex-5.2)
        % Nature du Projet : Data-Centric et Retrieval-Centric (ex-5.2.1)
        % Correspondance CRISP-DM -> Pipeline (ex-5.2.2)

\section{Notre Pipeline : Mapping Théorie \(\rightarrow\) Implémentation} % (ex-4.4)

\section{Contraintes de la Plateforme de Retrieval et Adaptation du Pipeline} % (ex-5.3)
    \subsection{Paramètres Imposés par la Plateforme}         % (ex-5.3.1)
    \subsection{Découpage PARENT\_CHILD}                      % (ex-5.3.2)
    \subsection{Embeddings AdaV2 et Qualité Sémantique du Contenu} % (ex-5.3.3)
    \subsection{Tailles de Lots (Batch Sizes) et Débit d'Indexation} % (ex-5.3.4)
    \subsection{Synthèse : Contrainte \(\rightarrow\) Décision \(\rightarrow\) Valeur} % (ex-5.3.5)
    \subsection{Valeur du Pipeline vs Preprocessing RAG Standard} % (ex-5.3.6)

\section{Architecture Cible}                                  % (ex-3.6)

\section{Architecture Globale}                                % (ex-5.4)

\section{Choix Techniques}                                    % (ex-5.5)

\section{Diagramme de Flux de Données}                        % (ex-5.6)

\section{Flux Source-to-Answer}                               % (ex-5.7)

\section{Architecture de Delivery et Upload KB}              % (ex-5.8)


% =========================================================================
\chapter{Réalisation et Implémentation}
% (fusion des ex-chapitres 6 et 7)
% =========================================================================

\section{Vue d'Orchestration du Pipeline}                     % (ex-6.1)

\section{Ingestion (Stage 1)}                                 % (ex-6.2)
    \subsection{Objectif}                                     % (ex-6.2.1)
    \subsection{Mécanisme}                                    % (ex-6.2.2)
    \subsection{Exemple de Sortie — Issue Brute}              % (ex-6.2.3)

\section{Nettoyage (Stage 2)}                                 % (ex-6.3)
    \subsection{Nettoyage des Issues}                         % (ex-6.3.1)
    \subsection{Nettoyage des Fichiers}                       % (ex-6.3.3)

\section{Nettoyage V3 — Nettoyage Intelligent par Type (Stage 2b)} % (ex-6.4)
    \subsection{Stratégies de Nettoyage par Type}             % (ex-6.4.1)
    \subsection{Filtrage CMSIS Device Headers}                % (ex-6.4.2)
    \subsection{Résultats du Nettoyage V3}                    % (ex-6.4.4)
    \subsection{Compatibilité et Non-Régression}              % (ex-6.4.5)

\section{Enrichissement V2 (Stage 3)}                         % (ex-6.5)
    \subsection{Heuristiques de Classification}               % (ex-6.5.1)
    \subsection{Résultats de Couverture des Métadonnées}      % (ex-6.5.3)

\section{Similarité (Stage 4)}                                % (ex-6.6)
    \subsection{Algorithme}                                   % (ex-6.6.1)

\section{Chunking V2 (Stage 5 — Optionnel)}                   % (ex-6.7)

\section{Delivery (Stage 7)}                                  % (ex-6.8)
    \subsection{Resolver Cases}                               % (ex-6.8.1)
    \subsection{Diagnostic Cards}                             % (ex-6.8.3)
    \subsection{Alfred Vision — Enrichissement d'Images}      % (ex-6.8.5)
    \subsection{Fiabilité Mesurée de l'Enrichissement Visuel} % (ex-6.8.6)

\section{Architecture Agents — Persona ST ChatGPT}           % (ex-6.9)
    \subsection{Persona : ST GitHub Analyzer}                 % (ex-6.9.2)
    \subsection{Tool 1 : KB Unstructured (Recherche Hybride)} % (ex-6.9.3)
    \subsection{Tool 2 : NovaX Fallback}                      % (ex-6.9.4)
    \subsection{Stratégie de Réponse (System Prompt)}         % (ex-6.9.5)

\section{Configuration de la Plateforme ST ChatGPT}          % (ex-7.1)

\section{Configuration du Tool KB}                            % (ex-7.2)
    \subsection{Paramètres Retenus}                           % (ex-7.2.1)
    \subsection{Justification : Recherche Hybride}            % (ex-7.2.2)
    \subsection{Justification : Seuil Sémantique à 0.55}      % (ex-7.2.3)
    \subsection{Justification : 20 Docs Sémantiques + 12 Full-text} % (ex-7.2.4)
    \subsection{Tool Description}                             % (ex-7.2.6)

\section{Configuration du Tool NovaX (Fallback)}             % (ex-7.3)
    \subsection{Problème Identifié}                           % (ex-7.3.1)
    \subsection{Fix : NovaX comme Fallback Strictement Secondaire} % (ex-7.3.2)
    \subsection{Impact Mesuré}                                % (ex-7.3.3)

\section{System Prompt de la Persona}                        % (ex-7.4)

\section{Couverture Actuelle et Future}                      % (ex-7.6)

\section{Synthèse de l'Implémentation}                       % (ex-6.10)


% =========================================================================
\chapter{Résultats, Évaluation et Industrialisation}
% (fusion des ex-chapitres 8 et 9)
% =========================================================================

\section{Cadrage Théorique et Définitions Préalables}        % (ex-8.1)
    \subsection{Métriques Fondamentales d'Information Retrieval} % (ex-8.1.1)
    \subsection{Similarité Textuelle}                         % (ex-8.1.2)
    \subsection{Métriques de Qualité des Données}             % (ex-8.1.3)
    \subsection{Confiance Contextuelle}                       % (ex-8.1.4)
    \subsection{Score Global Pondéré}                         % (ex-8.1.5)
    \subsection{Quality Index (QI)}                           % (ex-8.1.6)
    \subsection{Retrieval Hybride et Fallback}                % (ex-8.1.7)

\section{Justification des Seuils Décisionnels}              % (ex-8.2)
    \subsection{Cadre Normatif de Référence}                  % (ex-8.2.1)
    \subsection{Échelle de Classification}                    % (ex-8.2.2)
    \subsection{Logique de Calibration de Chaque Borne}       % (ex-8.2.3)
    \subsection{Seuils Différenciés par Champ}                % (ex-8.2.4)
    \subsection{Seuil de Cohérence Alfred (\(\tau = 0.12\))}  % (ex-8.2.5)

\section{Évaluation par Stage du Pipeline}                   % (ex-8.3)
    \subsection{Stage 1 : Ingestion — Complétude des Données Brutes} % (ex-8.3.1)
    \subsection{Stage 2 : Cleaning — Qualité de Préparation Textuelle} % (ex-8.3.2)
    \subsection{Stage 3a : Enrichissement — Classification NLP} % (ex-8.3.3)
    \subsection{Stage 4 : Similarité TF-IDF}                  % (ex-8.3.4)
    \subsection{Stage 5 : Delivery — Complétude des Artefacts} % (ex-8.3.5)
    \subsection{Synthèse des Scores par Stage}                % (ex-8.3.6)
    \subsection{Score Global : Application Numérique}         % (ex-8.3.7)

\section{Évaluation de la Confiance Alfred Vision}           % (ex-8.4)
    \subsection{Fiabilité Opérationnelle}                     % (ex-8.4.1)
    \subsection{Méthode de Calcul de la Cohérence Contextuelle} % (ex-8.4.2)
    \subsection{Résultats de Cohérence Contextuelle}          % (ex-8.4.3)
    \subsection{Analyse de l'Écart Issues vs PDF}             % (ex-8.4.4)

\section{Évolution Incrémentale du Quality Index}            % (ex-8.5 + ex-7.5)
    \subsection{Chronologie et Logique de Progression}        % (ex-8.5.1)
    \subsection{Analyse des Points d'Inflexion}               % (ex-8.5.2)
    \subsection{Matrice Valeur \(\times\) Effort}             % (ex-8.5.3)

\section{Architecture de Fallback : d'Alfred Permissif à NovaX Restrictif} % (ex-8.6)
    \subsection{Problème Initial : Fallback Trop Permissif}   % (ex-8.6.1)
    \subsection{Solution : Description Restrictive}           % (ex-8.6.2)
    \subsection{Évolution vers NovaX}                         % (ex-8.6.3)

\section{Étude Comparative : Alfred Générique vs Persona KB} % (ex-8.7)
    \subsection{Protocole Expérimental}                       % (ex-8.7.1)
    \subsection{Grille de Scoring}                            % (ex-8.7.2)
    \subsection{Résultats Synthétiques}                       % (ex-8.7.3)
    \subsection{Analyse par Catégorie}                        % (ex-8.7.4)

\section{Comparaison des Stratégies de Retrieval}           % (ex-8.8)

\section{Assurance Qualité du Chapitre d'Évaluation}        % (ex-8.9)

\section{Correspondance Métriques \(\leftrightarrow\) Normes \(\leftrightarrow\) Références} % (ex-8.10)

\section{Automatisation et CI/CD — GitHub Actions}          % (ex-9 / 9.1)
    \subsection{Architecture Opérationnelle Actuelle}         % (ex-9.1.1)
    \subsection{Déclenchement et Paramètres}                  % (ex-9.1.2)
    \subsection{Politique Add vs Replace}                     % (ex-9.1.3)
    \subsection{Gestion des Datasource IDs et Reprise après Incident} % (ex-9.1.4)
    \subsection{Disponibilité Runner et Déploiement Industriel} % (ex-9.1.5)
    \subsection{Garanties de Robustesse}                      % (ex-9.1.6)
    \subsection{Procédure Opérationnelle Recommandée}         % (ex-9.1.7)

\section{Synthèse et Bilan}                                  % (ex-8.11)


% =========================================================================
%  Conclusion (non numérotée)
% =========================================================================
\chapter*{Conclusion et Perspectives}
\addcontentsline{toc}{chapter}{Conclusion et Perspectives}
    % Bilan du Projet        (ex-10.1)
    % Valeur Industrielle    (ex-10.2)
    % Leçons Apprises        (ex-10.3)
    % Perspectives           (ex-10.4)
```

## Ajout majeur requis

Une sous-section **« Pourquoi CRISP-DM ? Choix et Justification Méthodologique »** est insérée dans le Chapitre 3 (Section *Approche Méthodologique*), **avant** l'adaptation de CRISP-DM (ex-5.2). Elle compare CRISP-DM à KDD, SEMMA, TDSP (Microsoft) et à une approche Agile pure, et justifie pourquoi CRISP-DM est le cadre le plus pertinent pour un projet orienté données/retrieval comme celui-ci, malgré l'absence de modèle prédictif entraîné.

**Statut : ✅ implémentée.** La sous-section `\subsection{Pourquoi CRISP-DM ? Choix et Justification Méthodologique}` (label `sec:pourquoi_crispdm`) est en place dans le Chapitre 3, entre `\subsection{Sélection de la Méthodologie : Scrum Adapté}` et `\subsection{Adaptation de CRISP-DM au Projet}`. Elle compare explicitement CRISP-DM à Agile/Scrum pur, KDD, SEMMA, TDSP et une approche ad hoc, avec une grille de comparaison synthétique et une conclusion argumentative.

## Statut de mise en œuvre

- [x] Fichier de structure créé/à jour (ce document).
- [x] Fusion physique du rapport LaTeX en 5 chapitres numérotés (Contexte, État de l'Art, Conception, Réalisation, Résultats), encadrés par une Introduction Générale et une Conclusion Générale non numérotées.
- [x] Nouvelle sous-section « Pourquoi CRISP-DM ? » rédigée et intégrée au Chapitre 3.
- [x] Démotions de niveaux de titres effectuées (Scrum, Adaptation CRISP-DM, `chapter_configuration.tex` en entier) pour respecter la hiérarchie à 5 chapitres.
- [x] Déplacements effectués : Acteurs/Besoins/Contraintes (ex-Ch3) fusionnés avec Méthodologie/Architecture (ex-Ch5) ; « Notre Pipeline : Mapping » déplacé du Chapitre 2 vers le Chapitre 3 ; « Architecture Cible » repositionnée après les Contraintes de la Plateforme.
- [x] `chapter_configuration.tex` démoté de `\chapter` à `\section` et intégré (via `\input`) dans le Chapitre 4, juste après la synthèse de l'implémentation — inclut l'Automatisation CI/CD (conservée ici plutôt que déplacée au Chapitre 5, car elle relève de la phase *Deployment* au même titre que la configuration de la persona).
- [x] `chapter_evaluation.tex` conservé tel quel comme `\chapter{Résultats et Évaluation}` = Chapitre 5 (titre non modifié en « ...et Industrialisation » car l'industrialisation/CI-CD est physiquement au Chapitre 4).
- [x] Introduction Générale : liste des chapitres mise à jour (5 chapitres au lieu de 8).
- [x] Conclusion : passée en `\chapter*` non numéré (cohérent avec l'Introduction Générale non numérotée).
- [x] Références croisées corrigées : `chap:conception`, `chap:realisation` définis ; renvoi `chap:methodologie` supprimé ; ligne *Deployment* du tableau CRISP-DM pointant vers `chap:realisation`.
- [ ] Nettoyage optionnel des blocs `\iffalse ... \fi` de contenu obsolète (ancien chapitre évaluation/configuration dupliqué) — laissés en l'état (non rendus à la compilation, donc sans impact) faute de gain net vs risque de régression sur un fichier volumineux.
- [ ] Compilation `pdflatex` complète non exécutée dans cet environnement (pas d'accès terminal) — à valider manuellement par l'utilisateur.

