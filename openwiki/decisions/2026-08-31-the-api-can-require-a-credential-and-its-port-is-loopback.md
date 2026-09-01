---
type: decision
title: 2026-08-31 - The API can require a credential, and its port is loopback
description: API_ACCESS_TOKEN gates the analysis routes when a deployment sets it, docker-compose binds the backend to 127.0.0.1, and real authentication is documented as belonging in a proxy in front.
tags: [backend, deployment, security, authentication, coolify]
---

# 2026-08-31 - The API can require a credential, and its port is loopback

## The problem this is answering

`POST /api/analyze` and `POST /api/analyze/stream` accept clinical documents
from whoever asks, and until now nothing on any route asked a caller for
anything. That was defensible while `docker-compose.yml` was a local stack: the
API was on `localhost`, and the person who could reach it was the person who
started it.

It stopped being defensible when the service began being deployed with Coolify.
`docker-compose.yml` published `8000:8000` - every interface the host answers on
- and Coolify will attach a public domain to whatever service it is pointed at.
That is an unauthenticated endpoint that ingests patient documents, on the open
internet.

`CORS_ALLOWED_ORIGINS` was never a defence and the 2026-08-28 entry that
introduced it said so, closing with "fixing it is a separate decision -
authentication, or a proxy in front of the port - not something this entry
claims to have done." This is that entry.

## What the risk actually is

Worth stating precisely, because it is not the one the phrase "unauthenticated
API" usually names. The service stores nothing and returns only a summary of
what the caller submitted, so an anonymous caller cannot read anybody else's
documents - there are none to read. What they can do is:

- spend the host's CPU, indefinitely, on a service a clinician is waiting for;
- make the operator the person running an open document intake on the internet;
- do both with no record of who they were, because no authentication means no
  identity and therefore no audit trail.

So this is an availability and operator-liability problem before it is a
confidentiality one. Saying otherwise would overstate what was fixed.

## What was decided

Two mechanisms, and the honest claim about them is that one closes a path and
the other narrows one. Neither authenticates a person.

**The backend's published port is bound to loopback.** `docker-compose.yml` now
reads `${BACKEND_BIND_ADDRESS:-127.0.0.1}:8000:8000`. A browser on the machine
running the stack still reaches `http://localhost:8000`, so a local
`docker compose up` is unchanged; a reverse proxy on the Docker network still
reaches the container, because a platform that attaches domains routes over that
network and never used the host port. What is gone is the path from the host's
public address straight into the API. It costs nothing that a localhost
deployment notices.

**How much that binding is worth, corrected.** The security pass of AGENTS.md
section 8 pushed back on an earlier draft of this entry, which called the
binding "the highest-value change in the set". Against the threat this entry
opens with - a platform attaching a public domain to the backend service - it is
worth nothing: the proxy routes over the Docker network and never used the host
port, and `deploy/README.md` says so one bullet after telling the operator not
to do it. So does any other container on that network. What the binding actually
closes is direct host-port access, which is a real path worth closing - Docker's
port publishing writes its own firewall rules, so `8000:8000` was reachable from
outside whatever `ufw` had been told - and a smaller one than the scenario that
prompted the work. **The credential is the only control for a domain pointed at
the backend, and it is off by default.** The correction is recorded rather than
edited away because the original ranking is exactly the misreading that would
lead an operator to ship the compose change and set no token.

**The analysis routes can require a shared credential.** `API_ACCESS_TOKEN`,
unset by default. Set, `POST /api/analyze` and `POST /api/analyze/stream` refuse
anything without `Authorization: Bearer <value>`; unset, nothing changes at all.
Four details of it are deliberate:

- **It is ASGI middleware, not a route dependency.** FastAPI parses a multipart
  body before it solves any dependency, so a dependency would have refused the
  caller only after the server had spooled up to the 50 MB ceiling into
  `TMPDIR`. The middleware decides from the request headers and reads nothing.
  It is mounted inside `CORSMiddleware` so the 401 carries an allow-origin
  header and a browser can read it, and outside `LimitRequestSize` so an
  anonymous oversized body is refused before it is measured.
- **A missing, malformed and wrong credential are one answer.** A fixed
  `401 {"detail": {"message": "Unauthorized"}}` with `WWW-Authenticate: Bearer`,
  compared with `hmac.compare_digest`. Which of the three it was is not
  information the caller has earned.
