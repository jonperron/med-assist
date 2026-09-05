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
- **there is no record of who did either.** One credential shared by every
  caller is not an identity, which means no audit trail worth the name.

CORS does not help with most of it. It is enforced by browsers; `curl` has never
read an `Access-Control-Allow-Origin` header in its life. The origin check
described below is a server-side control that reuses the same list, and it
constrains browsers only - which is the point, since the attack it closes is one
that needs a browser.

## What this repository does about it

Three things. Only the first asks the caller for anything:

**The backend's port is published on loopback.** `docker-compose.yml` binds
`127.0.0.1:8000:8000` rather than `8000:8000`. A browser on the machine running
the stack still reaches `http://localhost:8000`, and a reverse proxy on the
Docker network still reaches the container. What is gone is the path from the
host's public address straight into the API - which matters more than it sounds,
because Docker's port publishing writes its own firewall rules and `8000:8000`
was reachable from outside regardless of what `ufw` had been told.
`BACKEND_BIND_ADDRESS` undoes it, deliberately and by name.

Be clear about what this does *not* cover. A platform that attaches a domain
routes over the Docker network and never used the host port, so **a public
domain pointed at the backend service bypasses the loopback binding entirely**.
So does any other container on the same network. Against the scenario that
prompted this work - a domain attached to port 8000 - the binding is worth
nothing, and the credential is the only control. The binding closes host-port
scanning. That is a real path and a smaller one.

**The binding lives in `docker-compose.yml` only.** Run the published image
directly and it does not apply: `docker run -p 8000:8000` puts the API back on
every interface. The credential does travel with the image - the process will
not start without it, so an image run this way cannot be open by omission the
way it once could - but the port exposure is yours to reproduce. Publish it the
same way Compose does:

```bash
docker run -p 127.0.0.1:8000:8000 -e API_ACCESS_TOKEN=... <image>
```

**The analysis routes require a shared credential.** `POST /api/analyze` and
`POST /api/analyze/stream` refuse anything that does not carry
`Authorization: Bearer <API_ACCESS_TOKEN>`. There is no unconfigured mode: the
backend refuses to start without the variable and `docker compose up` refuses to
start the stack, so a deployment cannot end up open by omission. It was
off-by-default when this gate was introduced, and that default was the entire
security posture of every deployment whose operator did not read this file.

**The analysis routes check where the request came from.** A request whose
`Origin` is not in `CORS_ALLOWED_ORIGINS` is refused with a fixed `403` before
its body is read. This is what closes the cross-site hole that basic auth in
front cannot: cached credentials are ambient, so without it another site could
drive `POST /api/analyze` from an authenticated visitor's browser, and your
proxy would accept the forged request and add the backend's credential on the
way through. It constrains browsers and nothing else - a scripted caller writes
whatever `Origin` it likes, and a request carrying none is let through because
your proxy sends none. A browser reporting `Sec-Fetch-Site: same-origin` is let
through too, which is why the one-domain shape below works without you listing
your own origin; a page cannot set that header.

The credential gate runs first, so an anonymous caller sees `401` whatever origin
it claims and the analysis routes tell it nothing about your allow-list. Do not
read that as the list being secret: the CORS preflight is answered outside both
gates and without a credential, so an `OPTIONS` naming an origin already reveals
whether that origin is allowed. Treat `CORS_ALLOWED_ORIGINS` as public.

**Your proxy must forward `Origin` and the `Sec-Fetch-*` headers unmodified.**
The whole check rests on them arriving as the browser wrote them. A `header_up`
line that strips `Origin`, or a WAF that normalises it away, does not tighten
this control - it disables it, silently, with nothing in the log or at startup
to say so.

