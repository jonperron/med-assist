---
type: decision
title: 2026-08-31 - The model is mounted, not baked into the image
description: Superseded the same day. The weights moved from a COPY in backend/Dockerfile to a read-only bind mount in docker-compose.yml, until a deployment that builds from a Git clone showed the mount had nothing to point at.
tags: [deployment, docker, model, backend]
---

# 2026-08-31 - The model is mounted, not baked into the image

> **Superseded the same day by
> [[2026-08-31-the-weights-ship-as-their-own-private-image]].** The weights are
> baked into the backend image again, from a model image rather than from the
> build context, and the mount survives as an opt-in overlay in
> `docker-compose.dev.yml`. Read this entry for why they were unbaked and what
> that cost; read the newer one for what replaced it.
>
> Two things below are now false and are corrected in place: the weights are no
> longer absent from the image, and the accepted integrity risk in "What it
> costs" is largely closed. The reasoning that led here is left intact, because
> the two objections it raised - a build that fails on a clone without the
> weights, and a 420MB layer rebuilt on every source edit - are real, and the
> newer entry had to answer both rather than dismiss them.

## What was decided

`backend/Dockerfile` copied the weights into the image:

```dockerfile
COPY ./app ./app
COPY ./models ./models
```

The `COPY` is removed. `docker-compose.yml` mounts the same directory instead,
read-only, at the path `NER_MODEL_NAME` already pointed at:

```yaml
volumes:
  - ${MODEL_DIR:-./backend/models}:/app/models:ro
```

`models/` is added to `backend/.dockerignore`, so the weights are no longer
uploaded to the daemon as part of the build context either. `MODEL_DIR` is
documented in `.env.example` and defaults to `./backend/models`, which is where
the weights already live, so an existing checkout needs no new configuration.

Measured on the backend image: 2.47 GB baked, 1.62 GB mounted.

Read-only because nothing writes to the weights. The pipeline is pointed at a
local directory with `HF_HUB_OFFLINE` and `TRANSFORMERS_OFFLINE` set, so
`from_pretrained` reads and never fetches or caches. Verified: the container
reaches `{"status":"ready"}` on `/readyz` 11 seconds after start with the mount
in place, and answers 503 with the fixed message - carrying CORS headers, so the
browser reads it rather than blocking it - when the mount is empty.

Those two offline flags move from `docker-compose.yml` into `backend/Dockerfile`
as part of this change. They were survivable in compose alone while the weights
were baked in, because there was always a local model to read. An image that
ships without them changes that: the obvious way to "fix" an unready container
is to point `NER_MODEL_NAME` at a Hub id, and without the flags transformers
fetches it over the network - from a service whose whole claim is that nothing
leaves the machine. The refusal now travels with the image.

## The alternative that was rejected

Leaving the `COPY` and shipping a self-contained image.

That is the better answer for a registry-distributed artifact: one thing to
pull, one digest covering code and weights together, and no host path to get
wrong. It is not what this repository is. `backend/models/` is gitignored and
the weights are ~420 MB, so the image was never reproducible from a clone
anyway - the `COPY` failed the build outright on a checkout without them, which
is a build error for a condition the running service already handles. Every
edit to `app/` also rebuilt and re-exported a 420 MB layer that had not changed,
and the same bytes were sent to the daemon on every build regardless.

A named Docker volume was also rejected: it would have to be populated by a
copy step, which puts the weights in two places and makes "which model is this
serving" a question about volume contents rather than about a path on the host.

## What it costs

- **The image is no longer self-sufficient.** `docker run med-assist-backend`
  with no `-v` starts a service that cannot analyse anything. It does not crash
  - it answers 503 on `/readyz` and on both analysis routes - but nothing about
  the image announces the missing mount, and anyone deploying it outside
  `docker-compose.yml` has to arrange the mount themselves. `.env.example` and
  the root README say so; the image does not.

  **This is what broke the deployment, and it is why this entry was superseded.**
  Coolify builds from a Git clone. `backend/models/` is gitignored, so the clone
  has no weights; Docker created the missing bind source as an empty directory
  rather than refusing; the container started and answered 503 for ever. Every
  sentence of that was written down here as understood and accepted, and it was
  still a service that did not work, because the cost was priced as an operator
  inconvenience rather than as "this cannot be deployed anywhere that does not
  already have the weights on disk".
- **A wrong `MODEL_DIR` is silent at the compose layer.** Docker creates a
  missing bind-mount source as an empty directory rather than refusing, so a
  typo produces a started container that reports itself unready rather than an
  error naming the path. Three spellings fail this way and none of them warn: a
  bare `models` is read as a named volume rather than a directory, `~` is not
  expanded, and a relative path resolves against the compose file's directory
  rather than the operator's shell. `.env.example` names all three. This is the
  failure the interface warning added in
  [[2026-08-31-an-unavailable-service-is-announced-before-the-batch]] exists to
  make visible; without it, the same typo showed up only as a refused analysis
  after the clinician had already selected their documents.
- **The image digest no longer covers the weights, and nothing replaces it.**
  *Largely closed by
  [[2026-08-31-the-weights-ship-as-their-own-private-image]]: the backend image
  digest covers its weights again, and the model image's own digest covers the
  bytes that were published. What remains is that `docker-compose.dev.yml` can
  still mount a directory over them, and nothing checks - so the paragraph below
  describes the overlay's behaviour rather than the default one. The
  expected-digest manifest it calls for is still unwritten and still wants its
  own entry.*

  This is the real cost, and it is an integrity one rather than a code-execution
  one: transformers is pinned to 5.x on safetensors with `trust_remote_code` at
  its default, so a substituted `config.json` cannot plant an `auto_map` and the
  pickle path is gone. What is gone is the guarantee that the artifact reviewed
  is the artifact that ran. Whatever `MODEL_DIR` resolves to performs clinical
  entity extraction, nothing verifies it is the intended model, `:ro` stops the
  container writing the weights but not the host, and the flag exists only in
  `docker-compose.yml`. A stale directory or a half-copied training output
  therefore produces confidently wrong clinical output with no signal anywhere -
  the interface names no model by design, so it cannot be the thing that tells
  anyone. **Accepted, not solved.** The cheap next step is to log a digest of
  the loaded directory from the lifespan handler - operator-facing container
  log, never the interface, so the no-mechanism-on-screen rule is untouched -
  and the real fix is an expected-digest manifest that fails the load into the
  existing 503 on mismatch. Both are backend work beyond this change and want
  their own entry.
- **Model and code can now drift.** They were versioned together by
  construction and no longer are: restarting the backend against a different
  `MODEL_DIR` changes what the service returns with no rebuild and no trace in
  the image. Swapping in a retrained model becomes a restart, which is the
  point, but nothing records which weights answered a given summary.
- **The `:ro` flag is load-bearing and unenforced elsewhere.** It is set in
  `docker-compose.yml` only. Any other way of running the image can mount the
  same directory writable, and nothing in the application checks.
