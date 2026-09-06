---
type: decision
title: 2026-09-06 - The Node stages stay Debian, not Alpine
description: The root Dockerfile's frontend-builder and the copied node binary move back to node:24-trixie-slim so they share a libc with the python:3.12-slim-trixie runtime; the runtime itself stays off Alpine.
tags: [deployment, docker, release]
---

# 2026-09-06 - The Node stages stay Debian, not Alpine

## What was decided

A prior commit moved the root Dockerfile's Node stages to `node:24-alpine` -
the commit message doesn't say why, but Alpine's smaller layers are the
likely reason - while leaving the runtime stage on `python:3.12-slim-trixie`
and copying `/usr/local/bin/node` out of the alpine stage into it. Alpine's
`node` binary is linked against musl's dynamic loader
(`ld-musl-x86_64.so.1`); a Debian base ships `ld-linux-x86-64.so.2` instead and
has no musl loader to satisfy it. The copy step itself succeeds - it is a file
copy, not a link check - so `docker build` stays green and the break only
shows up as `node` refusing to execute inside the finished container. That
commit never reached `main` or a release; it was caught here, on the branch
that introduced it, before either ran.

The pull-request job in `.github/workflows/docker_build.yml` builds this exact
Dockerfile and starts the container specifically to catch this class of
failure ("a Node binary whose base moved out from under it", in that
workflow's own words) - so this would have been caught before merge in any
case. It is not caught on every path this image ships by, though: that job's
container-smoke step is gated on `env.TAG_NAME == ''` and skipped on the
release/`workflow_dispatch` push, so a tag build can still publish an image
whose interface half was never started. See "What it costs" below.

`frontend-builder` and the `COPY --from=` source for the node binary are back
to `node:24-trixie-slim`, the same Debian suite the runtime pins - and the
node binary is now copied from `frontend-builder` itself
(`COPY --from=frontend-builder /usr/local/bin/node ...`) rather than pulling
`node:24-trixie-slim` a second time, so the builder and the shipped binary
can't independently drift onto different resolutions of that tag the way the
alpine/glibc split did. A `RUN /usr/local/bin/node --version` right after the
copy turns a future mismatch of this kind into a build failure instead of a
runtime one. Verified by building the actual image and running both
`node --version` and `python -c "print(...)"` as uid 1001 inside it - the same
unprivileged user the image runs as - rather than trusting that a clean
`docker build` implies a working container.

## The alternative that was rejected

Move the whole runtime stage to `python:3.12-alpine` too, so the interface's
node binary and the backend's Python share musl instead of glibc.

Rejected because `backend/Dockerfile` - the per-service build `docker compose`
uses - already pins `python:3.12-slim` (Debian), not Alpine, and running
`uv sync --frozen --no-dev` against this project's own `uv.lock` inside
`python:3.12-alpine` confirms why: it fails outright, before a single package
installs, with `uv` reporting that `torch` "only has wheels for
manylinux_2_28_aarch64, manylinux_2_28_x86_64, linux_s390x, win_amd64,
win_arm64" - no musl target. Checking PyTorch's own CPU wheel index
(`download.pytorch.org/whl/cpu`) for the pinned `torch>=2.10.0,<3` confirms
this isn't specific to the resolved version: of 91 published wheels across
every supported CPython build, zero are `musllinux`. Alpine would mean
building PyTorch from source - a multi-hour C++ toolchain build, not a base
image swap - which is a materially larger and riskier change than putting the
Node stage back on the libc it already had. It would also leave the root
image's libc pointed the opposite way from the backend service image compose
builds, so the "one container, one shape" bet in
[[2026-09-05-the-release-image-is-one-container]] would have two different
Pythons behind it depending on which build path produced the image.

## What it costs

Alpine's smaller build layer for `frontend-builder` is given up:
`node:24-trixie-slim` is a heavier stage to build from than `node:24-alpine`,
though it costs build time only - the runtime stage discards the builder and
keeps just the `.next/standalone` output plus the lifted `node` binary, so the
shipped image size is unaffected.

`frontend/Dockerfile` - the per-service build compose runs for local
development - is untouched and still builds entirely on `node:24-alpine`. The
two per-service Dockerfiles were already on different libcs from each other
before this change (Alpine frontend, Debian backend); the root image resolves
that by following whichever service has the harder-to-satisfy dependency - the
backend's PyTorch wheels - rather than either service's own default base.

**Left unaddressed, not because it's fine, but because it's a bigger, separate
problem.** `python:3.12-slim-trixie` and `node:24-trixie-slim` are still
floating tags, not pinned digests, and `ghcr.io/astral-sh/uv:latest` - the
tool that runs `uv sync` against `uv.lock` - is not even pinned to a version,
only to `latest`. `uv.lock` constrains the packages that land in the image;
nothing constrains the installer that reads it. None of that is new here and
fixing it belongs in its own change, not folded into a libc revert. As noted
above, the release/`workflow_dispatch` path also never runs the container
smoke test that the pull-request path does, so this and any future
build-vs-run mismatch can still reach a published tag unexercised.
