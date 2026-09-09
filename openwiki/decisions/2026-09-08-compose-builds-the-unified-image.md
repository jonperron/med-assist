---
type: decision
title: 2026-09-08 - docker compose builds the unified image, not two Dockerfiles
description: docker-compose.yml now builds one `app` service from the root Dockerfile instead of two services from backend/Dockerfile and frontend/Dockerfile, which are deleted. Supersedes the "two shapes coexist on purpose" call in 2026-09-05-the-release-image-is-one-container.md.
tags: [deployment, docker, ci]
---

# 2026-09-08 - docker compose builds the unified image, not two Dockerfiles

## What was decided

`backend/Dockerfile` and `frontend/Dockerfile` are deleted. `docker-compose.yml`
now has one service, `app`, building the root `Dockerfile` with `context: .` -
the same image `.github/workflows/docker_build.yml` publishes on a release.
A working copy and a tagged version now run the exact same container, rather
than the working copy running two smaller ones assembled by hand from
`backend/Dockerfile` and `frontend/Dockerfile`.

This directly reverses the choice recorded in
[`2026-09-05-the-release-image-is-one-container.md`](2026-09-05-the-release-image-is-one-container.md):
"`docker-compose.yml` is untouched and still builds `backend/Dockerfile` and
`frontend/Dockerfile` as two services. The two shapes coexist on purpose: one
is what a working copy runs, the other is what a tagged version ships as."
That entry's own cost section flagged the reason this one exists: "A third
build description to keep in step... a change to either that is not mirrored
here produces a release image that differs from what compose builds and what
CI tested." It also flagged that `backend/Dockerfile` ran the API as root
while the unified image runs both processes as uid 1001 - a second drift
between the two shapes, on top of the build-description one. Collapsing to
one Dockerfile removes both by removing the second shape rather than by
keeping it in sync.

`docker-compose.yml`'s per-service settings were merged onto the one `app`
service: both ports (`${BACKEND_BIND_ADDRESS:-127.0.0.1}:8050` and `3000`,
unchanged from
[`2026-09-08-the-backends-published-port-moved-to-8050.md`](2026-09-08-the-backends-published-port-moved-to-8050.md)),
the model bind mount, the tmpfs, and `ulimits: core: 0` alongside the
entrypoint's own `ulimit -c 0` rather than instead of it, since the entrypoint
protects a container started outside Compose and Compose's own setting costs
nothing to keep. `cap_drop: [ALL]` and `security_opt:
[no-new-privileges:true]` are added, which neither prior service had.
`BACKEND_MEMORY_LIMIT`/`BACKEND_CPU_LIMIT` and
`FRONTEND_MEMORY_LIMIT`/`FRONTEND_CPU_LIMIT` are replaced by
`APP_MEMORY_LIMIT`/`APP_CPU_LIMIT`, defaulting to `2.5g`/`3`, the sum of the
two defaults they replace - see "What it costs" below for what that
replacement does to an operator's own overrides. `deploy/caddy/Caddyfile.example`
and `deploy/README.md` are updated for the one service name; `.env.example`
and the root `README.md` are updated for the one `docker compose restart app`.

The build arg is the one place "the same image" is a default, not a
guarantee: `docker-compose.yml` passes `NEXT_PUBLIC_API_URL` explicitly
(`${NEXT_PUBLIC_API_URL:-http://localhost:8050}`), matching the host port
Compose publishes; the root Dockerfile's own `ARG` default stays `8000`, for
`docker build .` run standalone or by the release workflow. Left at its
default, a `docker compose build` and a release build produce different
images - correctly, since they serve different ports - and setting
`NEXT_PUBLIC_API_URL` for a real deployment (the Coolify and Caddy cases in
`deploy/README.md`) makes them diverge further on purpose. What is now
genuinely shared is the Dockerfile itself and everything it does that isn't
gated by that one build arg: the non-root user, the ulimit, the tmpfs
contract, the entrypoint's shutdown behavior.

## The alternative that was rejected

Give the root `Dockerfile` named build stages - a `backend` target and a
`frontend` target alongside the combined `runtime` one - and point
`docker-compose.yml`'s two services at those targets instead of at
`backend/Dockerfile` and `frontend/Dockerfile`. That would have kept
independent containers for local development (independent restart, independent
resource ceilings, a frontend crash that does not take the API down with it)
while still deleting the two duplicated files and closing the root-vs-root
drift this entry is otherwise about.

