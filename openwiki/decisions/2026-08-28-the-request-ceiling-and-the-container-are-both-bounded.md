---
type: decision
title: 2026-08-28 - The request ceiling and the container are both bounded
description: The body limit moves onto the receive channel so an undeclared length cannot bypass it, and compose caps memory, CPU and log growth.
tags: [backend, deployment, footprint, security]
---

# 2026-08-28 - The request ceiling and the container are both bounded

## What was decided

Three limits that were assumed to exist are now enforced.

**The request ceiling holds without a declared length.** `reject_oversized_requests`
read `Content-Length` and nothing else. A body sent with `Transfer-Encoding:
chunked` declares no length, so the check never saw it - and the multipart
parser caps the fields around a file part but not the file part itself. A
chunked upload was therefore spooled to `TMPDIR` in full and only then answered
`413` by `validate_upload_file`, with the disk already spent. Measured before
the change: a 200 MB chunked part reached `TMPDIR` complete, four times the
50 MB ceiling and twenty times the per-file cap.

`LimitRequestSize` replaces it and counts bytes on the receive channel, so the
ceiling bites while the body is arriving. The declared-length check is kept
ahead of it because it refuses without reading anything.

**It is ASGI middleware, not an `@app.middleware("http")` function.** That is
forced, not stylistic: `BaseHTTPMiddleware` builds a fresh receive channel for
the app below it, so a dispatch function cannot reach the bytes the parser will
actually read.

**The middleware replaces the response the truncation produced.** Cutting the
body off mid-part makes FastAPI report a parse failure as its own `400`. That
answer describes the wrong problem, so once the ceiling has tripped the app's
response is dropped and the `413` is sent instead. The refusal names the
ceiling and never the received size: on this branch there is no complete figure,
and inventing one would be a measurement of the caller's documents.

**The refusal is sent inside CORS.** `LimitRequestSize` writes its 413 straight
to `send` rather than returning it through the router, so it carries CORS
headers only if `CORSMiddleware` is registered outside it. It was not, and the
declared-length refusal on `main` had the same shape: the browser saw an opaque
network error, and the frontend's `413 -> too_large` branch could never run. The
registration order in `app/main.py` is now load-bearing and says so.

**The containers are bounded.** `docker-compose.yml` gains memory and CPU limits
(`2g`/2 cores for the backend, `512m`/1 core for the frontend, all overridable),
log rotation on both services (three 10 MB files), `restart: unless-stopped`,
and `ulimits: core: 0` so a parser crash cannot dump document text onto the
host. The `tmpfs` grows from 128m to 256m and uvicorn gains
`--limit-concurrency 8`, because the 50 MB ceiling bounds one request and
nothing bounded the sum of those in flight.

Measured under those limits: ready 12 seconds after start, 470 MiB idle,
504 MiB peak across a batch of five long documents.

**`NER_INFERENCE_THREADS` defaults to the CPU limit.** Torch reads the host's
core count rather than the cgroup quota, so adding a CPU limit without pinning
the thread count would have made the service slower than it was before. On a
14-core host under a 2-core quota, five long documents took 11 seconds with the
two matched and 215 seconds without - a 20x difference, and the largest single
effect in this change. It is measured, not assumed: memory was unchanged
between the two runs, so this is contention, not capacity.

## The alternative that was rejected

**Leaving the ceiling on `Content-Length` and treating the per-file check as the
backstop.** That is what the old docstring claimed - "a body that lies about its
length is still caught by the per-file limit" - and it is true of the response
and false of the footprint. The `413` arrives after the bytes are written. On the
compose deployment the `tmpfs` caps the damage at 128 MB, but as `ENOSPC` and a
`500` rather than a clean refusal; run any other way, the write is unbounded on
host disk.

**Leaving the containers unbounded and documenting recommended limits instead.**
The README calls the footprint a product property. A limit that only exists in
prose is not one, and the default `json-file` log driver never rotates, so an
untouched deployment grows a log file until the disk fills - the one unbounded
write left after Redis was removed.

**Registering the ceiling outside CORS, as the old check was.** That keeps the
refusal unreadable by the only client the product has. Moving `CORSMiddleware`
outside costs nothing - it forwards `receive` untouched, so the ceiling still
wraps the channel the parser reads from.

## What it costs

- **A `413` where some callers saw a `400`.** A chunked request over the ceiling
  used to surface as FastAPI's generic parse error. It is now a refusal that
  says why. Better, but a status-code change on a public endpoint all the same.
- **The ceiling is charged against the whole body, not the documents.** Multipart
  framing counts toward the 50 MB, so the usable document budget is slightly
  under it. The three limits still do not agree with each other:
  `MAX_BATCH_FILES` (20) x `MAX_FILE_SIZE_BYTES` (10 MB) is 200 MB, which the
  50 MB ceiling makes unreachable. The batch cap does not mean what it looks
  like it means, and that is left as it was rather than folded into this change.
- **The memory limit is headroom, not a measurement.** 2 GB is roughly four
  times the observed 504 MiB peak. The service starts and analyses at 512 MB,
  so the default is deliberately loose: a large PDF is expanded in memory by
  its parser, and that path was not measured. A tighter limit would bound the
  DOCX and PDF expansion noted below; it would also OOM-kill legitimate work,
  and the failure is silent - the process stays up and answers `503` on
  `/readyz` rather than crashing, which is correct but reads as a hang.
- **`--limit-concurrency 8` and a 256m tmpfs are a stated pair, not a proof.**
  Four concurrent max-size uploads fit; eight do not. Beyond four, a request
  fails on a full filesystem with a generic 500 rather than a clean refusal.
  Sizing the tmpfs for the full concurrency allowance would mean 400 MB of the
  memory limit reserved for a case that has never occurred, so the mismatch is
  accepted and written down here instead.
- **Uvicorn has no request-body timeout.** A handful of clients trickling a
  49 MB body each can hold the tmpfs full indefinitely without exceeding any
  limit in this change. The ceiling bounds size, not duration.
- **The CPU limit is now the thing that decides latency.** Two cores is a
  deliberate default for a machine running other work, and it makes a batch of
  long documents take minutes. `BACKEND_CPU_LIMIT` is the dial; the cost of
  bounding CPU is that someone has to turn it.
- **Log rotation discards evidence.** Three 10 MB files is roughly a day of
  access logs under load. An operator investigating something older needs to
  have shipped them elsewhere first.
- **The unreachable branch is kept, and it degrades quietly.** If a route ever
  answers before it has read the body, the ceiling cannot replace a response
  already on the wire; it logs an error and lets the response stand rather than
  resetting the connection. No route reaches it today - both endpoints declare
  a body field, so FastAPI parses the form before any dependency or handler
  runs. A route taking a raw `Request` and reading the body inside a streaming
  generator is what would make it reachable.

## What was left alone

Found while measuring this, out of scope, and each needing its own entry:

- **A DOCX or PDF inside every declared limit can still exhaust memory.** Both
  are compressed containers expanded wholesale by their parser, with no bound
  on the expansion, so a 10 MB file well under the request ceiling can expand
  far past the memory limit. This change makes the limit that it trips, and did
  not create the path.
- **Both parsers run synchronously inside a coroutine**, so one expensive
  document blocks the event loop - including `/readyz`, which makes the
  healthcheck fail under load.
- **`validate_upload_file` reports `received_size_bytes` and `received_type`.**
  The middleware here deliberately reports neither, so the two 413s on the same
  service now disagree about whether a refusal may quote a measurement of the
  caller's document.
- **Both services still publish on all host interfaces with no authentication.**
  Changing that is a network exposure decision, not a footprint one.
