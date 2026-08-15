"""Write the OpenAPI document the frontend generates its client types from.

The frontend used to hand-copy the response models into TypeScript, so the
backend could change a field and nothing would notice until a clinician saw a
blank panel. The checked-in schema is the contract both sides read: a backend
test fails when it drifts from the app, and `npm run generate:types` turns it
into the types the components import.

Run it from the backend directory:

    uv run python scripts/export_openapi.py
"""

import json
from pathlib import Path

from app.main import app

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "openapi.json"


def export_schema(path: Path = SCHEMA_PATH) -> Path:
    """Write the application's OpenAPI document, sorted so diffs stay readable."""
    document = json.dumps(app.openapi(), indent=2, ensure_ascii=False, sort_keys=True)
    path.write_text(document + "\n", encoding="utf-8")
    return path


if __name__ == "__main__":
    print(f"wrote {export_schema()}")