It was rejected because the request behind this entry was to run one
container, not only to own one Dockerfile - collapsing the two shapes so a
working copy exercises exactly what a release ships, rather than a
build-description merge that leaves the working copy still running two
processes in two containers. A targets-based split is worth its own entry if
independent local restart or isolated resource ceilings turn out to matter
enough to reintroduce it.

## What it costs

**One shared resource ceiling instead of two.** The API and the interface
used to have independent memory and CPU limits; a runaway Node process was
walled off from the model's headroom by its own container. They now share
`APP_MEMORY_LIMIT`/`APP_CPU_LIMIT`, so a leak or spike on one side can starve
the other. The default sums the two prior defaults rather than shrinking
either, but the isolation itself is gone, not just renamed. The rename is
also silent: `BACKEND_MEMORY_LIMIT`/`BACKEND_CPU_LIMIT` and
`FRONTEND_MEMORY_LIMIT`/`FRONTEND_CPU_LIMIT` in a stale `.env` are not read
by the `app` service and are not refused either - a deployment that had
tightened either limit below its default silently gets the new, looser
default back instead.

**Local development now needs readable weights, where it previously did
not.** `backend/Dockerfile` ran the API as root, so `./backend/models` owned
by the developer's own account and left at its default permissions always
worked locally, whatever the published image required. The root Dockerfile
runs both processes as uid 1001, which was already true of the published
release image (see the "Non-root" cost in
[`2026-09-05-the-release-image-is-one-container.md`](2026-09-05-the-release-image-is-one-container.md)),
but `docker compose up` now inherits it too: a weights directory that is
`chmod 600` produces a container that starts, serves the interface, and
answers `503` on every analysis route, with the load failure deliberately
logged without its cause. `.env.example`'s `MODEL_DIR` comment now says so.

**The process parsing attacker-supplied documents now shares a trust
boundary with the browser-facing process.** Separate containers put a parser
compromise in a container with no browser-facing surface. Co-located, both
run as the same uid in the same PID and mount namespaces, sharing `/tmp`: a
compromised parser can read the interface process's environment via
`/proc/<pid>/environ`, and can signal or starve it. `cap_drop: [ALL]` and
`security_opt: [no-new-privileges:true]` (added to `docker-compose.yml` by
this change, matching what `deploy/README.md`'s `docker run` examples already
told operators to add for the release image) narrow what that gets an
attacker, but do not restore the isolation two separate containers gave for
free.

**One shared restart instead of two.** `docker-entrypoint.sh` takes the whole
container down when either process exits, and Compose restarts the one
service as a unit. A crash confined to the interface previously left the API
serving in-flight requests; it now ends those requests too. This was already
true of the published release image - see
[`2026-09-05-the-release-image-is-one-container.md`](2026-09-05-the-release-image-is-one-container.md)
- and is now also true of a local working copy, which did not have this
failure mode before.

**A model swap, or flipping `UNSECURED_DEPLOYMENT`, now bounces the interface
too.** `docker compose restart backend` used to restart only the API;
`docker compose restart app` restarts both, briefly dropping the browser's
connection to the interface as a side effect of picking up new weights or the
banner setting.

**Scaling the model's concurrency now duplicates an idle interface per
replica.** The former advice to run more backend processes for
`NER_MAX_CONCURRENT_INFERENCES` scaled a process that did nothing else; running
more replicas of `app` now also starts a Next.js server nobody needs per
replica. Wasted work, not an unsafe one, and there is no load balancer here to
make replicas meaningful yet regardless.

**A platform that attaches a domain to a whole service, not a port within
one, cannot point at the interface alone anymore.** Coolify's own domain
picker supports naming a port; a platform whose model is coarser than that
needs a proxy in front to make the API-vs-interface split reachable at all,
where two separate compose services used to give it that split for free.

**Local dev now builds and runs the full ~1.85 GB image** (size measured in
`2026-09-05-the-release-image-is-one-container.md`) **on every `docker compose
up --build`**, rather than two smaller images built and cached separately - a
frontend-only change still pays for resolving the backend's dependency layer
in the same build, torch wheels included, though Docker's layer cache absorbs
most of that after the first build.
