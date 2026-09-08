---
type: decision
title: 2026-09-08 - The backend's published port moved to 8050
description: docker-compose.yml now publishes the backend on host port 8050 instead of 8000, after a Coolify redeploy failed with "port is already allocated"; the number is fixed, not an environment variable.
tags: [deployment, docker, coolify]
---

# 2026-09-08 - The backend's published port moved to 8050

## The problem this is answering

A Coolify redeploy of the backend failed:

```
Error response from daemon: failed to set up container networking: driver
failed programming external connectivity on endpoint backend-...:
Bind for 0.0.0.0:8000 failed: port is already allocated
```

`docker-compose.yml` published the backend's host-side port as `8000` -
`"${BACKEND_BIND_ADDRESS:-127.0.0.1}:8000:8000"`. Coolify creates a
redeploy's replacement container before it removes the previous one, so a
fixed host port collides with that previous container until it is torn
down - and `8000` is a common default other services on the same host are
also likely to already hold.

Separately, this deployment's `BACKEND_BIND_ADDRESS` was set to `0.0.0.0`
rather than the documented default of `127.0.0.1` - not intentional. This
was a real exposure, not a harmless setting: `POST /api/analyze` takes
clinical documents from whoever asks and authenticates nobody, and
`0.0.0.0` published it on every address the host answers on, reachable by
anyone who could reach the host on that port at all - the exact scenario
[2026-08-31 - The API can require a credential, and its port is
loopback](./2026-08-31-the-api-can-require-a-credential-and-its-port-is-loopback.md)
introduced the loopback default to close. That the platform's own proxy
routes over the Docker network and ignores the published port explains why
`0.0.0.0` was unnecessary for Coolify to work - it does not make publishing
the API on every interface harmless. Reverting to `127.0.0.1` is an
operator-side environment change on the Coolify deployment itself, not
something this repository's default can force from here: the default was
already `127.0.0.1` before and after this change (`docker-compose.yml`
line 7), and the live deployment's own environment variable is what needs
correcting, on that platform.

## What was decided

`docker-compose.yml`'s backend `ports:` entry became:

```yaml
ports:
  - "${BACKEND_BIND_ADDRESS:-127.0.0.1}:8050:8000"
```

A plain, fixed number, not an environment variable - `8050` replaces the
literal `8000` that used to sit there. The container's internal port is
unchanged: the app still listens on `8000`, `EXPOSE 8000` in
`backend/Dockerfile` is untouched, and so is the healthcheck, which
requests `http://localhost:8000/readyz` from inside the container. The
bind-address knob (`BACKEND_BIND_ADDRESS`) is untouched too - only the
port number moved.

Because this is the port a browser resolves `NEXT_PUBLIC_API_URL` against
for a local `docker compose up`, every place that assumed `8000` as the
backend's host-published port moved with it: `.env.example`'s
`NEXT_PUBLIC_API_URL` default, `docker-compose.yml`'s own default for the
same build arg, the root `README.md`'s quick-start pointer, and
`deploy/README.md`'s description of the loopback binding and its Coolify
section. The single-container release image
(`ghcr.io/jonperron/med-assist`, built from the root `Dockerfile`) is a
separate artifact with its own port choice left to whoever runs it and is
unaffected.

## The alternative that was rejected

**Making the host port configurable via a new environment variable**
(`BACKEND_HOST_PORT`, defaulting to `8000`), so each deployment could pick
its own number without editing `docker-compose.yml`. This was the first
shape this fix took, and it works: default behavior is preserved, and a
colliding deployment sets one variable instead of touching source. It was
reversed in favor of a fixed `8050` on direct instruction - a plain number
is simpler for a problem that, so far, is one port colliding with one other
container on one host, and it avoids adding a second knob
(`BACKEND_BIND_ADDRESS` plus `BACKEND_HOST_PORT`) that has to be kept in
mind together for a single `ports:` mapping.

**Stopping the backend's host publish entirely** under Coolify, using
`expose: 8000` instead of `ports:` for that deployment shape - still the
structurally cleanest fix, since `deploy/README.md` already says Coolify's
proxy never uses the published host port. Rejected for the same reason as
before: it needs either a second, Coolify-specific compose file or a
conditional `ports:` entry Compose has no native syntax for, and it would
foreclose direct `host:port` access for anyone relying on it.

## What it costs

- **The collision is moved, not eliminated.** `8050` is one fixed number in
  the file. If it is ever also taken - by another application on the host,
  or by the same create-before-remove sequence landing on it too on some
  future redeploy - the fix is to edit `docker-compose.yml` and pick
  another number by hand, and that edit ships through the normal review and
  release process rather than being a deployment-time environment change.
- **Every place that named `8000` as the backend's host port had to be
  found and moved together**, rather than changing in one place. A future
  change to this number carries the same cost; nothing enforces the set of
  files that need to agree.
- **A local `docker compose up` following an older README, bookmark, or
  browser autofill for `localhost:8000` now gets nothing there.** The
  interface still starts and works at the documented `localhost:8050`; this
  only affects whoever had memorized or scripted against the old default.
