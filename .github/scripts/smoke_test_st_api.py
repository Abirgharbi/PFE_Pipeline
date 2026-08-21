from __future__ import annotations

import hashlib
import os
import random
import sys
import time

import requests
import urllib3


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def main() -> int:
    endpoint = os.environ["ENDPOINT"]
    client_app_name = os.environ["CLIENT_APP_NAME"]
    api_key = os.environ["API_KEY"]
    service = "chat"

    timestamp = int(time.time())
    nonce = random.randint(0, 999999)
    token_raw = f"{client_app_name}_{service}_{api_key}_{timestamp}_{nonce}"
    token = hashlib.sha1(token_raw.encode("utf-8")).hexdigest()

    headers = {
        "Content-Type": "application/json",
        "stchatgpt-auth-token": token,
        "stchatgpt-auth-nonce": str(nonce),
    }

    payload = {
        "version": 1,
        "clientAppName": client_app_name,
        "service": service,
        "timestamp": timestamp,
        "temperature": 0.0,
        "maxResponseTokens": 64,
        "responseFormat": "text",
        "persona": "st_copilot",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "content": "Connectivity smoke test. Reply with OK."}
                ],
            }
        ],
    }

    try:
        response = requests.post(
            endpoint,
            json=payload,
            headers=headers,
            timeout=60,
            verify=False,
        )
    except requests.RequestException as exc:
        print(f"::error::Request failed before API response: {exc}")
        return 3

    status = response.status_code
    body = response.text[:1200]

    print(f"HTTP status: {status}")
    print("Body preview:")
    print(body)

    normalized = body.lower()
    if status in (401, 403) or "unauthorized" in normalized or "forbidden" in normalized:
        print("::error::Auth rejected. Endpoint reachable, but key/policy is not accepted from GitHub Cloud.")
        return 4

    if status >= 500:
        print("::error::Server-side/API gateway error; retry required or endpoint policy issue.")
        return 5

    print("API reachability test passed from GitHub-hosted runner.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