The gate covers the `/api` prefix, so **everything outside it stays open**, not
only the health endpoints: `/healthz`, `/readyz`, `/`, and FastAPI's `/docs`,
`/redoc` and `/openapi.json`. The health pair is deliberate - the container
healthcheck calls readiness from inside the container, the interface polls it
from a browser that cannot hold a secret, and what they disclose is whether a
process is up. The schema endpoints are incidental, and the Caddy example keeps
them off the proxy by routing only `/api`, `/healthz` and `/readyz` to this
service. A deployment that routes the backend more broadly serves its own API
schema to anyone.

None of those authenticates a person. The token is one secret shared by every
caller: it identifies nobody, cannot be revoked for one client, and is only as
private as the least careful place it is stored. It answers "did this caller
come through the front door" and nothing else.

**The shipped browser interface cannot hold the token.** The page calls the API
directly, so anything it could send is in the bundle and in every visitor's
network tab. There is no arrangement where a public single-page application
keeps a secret - not `NEXT_PUBLIC_*`, not a value fetched at runtime from a
frontend that is itself unauthenticated. Because the credential is now required
rather than optional, **running this stack with nothing in front of it breaks the
interface in every deployment**: the page loads, `/readyz` answers, and every
analysis returns `401`. That is not a bug to work around; it is the honest answer
to "can the browser authenticate itself", and it is no. The proxy below is not
an optional hardening step any more - it is how you get a working interface.

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
are not, but they have to move together or the browser drops every answer. The
token also has to be in the *proxy's* environment, not only the backend's -
`{env.API_ACCESS_TOKEN}` is read by Caddy. If it is missing there, every request
reaches the backend as a bare `Bearer` with no value and is refused, which
looks like a wrong token rather than an absent one.

### The cost of basic auth in this shape

Basic auth is ambient: once the browser has cached the credentials for the
domain, it attaches them to *any* request to it, including one started by
another site. So a page a clinician visits elsewhere can drive a cross-origin
`POST /api/analyze` at your deployment, and it will be authenticated - the
browser supplies the password, Caddy accepts it, and Caddy adds the backend
token. The attacker cannot read the answer, because CORS blocks that and the
origin list is explicit, and nothing is stored, so this is compute abuse and
documents of their choosing being pushed through your deployment - not a
confidentiality breach. It is a hole the "one domain, basic auth" shape creates
and that basic auth cannot close.

**The backend's origin check closes it.** The forged request carries the
attacking page's `Origin`, which is not in `CORS_ALLOWED_ORIGINS`, so the backend
answers `403` and reads no body - after Caddy has authenticated the visitor and
added the token, and regardless of both. That is the reason the check exists on
the server rather than being left to the browser's CORS enforcement, which only
withholds the answer.

It is a backstop, not a licence to skip the rest. It relies on the browser
setting `Origin` honestly, so it does nothing against a caller that is not a
browser and has the token. Replacing the `basic_auth` block with `forward_auth`
to an identity provider that issues `SameSite=Lax` session cookies removes the
ambient-credential problem at its source, and is still the better shape.

## Coolify, specifically

Coolify will happily attach a public domain to whichever service you point it
at, and its proxy reaches containers over the Docker network. Three things
follow:

- **Give the domain to the frontend, not to the backend.** A domain on port 8000
  is the exact hole this page is about. If you route the API at all, route it as
  a path on the frontend's domain, the way the Caddy example does.
- **The loopback binding will not save you here.** Coolify's proxy does not use
  the published host port, so the API stays reachable at whatever domain you
  configured and unreachable at `your-host:8000`. The second half is the win;
  the first half means the binding does nothing at all about a domain you point
  at the backend. Only the first bullet, and the token, cover that.
- **Coolify's proxy does not authenticate anyone by default.** `API_ACCESS_TOKEN`
  is required now, so the proxy has to inject it whatever else you do - without
  that, the interface loads and every analysis returns `401`. Add basic auth or
  a `forward_auth` to your identity provider on the domain at the same time:
  injecting the token alone gets you a working interface that has authenticated
  nobody, which is the state this page exists to talk you out of.

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
