"""The OpenAPI schema is the client's source of truth, so it is asserted.

The frontend's types are generated from this document: a success contract that
also lists error shapes hands the client a type it can never rely on.
"""

import pytest

from app.main import app

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
