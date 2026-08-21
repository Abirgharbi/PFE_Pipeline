import time
import random
import hashlib
import os
import requests
import urllib3
 
"""
Generic reusable helper: list the Knowledge Bases (KBs) attached to the
"ST GitHub Analyzer" persona on ST's internal AI Bridge API
(https://api-ai-bridge.st.com/chatgpt/api/client-apps), and expose the
'ST GitHub Analyzer' KB (id 793) as a convenience lookup.

This module is imported by other scripts in this folder (Add_Data_Source_Files.py,
Chat_With_Persona_KB.py) as a fallback/legacy source of clientAppName, apiKey,
proxies, and the generate_token() helper. It can also be run standalone to print
the resolved KB info.

Required env vars (first non-empty wins): PERSONA_API_KEY, ST_GITHUB_ANALYZER_API_KEY,
ST_CHATGPT_API_KEY, ST_AI_BRIDGE_API_KEY, ST_API_KEY.
See README_upload_runtime_config.md for the config-file-based alternative.

Run standalone:
    python pipeline_Automation/upload/Get_Persona_KBs.py
"""
 
# Disable SSL certificate verification warnings (used with verify=False below;
# handle with care, this bypasses TLS cert checks).
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
 
 
clientAppName = "mdrf_st_github_analyzer"
apiKey = (
    os.getenv("PERSONA_API_KEY")
    or os.getenv("ST_GITHUB_ANALYZER_API_KEY")
    or os.getenv("ST_CHATGPT_API_KEY")
    or os.getenv("ST_AI_BRIDGE_API_KEY")
    or os.getenv("ST_API_KEY")
    or ""
).strip()
serviceName = "kb"
url = "https://api-ai-bridge.st.com/chatgpt/api/client-apps"
 
# NOTE: internal ST proxy, adjust or remove if not needed in your environment.
proxies = {
    "http": "http://185.46.212.88:80",
    "https": "http://185.46.212.88:80"
}
def generate_token(clientAppName, serviceName, apiKey, timestamp, nonce):
    """Generate the SHA1 auth token required by the AI Bridge API.

    Token = sha1("{clientAppName}_{serviceName}_{apiKey}_{timestamp}_{nonce}").
    Sent via the 'stchatgpt-auth-token' header alongside 'stchatgpt-auth-nonce'.
    """
    data_string = f"{clientAppName}_{serviceName}_{apiKey}_{timestamp}_{nonce}"
    return hashlib.sha1(data_string.encode('utf-8')).hexdigest()
 
def call_api(request_body, max_retries=3):
    """POST request_body to the AI Bridge API with retry/backoff on network errors.

    Generates a fresh auth token/nonce per attempt. Raises RuntimeError if no API key
    is configured. Re-raises the last exception if all max_retries attempts fail.
    """
    if not apiKey:
        raise RuntimeError(
            "Missing persona API key. Set PERSONA_API_KEY or ST_GITHUB_ANALYZER_API_KEY "
            "(fallbacks: ST_CHATGPT_API_KEY, ST_AI_BRIDGE_API_KEY, ST_API_KEY)."
        )

    for attempt in range(1, max_retries + 1):
        timestamp = request_body.get("timestamp", int(time.time()))
        nonce = random.randint(0, 999999)
        token = generate_token(clientAppName, serviceName, apiKey, timestamp, nonce)
 
        headers = {
            "Content-Type": "application/json",
            "stchatgpt-auth-token": token,
            "stchatgpt-auth-nonce": str(nonce)
        }
 
        try:
            response = requests.post(
                url,
                json=request_body,
                headers=headers,
                verify=False,  # Disable SSL certificate verification (not recommended in production).
                timeout=30,
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Attempt {attempt} failed: {e}")
            if attempt == max_retries:
                raise
            else:
                wait_time = 2 ** attempt
                print(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
 
 
 
#  if __name__ == "__main__":
#  try:
 #       get_kb_list_for_persona()
  #  except Exception as e:
   #     print(f"Failed to retrieve KB list: {e}")
def get_kb_list_for_persona():
    """Call the AI Bridge 'kb-list' service to fetch all KBs associated with
    the current clientAppName / persona.

    Returns a list of KB dicts, or [] on API error (printed to stdout).
    """
    request_body = {
        "service": "kb",
        "type": "kb-list",
        "clientAppName": clientAppName,
        "version": 1,
        "timestamp": int(time.time())
    }
 
    response = call_api(request_body)
 
    if response.get("errorCode"):
        print(f"API error: {response.get('message')}")
        return []
 
    kbs = response.get("kbs", [])
    return kbs
 
def get_ST_GitHub_Analyzer_kb():
    """Return the 'ST GitHub Analyzer' KB (matched by id 793 or name
    'ST GITHUB ANALYZER_UNSTRUCTURED') as a dict, or None if not found.
    """
    kbs = get_kb_list_for_persona()
    for kb in kbs:
        # Two match criteria (id or name) in case one changes upstream.
        if kb.get("id") == 793 or kb.get("name") == "ST GITHUB ANALYZER_UNSTRUCTURED":
            return kb
    return None
 
if __name__ == "__main__":
    kb = get_ST_GitHub_Analyzer_kb()
    if not kb:
        print("KB ST GitHub Analyzer non trouvée")
    else:
        print("KBs associated with persona:")
        print("-", kb)
        print("\nRésumé :")
        print("  id       :", kb.get("id"))
        print("  name     :", kb.get("name"))
        print("  kbType   :", kb.get("kbType"))
        print("  dataType :", kb.get("dataType"))
        print("  #dataSources :", len(kb.get("dataSources", [])))