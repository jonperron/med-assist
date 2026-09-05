---
type: decision
title: 2026-09-05 - The release image is one container, not two
description: A release publishes a single image holding the API and the interface, built from a root Dockerfile, while docker compose keeps building the two services separately.
tags: [deployment, docker, ci, release]
---

# 2026-09-05 - The release image is one container, not two

## What was decided

`.github/workflows/docker_build.yml` built with `context: .` and no `file:`, so
it looked for a `Dockerfile` at the repository root. There has never been one -
the two Dockerfiles live in `backend/` and `frontend/` - and the step failed
with `failed to read dockerfile: open Dockerfile: no such file or directory`.
The job had never once succeeded: it failed the same way on 0.1.0 and again on
1.0.0, which is how a release workflow can be broken for a month without anyone
noticing.

The root `Dockerfile` is now written rather than the workflow repointed. It
builds the interface with Next's standalone output, installs the backend's
dependencies, lifts the Node binary out of `node:24-trixie-slim` into the Python
image, and starts both processes under `docker-entrypoint.sh`. A release
publishes that one image at `ghcr.io/jonperron/med-assist`.

`docker-compose.yml` is untouched and still builds `backend/Dockerfile` and
`frontend/Dockerfile` as two services. The two shapes coexist on purpose: one is
what a working copy runs, the other is what a tagged version ships as.

The entrypoint takes the container down when either process exits:

```bash
wait -n
status=$?
stop
```

Docker restarts a container, not a process inside one. Without that, killing
the interface leaves a container that is still `Up`, still passing a port
check, and serving nothing on 3000.

Verified locally against the real weights: the image builds at 1.85 GB, reaches
`{"status":"ready"}` 20 seconds after start, refuses `POST /api/analyze` with
`401` when no credential is presented, and answers a summary when one is.
Killing the Next.js process exits the container with 137.

## The alternative that was rejected

Two images, `ghcr.io/jonperron/med-assist/backend` and `/frontend`, built by a
matrix over the two compose services. It is the conventional shape, it is a
smaller diff, and it keeps each service's Dockerfile as the single description
of that service.

It was rejected because the frontend half of it is close to useless.
`NEXT_PUBLIC_API_URL` is inlined into the client bundle at build time, so a
published frontend image is permanently pinned to whatever URL CI built it with
- `http://localhost:8000`, the only defensible default - and every deployment
whose API is anywhere else has to rebuild it anyway. Publishing an image whose
one build-time constant is wrong for its audience is worse than not publishing
it. In a single container that same default is simply correct: both processes
are there, and a browser given both published ports does reach the API at
`http://localhost:8000`.

Building only the backend was the other candidate, and matches how
`deploy/README.md` already talks about "the published image". It was rejected
for leaving a release that ships half the product, with no answer at all for
someone who wants to run a tagged version without a checkout.

## What it costs

**Two processes in one container, which is a thing to be argued with.** They
share a memory limit, a CPU quota and a log stream, so the interface's Node
process is charged against whatever the model is holding, and `docker logs`
interleaves both. The compose stack keeps the per-service limits, the
`ulimits: core: 0` and the separate healthchecks; none of that travels with
this image, and reproducing it on a `docker run` is the operator's job.
`deploy/README.md` now carries the run command that does.

**The `tmpfs` is the one that matters.** Multipart parts above 1MB are spooled
under `TMPDIR` before any route code runs, so an image run without
`--tmpfs /tmp` writes clinical documents to the container's writable layer -
exactly what the compose tmpfs exists to prevent. The image cannot mount that
for itself.

**A third build description to keep in step.** The root `Dockerfile` repeats
what `backend/Dockerfile` and `frontend/Dockerfile` say, and a change to either
that is not mirrored here produces a release image that differs from what
compose builds and what CI tested. The pull-request build added to the same
workflow catches the half of that which breaks the build; it does not catch the
half that merely drifts.

**Non-root, and the weights have to allow it.** Both processes run as uid 1001,
where `backend/Dockerfile` still runs the API as root. A weights directory whose
files are `chmod 600` and owned by the operator's account then produces a
container that starts, serves the interface, and answers `503` on every analysis
route - and the model-load failure is deliberately logged without its cause, so
there is nothing to read. This was hit while testing the image and is written
down in `deploy/README.md` rather than fixed in code: the alternative is running
the release image as root, which is a worse trade for a published artifact.

**Size.** 1.85 GB, carrying the torch CPU wheels and a Node runtime. Splitting
would not have made the sum smaller, only the parts.
