---
type: decision
title: 2026-08-27 - Progress is a stream, because a job would have to be stored
description: POST /api/analyze/stream reports a batch document by document as Server-Sent Events over the POST that carries the files; there is no job id to poll, and the progress events carry no clinical content.
tags: [backend, api, progress, privacy]
---

# 2026-08-27 - Progress is a stream, because a job would have to be stored

## What was decided

A batch of four documents takes about half a minute on a CPU, and one spinner
over the lot says nothing about whether it is progressing.
`POST /api/analyze/stream` takes the same body as `POST /api/analyze`, does the
same work, and sends Server-Sent Events as it goes: `batch` (how many documents
were accepted), one `document` per document as it is read, and then either
`result` - exactly the body the other endpoint would have returned - or `error`.
Each event's `data` is one JSON object tagged by `stage`, so a client narrows on
the tag rather than guessing.

**It is a stream and not a job because a job would have to be stored.** A
pollable job means an id, a place to keep the summary between the request that
produced it and the request that fetches it, and a retention rule for that
place. The service has none of those and is not getting them - see
[[2026-08-28-the-api-stores-nothing-and-redis-is-gone]]. One request from the
first byte to the last is what keeps the answer from ever resting on the server.

**It is a `POST`, so the browser reads it with `fetch` and a `ReadableStream`.**
`EventSource` only issues `GET`, and the documents have to travel in the body.

**Progress carries no clinical content.** A `document` event is a position, a
boolean and a reason code. Nothing the model marked, and no filename, travels
before the `result` event - which carries what the other endpoint would have
sent and nothing more. The reported flag and reason are read off `describe()`,
the same function the final result uses, so a `document` event cannot disagree
with the `result` that follows it.

**A refusal is still a status code.** Validation and the model-readiness check
run as dependencies, before the stream opens, so a rejected file type, an
oversized batch and an unloaded model answer `400`, `413` and `503` as JSON with
no events at all. Only a failure that cannot be known until documents are being
read - a batch nothing could be read from, or a server fault - arrives as an
`error` event, because by then the response is committed at `200` and there is
no status code left to send. `error` carries a machine-readable `reason`
(`unreadable_batch` for the caller's documents, `server_error` for the
service's own failure) precisely so a client never has to branch on wording.

Which of the two endpoints the interface calls is
[[2026-08-27-stream-is-the-only-analysis-path-the-client-takes]].

## The alternative that was rejected

**A job id and a polling endpoint.** The conventional shape, and it works
through any proxy without special handling. It requires the server to hold a
patient's summary between two requests, which is the one thing this API is built
not to do. Rejected on the boundary, not on the ergonomics.

**A `GET` with an `EventSource`, the documents uploaded first.** Two round trips,
and the first one has to leave the documents somewhere the second can find them.
Same objection.

**One long request with no progress at all - what the plain endpoint is.** It is
kept, and it is the right answer for anything that is not a person watching. For
a clinician it is thirty seconds of a bar that claims nothing.

**Deriving the progress flags separately from the final result.** Cheaper by one
function call and a place where two derivations of "was this document read"
could drift as `UnreadableReason` grows.

## What it costs

- **A buffering proxy silently turns the stream back into a spinner.** Anything
  that buffers `text/event-stream` delivers every event at once at the end.
  Nothing in the client can detect it, and the progress card then claims a count
  it never showed.
- **The client has three things to get right, and two of them fail loudly only
  in production.** Comment frames must be skipped: FastAPI inserts a `: ping`
  after 15 idle seconds to hold the connection through a proxy timeout, and a
  single large PDF exceeds that routinely, so a reader that parses every frame
  throws on the first ping. A stream that ends without `result` or `error` must
  be treated as a failure, because a transport fault below the endpoint can only
  appear as a stream that stops. And the event union has to be read from
  `components.schemas.AnalysisEvent`: `openapi-typescript` reads only `schema`
  from a media type and an SSE payload is described by `itemSchema`, so the
  generated client types the response body as `unknown`.
- **A failure after the first event is a `200` in every access log and metric.**
  The status code says the request succeeded; only the last event says
  otherwise.
- **Two endpoints do the same work.** They share a route module, a validation
  dependency and a use case, and the `result` event is defined as the other
  endpoint's body - but they are still two published contracts, and the plain
  one now has no first-party caller.
- **The broad `except Exception` in the generator is deliberate and coarse.** An
  exception escaping an async generator after the response is committed reaches
  no handler, so the alternative is a stream that stops with no reason at all.
  The type is logged and never sent.

---

Written down on 2026-09-05 from `backend/README.md`, which carried the reasoning
inline. The endpoint itself is `64658d1` (2026-08-27).
