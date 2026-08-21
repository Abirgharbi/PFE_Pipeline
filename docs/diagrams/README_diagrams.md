# Pipeline Architecture Diagrams

These diagrams are also available as `.drawio` files in this directory for editing.
Below are **Mermaid** versions you can preview directly in VS Code (Ctrl+Shift+V) or any Markdown viewer.

---

## 1. Master Architecture

```mermaid
graph LR
    subgraph "DATA SOURCES"
        A1[GitHub API<br/>Issues, PRs, Commits]
        A2[Local Clones<br/>GitHub_repos/]
        A3[PDF Documents<br/>User Manuals, App Notes]
        A4[Config JSON<br/>shared/config/config_*.json]
    end

    subgraph "PROCESSING ENGINE"
        B1[1. Ingestion]
        B2[2. Cleaning]
        B3[3. Enrichment V2]
        B4[4. Similarity]
        B5[5. Evaluation]
        B6[6. Delivery]
        B7[7. Upload]
        B1 --> B2 --> B3 --> B4 --> B5 --> B6 --> B7
    end

    subgraph "ALFRED VISION"
        C1[Path A: PDF Figures<br/>Step 7 - BEFORE cleaning]
        C2[Path B: Issue Images<br/>Step 23 - AFTER delivery]
    end

    subgraph "CONSUMPTION"
        D1[KB #793<br/>Hybrid Search]
        D2[ST ChatGPT Persona<br/>ST GitHub Analyzer]
        D3[End User<br/>Support Engineer]
        D1 --> D2 --> D3
    end

    A1 --> B1
    A2 --> B1
    A3 --> C1
    A4 --> B1
    C1 --> B3
    B6 --> C2
    C2 --> B7
    B7 --> D1
```

---

## 2. Full Pipeline — 23 Steps

```mermaid
graph TD
    subgraph "Phase 1: INGESTION (Steps 1-6)"
        S1[1. fetch_issues]
        S2[2. fetch_prs]
        S3[3. fetch_commits]
        S4[4. fetch_issue_pr_commit_links]
        S5[5. repo_sync_service]
        S6[6. fetch_files]
    end

    subgraph "Phase 2: ALFRED PDF (Step 7)"
        S7[7. extract_pdf_multimodal<br/>PyMuPDF → OpenCV → ALFRED]
    end

    subgraph "Phase 3: CLEANING (Steps 8-9)"
        S8[8. clean_issues]
        S9[9. clean_files]
    end

    subgraph "Phase 4: ENRICHMENT (Steps 10-12)"
        S10[10. issues_to_docs_v2]
        S11[11. files_to_docs_v2]
        S12[12. compute_issue_similarity_v2]
    end

    subgraph "Phase 5: EVALUATION (Steps 13-17)"
        S13[13. docs_to_chunks_issues_v2]
        S14[14. docs_to_chunks_files_v2]
        S15[15. test_stats_issues_v2]
        S16[16. test_stats_files_v2]
        S17[17. validate_schemas]
    end

    subgraph "Phase 6: DELIVERY (Steps 18-22)"
        S18[18. export_st_ready_issues]
        S19[19. export_st_ready_files]
        S20[20. export_st_ready_resolver_cases]
        S21[21. export_st_ready_diagnostic_cards]
        S22[22. export_st_ready_issues_with_images]
    end

    subgraph "Phase 7: ALFRED IMAGES (Step 23)"
        S23[23. enrich_json_images_with_alfred<br/>IMAGE ATTACHED → IMAGE DESCRIPTION]
    end

    S6 --> S7 --> S8
    S1 --> S8
    S9 --> S10
    S8 --> S10
    S12 --> S13
    S17 -->|--export-st-ready| S18
    S22 --> S23
```

---

## 3. ALFRED Vision — Two Paths

```mermaid
graph TD
    subgraph "Path A: PDF Figure Enrichment (Step 7)"
        PA1[PDF Documents<br/>in GitHub_repos/]
        PA2[PyMuPDF: render pages<br/>→ data/pdf_pages/*.png]
        PA3[OpenCV: detect & crop figures<br/>→ data/pdf_figures/*.png]
        PA4[Build JSONL task file<br/>→ data/pdf_image_tasks_*.jsonl]
        PA5[ALFRED Vision API<br/>api-ai-bridge.st.com]
        PA6[Output: data/pdf_image_descriptions.json<br/>242 descriptions, 19 series]
        PA7[Inject into files_to_docs_v2<br/>→ FIGURE_DESCRIPTIONS blocks]

        PA1 --> PA2 --> PA3 --> PA4 --> PA5 --> PA6 --> PA7
    end

    subgraph "Path B: Issue Image Enrichment (Step 23)"
        PB1[st_ready_issues_with_images_*.json<br/>contains image_urls field]
        PB2[Download screenshots<br/>from GitHub CDN]
        PB3[ALFRED Vision API<br/>same client, same endpoint]
        PB4[Replace text in-place<br/>IMAGE ATTACHED → IMAGE DESCRIPTION]
        PB5[Result: enriched file<br/>ready for KB upload]

        PB1 --> PB2 --> PB3 --> PB4 --> PB5
    end

    subgraph "Shared Infrastructure"
        SI1[API: api-ai-bridge.st.com]
        SI2[Client: mdrf_stgithub_analyzer_client]
        SI3[Rate limit: ~20 req before throttle]
        SI4[Retry: delay 5s, retry 2x, backoff 30s]
    end
```

---

## 4. ALFRED Integration Timing in Pipeline

```mermaid
sequenceDiagram
    participant Ingestion
    participant ALFRED_PDF as ALFRED (PDF)
    participant Cleaning
    participant Enrichment
    participant Delivery
    participant ALFRED_IMG as ALFRED (Images)
    participant Upload

    Ingestion->>Ingestion: Steps 1-6: fetch all data
    Ingestion->>ALFRED_PDF: Step 7: PDF pages → figures
    ALFRED_PDF->>ALFRED_PDF: PyMuPDF + OpenCV + API call
    ALFRED_PDF-->>Cleaning: pdf_image_descriptions.json ready
    Cleaning->>Cleaning: Steps 8-9: normalize
    Cleaning->>Enrichment: Steps 10-12: classify + inject PDF descriptions
    Enrichment->>Delivery: Steps 18-22: export 4 artifact types + with_images
    Delivery->>ALFRED_IMG: Step 23: with_images file has image_urls
    ALFRED_IMG->>ALFRED_IMG: Download + describe each screenshot
    ALFRED_IMG-->>Upload: In-place: IMAGE ATTACHED → IMAGE DESCRIPTION
    Upload->>Upload: Upload ENRICHED with_images file to KB
    Note over Upload: ⚠️ Upload the ALFRED-enriched file, NOT plain issues!
```

---

## How to View

- **VS Code**: Install "Markdown Preview Mermaid Support" extension, then Ctrl+Shift+V
- **GitHub**: Mermaid renders natively in .md files
- **draw.io**: Open the `.drawio` files with draw.io desktop app or VS Code draw.io extension
