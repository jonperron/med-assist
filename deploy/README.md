# Deploying Med-Assist somewhere other than your own machine

`POST /api/analyze` takes clinical documents from whoever asks. Read that
sentence again before you attach a domain to this stack.

Med-Assist was written to run on one machine, for the person running it. Nothing
is stored, nothing leaves the host, and the model is local - so the risk in
front of you is not a database anyone can read. It is narrower and still real:

- **anyone who can reach the API can use it.** They submit their documents and
  get their own summary back. They cannot read anyone else's, because there is
  no one else's to read - the service keeps nothing. What they can do is spend
  your CPU, for as long as they like, on a service a clinician is waiting for.
- **you are running an open document intake on the internet.** What arrives is
  your problem once it arrives, whatever you do with it afterwards.
- **there is no record of who did either.** No authentication means no identity,
  which means no audit trail worth the name.

CORS does not help with any of it. It is enforced by browsers; `curl` has never
read an `Access-Control-Allow-Origin` header in its life.

## What this repository does about it

Two things, and neither of them is authentication:

**The backend's port is published on loopback.** `docker-compose.yml` binds
`127.0.0.1:8000:8000` rather than `8000:8000`. A browser on the machine running
the stack still reaches `http://localhost:8000`, and a reverse proxy on the
Docker network still reaches the container - a platform that attaches domains,
Coolify included, routes over that network and never needed the host port. What
is gone is the path from the host's public address straight into the API.
`BACKEND_BIND_ADDRESS` undoes it, deliberately and by name.

**The analysis routes can require a shared credential.** Set `API_ACCESS_TOKEN`
and `POST /api/analyze` and `POST /api/analyze/stream` refuse anything that does
not carry `Authorization: Bearer <that value>`. Unset - the default - nothing
changes. `/healthz` and `/readyz` are never gated: the container healthcheck
calls readiness from inside the container, the interface polls it from a
browser, and what they disclose is whether a process is up.

Neither of those authenticates a person. The token is one secret shared by every
caller: it identifies nobody, cannot be revoked for one client, and is only as
private as the least careful place it is stored. It answers "did this caller
come through the front door" and nothing else.

**The shipped browser interface cannot hold the token.** The page calls the API
directly, so anything it could send is in the bundle and in every visitor's
network tab. There is no arrangement where a public single-page application
keeps a secret - not `NEXT_PUBLIC_*`, not a value fetched at runtime from a
frontend that is itself unauthenticated. Setting `API_ACCESS_TOKEN` with nothing
in front of the stack breaks the interface. That is not a bug to work around; it
is the honest answer to "can the browser authenticate itself", and it is no.

## The shape that works

Authentication belongs in a proxy in front of the application. The proxy
authenticates the human, and adds the backend's credential on the way through -
so the person's password never reaches the application, and the application
still refuses anything that did not come through the proxy.

    browser --TLS--> proxy --Bearer--> backend  (loopback / docker network)
                       \-------------> frontend

[`caddy/Caddyfile.example`](./caddy/Caddyfile.example) is that, in about thirty
lines. Copy it, replace the placeholders, and note the one design detail that
matters: **one domain, not two.** The interface and the API served from the same
origin means a browser that has authenticated to the domain sends its
credentials on the interface's own calls. Split them across `app.` and `api.`
and the browser prompts on the page and then silently fails every fetch, because
it does not volunteer credentials cross-origin.

With that file in place:

```bash
# In .env
NEXT_PUBLIC_API_URL=https://med-assist.example.org   # rebuild the frontend after
CORS_ALLOWED_ORIGINS=https://med-assist.example.org
API_ACCESS_TOKEN=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
```

Keep `.env` out of git and `chmod 600` it. The token is a secret; the two URLs
are not, but they have to move together or the browser drops every answer.

## Coolify, specifically

Coolify will happily attach a public domain to whichever service you point it
at, and its proxy reaches containers over the Docker network. Three things
follow:

- **Give the domain to the frontend, not to the backend.** A domain on port 8000
  is the exact hole this page is about. If you route the API at all, route it as
  a path on the frontend's domain, the way the Caddy example does.
- **The loopback binding does not stop you.** Coolify's proxy does not use the
  published host port, so the API stays reachable through the domain you
  configured and unreachable at `your-host:8000`. Both of those are what you
  want.
- **Coolify's proxy does not authenticate anyone by default.** Add basic auth or
  a `forward_auth` to your identity provider on the domain, then set
  `API_ACCESS_TOKEN` and have the proxy inject it. Doing only the second is
  worse than doing neither, because the interface stops working and nothing has
  been authenticated.

## What is still true afterwards

With the proxy, the token, and the loopback binding all in place:

- Anyone who gets the token, or reaches the container on the Docker network,
  reaches the API. A compromised neighbour container on the same host is inside
  the boundary.
- One shared credential is one revocation for everybody, and rotating it is a
  restart of the backend and the proxy together.
- Nothing here rate-limits. An authenticated caller, or an anonymous one on a
  deployment with no token, can hold the model busy indefinitely; the only
  ceilings are 50 MB per request and the container's CPU limit.
- Nothing here is an audit trail. The access log records paths and statuses, not
  who submitted what, and deliberately so - the alternative is a log of clinical
  activity that nobody scoped, sized or agreed to keep.
