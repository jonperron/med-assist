---
type: decision
title: 2026-08-28 - Entity offsets do not leave the server
description: EntityDetail.start and EntityDetail.end are excluded from serialisation; the summarizer still pairs by them.
tags: [backend, api, privacy, breaking-change]
---

# 2026-08-28 - Entity offsets do not leave the server

## What was decided

`EntityDetail.start` and `EntityDetail.end` carry `exclude=True`. Pydantic then
leaves them out of the serialised model and out of the serialisation-mode JSON
schema, which is the mode FastAPI generates response schemas in - so they are
gone from the body of `POST /api/analyze`, from the `result` event of
`POST /api/analyze/stream`, from `GET /mock_summary`, and from
`backend/openapi.json` and the TypeScript generated from it.

The fields stay on the model. `summarizer.py` pairs an examination with the
value that follows it by comparing an examination's `end` to a measurement's
`start`, and that runs while building the summary, before the response is
serialised. Excluding them is therefore a boundary change and not a data
change: the pairing, the gap rule and the summary it produces are untouched.

The offsets index the text extracted from the document, and the API deliberately
never returns that text. A caller could not locate a span with them unless it
still held the document and re-extracted it exactly the same way. What crossed
the boundary was position information about clinical content that bought the
caller nothing - the opposite of the no-more-than-needed rule in AGENTS.md
section 9.

This settles the last item left open by
[the API stores nothing and Redis is gone](2026-08-28-the-api-stores-nothing-and-redis-is-gone.md),
which removed the storing path's `drop_offsets` step and noted that the analysis
path had never applied the same rule.

The mock keeps its offsets in `MOCK_ENTITIES`, for the same reason the real
model keeps them: `summarize` reads them, and a mock built without them would
answer a summary the real route would not. They no longer reach its response
either.

## The alternative that was rejected

Returning the extracted text, so the offsets become usable.

That is the honest version of the same feature and it is the wrong trade. The
text is the whole document's clinical content; returning it to make two integers
meaningful widens what leaves the server by orders of magnitude to serve a use
case nobody has asked for. `POST /api/analyze` already documents the opposite -
the summary is the product, and echoing the text would widen the boundary for no
gain.

Also rejected: leaving the fields as dead but harmless. They are not quite
harmless - offsets over marked spans describe where clinical material sits in a
document, which is a shape the response otherwise does not carry - and a field
that is documented, typed and always wrong is a trap for the next client. The
previous field descriptions already conceded the span "can only be located by
extracting it again the same way", which is a description of a field that should
not be there.

Also rejected: a `drop_offsets` step applied to `describe()`'s output in the
route. It would have to be applied at two call sites on one route file and
again in the mock, and it would strip the response while `openapi.json` kept
advertising the fields unless a second edit removed them there too. `exclude=True`
states it once, on the field, and the schema follows automatically.

## What it costs

- **A breaking change to the response shape.** A client outside this repository
  that read `start`/`end` - or stored them - loses them in one step, with no
  deprecation window. The repository is public, so such a client cannot be ruled
  out by inspection. Nothing in `frontend/` read them.
- **The fields are now invisible in the contract.** A backend developer reading
  `openapi.json`, or the generated `app/types/api.ts`, sees an `EntityDetail`
  with three fields and no hint that the model carries two more. Only
  `extraction.py` and this entry say so, and the openapi contract test pins the
  three-field schema so the omission cannot be undone by accident.
- **`exclude=True` is easy to lose.** Deleting one keyword silently restores the
  leak, in the body and in the document at once. That is what
  `test_the_entity_contract_names_no_offsets` and the per-route assertions on
  the analysis, stream and mock responses are for. The other half of the
  contract - that the offsets are still read - is pinned by
  `test_summarizer.py::TestMeasurementPairing`, which predates this change and
  is deliberately not near the new tests: it exercises the pairing directly,
  with no response in it at all.
- **`exclude=True` is process-wide, not response-wide.** It applies to every
  `model_dump()` and `model_dump_json()` an `EntityDetail` ever goes through,
  not only to the one FastAPI performs. No internal path round-trips an entity
  through a dict today, so nothing is affected; one added later would silently
  read `None` for both offsets and produce unpaired summaries with no error
  anywhere. Read the fields off the model, never off a dump of it.
