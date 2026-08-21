"""
Generate PDF documentation from content (no LaTeX required).
Uses fpdf2 library: pip install fpdf2
"""
import sys
from pathlib import Path

try:
    from fpdf import FPDF
except ImportError:
    print("Installing fpdf2...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "fpdf2"])
    from fpdf import FPDF


class STReport(FPDF):
    def __init__(self, title, subtitle):
        super().__init__()
        self.doc_title = title
        self.doc_subtitle = subtitle
        self.set_auto_page_break(auto=True, margin=20)

    def header(self):
        if self.page_no() > 1:
            self.set_font("Helvetica", "I", 8)
            self.set_text_color(100, 100, 100)
            self.cell(0, 5, self.doc_title, align="L")
            self.cell(0, 5, f"Page {self.page_no()}", align="R")
            self.ln(8)
            self.set_draw_color(200, 200, 200)
            self.line(10, self.get_y(), 200, self.get_y())
            self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f"{self.page_no()}/{{nb}}", align="C")

    def title_page(self, author, date_str, extra_lines=None):
        self.add_page()
        self.ln(40)
        self.set_font("Helvetica", "B", 28)
        self.set_text_color(26, 35, 126)
        self.multi_cell(0, 12, self.doc_title, align="C")
        self.ln(8)
        self.set_font("Helvetica", "", 16)
        self.set_text_color(80, 80, 80)
        self.multi_cell(0, 8, self.doc_subtitle, align="C")
        self.ln(20)
        if extra_lines:
            self.set_font("Helvetica", "", 11)
            for line in extra_lines:
                self.cell(0, 7, line, align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(20)
        self.set_font("Helvetica", "", 12)
        self.set_text_color(60, 60, 60)
        self.cell(0, 7, author, align="C", new_x="LMARGIN", new_y="NEXT")
        self.cell(0, 7, date_str, align="C", new_x="LMARGIN", new_y="NEXT")

    def chapter_title(self, title):
        self.add_page()
        self.set_font("Helvetica", "B", 20)
        self.set_text_color(26, 35, 126)
        self.cell(0, 12, title, new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(26, 35, 126)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(8)

    def section_title(self, title):
        self.ln(4)
        self.set_font("Helvetica", "B", 14)
        self.set_text_color(40, 40, 40)
        self.cell(0, 8, title, new_x="LMARGIN", new_y="NEXT")
        self.ln(3)

    def subsection_title(self, title):
        self.ln(2)
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(60, 60, 60)
        self.cell(0, 7, title, new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def body_text(self, text):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(30, 30, 30)
        self.multi_cell(0, 5.5, text)
        self.ln(2)

    def bullet_list(self, items):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(30, 30, 30)
        for item in items:
            self.cell(5)
            self.cell(5, 5.5, chr(8226))
            self.multi_cell(0, 5.5, item)
            self.ln(1)
        self.ln(2)

    def code_block(self, code):
        self.set_font("Courier", "", 8)
        self.set_fill_color(245, 245, 245)
        self.set_text_color(50, 50, 50)
        lines = code.split("\n")
        for line in lines:
            self.cell(0, 4.5, "  " + line, fill=True, new_x="LMARGIN", new_y="NEXT")
        self.ln(3)
        self.set_font("Helvetica", "", 10)

    def table(self, headers, rows):
        self.set_font("Helvetica", "B", 9)
        self.set_fill_color(26, 35, 126)
        self.set_text_color(255, 255, 255)
        col_w = (190 - 10) / len(headers)
        for h in headers:
            self.cell(col_w, 7, h, border=1, fill=True, align="C")
        self.ln()
        self.set_font("Helvetica", "", 9)
        self.set_text_color(30, 30, 30)
        fill = False
        for row in rows:
            if fill:
                self.set_fill_color(240, 240, 250)
            else:
                self.set_fill_color(255, 255, 255)
            for cell in row:
                self.cell(col_w, 6, cell, border=1, fill=True, align="C")
            self.ln()
            fill = not fill
        self.ln(4)


def generate_enterprise_doc(output_path):
    pdf = STReport(
        "STM32Cube GitHub Preprocessing Pipeline",
        "Technical Documentation - Enterprise Reference"
    )
    pdf.alias_nb_pages()

    # Title page
    pdf.title_page(
        "Abir Gharbi - STMicroelectronics",
        "Version 2.0 - June 2026",
        ["AI & Digital Tools Division", ""]
    )

    # Chapter 1: Executive Summary
    pdf.chapter_title("1. Executive Summary")
    pdf.section_title("1.1 Project Overview")
    pdf.body_text(
        "This project implements an automated preprocessing pipeline that transforms raw GitHub data "
        "from STMicroelectronics' public STM32Cube repositories into structured, RAG-ready "
        "(Retrieval-Augmented Generation) knowledge base content. The system feeds the ST GitHub "
        "Analyzer AI persona, enabling intelligent technical support for STM32 embedded systems engineers."
    )
    pdf.section_title("1.2 Key Achievements")
    pdf.bullet_list([
        "5 STM32 series fully processed: H7, F4, H5, U5, WL",
        "47 repositories ingested (main repos + HAL/CMSIS/BSP drivers)",
        "4 delivery artifact types: Issues, Files, Resolver Cases, Diagnostic Cards",
        "Automated KB upload via ST AI Bridge API (KB #793)",
        "Alfred Vision AI integration for image-to-text enrichment",
        "50-question test suite for quality benchmarking",
    ])
    pdf.section_title("1.3 System Context")
    pdf.code_block(
        "GitHub (STMicroelectronics)\n"
        "    -> Preprocessing Pipeline (this project)\n"
        "        -> ST-Ready JSON artifacts\n"
        "            -> ST AI Bridge KB (#793)\n"
        "                -> ST GitHub Analyzer Persona (Chatbot)\n"
        "                    -> End users (Engineers/Customers)"
    )

    # Chapter 2: Architecture
    pdf.chapter_title("2. Architecture")
    pdf.section_title("2.1 Pipeline Stages")
    pdf.body_text("The pipeline consists of 7 sequential stages:")
    pdf.bullet_list([
        "Stage 1: Ingestion - Fetch raw data from GitHub API and local clones",
        "Stage 2: Cleaning - Normalize, deduplicate, structure metadata",
        "Stage 3: Enrichment V2 - Classify issues/files with heuristic NLP",
        "Stage 4: Similarity - Compute TF-IDF cross-issue similarity",
        "Stage 5: Chunking V2 - Split documents for optimal retrieval",
        "Stage 6: Evaluation - Stats, TF-IDF search tests, schema validation",
        "Stage 7: Delivery - Export ST-ready JSON for KB upload",
    ])
    pdf.section_title("2.2 Repository Structure")
    pdf.code_block(
        "PFE_Chatbot_STM32Cube/\n"
        "|-- pipeline/                  # Core pipeline stages\n"
        "|   |-- ingestion/             # GitHub API fetchers\n"
        "|   |-- cleaning/              # Data normalization\n"
        "|   |-- enrichment/            # NLP classification\n"
        "|   |-- similarity/            # TF-IDF similarity\n"
        "|   |-- chunking/              # Document splitting\n"
        "|   |-- evaluation/            # Quality testing\n"
        "|   |-- delivery/              # ST-ready export\n"
        "|   +-- run_full_workflow.py   # Orchestrator\n"
        "|-- pipeline_Automation/       # Upload & batch scripts\n"
        "|-- shared/config/             # Per-series config files\n"
        "|-- shared/schemas/            # JSON Schema definitions\n"
        "|-- datasets/01_raw/           # Raw ingested data\n"
        "|-- datasets/07_delivery/      # Final delivery outputs\n"
        "+-- docs/                      # Documentation & diagrams"
    )
    pdf.section_title("2.3 Configuration System")
    pdf.body_text("Each MCU series has a dedicated configuration file:")
    pdf.bullet_list([
        "shared/config/config.json - Default (H7, 12 repos)",
        "shared/config/config_f4.json - STM32F4 (16 repos)",
        "shared/config/config_h5.json - STM32H5 (6 repos)",
        "shared/config/config_u5.json - STM32U5 (8 repos)",
        "shared/config/config_wl.json - STM32WL (5 repos)",
    ])

    # Chapter 3: Pipeline Stage Details
    pdf.chapter_title("3. Pipeline Stage Details")

    pdf.section_title("3.1 Stage 1: Ingestion")
    pdf.body_text("Scripts and their functions:")
    pdf.table(
        ["Script", "Function"],
        [
            ["fetch_issues.py", "Fetch all issues (open+closed) with comments"],
            ["fetch_prs.py", "Fetch pull requests with diff stats"],
            ["fetch_commits.py", "Fetch commits with messages"],
            ["fetch_issue_pr_commit_links.py", "Cross-reference issues/PRs/commits"],
            ["repo_sync_service.py", "Git clone/pull repositories locally"],
            ["fetch_files.py", "Extract file content from local clones"],
            ["github_service.py", "Auth, rate-limiting, pagination"],
        ]
    )

    pdf.section_title("3.2 Stage 2: Cleaning")
    pdf.bullet_list([
        "clean_issues.py - Normalize issue fields, filter spam, deduplicate",
        "clean_files.py - Normalize file paths, filter binary/irrelevant files",
    ])

    pdf.section_title("3.3 Stage 3: Enrichment V2")
    pdf.subsection_title("Issues Classification (issues_to_docs_v2.py)")
    pdf.body_text(
        "Uses stm32cube_preprocessing_heuristics.py to classify each issue with "
        "regex patterns, label analysis, and weighted scoring:"
    )
    pdf.table(
        ["Field", "Type", "Example Values"],
        [
            ["mcu_series", "string", "F4, H5, H7, U5, WL"],
            ["layer", "string", "HAL, LL, Middleware, BSP"],
            ["component", "string", "SPI, I2C, USB, ETH, DMA"],
            ["board", "string", "NUCLEO-F446RE, Discovery"],
            ["issue_kind", "string", "bug_report, usage_question"],
            ["severity", "string", "low, medium, high, critical"],
            ["evidence_strength", "string", "low, medium, high"],
            ["is_valid", "boolean", "true/false (quality gate)"],
        ]
    )
    pdf.subsection_title("Files Classification (files_to_docs_v2.py)")
    pdf.body_text(
        "Classifies files by type (readme/release_notes/source/example/bsp), "
        "extracts board from path, detects component from HAL module name."
    )

    pdf.section_title("3.4 Stage 4: Similarity")
    pdf.body_text(
        "compute_issue_similarity_v2.py builds a TF-IDF matrix from issue text, "
        "computes pairwise cosine similarity, and attaches related_issue_ids[] "
        "(top-5, threshold > 0.3) for cross-linking related problems."
    )

    pdf.section_title("3.5 Stage 5: Chunking V2")
    pdf.body_text("Two chunking strategies optimized for retrieval:")
    pdf.bullet_list([
        "Issues: Paragraph-based, max 512 tokens, 50-token overlap",
        "Files: Section-based (markdown headers / function boundaries)",
        "512 tokens matches ST AI Bridge semantic search window",
        "50-token overlap ensures sentence continuity at boundaries",
    ])

    pdf.section_title("3.6 Stage 6: Evaluation")
    pdf.table(
        ["Script", "Purpose"],
        [
            ["test_stats_issues_v2.py", "Distribution: severity, layer, component"],
            ["test_stats_files_v2.py", "File type distribution, board coverage"],
            ["test_tfidf_search_issues_v2.py", "TF-IDF retrieval precision (P@5)"],
            ["test_tfidf_search_files_v2.py", "File retrieval precision testing"],
            ["validate_schemas.py", "JSON Schema validation gate"],
        ]
    )

    pdf.section_title("3.7 Stage 7: Delivery")
    pdf.subsection_title("Resolver Cases")
    pdf.body_text(
        "Generated from closed issues with linked PRs. Builds the chain: "
        "Issue -> PR -> Commits. Evaluates resolution_status (merged_fix, "
        "candidate_fix, reference_only). Structured text: Problem -> Signal -> "
        "Assessment -> Evidence."
    )
    pdf.subsection_title("Diagnostic Cards")
    pdf.body_text(
        "Structured fault analysis for high-value issues. Includes query_aliases "
        "for retrieval, keywords as technical anchors, and evidence_refs. "
        "Template: Symptom -> Root Cause -> Resolution -> Validation Steps."
    )

    # Chapter 4: KB Upload & Deployment
    pdf.chapter_title("4. KB Upload & Deployment")
    pdf.section_title("4.1 ST AI Bridge API")
    pdf.bullet_list([
        "Endpoint: https://api-ai-bridge.st.com/chatgpt/api/client-apps",
        "KB ID: 793 (ST GitHub Analyzer)",
        "Auth: clientAppName + apiKey (header)",
        "Upload tool: Add_Data_Source_Files.py",
    ])
    pdf.section_title("4.2 Datasource Registry")
    pdf.table(
        ["Series", "Issues", "Files", "Resolver", "Diagnostic"],
        [
            ["F4", "#28099", "#28103", "#28118", "#28122"],
            ["H5", "#28158", "#28163", "#28164", "#28165"],
            ["U5", "#28167", "#28168", "#28244", "#28170"],
            ["WL", "#28171", "#28172", "#28245", "#28173"],
        ]
    )
    pdf.section_title("4.3 Large File Handling")
    pdf.body_text(
        "Files exceeding Azure Blob limits (>10MB) are automatically split using "
        "--json-split-size 1000 (splits arrays into 1000-doc parts). "
        "Example: st_ready_files_stm32cubef4.json (25.5MB, 5397 items) -> 6 parts."
    )

    # Chapter 5: Alfred Vision AI
    pdf.chapter_title("5. Alfred Vision AI Integration")
    pdf.body_text(
        "Many GitHub issues contain screenshots (error dialogs, logic analyzer traces, "
        "CubeMX configurations). These images are opaque to text-based RAG retrieval. "
        "Alfred converts images to searchable text."
    )
    pdf.section_title("5.1 Process")
    pdf.bullet_list([
        "Scan JSON for image URLs in issue body/comments",
        "Send each image to Alfred Vision API",
        "Receive: semantic description + OCR-extracted text",
        "Append [IMAGE DESCRIPTION] and [IMAGE TEXT] to issue content",
        "Upload enriched version to KB (replaces original)",
    ])
    pdf.section_title("5.2 Impact")
    pdf.body_text(
        "Error messages in screenshots become queryable. Users searching for "
        "'HAL_SPI_ERROR_OVR' now find issues where that error only appeared in an image."
    )

    # Chapter 6: Persona Configuration
    pdf.chapter_title("6. Persona Configuration")
    pdf.section_title("6.1 Recommended Settings")
    pdf.table(
        ["Parameter", "Value"],
        [
            ["Tool Name", "ST-GitHub-Analyzer-Unstructured"],
            ["Search Type", "Hybrid (Semantic + Full-text)"],
            ["Semantic Threshold", "0.55"],
            ["Semantic Max Doc Count", "20"],
            ["Full-text Max Doc Count", "12"],
        ]
    )
    pdf.section_title("6.2 Answer Strategy")
    pdf.bullet_list([
        "Direct KB match -> cite source with link",
        "Partial match -> diagnosis + candidate workaround + validation steps",
        "General config question -> direct technical explanation",
        "No match -> actionable next step (never only 'I don't know')",
    ])

    # Chapter 7: Automation
    pdf.chapter_title("7. Automation & Operations")
    pdf.section_title("7.1 Full Workflow Execution")
    pdf.code_block(
        "# Standard run\n"
        "python -m pipeline.run_full_workflow\n\n"
        "# With delivery export\n"
        "python -m pipeline.run_full_workflow --export-st-ready\n\n"
        "# Skip ingestion (reprocess from existing raw data)\n"
        "python -m pipeline.run_full_workflow --skip-ingestion --continue-on-error"
    )
    pdf.section_title("7.2 Upload Scripts")
    pdf.bullet_list([
        "upload_f4_files_datasource.py - F4 files with --json-split-size 1000",
        "upload_u5_all_datasources.py - All-in-one with --create-only / --upload-only",
        "upload_wl_all_datasources.py - Same pattern as U5",
        "upload_alfred_issues_all_series.py - Alfred-enriched to all series",
        "create_missing_resolver_datasources.py - Creates missing datasources",
    ])
    pdf.section_title("7.3 GitHub Actions CI/CD")
    pdf.body_text(
        "GitHub Actions workflow (.github/workflows/auto_update_kb.yml) defines automated bi-weekly pipeline: checkout -> setup -> "
        "ingest -> process -> validate -> deliver -> upload. "
        "Parameterized for series selection. Runs on cloud + self-hosted runner for upload."
    )

    # Chapter 8: Quality Assurance
    pdf.chapter_title("8. Quality Assurance")
    pdf.section_title("8.1 Test Suite")
    pdf.body_text(
        "50-question test suite (all_series_test_suite_50q_v2.csv) with realistic "
        "customer-voice questions: 13 F4, 12 H5, 13 U5, 12 WL. Each includes "
        "board context + symptom + expected technical anchors."
    )
    pdf.section_title("8.2 Schema Validation")
    pdf.body_text(
        "JSON schemas under shared/schemas/ enforce structural contracts. "
        "Run: python -m pipeline.evaluation.validate_schemas"
    )
    pdf.section_title("8.3 Quality Metrics")
    pdf.table(
        ["Metric", "Target", "Actual"],
        [
            ["Layer detection rate", ">80%", "~85%"],
            ["Component detection", ">60%", "~70%"],
            ["TF-IDF P@5 (issues)", ">0.6", "~0.72"],
            ["TF-IDF P@5 (files)", ">0.6", "~0.78"],
            ["Schema validation", "0 errors", "0 errors"],
        ]
    )

    pdf.output(str(output_path))
    print(f"[OK] Enterprise doc: {output_path}")


def generate_pfe_report(output_path):
    pdf = STReport(
        "Pipeline de Preprocessing STM32Cube",
        "Rapport de Projet de Fin d'Etudes"
    )
    pdf.alias_nb_pages()

    # Title page
    pdf.title_page(
        "Abir Gharbi",
        "Annee universitaire 2025-2026",
        [
            "STMicroelectronics - AI & Digital Tools Division",
            "",
            "Conception et Implementation d'un Pipeline",
            "de Pretraitement Intelligent pour la",
            "Base de Connaissances STM32Cube",
        ]
    )

    # Remerciements
    pdf.chapter_title("Remerciements")
    pdf.body_text(
        "Je tiens a exprimer ma sincere gratitude envers toute l'equipe "
        "STMicroelectronics pour leur accueil, leur encadrement et leur soutien "
        "tout au long de ce stage. Je remercie particulierement mon tuteur entreprise "
        "pour sa disponibilite et ses conseils avises."
    )

    # Introduction
    pdf.chapter_title("1. Introduction Generale")
    pdf.section_title("1.1 Contexte")
    pdf.body_text(
        "STMicroelectronics est un leader mondial dans la conception de semi-conducteurs. "
        "La famille STM32 represente plus de 1500 references de microcontroleurs utilises "
        "dans l'industrie, l'automobile, l'IoT et l'electronique grand public."
    )
    pdf.body_text(
        "Les depots GitHub publics de STMicroelectronics contiennent des milliers d'issues, "
        "pull requests, et fichiers de documentation technique qui representent une source "
        "de connaissances precieuse mais inexploitee de maniere structuree."
    )
    pdf.section_title("1.2 Problematique")
    pdf.body_text(
        "Les ingenieurs rencontrant des problemes avec les MCU STM32 n'ont pas de moyen "
        "efficace d'exploiter la richesse des donnees GitHub. La recherche manuelle est:"
    )
    pdf.bullet_list([
        "Lente - des milliers d'issues par serie MCU",
        "Bruitee - contenu non structure, images, discussions hors-sujet",
        "Fragmentee - correlations entre issues/PRs/commits non visibles",
    ])
    pdf.section_title("1.3 Objectifs")
    pdf.bullet_list([
        "Concevoir un pipeline automatise d'ingestion depuis GitHub",
        "Nettoyer, enrichir et structurer les documents avec du NLP",
        "Generer des artefacts RAG-ready pour une base de connaissances",
        "Alimenter un chatbot IA specialise STM32 via l'API ST AI Bridge",
    ])

    # Etat de l'art
    pdf.chapter_title("2. Etat de l'Art")
    pdf.section_title("2.1 Retrieval-Augmented Generation (RAG)")
    pdf.body_text(
        "Le paradigme RAG combine la recherche d'information avec la generation de texte "
        "par des LLMs. Au lieu de se fier uniquement aux connaissances parametrisees du "
        "modele, RAG recupere des documents pertinents depuis une base de connaissances, "
        "augmente le contexte du prompt, puis genere une reponse fondee sur des preuves."
    )
    pdf.subsection_title("Avantages pour le domaine technique")
    pdf.bullet_list([
        "Reduction des hallucinations grace aux sources verifiables",
        "Mise a jour continue de la KB sans re-entrainement",
        "Tracabilite des reponses vers les issues/PRs source",
    ])
    pdf.section_title("2.2 Pretraitement pour Knowledge Bases")
    pdf.body_text(
        "La qualite du RAG depend directement de la qualite des documents indexes. "
        "Les strategies de chunking (fixed-size, paragraph, section) et l'enrichissement "
        "de metadonnees determinent la precision de la recherche."
    )
    pdf.section_title("2.3 Solutions Existantes")
    pdf.table(
        ["Solution", "Forces", "Limites"],
        [
            ["GitHub Copilot", "Code completion", "Pas de KB custom"],
            ["Stack Overflow", "Communaute large", "Pas specifique ST"],
            ["RAG generique", "Flexible", "Pas domain-aware"],
            ["Notre approche", "Domain-specific", "Pipeline custom"],
        ]
    )

    # Methodologie
    pdf.chapter_title("3. Methodologie et Architecture")
    pdf.section_title("3.1 Approche Iterative")
    pdf.bullet_list([
        "Phase 1: Pipeline H7 (serie pilote, 12 repos)",
        "Phase 2: Extension multi-series (F4, H5, U5, WL)",
        "Phase 3: Enrichissement IA (Alfred Vision) et evaluation",
    ])
    pdf.section_title("3.2 Architecture Globale")
    pdf.body_text("Le systeme s'articule autour de 3 couches:")
    pdf.bullet_list([
        "Couche Data: ingestion et stockage structure (JSON)",
        "Couche Processing: pipeline Python en 7 etapes",
        "Couche Delivery: export et upload vers la KB cloud",
    ])
    pdf.section_title("3.3 Choix Techniques")
    pdf.table(
        ["Choix", "Justification"],
        [
            ["Python 3.14", "Ecosysteme riche, deploiement simple"],
            ["JSON format pivot", "Natif REST, lisible, versionnable"],
            ["TF-IDF (scikit-learn)", "Leger, rapide, suffisant"],
            ["Heuristiques vs ML", "Deterministe, explicable"],
            ["Architecture modulaire", "Chaque etape rejouable"],
        ]
    )
    pdf.section_title("3.4 Pipeline en 7 Etapes")
    pdf.code_block(
        "GitHub API -> 01_raw -> 02_clean -> 03_enriched -> 04_similarity\n"
        "          -> 05_chunked -> 06_evaluated -> 07_delivery -> KB #793"
    )

    # Implementation
    pdf.chapter_title("4. Implementation")
    pdf.section_title("4.1 Ingestion (Stage 1)")
    pdf.body_text(
        "Recuperation exhaustive des donnees via l'API GitHub: issues avec commentaires, "
        "PRs, commits, liens croises, et fichiers source. Pagination automatique, "
        "gestion du rate-limiting (5000 req/h), retry exponentiel."
    )
    pdf.section_title("4.2 Nettoyage (Stage 2)")
    pdf.bullet_list([
        "Suppression des issues bot/spam",
        "Normalisation des labels GitHub",
        "Extraction du texte utile (templates vides supprimes)",
        "Deduplication par identifiant",
    ])
    pdf.section_title("4.3 Enrichissement V2 (Stage 3)")
    pdf.body_text(
        "Le module stm32cube_preprocessing_heuristics.py applique des regles basees sur "
        "des regex patterns, l'analyse des labels, et un scoring pondere pour classifier "
        "chaque issue (layer, component, board, severity, issue_kind)."
    )
    pdf.section_title("4.4 Similarite (Stage 4)")
    pdf.body_text(
        "Construction de la matrice TF-IDF sur le corpus, calcul de la similarite cosinus "
        "paire-a-paire, selection des top-5 voisins (seuil > 0.3). "
        "Formule: sim(A,B) = (A.B) / (||A|| x ||B||)"
    )
    pdf.section_title("4.5 Chunking V2 (Stage 5)")
    pdf.bullet_list([
        "Issues: chunks par paragraphe, max 512 tokens, overlap 50",
        "Files: chunks par section (headers markdown, fonctions C)",
        "512 tokens = fenetre de recherche semantique ST AI Bridge",
    ])
    pdf.section_title("4.6 Delivery (Stage 7)")
    pdf.subsection_title("Resolver Cases")
    pdf.body_text(
        "Generes a partir d'issues fermees avec PRs liees. "
        "Chaine: Issue -> PR -> Commits. Statut: merged_fix / candidate_fix / reference_only."
    )
    pdf.subsection_title("Diagnostic Cards")
    pdf.body_text(
        "Cartes de diagnostic structurees: Symptome -> Cause Racine -> Resolution -> Validation. "
        "Incluent query_aliases et keywords pour ameliorer la recuperation."
    )
    pdf.section_title("4.7 Integration Alfred Vision")
    pdf.body_text(
        "Les images dans les issues (screenshots d'erreurs, traces oscilloscope) sont "
        "converties en texte par Alfred Vision API: description semantique + OCR. "
        "Les messages d'erreur dans les images deviennent cherchables."
    )

    # Results
    pdf.chapter_title("5. Resultats et Evaluation")
    pdf.section_title("5.1 Couverture des Donnees")
    pdf.table(
        ["Serie", "Repos", "Issues", "Files", "Resolver"],
        [
            ["STM32F4", "16", "~800", "~5400", "~150"],
            ["STM32H5", "6", "~200", "~1200", "~40"],
            ["STM32U5", "8", "~350", "~2000", "~70"],
            ["STM32WL", "5", "~150", "~800", "~30"],
            ["STM32H7", "12", "~500", "~3000", "~100"],
            ["TOTAL", "47", "~2000", "~12400", "~390"],
        ]
    )
    pdf.section_title("5.2 Qualite de l'Enrichissement")
    pdf.table(
        ["Metrique", "Resultat"],
        [
            ["Detection layer", "~85% des issues"],
            ["Detection component", "~70% des issues"],
            ["Detection board", "~45% (mention explicite)"],
            ["Severity (toujours calcule)", "100%"],
        ]
    )
    pdf.section_title("5.3 Performance de Recherche")
    pdf.bullet_list([
        "Precision@5 issues: ~0.72",
        "Precision@5 files: ~0.78",
        "Recherche hybride (semantic + full-text) > TF-IDF seul",
    ])
    pdf.section_title("5.4 Test Suite (50 Questions)")
    pdf.body_text(
        "50 questions realistes couvrant F4, H5, U5, WL. "
        "Formulees en langage naturel 'client' avec contexte board et symptome technique."
    )

    # Conclusion
    pdf.chapter_title("6. Conclusion et Perspectives")
    pdf.section_title("6.1 Bilan")
    pdf.body_text("Ce projet a permis de concevoir et deployer un pipeline complet qui:")
    pdf.bullet_list([
        "Transforme des donnees GitHub brutes en connaissances structurees",
        "Alimente un chatbot IA specialise STM32 en production",
        "Couvre 5 series MCU (47 repositories, ~14400 documents)",
        "Integre l'enrichissement IA par vision (Alfred)",
    ])
    pdf.section_title("6.2 Perspectives")
    pdf.bullet_list([
        "Extension a d'autres series: STM32L4, STM32G4, STM32MP",
        "Enrichissement semantique: embeddings pre-calcules",
        "CI/CD automatise: GitHub Actions pipeline pour mise a jour continue",
        "Evaluation automatique: scoring RAG (Faithfulness, Relevance)",
        "Multi-langue: support des issues en chinois/japonais",
    ])

    # References
    pdf.chapter_title("References")
    pdf.bullet_list([
        "[1] Lewis, P. et al. (2020). Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks. NeurIPS 2020.",
        "[2] OpenAI (2023). GPT-4 Technical Report. arXiv:2303.08774.",
        "[3] Salton, G., Buckley, C. (1988). Term-weighting approaches in automatic text retrieval.",
        "[4] STMicroelectronics (2024). STM32Cube MCU & MPU Packages. github.com/STMicroelectronics",
    ])

    # Annexes
    pdf.chapter_title("Annexes")
    pdf.section_title("A. Liste des Diagrammes")
    pdf.bullet_list([
        "01_pipeline_overview.drawio - Pipeline 7 etapes (presentation)",
        "02_delivery_kb_upload.drawio - Delivery + upload KB (presentation)",
        "03_data_flow_source_to_answer.drawio - Flux end-to-end (presentation)",
        "04_series_coverage_scale.drawio - Couverture 5 series (presentation)",
        "05_alfred_vision_integration.drawio - Alfred Vision (presentation)",
        "01_ingestion_detail.drawio - Scripts ingestion (technique)",
        "02_enrichment_similarity_detail.drawio - Heuristiques (technique)",
        "03_delivery_resolver_diagnostic.drawio - Resolver/Diagnostic (technique)",
        "04_chunking_v2_strategy.drawio - Strategies chunking (technique)",
        "05_evaluation_validation.drawio - Quality gate (technique)",
        "06_automation_ci_upload.drawio - CI/CD et upload (technique)",
    ])
    pdf.section_title("B. Datasource IDs")
    pdf.table(
        ["Serie", "Issues", "Files", "Resolver", "Diagnostic"],
        [
            ["F4", "#28099", "#28103", "#28118", "#28122"],
            ["H5", "#28158", "#28163", "#28164", "#28165"],
            ["U5", "#28167", "#28168", "#28244", "#28170"],
            ["WL", "#28171", "#28172", "#28245", "#28173"],
        ]
    )
    pdf.section_title("C. Commandes d'Execution")
    pdf.code_block(
        "# Pipeline complet avec delivery\n"
        "python -m pipeline.run_full_workflow --export-st-ready\n\n"
        "# Validation des schemas\n"
        "python -m pipeline.evaluation.validate_schemas\n\n"
        "# Upload vers KB\n"
        "python Add_Data_Source_Files.py --operation add \\\n"
        "  --ds-id 28099 --json-split-size 1000 \\\n"
        "  --file \"datasets/07_delivery/st_ready/.../issues.json\""
    )

    pdf.output(str(output_path))
    print(f"[OK] PFE report: {output_path}")


if __name__ == "__main__":
    docs_dir = Path(__file__).parent
    generate_enterprise_doc(docs_dir / "STM32Cube_Pipeline_Documentation_Enterprise.pdf")
    generate_pfe_report(docs_dir / "PFE_Report_STM32Cube_Pipeline.pdf")
    print("\nDone! Both PDFs generated in docs/")
