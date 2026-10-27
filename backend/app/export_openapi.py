"""Write the API contract to ``backend/openapi.json``.

Usage: ``python -m app.export_openapi`` (from ``backend/``). Builds the app
against a throwaway database; no server starts and no real DB is touched. The
UI generates its TypeScript types from the output (``npm run gen:api``).
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from .config import Settings
from .main import create_app

OPENAPI_PATH = Path(__file__).resolve().parents[1] / "openapi.json"


def build_openapi() -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as scratch:
        settings = Settings(
            db_path=str(Path(scratch) / "openapi.db"),
            ui_dist=str(Path(scratch) / "no-ui"),
        )
        return create_app(settings).openapi()


def render_openapi() -> str:
    return json.dumps(build_openapi(), indent=2, sort_keys=True) + "\n"


def main() -> None:
    OPENAPI_PATH.write_text(render_openapi(), encoding="utf-8")
    print(f"wrote {OPENAPI_PATH}")


if __name__ == "__main__":
    main()
