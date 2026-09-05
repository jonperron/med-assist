---
type: decision
title: 2026-09-03 - The credential is required, and the request's origin is checked
description: API_ACCESS_TOKEN stops being optional and the process refuses to start without it, and the analysis routes refuse a request whose Origin is outside CORS_ALLOWED_ORIGINS - closing the cross-site hole the 2026-08-31 entry left open.
tags: [backend, deployment, security, authentication, csrf]
---

# 2026-09-03 - The credential is required, and the request's origin is checked

> **Superseded on 2026-09-05.** The shared credential described here was
> removed - see
> [2026-09-05 - The credential is removed and the deployment warns instead](./2026-09-05-the-credential-is-removed-and-the-deployment-warns-instead.md).
> The loopback binding and the origin check survive; everything below about
> `API_ACCESS_TOKEN` is history.


## The problem this is answering

The 2026-08-31 entry introduced `API_ACCESS_TOKEN` off by default and listed, in
its own residual risk section, the two things it had not done:

> The recommended proxy shape has a CSRF exposure basic auth cannot close -
> cached basic credentials are ambient, so another site can drive a cross-origin
> `POST /api/analyze`.

> **The default deployment is still unauthenticated.** Off-by-default means the
> protection exists only where an operator switched it on.

This entry closes both. They are one decision rather than two because each one
alone leaves a deployment that reads as protected and is not: a required
credential that a forged cross-site request carries anyway, or an origin check
on routes that answer anonymous callers.

## What was decided

**The credential is required.** `configured_access_token` raises when the
variable is unset or blank, `create_app` no longer has a branch for the
unconfigured case, and `docker-compose.yml` uses `${API_ACCESS_TOKEN:?...}` so
Compose refuses to start the stack before an image is pulled. There is no
configuration in which the analysis routes answer a caller that presented
nothing.

**The origin is checked on the server.** `RequireKnownOrigin` compares the
request's `Origin` against the origins `CORSConfiguration` already parsed, and
answers a fixed `403` when it is not one of them - before the body is read, so a
refused document is never spooled to `TMPDIR`. A request carrying no `Origin`
passes; where there is no `Origin` but there is a `Sec-Fetch-Site`, the
browser's own account of where the request came from is used instead.

**A browser reporting `Sec-Fetch-Site: same-origin` is accepted regardless of
the allow-list.** `Sec-Fetch-Site` is a forbidden header name, so no page can
set it. Without this, the one-domain proxy shape `deploy/` recommends refused
its own interface unless the operator set `CORS_ALLOWED_ORIGINS` - a variable
that shape never needed, because CORS does not apply to a same-origin call. The
review pass found this; it was a silent upgrade break with an undiagnosable
symptom.

**The credential gate runs first.** An anonymous caller gets `401` whatever
origin it claims, so the *analysis routes* do not report on the allow-list. That
is narrower than the list being private, and the first draft of this entry
overstated it. The CORS preflight is answered outside both gates and without a
credential, so an `OPTIONS` naming an origin already confirms whether that origin
is allowed. The ordering is still worth having - it stops the analysis routes
becoming a second oracle - but `CORS_ALLOWED_ORIGINS` should be treated as
public. The overstatement is corrected here rather than edited away, because it
is exactly the sort of claim that gets repeated into a threat model.

**Both gates share `app/core/gate.py`**, which owns the `root_path` stripping
rule that a security review found missing from the first gate (CWE-288); writing
it a second time is how that bug comes back. The rule mirrors Starlette's
`get_route_path` branch for branch, including the one this change originally got
wrong: stripping on `startswith` rather than on a path-segment boundary meant
that under `--root-path /a`, a request the router still sent to `/api/analyze`
was one the gates declined to judge. `test_gate_paths.py` compares the copy
against Starlette's own function so a future divergence fails a test.

## What this costs

**The shipped browser interface no longer works in a default deployment.** This
is the sharp end of the decision and it is not a side effect - it is the
mandatory credential applied to a frontend that provably cannot hold one. The
page calls the API directly, so any value it could send is in the bundle and in
every visitor's network tab. `docker compose up` now yields an interface that
loads, polls `/readyz` successfully, and fails every analysis with `401` unless
a proxy in front injects the header.