- **The value never reaches a log, a message or an exception.** Not truncated,
  not hashed, not its length. The startup refusal for a too-short value names
  the variable and not the value, for the same reason `CORSOriginError` is a
  `RuntimeError`: a `ValueError` out of a pydantic validator becomes a
  `ValidationError` that quotes its input, and here the input is the secret.
- **Everything outside `/api` is ungated, not only the health endpoints.**
  The gate is a prefix, so `/healthz`, `/readyz`, `/`, FastAPI's `/docs`,
  `/redoc` and `/openapi.json`, and the development-only `/mock_summary` all
  answer a configured deployment without a credential. An earlier draft of this
  entry, and of the code comments, enumerated only the first three; the review
  pass caught it. A test now pins the exact set so a router mounted outside
  `/api` fails rather than shipping ungated in silence. The health pair is the
  deliberate part: the container healthcheck
  calls readiness from inside the container, where it does not need a
  credential; the interface polls it from a browser, which cannot hold one. What
  the two disclose is whether a process is up and whether weights are in memory
  - no configuration, no document. Gating them would cost the interface its "the
  service is starting" notice and buy nothing.

**Authentication of a person is documented as belonging in front.**
`deploy/README.md` and `deploy/caddy/Caddyfile.example` describe and implement
the shape that works: one domain, the proxy authenticating the human, the proxy
adding the backend's credential on the way through, so the person's password
never reaches the application and the application still refuses anything that
did not come through the proxy.

## The contract change

Both analysis endpoints can now answer `401`, and both document it in
`backend/openapi.json` and the generated `frontend/app/types/api.ts`. A
deployment that sets nothing sees no change - no new status, no changed body, no
new required header - so this is a contract change conditional on
configuration, which is why the schema description says when it applies rather
than asserting every deployment refuses anonymous callers.

## What the review passes changed

The four passes of AGENTS.md section 8 ran before this was proposed for merge.
Two of their findings changed the code rather than the wording, and both were
failures of the control itself:

**A mounted application was not gated at all** (security pass, CWE-288). The
gate compared `scope["path"]`, but Starlette's router matches on the path with
`root_path` stripped. Served behind a prefix - `--root-path /med-assist`, which
is FastAPI's own documented recipe for running behind a proxy - a request for
`/med-assist/api/analyze` did not match the gate's `/api` prefix, passed through
without a word, and was analysed by the route registered at `/api/analyze`. The
control was silently absent on exactly the deployment that had added a proxy,
which is the deployment this feature exists for. `routed_path` now strips the
prefix the same way the router does, and three tests cover it.

**WebSocket scopes were exempt** (security pass, CWE-306, latent). The early
return covered every scope that was not `http`, which is necessary for
`lifespan` and wrong for `websocket`. No route here is one today, so nothing was
reachable - the problem was that the first `/api` socket anyone added would have
shipped ungated with no test failing. The gate now refuses a covered WebSocket
handshake with close code 1008.

The rest were documentation and test-isolation findings: the ungated set above,
a `read_timeout` in the Caddy example that Caddy rejects at config-adapt time so
a copied file would not have started, `backend/README.md` still saying the
configuration holds no secret, the root README's relocation recipe now being
wrong under the loopback binding, a copied `Caddyfile` not being gitignored
while holding the operator's bcrypt hash, and a `conftest.py` so a developer's
own `.env` cannot decide what the suite tests.

The interface gained a `unauthorized` failure branch as a result: a 401 was
falling through to `transport`, which rendered the backend's fixed English word
under a French headline and offered a retry that can never succeed.

## The alternatives that were rejected

**A credential the shipped frontend sends.** This is the obvious shape and it
does not work. The page calls the API directly from the browser, so anything the
frontend could send is in the bundle and in every visitor's network tab. A
`NEXT_PUBLIC_*` value is inlined at build time; a value fetched at runtime is
handed out by a frontend that is itself unauthenticated. There is no arrangement
where a public single-page application holds a secret, and shipping one would
have been security theatre with a configuration variable attached. Rejected, and
the consequence is written down rather than hidden: **setting `API_ACCESS_TOKEN`
turns the shipped interface off** unless a proxy in front injects the header.

**A Next.js server-side proxy in the frontend, holding the token.** This would
have kept the interface working with the token set: the browser calls the
frontend's own origin, a route handler adds the credential server-side. Rejected
for now because it moves the whole analysis path - including a 50 MB streaming
multipart upload and a Server-Sent Events response - through a Node process that
does not touch it today, for no gain in *authentication*: the frontend is
unauthenticated, so the proxy would forward anonymous callers with a valid
credential attached. It would make the token compatible with the interface
without making the interface authenticated. If a future entry adds real
sessions to the frontend, this becomes the right shape.

