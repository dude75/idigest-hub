"""OpenAPI export script produces a valid schema file."""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "web" / "openapi" / "openapi.json"
SCRIPT = ROOT / "scripts" / "export_openapi.py"


def test_export_openapi_writes_health_path():
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    assert OUT.is_file()
    schema = json.loads(OUT.read_text(encoding="utf-8"))
    assert "/api/v1/health" in schema.get("paths", {})
    assert schema["paths"]["/api/v1/audios"]["get"]["parameters"]
    components = schema.get("components", {}).get("schemas", {})
    assert "AudioListResponse" in components
    assert "total" in components["AudioListResponse"]["properties"]
    assert "TaskListResponse" in components
    assert "done_total" in components["TaskListResponse"]["properties"]
    get_task = schema["paths"]["/api/v1/tasks/{task_id}"]["get"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"]
    assert get_task.get("$ref", "").endswith("/TaskListItem")
    transcribe_202 = schema["paths"]["/api/v1/tasks/transcribe"]["post"]["responses"]["202"]["content"][
        "application/json"
    ]["schema"]
    assert transcribe_202.get("$ref", "").endswith("/TaskListItem")
