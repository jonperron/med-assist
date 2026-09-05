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
import os
from pathlib import Path

# Imported before the placeholder is set: reading the constant does not build
# an application, and naming the variable here rather than spelling it out means
# a rename breaks this loudly instead of silently exporting nothing.
from app.core.access import ACCESS_TOKEN_VARIABLE

# Set before `app.main` is imported, and that ordering is the point: the module
# builds an application at import for `uvicorn app.main:app` to serve, and
# `create_app` refuses to build one without a credential. This script serves
# nothing and listens on no port - it writes a JSON document and exits - so it
# supplies a placeholder rather than requiring whoever regenerates the schema to
# hold a deployment's secret.
#
# `setdefault`, so a developer who already has one in their environment keeps
# it. The value never reaches the schema: the credential is checked in
# middleware, which FastAPI does not describe.
SCHEMA_EXPORT_PLACEHOLDER = "schema-export-placeholder-not-a-deployment-value"
os.environ.setdefault(ACCESS_TOKEN_VARIABLE, SCHEMA_EXPORT_PLACEHOLDER)

from app.main import PRODUCTION, create_app  # noqa: E402  pylint: disable=C0413

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "openapi.json"


def export_schema(path: Path = SCHEMA_PATH) -> Path:
    """Write the application's OpenAPI document, sorted so diffs stay readable."""
    # Built for production explicitly: exporting from a shell with
    # APP_ENV=development would advertise the dev-only mock endpoints to every
    # generated client.
    schema = create_app(PRODUCTION).openapi()
    document = json.dumps(schema, indent=2, ensure_ascii=False, sort_keys=True)
    path.write_text(document + "\n", encoding="utf-8")
    return path


if __name__ == "__main__":
    print(f"wrote {export_schema()}")
