---
type: decision
title: 2026-09-09 - The frontend's published port moved to 3050
description: docker-compose.yml now publishes the frontend on host port 3050 instead of 3000, the same treatment already applied to the backend's port; CORS_ALLOWED_ORIGINS's default moved with it.
tags: [deployment, docker, coolify]
---

# 2026-09-09 - The frontend's published port moved to 3050

## The problem this is answering

Requested directly, in the same shape as [2026-09-08 - The backend's
published port moved to
8050](./2026-09-08-the-backends-published-port-moved-to-8050.md): apply the
same fix to the frontend's port that the backend already got.

That entry is explicit about what moving a fixed number does and does not
fix, and the same limits apply here without repeating. Coolify creates a
redeploy's replacement container before it removes the previous one, so any
fixed host port a deployment publishes collides with its own previous
container until that one is torn down - moving the number does not change
that, for the frontend any more than it did for the backend. What moving off
`3000` does avoid is a *different* service on the host also wanting that
port, the same way `8050` avoided some other service that wanted `8000`;
`3000` is at least as commonly claimed elsewhere, since it's `next dev`'s own
default. This entry does not have a captured daemon error to quote for the
frontend the way the 2026-09-08 entry does for the backend - the request was
to apply the identical treatment, not a freshly observed failure - so what
this records is the fix applied on that basis, not a confirmed diagnosis of
which collision the frontend hit.

## What was decided

`docker-compose.yml`'s frontend `ports:` entry became:

```yaml
ports:
  - "3050:3000" # Exposes Next.js standalone server on host port 3050
```

A plain, fixed number, the same shape as the backend's `8050` - not an
environment variable. The container's internal port is unchanged: the
Next.js standalone server still listens on `3000`, `frontend/Dockerfile`'s
`EXPOSE 3000` and `ENV PORT=3000` are untouched, and so is the compose
healthcheck's compound Python check inside the backend container (it does
not probe the frontend's port at all). Nothing that binds an address, the
way `BACKEND_BIND_ADDRESS` does for the backend - the frontend service never
had that knob, and this change doesn't add one - only the host-side port
number moved.

The browser origin the frontend is served from moved with its port, so
`CORS_ALLOWED_ORIGINS`'s default in `docker-compose.yml` moved from
`http://localhost:3000` to `http://localhost:3050` to match - left
unmoved, a plain `docker compose up` would serve the interface from
`localhost:3050` while the backend kept refusing every request from that
origin with a 403, since its allow-list default would still name `3000`.
Every other place that named `3000` as *this stack's* host-published
frontend port moved with it: `.env.example`'s `CORS_ALLOWED_ORIGINS`
default, the root `README.md`'s quick-start pointer, and
`deploy/README.md`'s Coolify section. `README.md`'s `CORS_ALLOWED_ORIGINS`
table entry needed more than a substitution: it had been describing one
default (the code-level fallback), and now had to describe two - Compose's
own passthrough default (`3050`, above) and the code-level fallback that
only applies outside Compose (`3000`, unchanged, next paragraph) - so it
now names both rather than picking one.

`backend/app/core/config.py`'s `DEFAULT_ALLOWED_ORIGINS` constant - the
code-level fallback used only when `CORS_ALLOWED_ORIGINS` is unset
entirely - deliberately kept the literal `http://localhost:3000`. It backs
a plain local run of the backend (`uv run`, no compose) alongside a
frontend started with `next dev`, which defaults to port `3000` on its own
and is untouched by anything in `docker-compose.yml`. `docker-compose.yml`
always passes `CORS_ALLOWED_ORIGINS` explicitly, so that stack never reads
this fallback; its docstring now says so instead of claiming to describe
"a local `docker compose up`."

Two places name `3000` as the frontend's port and are unrelated to this
stack, so they were left alone: the root `Dockerfile` and
`.github/workflows/docker_build.yml`'s smoke test both describe the
single-container release image - see [2026-09-05 - The release image is
one container, not two](./2026-09-05-the-release-image-is-one-container.md)
- which `docker-compose.yml` does not build and whose own port choice this
change does not touch. `deploy/README.md`'s `docker run` examples for that
same image keep `-p 127.0.0.1:3000:3000` for the same reason.

## The alternative that was rejected

**Leaving the frontend's port alone.** The two services publish independent
fixed ports, so fixing the backend's does nothing for the frontend's - a
deployment could still hit "port is already allocated" on its next
redeploy, on a different port, with no code change of its own to explain
why. Rejected on direct instruction: apply the same treatment already given
to the backend.

**A configurable `FRONTEND_HOST_PORT` environment variable**, mirroring the
`BACKEND_HOST_PORT` shape [2026-09-08](./2026-09-08-the-backends-published-port-moved-to-8050.md)
tried first and reversed. Not attempted here: that alternative was already
rejected once, on direct instruction, for the identical problem shape on
the backend, and nothing about the frontend's version of it changes that
reasoning.

## What it costs

- **The collision is moved, not eliminated**, exactly as it was for the
  backend: `3050` is one fixed number in the file, and a future collision
  on it is a `docker-compose.yml` edit, not a deployment-time variable.
- **A third port to keep in step across documentation**, alongside `8050`
  and the release image's own `3000`. The set of files that has to agree on
  the frontend's compose-published port is not enforced by anything; a
  future change to this number carries the same cost this one did.
- **A local `docker compose up` following an older README, bookmark, or
  browser autofill for `localhost:3000` now gets nothing there.** The
  interface still starts and works at the documented `localhost:3050`; this
  only affects whoever had memorized or scripted against the old default.
- **An existing `.env` copied before this change carries the old value as
  an explicit assignment, not an absence.** `.env.example` ships
  `CORS_ALLOWED_ORIGINS` set rather than commented out, so Compose's
  `${CORS_ALLOWED_ORIGINS:-...}` default never applies to an `.env` that
  already has the line - it stays at `http://localhost:3000` until someone
  edits it. After an upgrade that pulls this change but keeps an old `.env`,
  the interface serves from `3050` while the backend's allow-list still
  names `3000`, and every analysis is refused with a `403`. The fix is the
  same one `.env.example` line: change the value to `http://localhost:3050`.
- **The frontend keeps publishing on every interface, unchanged by this
  move.** `docker-compose.yml`'s frontend `ports:` entry has no bind-address
  parameter the way the backend's `${BACKEND_BIND_ADDRESS:-127.0.0.1}` does,
  and this change doesn't add one - `3050` is reachable from any address the
  host answers on, exactly as `3000` was. Moving the number is not a
  hardening step; it says nothing about who can reach the interface.