**Rate limiting instead of, or alongside, a credential.** It matches the actual
risk - compute abuse - and it works for a browser with no credential at all, so
it was the strongest candidate. Rejected because keying it is not solvable here:
behind Coolify's proxy every request arrives from the proxy's address, so a
limiter on the socket peer would throttle every clinician in the deployment as
one client, and the fix - trusting `X-Forwarded-For` - is a header any caller can
write unless the trusted proxy addresses are pinned, which is configuration this
project has no way to validate. A limiter that is either useless or
trivially bypassed is worse than none, because it reads in the README as a
control. The cost of rejecting it is recorded below.

**Gating `/readyz` too.** Rejected: the two callers that need it are a
healthcheck inside the container and a browser, and it discloses nothing.

**Doing nothing in the application and only documenting the proxy.** Defensible
- the proxy is where authentication belongs, and the loopback binding plus a
document would have been a smaller change. Rejected because the token is what
defends against the proxy being bypassed rather than absent: on a shared host,
a neighbouring container on the same Docker network reaches
`med_assist_backend:8000` whatever the host port is bound to, and the loopback
binding does nothing about that.

## What it costs

- **A non-localhost deployment that browsed straight to `host:8000` breaks.**
  That is the change working as intended, but it is a breaking change for anyone
  who had published the backend and pointed `NEXT_PUBLIC_API_URL` at it.
  `BACKEND_BIND_ADDRESS=0.0.0.0` restores the old behaviour, deliberately and by
  name; the README and `.env.example` both say what that puts back on the
  public interface.
- **The credential and the interface are mutually exclusive without a proxy.**
  An operator who sets `API_ACCESS_TOKEN` expecting the frontend to keep working
  gets a frontend that cannot analyse anything. Three files say so - the
  variable's own comment, the README, `deploy/README.md` - which is the most
  that documentation can do about a genuinely awkward truth.
- **One secret shared by everyone is one revocation for everyone.** It
  identifies nobody, cannot be revoked per client, and rotating it restarts the
  backend and the proxy together.
- **It fails open on a typo.** A mistyped variable name leaves the routes
  answering anyone while looking locked down. Mitigated only by a startup log
  line stating which of the two modes the process is in - not by anything that
  would stop it.
- **Nothing rate-limits.** An authenticated caller, or an anonymous one on a
  deployment that sets no token, can hold the model busy indefinitely. The only
  ceilings remain 50 MB per request and the container's CPU limit. This is the
  cost of the rejection above and it is the largest thing still open.
- **Nothing here is an audit trail.** The proxy's access log records paths and
  statuses, not who submitted what - deliberately, since the alternative is a
  log of clinical activity that nobody scoped, sized or agreed to retain, and
  this service keeps nothing by design.
- **A public domain pointed at the backend service bypasses the loopback
  binding entirely**, and so does any container on the same Docker network.
  This is the correction above, repeated here because it belongs in the list of
  what is still open rather than only in the description of the control.
- **The binding lives in `docker-compose.yml` and does not travel with the
  image.** This repository publishes a backend image, and `docker run -p
  8000:8000` on it reproduces the original exposure with no credential set.
  `deploy/README.md` shows the `docker run` form that does not, which is all
  documentation can do about an artifact run outside this repository's control.
- **The recommended proxy shape has a CSRF exposure that basic auth cannot
  close.** Once a browser has cached basic credentials for the domain, another
  site can drive a cross-origin `POST /api/analyze` and the browser will attach
  them - the proxy authenticates it and adds the backend credential. The
  attacker cannot read the answer (CORS blocks it, the origin list is explicit)
  and nothing is stored, so this is compute abuse and documents of their
  choosing pushed through the deployment, not a confidentiality breach. A
  `forward_auth` to an identity provider issuing `SameSite=Lax` cookies removes
  it; the example says so.
- **The proxy's access log records client IPs and request headers**, not just
  paths. That makes it a record of who used a clinical tool and when. Caddy
  redacts `Authorization` only because `log_credentials` defaults to off. The
  example says both; the retention decision is the operator's and is not made
  here.
- **The default deployment is still unauthenticated.** Off-by-default was chosen
  so an upgrade breaks nothing, which means the protection only exists where an
  operator switched it on. A deployment that upgrades and reads no release note
  gains the loopback binding and nothing else.
