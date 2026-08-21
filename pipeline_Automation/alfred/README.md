# pipeline_Automation/alfred

Scripts that call **Alfred**, ST's internal LLM service (accessed through the ST
ChatGPT / AI-bridge infrastructure at `api-ai-bridge.st.com`), for two purposes in this
project: enriching figures/screenshots referenced in the knowledge base with textual
descriptions (vision), and ad hoc interactive chat.

## Scripts

### `chat_with_Alfred.py`
Small CLI utility to send a one-off text prompt (and optionally a local image) to the
Alfred chat API and print the reply. Intended for interactive/manual use — testing a
persona, debugging prompts, asking quick questions — as opposed to the batch
enrichment scripts below.

```powershell
python pipeline_Automation/alfred/chat_with_Alfred.py --prompt "Explain HAL_UART_Transmit"
```

### `enrich_json_images_with_alfred.py`
Batch-enriches ST-ready / PR JSON records: extracts image URLs referenced via
markdown/HTML tags, `[IMAGE ATTACHED]` markers, or an `image_urls` field, sends each
image to Alfred Vision (persona `mdrf_stgithub_analyzer_client`), and replaces the
placeholder/marker in the record's text with `[IMAGE DESCRIPTION] ...` /
`[IMAGE TEXT] ...` so image content becomes searchable plain text for KB/RAG
retrieval. This is the script used for the "Alfred Image Enrichment" step, typically
run against `issues_json/st_ready_issues_with_images_<repo>.json`.

```powershell
python pipeline_Automation/alfred/enrich_json_images_with_alfred.py --input <file> --inplace
```

### `enrich_pdf_figures_with_alfred.py`
Reads `pdf_image_tasks_*.jsonl` files (produced by `pipeline/ingestion/pdf_figure_service.py`
during ingestion), sends each cropped PDF figure to Alfred Vision, and stores the
resulting descriptions in `data/pdf_image_descriptions.json`. A subsequent
enrichment/delivery pass injects these descriptions into PDF text content via
`[FIGURE_DESCRIPTIONS]` blocks.

```powershell
python pipeline_Automation/alfred/enrich_pdf_figures_with_alfred.py --repo STM32CubeH7
```

## Notes

- Vision API credentials are read from environment variables:
  `ALFRED_CLIENT_APP_NAME`, `ST_CHATGPT_API_KEY` (or `ST_AI_BRIDGE_API_KEY`/`ST_API_KEY`),
  `ALFRED_API_URL`.
- All three scripts support `--use-proxy` to route requests through the ST proxy.
- `enrich_json_images_with_alfred.py` writes a companion `*__alfred_summary.json`
  file alongside its output with run statistics.
