# Workflow STM32Cube Preprocessing Agent

## 1. Objective
This document presents a workflow that is simple to explain and detailed enough to execute, in order to transform STM32Cube data into a corpus ready for a RAG system.

The central element is the STM32Cube Preprocessing Agent, which does more than just run scripts:
- it structures the data flow,
- it controls artifact quality,
- it documents heuristic choices,
- it supports evaluation before final RAG integration.

## 2. Full Pipeline

### Step A. GitHub Issues Ingestion
- Script: src/scripts/fetch_issues.py
- Service: src/services/github_service.py
- Input: owner + repos in src/config/config.json
- Output: data/raw_issues_<repo>.json
- Goal: retrieve all open and closed issues with comments

### Step B. File Ingestion from Cloned Repositories
- Script: src/scripts/fetch_files.py
- Service: src/services/file_collect_service.py
- Input: local folders GitHub_repos/<Repo>
- Output: data/raw_files_<repo>.json
- Goal: collect README, Release Notes, and Projects documentation files

### Step C. Issues Cleaning
- Script: src/scripts/clean_issues.py
- Service: src/services/cleaning_service.py
- Output: data/clean_issues_<repo>.json
- Goal: normalize text, replace image tags, merge body + comments

### Step D. Files Cleaning
- Script: src/scripts/clean_files.py
- Output: data/clean_files_<repo>.json
- Goal: normalize text and classify file_type

### Step E. Issues V2 Enrichment
- Script: src/scripts/issues_to_docs_v2.py
- Services: src/services/preprocessing_model.py + src/services/stm32cube_preprocessing_heuristics.py
- Output: data/docs_issues_<repo>_v2.json
- Key fields: layer, severity, issue_kind, board, component, is_valid

### Step F. Files V2 Enrichment
- Script: src/scripts/files_to_docs_v2.py
- Service: src/services/preprocessing_model.py
- Output: data/docs_files_<repo>_v2.json
- Key fields: file_type, board, component, example_name, is_valid

### Step G. Similarity Between Issues
- Script: src/scripts/compute_issue_similarity_v2.py
- Output: data/docs_issues_<repo>_v2_sim.json
- Goal: add related_issue_ids using TF-IDF + cosine similarity

### Step H. Chunking
- Issues: src/scripts/docs_to_chunks_issues_v2.py
- Files: src/scripts/docs_to_chunks_files_v2.py
- Service: src/services/chunk_service.py
- Outputs: data/chunks_issues_<repo>_v2.json and data/chunks_files_<repo>_v2.json
- Goal: multi-paragraph splitting with complete metadata

Important for your case:
If ST RAG does chunking internally, use docs_issues_<repo>_v2.json and docs_files_<repo>_v2.json directly as input, not chunks files.

## 3. Pipeline Summary Diagram

[GitHub API Issues] + [Local STM32Cube Repositories]
                |
                v
       Ingestion (fetch_issues, fetch_files)
                |
                v
        Raw JSON (raw_issues, raw_files)
                |
                v
      Cleaning (clean_issues, clean_files)
                |
                v
      Clean JSON (clean_issues, clean_files)
                |
                v
 Enrichment V2 (issues_to_docs_v2, files_to_docs_v2)
                |
                v
      Docs V2 (metadata + clean_text + is_valid)
                |
                +----> Issues Similarity V2 (related_issue_ids)
                |
                +----> Chunking V2 (if needed)
                |
                v
   Recommended ST RAG input: docs_issues_v2 + docs_files_v2

## 4. Current Progress Status

### 4.1 Available Artifacts
- H7 Issues: raw, clean, docs_v2, docs_v2_sim, chunks_v2 available
- H7 Files: raw, clean, docs_v2, chunks_v2 available
- H5 Issues: raw, clean, docs_v2, docs_v2_sim, chunks_v2 available
- H5 Files: V2 file artifacts missing

### 4.2 Overall Rate
- Expected artifacts across 2 repos (issues + files): 18
- Currently available artifacts: 14
- Estimated overall progress: 77.8%

### 4.3 Available Quality Tests
- src/test/test_stats_issues_v2.py
- src/test/test_stats_files_v2.py
- src/test/test_tfidf_search_issues_v2.py
- src/test/test_tfidf_search_files_v2.py

## 5. Evaluation and Quality Validation

### 5.1 Statistical Validation
Scripts:
- src/test/test_stats_issues_v2.py
- src/test/test_stats_files_v2.py

Objectives:
- verify distributions of layer, severity, issue_kind, file_type, board, component
- verify valid document ratio
- detect classification bias

Expected interpretation:
- too much Other in layer means heuristics need improvement
- too much high in severity means thresholds or keywords may be too aggressive
- frequent empty board/component means detection regex should be strengthened

### 5.2 Pre-RAG Retrieval Validation (TF-IDF)
Scripts:
- src/test/test_tfidf_search_issues_v2.py
- src/test/test_tfidf_search_files_v2.py

Objectives:
- verify documents are retrievable with relevant results before vector embeddings
- check that top-ranked results match technical queries

How to read results:
- a relevant top 5 across several domain queries indicates preprocessing preserves useful signal
- off-topic results usually indicate cleaning, filtering, or metadata issues

## 6. Immediate Recommendations for ST RAG Integration
1. Primary input files:
   - data/docs_issues_stm32cubeh7_v2.json
   - data/docs_files_stm32cubeh7_v2.json
   - data/docs_issues_stm32cubeh5_v2.json
2. Optional:
   - data/docs_issues_stm32cubeh7_v2_sim.json
   - data/docs_issues_stm32cubeh5_v2_sim.json
3. Filter is_valid = true before ingestion.
4. Keep useful metadata: repo, mcu_series, layer, severity, issue_kind, board, component, file_type.

## 7. Short-Term Action Plan
1. Complete the H5 files branch (raw_files, clean_files, docs_files_v2, chunks_files_v2).
2. Run H7 and H5 stats and archive outputs in docs/evaluation_results.md.
3. Build a list of 20 STM32 domain queries for a reproducible retrieval benchmark.

