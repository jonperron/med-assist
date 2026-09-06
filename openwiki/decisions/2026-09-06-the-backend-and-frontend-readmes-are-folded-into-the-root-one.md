---
type: decision
title: 2026-09-06 - The backend and frontend READMEs are folded into the root one
description: backend/README.md and frontend/README.md are removed; their user-facing content moves into the root README, and backend/pyproject.toml drops its `readme` field rather than pointing at a file outside the package directory.
tags: [docs, packaging, docker, ci]
---

# 2026-09-06 - The backend and frontend READMEs are folded into the root one

## What was decided

`backend/README.md` and `frontend/README.md` are deleted. The root `README.md`
is now the one file a human reads to run the project and know its boundaries:
it gained a `## Configuration` table covering the backend's own environment
variables (`NER_MODEL_NAME`, `APP_ENV`, `MAX_BATCH_FILES`,
`NER_INFERENCE_THREADS`, `NER_MAX_CONCURRENT_INFERENCES`) alongside the
frontend/deployment ones it already listed, plus the two upgrade notices
(`API_ACCESS_TOKEN`, `STORAGE_ENCRYPTION_KEY`) and the model-mounting section
that used to be split across files.

Removing `backend/README.md` is not only a documentation change:
`backend/pyproject.toml` declared `readme = "README.md"`, which is a build
input, not decoration - hatchling refuses to compute the package's metadata
without that file present (`backend/Dockerfile`'s `COPY uv.lock pyproject.toml
README.md ./` and the root `Dockerfile`'s equivalent line both existed because
of this). The `readme` field is now removed from `backend/pyproject.toml`
entirely, and both Dockerfiles' `COPY` lines drop `README.md`/`backend/README.md`
accordingly. `.github/workflows/docker_build.yml`'s path filter and the root
`.dockerignore`'s comment are updated to match - neither excluded or needed to
exclude the root `README.md`, since no rule matched it, but the comment
explaining `backend/README.md`'s presence no longer applied to anything.

Verified locally: `uv build --sdist --wheel` succeeds from `backend/` with no
`README.md` anywhere in the project, and both `docker build -f
backend/Dockerfile ./backend` and `docker build -f Dockerfile .` complete and
produce a container that answers `/healthz` 200, serves the interface at 200,
and reports `/readyz` 503 with no weights mounted - the same assertions
`docker_build.yml`'s pull-request job makes.

Backend and frontend developer-internals content that lived only in the
removed files - API and SSE behavior, entity types, health-check semantics,
CSP specifics, the footer/version and banner-parsing mechanics, API-type
generation - is not carried over anywhere. It was not duplicated in
`AGENTS.md` or elsewhere in `openwiki/`, so it is simply gone; anything on
that list can be reconstructed from the code and tests, or from git history
before this entry's date, or given its own `openwiki/` page if it turns out
to be needed again.

## The alternative that was rejected

Repointing `backend/pyproject.toml` at the root README with a relative path
(`readme = "../README.md"`) instead of dropping the field. This would have
kept a `readme` value on the package while still having a single file for a
human to read.

It does not work: `hatchling`'s metadata validation raises `Readme path must
be within the project directory` for any path that resolves outside the
directory holding `pyproject.toml`, regardless of how the path is spelled.
Confirmed by running `uv build` against the repointed value before touching
anything else. The only way to keep a `readme` field pointing at the root
file would be moving `backend/pyproject.toml` itself to the repository root,
which changes the project layout `AGENTS.md`'s quick commands and every `cd
backend && uv run ...` instruction assume, for a documentation consolidation
that does not need it.

A minimal `backend/README.md` stub (package name plus a line pointing at the
root file) was also considered, as the option that changes no packaging or
CI files at all. It was rejected in favor of dropping the `readme` field
because the package is never published anywhere that reads a `readme` field
(no PyPI index, no wheel repository) - the field was serving the Docker
builds and nothing else, so removing it in both places it was read is less
to keep in sync than a stub file plus its two `COPY` lines.

## What it costs

**No `long_description` on the wheel's own metadata.** `PKG-INFO` for
`med-assist-backend` now carries no readme text. This matters only if the
package is ever published to an index that renders it, which it is not.

**Two Dockerfiles' `COPY` lines and one CI path filter had to move together
with the `pyproject.toml` field.** They are already duplicated by
`openwiki/decisions/2026-09-05-the-release-image-is-one-container.md`'s own
"a third build description to keep in step" cost; this entry adds one more
line to the list of things that drift together rather than reduces it.

**The root README is now longer and covers two audiences it used to keep
separate** - the docker-compose quickstart and the direct-`uv run` backend
configuration. The `## Configuration` table mixes `NEXT_PUBLIC_API_URL` (read
only by the frontend build) with `NER_MODEL_NAME` (read only by a bare
`uv run uvicorn`, since Compose hardcodes it to `/app/models/` and exposes
`MODEL_DIR` instead) without marking which deployment shape each row belongs
to.
