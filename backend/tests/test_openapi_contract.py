"""The OpenAPI schema is the client's source of truth, so it is asserted.

The frontend's types are generated from this document: a success contract that
also lists error shapes hands the client a type it can never rely on.
"""

# pylint: disable=W0621
import json
from pathlib import Path

import pytest

from app.main import PRODUCTION, create_app

# Kept in step with scripts/export_openapi.py, which writes this file. Locating
# it here rather than importing the script keeps the test independent of how
# pytest was invoked.
SCHEMA_PATH = Path(__file__).resolve().parents[1] / "openapi.json"

# FastAPI's own request-validation answer. It has its own shape and is not
# something the routes raise.
REQUEST_VALIDATION_STATUS = "422"


@pytest.fixture(scope="module")
def schema():
    # The production contract, whatever APP_ENV says in this shell.
    return create_app(PRODUCTION).openapi()


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


def test_the_entity_contract_names_no_offsets(schema):
    # `start` and `end` index the text extracted from the document, and the API
    # never returns that text - so an offset was unusable to a caller and was
    # position information about clinical content leaving the server for no
    # gain. They stay on the model, excluded from serialisation, because the
    # summarizer pairs an examination with its value by them.
    entity = schema["components"]["schemas"]["EntityDetail"]

    assert set(entity["properties"]) == {"text", "label", "score"}


STREAM = "/api/analyze/stream"
EVENT_STREAM = "text/event-stream"


def test_every_refusal_is_documented_as_json(schema):
    # The streaming endpoint declares text/event-stream as its media type, and
    # FastAPI files a `model=` response under it. A refusal there is ordinary
    # JSON sent before any stream opens, so documenting it as an event would
    # describe a body the API never sends.
    for endpoint, status, response in documented_responses(schema):
        if status.startswith("2"):
            continue
        assert list(response.get("content", {})) == [
            "application/json"
        ], f"{endpoint} {status} is not documented as JSON"


def test_the_streamed_analysis_names_the_events_it_sends(schema):
    # FastAPI infers this from the endpoint's return annotation and loses it
    # when the router is mounted under a prefix, so the route states it. If a
    # FastAPI upgrade ever makes the workaround unnecessary, this still passes;
    # what it guards is the frontend generating a union rather than a string.
    item = schema["paths"][STREAM]["post"]["responses"]["200"]["content"][EVENT_STREAM][
        "itemSchema"
    ]

    assert item["properties"]["data"]["contentSchema"] == {
        "$ref": "#/components/schemas/AnalysisEvent"
    }


def test_the_events_are_a_union_a_client_can_narrow(schema):
    event = schema["components"]["schemas"]["AnalysisEvent"]

    # Without the discriminator a generated client cannot tell which event it
    # is holding, and every field of every event becomes optional.
    assert event["discriminator"]["propertyName"] == "stage"
    assert set(event["discriminator"]["mapping"]) == {
        "batch",
        "document",
        "result",
        "error",
    }


def test_the_discriminator_is_required_on_every_event(schema):
    # OpenAPI requires the property a discriminator names to be present in the
    # payload. Pydantic leaves it out of `required` because each event defaults
    # its own tag, which would type the one field a client narrows on as
    # possibly absent.
    for name in (
        "BatchStarted",
        "DocumentProgress",
        "AnalysisCompleted",
        "AnalysisFailed",
    ):
        assert "stage" in schema["components"]["schemas"][name]["required"], name


def test_an_event_cannot_carry_a_field_the_schema_does_not_name(schema):
    # `response_model` documents the payload but does not filter it: FastAPI
    # serialises whatever the endpoint yields. These definitions are what keeps
    # document content out of the progress channel, so they stay closed.
    for name in ("BatchStarted", "DocumentProgress", "AnalysisFailed"):
        assert (
            schema["components"]["schemas"][name]["additionalProperties"] is False
        ), name


def test_the_streamed_result_is_the_body_the_plain_endpoint_returns(schema):
    completed = schema["components"]["schemas"]["AnalysisCompleted"]

    # The two endpoints answer the same question. A separate result shape would
    # be two contracts to keep in step, and one of them would drift.
    assert completed["properties"]["result"]["$ref"] == (
        "#/components/schemas/AnalysisResponse"
    )
