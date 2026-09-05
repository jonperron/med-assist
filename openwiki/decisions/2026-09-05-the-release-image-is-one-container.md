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
`{"status":"ready"}` 20 seconds after start, serves the interface on 3000, and
answers `POST /api/analyze` with a summary for synthetic text. Killing the
Next.js process exits the container with 137, and a `docker stop` at any point
after start exits 143 without waiting for Docker's SIGKILL.

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
one build-time constant is wrong for its whole audience is worse than not
publishing it.

The single container does not remove that pin. It narrows who the default is
right for from nobody to somebody: the browser is on the machine running Docker,
where `localhost:8000` is both ends of one connection, and that is the
deployment this project is built for. It is right for no other reader.
`NEXT_PUBLIC_API_URL` is an address the *browser* resolves, so opening the
interface from a second machine names that machine's own port 8000 and every
analysis fails as a network error, however the container's ports are published.
See "What it costs" below.

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

**The published tag is a local deployment and cannot be reconfigured into any
other.** `NEXT_PUBLIC_API_URL` is frozen when the image is built, so a
deployment reached from another machine builds its own image with `--build-arg`
and moves `CORS_ALLOWED_ORIGINS` with it - a published tag plus environment
variables will not get there. The published artifact is therefore useful for
running a tagged version locally without a checkout, and is not the thing you
deploy behind a domain.

The alternative was a same-origin proxy: have the interface call its own origin
and let the Next.js server forward `/api` to `127.0.0.1:8000`, which would make
one image work from anywhere. It was rejected here as out of proportion to the
change - it moves every browser call in the application onto a new path, changes
what the CSP has to allow, and puts the origin check in front of a proxy that
sends no `Origin` at all, none of which belongs in a fix for a release workflow
that was looking for a `Dockerfile` that did not exist. It is the right shape
for a deployment story, and is worth its own entry if the project ever wants
one.

**Size.** 1.85 GB, carrying the torch CPU wheels and a Node runtime. Splitting
would not have made the sum smaller, only the parts.
