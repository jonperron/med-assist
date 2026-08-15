"""The OpenAPI schema is the client's source of truth, so it is asserted.

The frontend's types are generated from this document: a success contract that
also lists error shapes hands the client a type it can never rely on.
"""

# pylint: disable=W0621
import json
from pathlib import Path

import pytest

from app.main import app

# Kept in step with scripts/export_openapi.py, which writes this file. Locating
# it here rather than importing the script keeps the test independent of how
# pytest was invoked.
SCHEMA_PATH = Path(__file__).resolve().parents[1] / "openapi.json"

# FastAPI's own request-validation answer. It has its own shape and is not
# something the routes raise.
REQUEST_VALIDATION_STATUS = "422"


@pytest.fixture(scope="module")
def schema():
    return app.openapi()


def response_refs(response):
    """Every schema referenced by one documented response."""
    content = response.get("content", {}).get("application/json", {})
    body = content.get("schema", {})
    refs = [body["$ref"]] if "$ref" in body else []
    for variant in body.get("anyOf", []) + body.get("oneOf", []):
        if "$ref" in variant:
            refs.append(variant["$ref"])
    return refs


def documented_responses(schema):
    for path, operations in schema["paths"].items():
        for method, operation in operations.items():
            for status, response in operation.get("responses", {}).items():
                yield f"{method.upper()} {path}", status, response


def test_success_responses_never_document_an_error_shape(schema):
    for endpoint, status, response in documented_responses(schema):
        if not status.startswith("2"):
            continue
        for ref in response_refs(response):
            assert "Error" not in ref, f"{endpoint} {status} documents {ref}"


def test_failure_responses_document_the_envelope_the_api_sends(schema):
    # A raised HTTPException reaches the client as {"detail": {...}}. Anything
    # else documented here describes a body the API never sends.
    for endpoint, status, response in documented_responses(schema):
        if status.startswith("2") or status == REQUEST_VALIDATION_STATUS:
            continue
        refs = response_refs(response)
        assert refs, f"{endpoint} {status} documents no shape"
        for ref in refs:
            assert ref.endswith("/ErrorResponse"), f"{endpoint} {status} -> {ref}"


def test_the_error_envelope_carries_a_message(schema):
    detail = schema["components"]["schemas"]["ErrorDetail"]
    assert detail["required"] == ["message"]


def test_the_exported_schema_still_describes_the_app(schema):
    # The frontend's types are generated from the exported document, so a
    # backend change that skips the export is a client that has already drifted.
    exported = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    assert exported == schema, (
        "backend/openapi.json is stale: run `uv run python scripts/export_openapi.py`, "
        "then `npm run generate:types` in frontend/"
    )