The previous entry described that proxy as the shape a hardened deployment
should adopt. It is now the shape *any* working deployment must adopt.
`deploy/README.md` and `deploy/caddy/Caddyfile.example` already documented it;
what changed is that it is no longer optional. A first run is a step longer:
generate a value, put it in `.env`, and put a proxy in front if you want the
bundled interface.

**A conditional API contract became an unconditional one.** `401` was documented
as "only a deployment that configures a credential answers this". Both analysis
endpoints now answer `401` and `403` in every deployment, and `backend/openapi.json`
and the generated `frontend/app/types/api.ts` say so. The frontend needed no
change: it already mapped both statuses onto one unretryable `unauthorized`
failure.

## Alternatives rejected

**A Next.js server-side proxy holding the token.** This is the option that would
have kept the bundled interface working with a required credential: the browser
calls the frontend's own server, which holds the secret and calls the backend.
It was rejected in the 2026-08-31 entry and is rejected again here, for the same
reason and with the cost now higher. It moves the trust boundary into the
frontend service without authenticating anyone - the proxy would forward
whatever arrived, so the deployment would be exactly as open as before while
looking locked down, and the honest "the page cannot hold a secret" statement
would become a false "the page holds it safely". A proxy that authenticates a
human belongs in front of both services, which is what `deploy/` documents.
The cost of rejecting it is the broken default interface described above.

**Keeping the credential optional and adding only the origin check.** Cheaper,
and it would have kept `docker compose up` working out of the box. Rejected
because the origin check constrains browsers only: a deployment with no
credential would still answer any `curl` on the internet, and would now do so
while carrying a control that reads, in the code and in the README, like
access control.

**Refusing requests that carry no `Origin` at all.** Considered as a strict mode
and dropped rather than shipped off by default. It would refuse the container
healthcheck, every scripted caller, and the documented proxy itself, which sends
no `Origin` on a forwarded server-side call. A mode that must be left off in the
deployment shape this repository recommends is a knob that exists to be
misconfigured.

**Trusting `Sec-Fetch-Site` alone instead of `Origin`.** Simpler, and wrong for
the split-host deployment: a frontend on `app.example` calling an API on
`api.example` is `cross-site` and entirely legitimate. `Sec-Fetch-Site` is
consulted only when there is no `Origin` to judge.

## Residual risk

- **The origin check constrains browsers and nothing else.** A client that is
  not a browser writes whatever `Origin` it likes, or omits it. Against a caller
  holding the token it is worth nothing; the token is the control there.
- **One shared secret still identifies nobody.** It cannot be revoked for one
  client, rotating it restarts the backend and the proxy together, and there is
  still no audit trail worth the name.
- **The `403`/`401` split is a small oracle for a credentialed caller.** Someone
  holding the token can map the allow-list. They can also just use the API, so
  this is not ranked as a finding.
- **The CORS preflight is the same oracle without a credential.** `OPTIONS` is
  answered by `CORSMiddleware`, outside both gates, 200 or 400 according to the
  origin. It confirms a guess at a time rather than enumerating, and it cannot
  be closed by reordering - CORS must sit outside the gates or preflight breaks.
  `CORS_ALLOWED_ORIGINS` is public in practice.
- **The origin check depends on intermediaries forwarding `Origin` untouched.**
  A proxy or WAF that strips it turns the check off rather than tightening it,
  because an absent `Origin` reads as a server-side call. Nothing detects this;
  `deploy/caddy/Caddyfile.example` warns against it next to the one `header_up`
  line it does use.
- **The check is method-scoped.** A browser always sends `Origin` on a POST, and
  both analysis routes are POST. A GET route added under `/api` would fall back
  to `Sec-Fetch-Site`, which a browser old enough not to send it omits entirely,
  and such a request would be let through.
- **A refused path is written to the log, escaped and capped.** The first draft
  logged it raw; uvicorn percent-decodes the request target, so an anonymous
  caller could forge log lines and inject terminal escapes. Found by the
  security pass (CWE-117). What remains is one bounded line per refusal.
- **Nothing rate-limits.** Unchanged, and still the strongest rejected
  alternative in the previous entry, for the same reason: behind a proxy every
  request arrives from the proxy's address.
- **The loopback binding still does nothing about a domain pointed at the
  backend.** Unchanged from 2026-08-31, and the correction recorded there stands.
- **A deployment can still put the interface on the internet with the proxy
  injecting the token and authenticating nobody.** Required credential means no
  deployment is open by omission; it does not mean any deployment is
  authenticated.
