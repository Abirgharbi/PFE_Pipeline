# pipeline/ingestion

Ingestion stage of the STM32Cube preprocessing pipeline. This is the first
stage of the end-to-end flow:

```
ingestion -> cleaning -> enrichment -> similarity -> chunking -> evaluation -> delivery
```

It is responsible for pulling raw data into the pipeline from two sources:

- **GitHub REST API**: issues (with comments), pull requests (with changed
  files), commits, and issue/PR/commit linkage — written as JSON under `data/`.
- **Local git clones**: README/Release Notes/technical source files/PDF
  documentation, scanned from repos cloned under `GitHub_repos/`.

All scripts resolve the active configuration via
`shared.utils.paths.get_config_path()` (default
`shared/config/config_all_series.json` plus per-series
`shared/config/config_<series>.json`, overridable with the
`STM32CUBE_CONFIG` environment variable).

## Scripts

| Script | Description | How to run |
| --- | --- | --- |
| `fetch_issues.py` | Fetch all issues (all states) + their comments for each configured repo via the GitHub API. | `python -m pipeline.ingestion.fetch_issues` |
| `fetch_prs.py` | Fetch all pull requests (all states) with full detail and changed files. | `python -m pipeline.ingestion.fetch_prs` |
| `fetch_commits.py` | Fetch commit details for the pull requests selected by `commit_pr_scope` (self-heals by fetching PRs first if missing). | `python -m pipeline.ingestion.fetch_commits` |
| `fetch_issue_pr_commit_links.py` | Cross-reference raw issues/PRs/commits to build per-issue resolution-status evidence (`merged_fix`, `candidate_fix`, etc.) with a heuristic confidence score. | `python -m pipeline.ingestion.fetch_issue_pr_commit_links` |
| `fetch_files.py` | Scan local repo clones under `GitHub_repos/` and collect raw file artifacts (README, release notes, source, documentation PDFs). | `python -m pipeline.ingestion.fetch_files [--skip-repo-sync] [--repo NAME ...]` |
| `repo_sync_service.py` | Ensure every configured repo is cloned under `GitHub_repos/<repo>` and pinned to the ref in `linked_repo_refs`, if any. Called automatically by `fetch_files.py` unless `--skip-repo-sync` is passed. | `python -m pipeline.ingestion.repo_sync_service` |
| `github_service.py` | `GitHubService` — shared GitHub REST API client (auth, retries, pagination, rate limiting) used by `fetch_issues.py`, `fetch_prs.py`, `fetch_commits.py`. Library only, no CLI. | n/a |
| `file_collect_service.py` | File classification (README/release notes/technical source/etc.) and content extraction logic used by `fetch_files.py`. Library only, no CLI. | n/a |
| `pdf_figure_service.py` | Multimodal PDF extraction: per-page text, page rendering, OpenCV figure/diagram detection and cropping, and vision-model description task generation, used by `file_collect_service.py` for documentation PDFs. Library only, no CLI. | n/a |

## Typical inputs / outputs

- Config: `shared/config/config_all_series.json` (or `STM32CUBE_CONFIG` override)
- GitHub token: environment variable named by `github_token_env` in the config
  (default `GITHUB_TOKEN`)
- Local repo clones: `GitHub_repos/<repo>/`
- Raw JSON outputs (all under `data/`):
  - `raw_issues_<repo>.json`
  - `raw_prs_<repo>.json`
  - `raw_commits_<repo>.json`
  - `issue_pr_commit_links_<repo>.json`, `..._linked_only.json`, `..._summary.json`
  - `raw_files_<repo>.json`
  - `pdf_pages/<repo>/...`, `pdf_figures/<repo>/...`, `pdf_image_tasks_<repo>.jsonl`,
    `pdf_image_descriptions.json`

## Role in the pipeline

Ingestion output is exclusively consumed by `pipeline/cleaning`
(`clean_issues.py` reads `raw_issues_<repo>.json`; `clean_files.py` reads
`raw_files_<repo>.json`). The issue/PR/commit linkage file is consumed later
by enrichment and delivery stages that need resolution-status evidence for
issues (e.g. diagnostic cards, resolver cases).
