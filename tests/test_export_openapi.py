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
