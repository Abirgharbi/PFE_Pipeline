# test_suites

Scripts that build and populate QA/evaluation test suites (Excel `.xlsx` files) used
to manually or semi-automatically grade the STM32Cube knowledge base's answer
quality, including a head-to-head comparison against the internal "Alfred"
generic LLM persona.

These scripts do **not** read the pipeline's `datasets/*.json` documents/chunks
directly. Question sets are either hardcoded, read from a pre-generated CSV, or
derived from `shared/config/config*.json` series configuration files. Outputs are
written under `datasets/07_delivery/st_ready/`.

## Scripts

- **`build_all_series_test_suite_xlsx.py`** — Converts the legacy
  `all_series_test_suite_50q.csv` into a styled `.xlsx` workbook (v1 format).
  ```
  python pipeline_Automation/test_suites/build_all_series_test_suite_xlsx.py
  ```

- **`build_test_suite_v2_xlsx.py`** — Converts the v2 CSV
  `all_series_test_suite_50q_v2.csv` into a styled `.xlsx` workbook (plain
  script, no `main()`/CLI args).
  ```
  python pipeline_Automation/test_suites/build_test_suite_v2_xlsx.py
  ```

- **`generate_quality_test_suite.py`** — Generates 4 generic troubleshooting
  questions per configured STM32Cube series (from `shared/config/config.json`
  and `shared/config/config_*.json`) and exports them with an empty Answer
  column, ready to be filled in.
  ```
  python pipeline_Automation/test_suites/generate_quality_test_suite.py
  ```

- **`fill_answers_from_alfred.py`** — Imports the `QUESTIONS` list from
  `generate_quality_test_suite.py` and calls the Alfred (`st_copilot`) chat API
  for each question, writing a fresh `.xlsx` with Alfred's answers.
  ```
  python pipeline_Automation/test_suites/fill_answers_from_alfred.py
  ```
  Requires environment variables: `ALFRED_CLIENT_APP_NAME` (optional, has a
  default) and one of `ST_CHATGPT_API_KEY` / `ST_AI_BRIDGE_API_KEY` / `ST_API_KEY`.

- **`compare_alfred_vs_persona.py`** — Sends a fixed, hand-curated list of
  20 technical STM32 questions to both Alfred (generic) and the "ST GitHub
  Analyzer" KB-powered persona, and exports a 3-sheet comparison workbook plus
  a raw JSON dump for further analysis.
  ```
  python pipeline_Automation/test_suites/compare_alfred_vs_persona.py
  python pipeline_Automation/test_suites/compare_alfred_vs_persona.py --max-questions 10
  python pipeline_Automation/test_suites/compare_alfred_vs_persona.py --use-proxy --delay 5 --output custom.xlsx
  ```
  Requires environment variables: `ALFRED_CLIENT_APP_NAME` / one of
  `ST_CHATGPT_API_KEY` / `ST_AI_BRIDGE_API_KEY` / `ST_API_KEY` for Alfred, and
  `PERSONA_CLIENT_APP_NAME` / one of `PERSONA_API_KEY` /
  `ST_GITHUB_ANALYZER_API_KEY` / `ST_CHATGPT_API_KEY` / `ST_AI_BRIDGE_API_KEY` /
  `ST_API_KEY` for the persona.

All scripts require `openpyxl`; `fill_answers_from_alfred.py` and
`compare_alfred_vs_persona.py` also require `requests`.

## Expected `.xlsx` output structure

| Script | Output file | Sheet(s) | Columns |
|---|---|---|---|
| `build_all_series_test_suite_xlsx.py` | `datasets/07_delivery/st_ready/all_series_test_suite_50q.xlsx` | "Test Suite 50Q All Series" | Question, Answer, Tags |
| `build_test_suite_v2_xlsx.py` | `datasets/07_delivery/st_ready/all_series_test_suite_50q_v2.xlsx` | "Test Suite 50Q v2" | Question, Answer, Tags |
| `generate_quality_test_suite.py` | `datasets/07_delivery/st_ready/quality_test_suite_all_series.xlsx` | "Quality Test Suite" | Question, Answer (empty), Tags (series) |
| `fill_answers_from_alfred.py` | `datasets/07_delivery/st_ready/quality_test_suite_all_series.xlsx` | "Quality Test Suite" | Question, Answer (filled by Alfred), Tags (series) |
| `compare_alfred_vs_persona.py` | `datasets/07_delivery/st_ready/evaluation_report/comparison_alfred_vs_persona.xlsx` (+ matching `.json`) | "Comparison", "Grille d'évaluation", "Metadata" | N°, Question, Catégorie, Tags, Réponse Alfred, Réponse ST GitHub Analyzer, Avantage attendu/réel, citation/actionability flags, Commentaire évaluation |

All workbooks use a bold white-on-blue header row, wrapped/top-aligned text in
data cells, thin borders, and a frozen header row for easier manual review.

## Notes / ambiguities

- `fill_answers_from_alfred.py` and `generate_quality_test_suite.py` write to
  the **same** output path (`quality_test_suite_all_series.xlsx`); running
  `fill_answers_from_alfred.py` overwrites the file with a brand-new workbook
  rather than editing the existing one in place, so re-running
  `generate_quality_test_suite.py` afterwards would discard the collected answers.
- `compare_alfred_vs_persona.py`'s Excel headers and rubric/metadata sheets mix
  French labels (e.g. "Catégorie", "Avantage attendu", "Grille d'évaluation")
  with English code/comments — this is existing behavior and was left
  unchanged since it affects workbook output, not documentation.
