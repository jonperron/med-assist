---
type: decision
title: 2026-08-28 - The API stores nothing, and Redis is gone
description: The stored-document endpoints and the Redis layer behind them are removed; analysis is the only path.
tags: [backend, storage, privacy, api]
---

# 2026-08-28 - The API stores nothing, and Redis is gone

## What was decided

Med-Assist keeps nothing after a request. Four endpoints and the persistence
layer under them are removed:

- `POST /api/upload_document/`
- `POST /api/upload_documents/`
- `GET /api/get_extracted_text/{file_id}`
- `DELETE /api/documents/{file_id}`

With them go `app/db/` (the Redis client and the Fernet value cipher),
`app/repositories/`, `TextRepositoryInterface`, `FileHandler`,
`RedisConfiguration`, `PrivacyConfiguration` and the `STORE_DOCUMENT_TEXT`
switch, the `redis` compose service, and the `redis` dependency.

`POST /api/analyze` and `POST /api/analyze/stream` are what remains, and both
already stored nothing. There is now no code path that writes patient-derived
data anywhere, so no retention window, no encryption key and no deletion
endpoint are needed to bound it.

Two response fields go with the layer that gave them meaning:

- `AnalysisResponse.retained`, a constant `false` that only ever meant "unlike
  the storing path".
- `ExtractionResponse` and `UploadResponse` in full, along with the
  `/mock_extracted_text/{file_id}` development endpoint that mirrored the
  extraction route. `/mock_summary` stays.

`EntityDetail.start` and `EntityDetail.end` stay, and their description no
longer refers to retention. See the cost below.

## The alternative that was rejected

Keeping the endpoints and the Redis service, unused.

They had no consumer. The frontend calls `POST /api/analyze/stream` and nothing
else, so the storing path was reachable only by a caller writing against the
OpenAPI document directly. Keeping it meant carrying the encryption key, the
TTL, the password, the compose service and roughly 900 lines of tests to defend
a feature nobody had asked for since the product moved to the stateless path -
and, more to the point, keeping the only place in the system where clinical
material outlives the request that carried it.

Also rejected: keeping `DELETE /api/documents/{file_id}` as a no-op for
compatibility. An endpoint that answers 204 without deleting anything tells a
clinician their withdrawal succeeded, which is true only because there was
never anything to withdraw. Removing the route says that plainly; a 404 on a
path that no longer exists is not ambiguous.

## What it costs

- **A breaking API change.** A client outside this repository built against the
  upload or extraction endpoints stops working, and there is no deprecation
  window - the routes are gone in one step. The repository is public, so such a
  client cannot be ruled out by inspection.
- **No analyse-once, read-later flow.** A document must be resubmitted to be
  summarised again, and every summary costs a full inference. If that flow is
  ever wanted back, it is a new storage design, not a revert - and it needs its
  own decision entry, because it reintroduces persisted patient-derived data.
- **`STORE_DOCUMENT_TEXT` is gone as a debugging aid.** Inspecting what the
  extractor read now means reproducing it outside the service.
- **The offsets outlive their justification.** `drop_offsets` removed
  `start`/`end` before writing, on the grounds that an offset means nothing
  without the text it indexes. The analysis path never applied that rule and
  still returns offsets into text the API does not send. That predates this
  change and is left as it was rather than widened into it, but it is now the
  only remaining trace of the retention argument and should be settled on its
  own.
