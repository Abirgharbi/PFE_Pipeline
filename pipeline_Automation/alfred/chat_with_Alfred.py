"""
Send a one-off text (and optionally image) prompt to the Alfred chat API and print the reply.

Role in the automation layer:
    Alfred is ST's internal LLM service (accessed through the ST ChatGPT / AI-bridge
    infrastructure). This script is a small CLI utility for ad hoc interactive use
    (manual testing, debugging a persona, quick one-off questions) as opposed to the
    batch enrichment scripts in this folder (``enrich_json_images_with_alfred.py``,
    ``enrich_pdf_figures_with_alfred.py``) which call the same kind of API in bulk
    over pipeline artifacts.

Inputs:
    - ``--prompt`` or ``--prompt-file``: the user prompt text.
    - ``--image`` (optional): local image path sent alongside the prompt as a
      base64 data URL.
    - Credentials/config imported from ``Get_Persona_KBs`` (API key, client app
      name, proxy settings, base URL).

Outputs:
    - Prints the extracted assistant text to stdout, or the full JSON response
      if ``--print-json`` is passed or no text could be extracted.

Usage:
    python pipeline_Automation/alfred/chat_with_Alfred.py --prompt "Explain HAL_UART_Transmit"
    python pipeline_Automation/alfred/chat_with_Alfred.py --prompt-file question.txt --image screenshot.png
"""

import argparse
import base64
import importlib.util
import json
import mimetypes
import random
import sys
import time
from pathlib import Path
from typing import Any

import requests
import urllib3

# Resolve shared AI Bridge credentials/helpers from upload/Get_Persona_KBs.py
# without relying on cwd-dependent import paths.
upload_dir = Path(__file__).resolve().parents[1] / "upload"
persona_module_path = upload_dir / "Get_Persona_KBs.py"
spec = importlib.util.spec_from_file_location("Get_Persona_KBs", str(persona_module_path))
if spec is None or spec.loader is None:
	raise RuntimeError(f"Cannot load persona helper module: {persona_module_path}")
persona_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(persona_mod)

apiKey = persona_mod.apiKey
clientAppName = persona_mod.clientAppName
generate_token = persona_mod.generate_token
proxies = persona_mod.proxies
url = persona_mod.url


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


CHAT_SERVICE_NAME = "chat"
DEFAULT_PERSONA = "st_copilot"
DEFAULT_MAX_RETRIES = 3
DEFAULT_TIMEOUT_SECONDS = 120


def build_data_url(image_path: str) -> str:
	"""Read a local image file and return it encoded as a base64 ``data:`` URL."""
	path = Path(image_path)
	if not path.exists() or not path.is_file():
		raise FileNotFoundError(f"Image file not found: {image_path}")

	mime_type, _ = mimetypes.guess_type(path.name)
	if not mime_type:
		mime_type = "application/octet-stream"

	encoded = base64.b64encode(path.read_bytes()).decode("ascii")
	return f"data:{mime_type};base64,{encoded}"


def extract_text_from_response(response_json: dict[str, Any]) -> str | None:
	"""Best-effort extraction of the assistant's reply text from a chat API response.

	The API response shape can vary by persona/backend, so this checks several
	known keys/paths (``completion``, ``text``/``content``/``message``/``answer``,
	``messages``, OpenAI-style ``choices``) in order of likelihood and returns the
	first non-empty string found.
	"""
	if not isinstance(response_json, dict):
		return None

	completion = response_json.get("completion")
	if isinstance(completion, str) and completion.strip():
		return completion.strip()

	for key in ("text", "content", "message", "answer"):
		value = response_json.get(key)
		if isinstance(value, str) and value.strip():
			return value.strip()

	messages = response_json.get("messages")
	if isinstance(messages, list):
		for item in reversed(messages):
			if isinstance(item, dict):
				content = item.get("content")
				if isinstance(content, str) and content.strip():
					return content.strip()

	choices = response_json.get("choices")
	if isinstance(choices, list) and choices:
		first = choices[0]
		if isinstance(first, dict):
			message = first.get("message")
			if isinstance(message, dict):
				content = message.get("content")
				if isinstance(content, str) and content.strip():
					return content.strip()

			content = first.get("content")
			if isinstance(content, str) and content.strip():
				return content.strip()

			text = first.get("text")
			if isinstance(text, str) and text.strip():
				return text.strip()

	return None


