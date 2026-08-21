# Copilot Instructions — STM32Cube Preprocessing Pipeline

## Project Context

This is a PFE (Projet de Fin d'Études) repository for STMicroelectronics implementing an intelligent preprocessing pipeline for the STM32Cube knowledge base.

## Key Files

- **Report**: `docs/reports/PFE_Report_STM32Cube_Pipeline.tex`
- **Config**: `shared/config/config_all_series.json`
- **Pipeline**: `pipeline/` (ingestion, cleaning, enrichment, similarity, chunking, delivery)
- **Delivery**: `datasets/07_delivery/st_ready/by_series/`
- **Upload**: `pipeline_Automation/upload/Add_Data_Source_Files.py`

## Agent System

This repo uses a modular agentic architecture (see `.github/AGENTS.md`):
- Main orchestrator: `PFE Report Writer`
- Subagents for quality, methodology, technology, consistency
- Skills for LaTeX writing, evaluation analysis, diagrams, stats

## Coding Conventions

- Python: type hints, pathlib for paths, json for configs
- Pipeline scripts: argparse CLI, shared config via `STM32CUBE_CONFIG` env var
- Tests: `py_compile` for syntax, `jsonschema` for data validation
- PowerShell: for automation/upload scripts

## Report Conventions

- Language: French academic (formal, not robotic)
- Format: LaTeX with TikZ diagrams
- Methodology: CRISP-DM (all 6 phases must be explicit)
- Compilation: `pdflatex` from `docs/reports/` directory
