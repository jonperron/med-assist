---
type: decision
title: 2026-09-05 - The credential is removed and the deployment warns instead
description: API_ACCESS_TOKEN and its gate are deleted because they turned the shipped interface off in every deployment; the origin check stays, and a public deployment now tells the clinician on screen that it is open.
tags: [backend, frontend, deployment, security, authentication]
---

# 2026-09-05 - The credential is removed and the deployment warns instead

## The problem this is answering

The 2026-09-03 entry made `API_ACCESS_TOKEN` required. It also wrote down, as a
cost it accepted, that the browser interface could not present the credential
and that a deployment therefore needed an authenticating proxy in front to have
a working interface at all.

That cost turned out to be the whole feature. In practice the stack now behaved
like this: `docker compose up` starts, the page loads, `/readyz` answers, and
every analysis returns `401` - because the frontend sends no `Authorization`
header from anywhere, and cannot hold a secret that would let it. The credential
did not protect a deployment; it broke one, and the only way to get a working
interface back was to run a proxy that added the header, which no local
developer was going to do.

The gate was also protecting less than its length suggested. It is one secret
shared by every caller: it identifies nobody, cannot be revoked for one client,
and turns into a nuisance the moment more than one person has it.

## What was decided

**The credential is removed.** `app/core/access.py`, `RequireAccessToken`,
`AccessTokenConfiguration`, the `API_ACCESS_TOKEN` variable, the Compose `:?`
guard, the bearer scheme in the OpenAPI document and the `401` on both analysis
routes are all deleted. `POST /api/analyze` and `POST /api/analyze/stream`
answer any caller that reaches them. The frontend needed no change to work
again: it never sent the header.

**The origin check stays.** `RequireKnownOrigin` is untouched and is now the
only gate. It costs nothing, breaks nothing, and closes the one attack it was
built for - another site driving an upload through a visitor's browser. It is
not authentication and is documented as not being authentication.

**The loopback binding stays.** `127.0.0.1:8000:8000` still decides who can
reach the API on a host, and is now the main thing that does.

**A public deployment says so on screen.** `UNSECURED_DEPLOYMENT=true` puts a
banner on every screen of the interface: this installation is open, anyone can
reach it, documents sent through it may be read by a third party, use fictional
documents. It is read at request time rather than inlined into the bundle, so
turning it on is a variable and a restart - a `NEXT_PUBLIC_` flag would have
required a rebuild, which is the step that gets skipped.

**The privacy badge is hidden when that banner is on.** "Reste sur cette
machine" is read by a clinician as "reste sur la mienne". On a published address
that reading is wrong, and it would have sat one row under a banner saying the
opposite.

## The alternatives that were rejected

**A Next.js server-side proxy holding the credential.** The frontend runs a Node
server, so route handlers under `frontend/app/api/` could have injected the
header and kept the secret off the browser - `docker compose up` would work out
of the box with the gate intact. Rejected because it authenticates nobody:
anyone who can reach the frontend still reaches the API through it, so it buys
the appearance of a credential and none of the substance, in exchange for a
proxy layer to maintain and a streaming passthrough to get right.

**Wiring the documented Caddy proxy into `docker-compose.yml`.** This is the
honest version of keeping the credential, and it was rejected on cost: local
development would go through a proxy on one domain, needing a password hash and
both URL variables moved together, to protect a machine whose only user is the
person typing on it.

**Making the credential optional again.** Rejected because that is the state the
2026-09-03 entry existed to end: a deployment open by omission, looking from the
outside exactly like a configured one. If there is no credential, the honest
thing is to have no credential and say so, not to have one that is usually off.

## What this costs

**The API is unauthenticated, everywhere, with no way to turn that off in the
application.** Anyone who can reach the port can submit documents and spend the
host's CPU indefinitely - nothing rate-limits, and the only ceilings are 50 MB
per request and the container's CPU limit. On a public deployment this is real
and is not mitigated by anything in this repository. The controls that remain
are the loopback binding, the origin check, and whatever proxy an operator puts
in front.

**The banner is not a control.** It changes what a clinician does, not what the
service accepts. A deployment that sets it is honest, not safe.

**`force-dynamic` on the root layout.** Reading the flag at request time means
the interface is no longer statically prerendered. The application is a single
interactive screen, so the cost is one server render per page load, but it is a
real change to how the frontend is served.

**This is a breaking change for anyone who had configured the credential.**
`API_ACCESS_TOKEN` is now ignored. A proxy that injects `Authorization: Bearer`
keeps working - the header is simply not read any more - so the failure mode is
a deployment that believes it is protected and is not. `deploy/README.md` says
so, and `.env.example` no longer mentions the variable.

## The direction instead

Access control is stated as an open contribution rather than a solved problem:
accounts, sessions, per-caller rate limiting and a scoped audit trail are listed
in `deploy/README.md` and in the root README's contributing section. An account
system would be the first thing to make this service persist anything, so it
needs its own decision entry before it needs code.
