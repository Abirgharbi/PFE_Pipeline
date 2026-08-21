"""
Fill the Answer column of the quality test suite by calling Alfred (generic
st_copilot persona) for every question, so graders can compare the KB-powered
persona's answers (collected elsewhere, e.g. manually or via the KB chat UI)
against Alfred's generic answers on a level Question/Tags basis.

For each question, sends it to Alfred's chat API (same auth scheme as
enrich_json_images_with_alfred.py), collects the text response, and writes a
fresh Excel workbook (it does not edit an existing file in place).

Input:
    QUESTIONS list imported from generate_quality_test_suite.py, which is itself
    built from shared/config/config*.json series configs (no datasets/*.json
    dataset is read directly by this script).

Output:
    datasets/07_delivery/st_ready/quality_test_suite_all_series.xlsx
    Sheet "Quality Test Suite" with columns:
      A = Question (width 80), B = Answer (width 100, filled by Alfred), C = Tags (width 12)
    Header row is bold/white-on-blue, data rows wrap text, all cells have thin
    borders. The workbook is saved every 5 questions (crash-resilience) and once
    more at the end with frozen header and AutoFilter applied.

Usage:
    python pipeline_Automation/test_suites/fill_answers_from_alfred.py

Requires: openpyxl, requests
Required environment variables:
    ALFRED_CLIENT_APP_NAME (defaults to "mdrf_stgithub_analyzer_client")
    ST_CHATGPT_API_KEY / ST_AI_BRIDGE_API_KEY / ST_API_KEY (first one set wins)
"""

import hashlib
import os
import random
import shutil
import sys
import time
from pathlib import Path

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

try:
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
except ImportError:
    print("Install openpyxl: pip install openpyxl")
    raise SystemExit(1)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = PROJECT_ROOT / "datasets" / "07_delivery" / "st_ready"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
XLSX_PATH = OUTPUT_DIR / "quality_test_suite_all_series.xlsx"

# Import questions from the generate script
sys.path.insert(0, str(Path(__file__).resolve().parent))
from generate_quality_test_suite import QUESTIONS

# --- Alfred API credentials (same as enrich_json_images_with_alfred.py) ---
CLIENT_APP_NAME = os.getenv("ALFRED_CLIENT_APP_NAME", "mdrf_stgithub_analyzer_client").strip()
API_KEY = (
    os.getenv("ST_CHATGPT_API_KEY")
    or os.getenv("ST_AI_BRIDGE_API_KEY")
    or os.getenv("ST_API_KEY")
    or ""
).strip()
API_URL = os.getenv("ALFRED_API_URL", "https://api-ai-bridge.st.com/chatgpt/api/client-apps").strip()
CHAT_SERVICE = "chat"
PERSONA = "st_copilot"


def _generate_token(timestamp: int, nonce: int) -> str:
    """Compute the SHA1 auth token expected by the Alfred/ST AI Bridge API.

    The token binds the client app name, service name, API key, timestamp and
    nonce together so the server can validate the request without the raw API
    key travelling on the wire in a replayable form.
    """
    data_string = f"{CLIENT_APP_NAME}_{CHAT_SERVICE}_{API_KEY}_{timestamp}_{nonce}"
    return hashlib.sha1(data_string.encode("utf-8")).hexdigest()