def call_chat(
	prompt: str,
	image_path: str | None,
	persona: str = DEFAULT_PERSONA,
	temperature: float = 0.2,
	max_response_tokens: int = 4096,
	max_retries: int = DEFAULT_MAX_RETRIES,
	timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
	use_proxy: bool = False,
) -> dict[str, Any]:
	"""Call the Alfred chat API with a text prompt and optional image, retrying on failure.

	Generates a fresh HMAC-style auth token/nonce per attempt (required by the
	backend), retries with exponential backoff on network errors or invalid JSON,
	and returns the raw parsed response JSON.

	Raises:
		RuntimeError: if all retry attempts fail.
	"""
	data_url = build_data_url(image_path) if image_path else None

	content: list[dict[str, str]] = [
		{
			"type": "text",
			"content": prompt,
		}
	]
	if data_url:
		content.append(
			{
				"type": "image",
				"content": data_url,
			}
		)

	last_error: Exception | None = None

	for attempt in range(1, max_retries + 1):
		timestamp = int(time.time())
		nonce = random.randint(0, 999999)
		token = generate_token(clientAppName, CHAT_SERVICE_NAME, apiKey, timestamp, nonce)

		headers = {
			"Content-Type": "application/json",
			"stchatgpt-auth-token": token,
			"stchatgpt-auth-nonce": str(nonce),
		}

		request_body = {
			"version": 1,
			"clientAppName": clientAppName,
			"service": "chat",
			"timestamp": timestamp,
			"messages": [
				{
					"role": "user",
					"content": content,
				}
			],
			"temperature": temperature,
			"maxResponseTokens": max_response_tokens,
			"persona": persona or "st_copilot",
			"responseFormat": "text",
		}

		try:
			response = requests.post(
				url,
				json=request_body,
				headers=headers,
				verify=False,
				timeout=timeout_seconds,
				proxies=proxies if use_proxy else None,
			)
			response.raise_for_status()
			return response.json()
		except requests.exceptions.RequestException as exc:
			last_error = exc
			if attempt < max_retries:
				time.sleep(2**attempt)
				continue
			raise RuntimeError(f"Chat request failed after {max_retries} attempts: {exc}") from exc
		except ValueError as exc:
			last_error = exc
			if attempt < max_retries:
				time.sleep(2**attempt)
				continue
			raise RuntimeError("Chat response is not valid JSON.") from exc

	if last_error:
		raise RuntimeError(f"Chat request failed: {last_error}")

	raise RuntimeError("Chat request failed with unknown error.")


def resolve_prompt(prompt: str | None, prompt_file: str | None) -> str:
	"""Return the effective prompt text: prefer ``--prompt``, fall back to ``--prompt-file``.

	Raises:
		FileNotFoundError: if ``prompt_file`` is given but does not exist.
		ValueError: if neither a usable prompt nor prompt file was provided.
	"""
	if prompt and prompt.strip():
		return prompt.strip()

	if prompt_file:
		path = Path(prompt_file)
		if not path.exists() or not path.is_file():
			raise FileNotFoundError(f"Prompt file not found: {prompt_file}")
		value = path.read_text(encoding="utf-8").strip()
		if value:
			return value

	raise ValueError("Provide --prompt or --prompt-file.")


def main() -> None:
	"""CLI entry point: parse arguments, call Alfred chat, and print the result."""
	parser = argparse.ArgumentParser(description="Send prompt/image to Alfred chat API using persona st_copilot by default.")
	parser.add_argument("--prompt", help="User prompt text.")
	parser.add_argument("--prompt-file", help="Path to UTF-8 text file containing the prompt.")
	parser.add_argument("--image", help="Optional path to an image sent as data URL.")
	parser.add_argument("--persona", default=DEFAULT_PERSONA, help=f"Persona name (default: {DEFAULT_PERSONA}).")
	parser.add_argument("--temperature", type=float, default=0.2, help="Sampling temperature.")
	parser.add_argument("--max-response-tokens", type=int, default=4096, help="Max response tokens.")
	parser.add_argument("--max-retries", type=int, default=DEFAULT_MAX_RETRIES, help="Maximum retry attempts.")
	parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS, help="Request timeout in seconds.")
	parser.add_argument("--use-proxy", action="store_true", help="Use proxy configuration from Get_Persona_KBs.py.")
	parser.add_argument(
		"--print-json",
		action="store_true",
		help="Print full API response JSON instead of extracted assistant text.",
	)
	args = parser.parse_args()

	prompt = resolve_prompt(args.prompt, args.prompt_file)
	response_json = call_chat(
		prompt=prompt,
		image_path=args.image,
		persona=args.persona,
		temperature=args.temperature,
		max_response_tokens=args.max_response_tokens,
		max_retries=args.max_retries,
		timeout_seconds=args.timeout,
		use_proxy=args.use_proxy,
	)

	if args.print_json:
		print(json.dumps(response_json, ensure_ascii=False, indent=2))
		return

	text = extract_text_from_response(response_json)
	if text:
		print(text)
	else:
		print(json.dumps(response_json, ensure_ascii=False, indent=2))


if __name__ == "__main__":
	main()
