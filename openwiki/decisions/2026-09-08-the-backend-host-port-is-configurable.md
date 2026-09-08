---
type: decision
title: 2026-09-08 - The backend's host-side port is configurable
description: docker-compose.yml gained BACKEND_HOST_PORT so a deployment can move the backend's published port off 8000 without editing the compose file, after a Coolify redeploy failed with "port is already allocated".
tags: [deployment, docker, coolify]
---

# 2026-09-08 - The backend's host-side port is configurable

## The problem this is answering

A Coolify redeploy of the backend failed:

```
Error response from daemon: failed to set up container networking: driver
failed programming external connectivity on endpoint backend-...:
Bind for 0.0.0.0:8000 failed: port is already allocated
```

`docker-compose.yml` published the backend's host-side port as a literal
`8000` - `"${BACKEND_BIND_ADDRESS:-127.0.0.1}:8000:8000"` - with no env
knob for the number itself, only for the bind address. Coolify creates a
redeploy's replacement container before it removes the previous one, so a
fixed host port collides with that previous container until it is torn
down. There was no way to point the new container at a free port without
editing the compose file.

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
the API on every interface harmless, and this entry originally read as if
it did. Reverted to the documented default `127.0.0.1` as part of the same
fix; it needed no code change since it was already environment-driven.

## What was decided

`docker-compose.yml`'s backend `ports:` entry became:

```yaml
ports:
  - "${BACKEND_BIND_ADDRESS:-127.0.0.1}:${BACKEND_HOST_PORT:-8000}:8000"
```

The container's internal port is unchanged - the app still listens on
`8000`, `EXPOSE 8000` in `backend/Dockerfile` is untouched, and so is the
healthcheck, which requests `http://localhost:8000/readyz` from inside the
container. Only the host-side publish port gained a name. The default stays
`8000`, so an existing local `docker compose up` and the default
`NEXT_PUBLIC_API_URL=http://localhost:8000` in `.env.example` are unchanged.
This specific Coolify deployment sets `BACKEND_HOST_PORT` to a free high
port, in its own environment variables (not in this repository), to move
off the port the previous container held.

`.env.example` documents the new variable next to `BACKEND_BIND_ADDRESS`,
and `deploy/README.md`'s Coolify section now names this failure mode and
the fix directly, since it is a predictable consequence of Coolify's
create-before-remove redeploy sequence combined with a fixed host port -
not a one-off.

## The alternative that was rejected

**Stop publishing the backend's port to the host at all under Coolify**,
using `expose: 8000` instead of `ports:` for that deployment shape. This is
the structurally cleaner fix: `deploy/README.md` already says Coolify's
proxy never uses the published host port, so nothing Coolify does depends
on it being published, and removing the publish removes this entire class
of collision rather than moving it to a different fixed number.

Rejected for now, on the operator's call rather than a technical one: doing
this cleanly means either a second, Coolify-specific compose file (this
repository has one `docker-compose.yml` today, used both for local
`docker compose up` and as the file Coolify runs) or making the `ports:`
entry conditional, which Compose has no native syntax for short of an
override file or profiles - more moving parts than a single new env var for
a problem that, today, is "one port number collided with one other
container." If a Coolify deployment needs the backend reachable directly at
`host:port` for some reason, publishing still supports that; not publishing
would foreclose it.

## What it costs

- **The collision class is not eliminated, only moved.** `BACKEND_HOST_PORT`
  still names one fixed host port. If the new one is ever also taken - by
  another application on the same host, or by the same create-before-remove
  sequence landing on it too on a later redeploy - the fix is to pick yet
  another free port by hand, not something that stops happening on its own.
- **Two knobs now have to be kept in mind together.** `BACKEND_BIND_ADDRESS`
  and `BACKEND_HOST_PORT` both describe the same `ports:` mapping; changing
  one without checking the other is an easy way to end up publishing on a
  wider interface than intended while chasing a port conflict.
- **Nothing enforces that `NEXT_PUBLIC_API_URL` (or a reverse proxy target)
  is updated to match.** A deployment that changes `BACKEND_HOST_PORT` for
  direct host access and forgets the corresponding URL gets a silent
  connection failure from the browser, not a startup error - the same shape
  of quiet failure `.env.example` already warns about for `MODEL_DIR`.
