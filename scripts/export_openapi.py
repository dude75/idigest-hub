#!/usr/bin/env python3
"""Write OpenAPI JSON for frontend type generation (no server, no DB init)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "web" / "openapi" / "openapi.json"


def main() -> int:
    os.chdir(ROOT)
    os.environ.setdefault("METRICS_TOKEN", "openapi-export")
    os.environ["OPENAPI_ENABLED"] = "true"
    sys.path.insert(0, str(ROOT))

    from app.config import Settings
    from app.main import create_app

    app = create_app(Settings(OPENAPI_ENABLED=True))
    schema = app.openapi()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(schema, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
