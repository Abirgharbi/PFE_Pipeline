"""Upload only st_ready_files_stm32cubef4.json (main repo) with split.

Minimal one-shot uploader: appends the single main-repo STM32CubeF4 files JSON
export to existing KB #793 (ST GitHub Analyzer) datasource #28103
(STready_F4_Files_Datasource_JSON_V2), via Add_Data_Source_Files.py
(--operation add --json-split-size 1000). Unlike upload_f4_files_datasource.py,
this script does not include per-driver sub-repo files and hardcodes the
--remote-user value below.

Required env vars: same as Add_Data_Source_Files.py (PERSONA_API_KEY /
ST_GITHUB_ANALYZER_API_KEY / ST_CHATGPT_API_KEY / ST_AI_BRIDGE_API_KEY / ST_API_KEY).

Required input file: datasets/07_delivery/st_ready/by_series/stm32cubef4/
files_json/st_ready_files_stm32cubef4.json

How to run:
    python pipeline_Automation/upload/upload_f4_files_main_only.py
"""
import subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

cmd = [
    sys.executable,
    str(ROOT / "pipeline_Automation" / "Add_Data_Source_Files.py"),
    "--kb", "793",
    "--operation", "add",
    "--datasource-id", "28103",
    "--remote-user", "abir.gharbi@st.com",
    "--processor", "JSON",
    "--processor-params",
    '{"label": "{{repo}} {{file_type}} - {{path}}", "externalURL": "https://github.com/STMicroelectronics/{{repo}}/{{root_dir}}/{{root_ref}}/{{path_url}}", "rootTagPath": "files"}',
    "--json-split-size", "1000",
    "--files",
    str(ROOT / "datasets" / "07_delivery" / "st_ready" / "by_series" / "stm32cubef4" / "files_json" / "st_ready_files_stm32cubef4.json"),
    "--verbose",
]

sys.exit(subprocess.run(cmd, cwd=str(ROOT)).returncode)