def ask_alfred(question: str, retries: int = 3) -> str:
    """Send question to Alfred and return the text answer.

    Retries on HTTP errors or exceptions with exponential backoff
    (2, 4, 8, ... seconds) since the AI Bridge API can be transiently
    unavailable; a fresh timestamp/nonce/token is generated per attempt
    because the token embeds the timestamp and would otherwise be rejected
    as stale or replayed.
    """
    system_prompt = (
        "You are a technical support assistant for STM32 microcontrollers. "
        "Answer user questions about STM32Cube firmware, HAL drivers, BSP, "
        "middleware, and development boards. Be concise and technical."
    )

    for attempt in range(1, retries + 1):
        timestamp = int(time.time())
        nonce = random.randint(0, 999999)
        token = _generate_token(timestamp, nonce)

        headers = {
            "Content-Type": "application/json",
            "stchatgpt-auth-token": token,
            "stchatgpt-auth-nonce": str(nonce),
        }

        payload = {
            "version": 1,
            "clientAppName": CLIENT_APP_NAME,
            "service": CHAT_SERVICE,
            "timestamp": timestamp,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": [{"type": "text", "content": question}]},
            ],
            "temperature": 0.3,
            "persona": PERSONA,
            "maxResponseTokens": 2048,
            "responseFormat": "text",
        }

        try:
            resp = requests.post(
                API_URL, json=payload, headers=headers,
                verify=False, timeout=120,
            )
            if resp.status_code >= 400:
                print(f"    [Attempt {attempt}] HTTP {resp.status_code}: {resp.text[:200]}")
                if attempt < retries:
                    time.sleep(2 ** attempt)
                    continue
                return f"(HTTP Error {resp.status_code})"

            data = resp.json()

            # Extract answer from response
            completion = data.get("completion", "")
            if completion:
                return completion.strip()

            # Fallback extraction: different AI Bridge personas / API versions
            # have been observed to return the text under different keys, so
            # try each known shape before giving up.
            for key in ("text", "content", "message", "answer"):
                val = data.get(key)
                if isinstance(val, str) and val.strip():
                    return val.strip()

            choices = data.get("choices", [])
            if choices and isinstance(choices[0], dict):
                msg = choices[0].get("message", {})
                if isinstance(msg, dict) and msg.get("content"):
                    return msg["content"].strip()

            return f"(Unexpected response: {list(data.keys())})"

        except Exception as exc:
            print(f"    [Attempt {attempt}] Error: {exc}")
            if attempt < retries:
                time.sleep(2 ** attempt)
                continue
            return f"(Error: {exc})"

    return "(No answer after retries)"


def backup_if_exists(path: Path) -> Path | None:
    """Create a side-by-side .bak copy when the target output already exists."""
    if not path.exists():
        return None
    backup_path = path.with_suffix(path.suffix + ".bak")
    shutil.copy2(path, backup_path)
    return backup_path


def main():
    """Call Alfred for every question in QUESTIONS and write answers to .xlsx.

    Validates required credentials up front, then builds the workbook
    incrementally: each question's answer is written as soon as it is
    received, and the workbook is saved every 5 questions so a crash or
    interruption does not lose already-collected answers.
    """
    if not CLIENT_APP_NAME:
        raise SystemExit("Missing Alfred client app name. Set ALFRED_CLIENT_APP_NAME.")
    if not API_KEY:
        raise SystemExit("Missing Alfred API key. Set ST_CHATGPT_API_KEY (or ST_AI_BRIDGE_API_KEY/ST_API_KEY).")

    print(f"Calling Alfred ({PERSONA}) for {len(QUESTIONS)} questions...")
    print(f"Output: {XLSX_PATH}")
    backup_path = backup_if_exists(XLSX_PATH)
    if backup_path is not None:
        print(f"Existing file backed up to: {backup_path}")
    print("=" * 60)

    wb = Workbook()
    ws = wb.active
    ws.title = "Quality Test Suite"

    # Styles
    header_fill = PatternFill(start_color="1A2382", end_color="1A2382", fill_type="solid")
    header_font = Font(bold=True, size=11, color="FFFFFF")
    wrap_align = Alignment(wrap_text=True, vertical="top")
    thin_border = Border(
        left=Side(style="thin"), right=Side(style="thin"),
        top=Side(style="thin"), bottom=Side(style="thin"),
    )

    # Headers
    headers = ["Question", "Answer", "Tags"]
    col_widths = [80, 100, 12]

    for col_idx, (header, width) in enumerate(zip(headers, col_widths), start=1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = thin_border
        ws.column_dimensions[chr(64 + col_idx)].width = width

    # Process each question
    for idx, q in enumerate(QUESTIONS, start=1):
        question = q["question"]
        tags = q["tags"]

        print(f"[{idx}/{len(QUESTIONS)}] {tags} | {question[:60]}...")

        answer = ask_alfred(question)

        print(f"  -> {answer[:80]}...")
        print()

        row_idx = idx + 1
        row_data = [question, answer, tags]
        for col_idx, value in enumerate(row_data, start=1):
            cell = ws.cell(row=row_idx, column=col_idx, value=value)
            cell.alignment = wrap_align
            cell.border = thin_border
            cell.font = Font(size=10)

        # Save after each question (in case of crash)
        if idx % 5 == 0:
            wb.save(XLSX_PATH)
            print(f"  [Saved progress: {idx}/{len(QUESTIONS)}]")

        # Rate limiting - wait between requests
        time.sleep(2)

    # Final save
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:C{len(QUESTIONS) + 1}"
    wb.save(XLSX_PATH)

    print("=" * 60)
    print(f"Done! Generated: {XLSX_PATH}")
    print(f"Total questions answered: {len(QUESTIONS)}")


if __name__ == "__main__":
    main()
