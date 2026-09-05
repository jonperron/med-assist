---
type: decision
title: 2026-08-31 - The model loads once, and a failed load stays unready
description: The lifespan handler loads the weights before the socket opens, a failed load leaves the process up and permanently unready, and a readiness flag keeps routes from re-attempting the load per request.
tags: [backend, deployment, readiness, model]
---

# 2026-08-31 - The model loads once, and a failed load stays unready

## What was decided

The weights are read once, by the lifespan handler in `app/main.py`, on a worker
thread. Uvicorn opens its listening sockets only after that handler returns, so
during the load the port is closed rather than slow: a connection is refused, not
queued behind a multi-second load.

**A failed load does not stop the process.** The handler catches whatever a
missing, unreadable or misconfigured model directory raises, logs the exception
type - never the path, and no document has been read yet, so the type is safe -
and leaves `app.state.model_loaded` false. The service stays up and permanently
unready rather than crash-looping, which says nothing about why.

**Two health endpoints answer two different questions.** `GET /healthz` is
liveness: the process is up and the loop is answering, and it says nothing about
the model. `GET /readyz` is readiness: `200 {"status": "ready"}` once the weights
are in memory, otherwise `503` with the same `{"detail": {"message": ...}}`
envelope and the same fixed message the analysis routes use - no path, no
configuration, no reason. `docker-compose.yml` points its healthcheck at
`/readyz` with a `start_period` long enough to cover the load.

**The routes that need the model check a flag, not the cache.**
`require_the_model` reads `app.state.model_loaded` and refuses with `503`.
Nothing outside the lifespan handler builds the extractor, because `lru_cache`
does not memoise an exception: a route that built it after a failed startup
would re-attempt the whole multi-second load on every request, in a worker
thread, forever. The flag turns that into one cheap refusal per request. An
application whose lifespan never ran - a router mounted in a test, an embedding
that manages its own startup - has made no claim either way, so the absent flag
reads as ready; a guard is not the place to invent a claim.

What a clinician sees while this is happening is
[[2026-08-31-an-unavailable-service-is-announced-before-the-batch]]; the mount
that most often causes it is
[[2026-08-31-the-model-is-mounted-not-baked-into-the-image]].

## The alternative that was rejected

**Exiting on a failed load.** A process that will not start is the clearest
possible signal - to whoever reads the logs. Under compose or an orchestrator it
is a restart loop, and a restart loop replaces one legible error with a stream
of them; the container never reaches a state where `/readyz` can be asked what
is wrong, and the interface has nothing to poll. Staying up and unready keeps
the diagnosis reachable from outside.

**Loading lazily, on the first analysis request.** Startup is instant and the
first clinician pays thirty seconds for it, with a timeout somewhere in between
deciding whether they pay it twice. It also makes "is this deployment working"
unanswerable without submitting a document.

**Retrying the load in the background.** Tempting, and it hides a fixed
deployment fault behind an eventually-working service, which makes the fault
survive into production unnoticed. A fixed mount is a restart, which is cheap
and explicit.

## What it costs

- **A failed load is permanent until someone restarts the process.** Correcting
  `MODEL_DIR` on the host does nothing until the container is restarted, and
  nothing in the service says so.
- **The reason is only in the logs, and only as a type.** `/readyz` answers a
  fixed sentence by design, so an operator diagnosing an unready service has to
  reach the container logs, where they get an exception class name and no path.
  That is the privacy boundary being paid for in diagnosability.
- **The readiness flag can disagree with reality.** It records what happened at
  startup. A model directory that is unmounted, replaced or corrupted while the
  process runs leaves the flag true, and the failure then surfaces as a `500`
  from an analysis rather than as unreadiness.
- **`model_is_loaded` defaults to true when the flag is absent.** That is right
  for tests and wrong for any future embedding that skips the lifespan handler
  and expects the guard to protect it.
- **`/healthz` passing means very little.** It answers as soon as the socket is
  open, which - because the socket opens after the lifespan handler - includes
  the case where the load has already failed. Anything checking liveness alone
  reports a broken deployment as healthy.

---

Written down on 2026-09-05 from `backend/README.md`, which carried the reasoning
inline. The behaviour landed with `03d115b` (2026-08-18) and `cf949cf`
(2026-08-31).
