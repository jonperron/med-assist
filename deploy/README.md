# Deploying Med-Assist somewhere other than your own machine

`POST /api/analyze` takes clinical documents from whoever asks, and asks the
caller for nothing. Read that sentence again before you attach a domain to this
stack.

Med-Assist is a research project. Its product is a French clinical NER model;
the API and the interface exist to exercise it and to show what it does. It was
written to run on one machine, for the person running it - and it authenticates
nobody, because on that machine there was nobody to authenticate.

Nothing is stored, nothing leaves the host, and the model is local, so the risk
in front of you is not a database anyone can read. It is narrower and still
real:

- **anyone who can reach the API can use it.** They submit their documents and
  get their own summary back. They cannot read anyone else's, because there is
  no one else's to read - the service keeps nothing. What they can do is spend
  your CPU, for as long as they like, on a service a clinician is waiting for.
- **you are running an open document intake on the internet.** What arrives is
  your problem once it arrives, whatever you do with it afterwards.
- **there is no record of who did any of it.** No caller is identified, so there
  is no audit trail worth the name.

CORS does not help with most of it. It is enforced by browsers; `curl` has never
read an `Access-Control-Allow-Origin` header in its life. The origin check
described below is a server-side control that reuses the same list, and it
constrains browsers only - which is the point, since the attack it closes is one
that needs a browser.

## The short version

**Run it locally.** That is the deployment this project is built for, and on
localhost none of the above applies.

**If you publish it, publish it as a demonstration.** Set
`UNSECURED_DEPLOYMENT=true` so every screen carries a banner telling the person
using it not to submit real documents, and put an authenticating proxy in front
if the audience is narrower than everybody. Do not point clinicians at a public
instance and let them work from it.

**If you need real access control, it is a contribution, not a setting.** There
is no account system here, no login, no per-user anything. Adding one - sign-up,
sessions, an identity provider, rate limits per caller - is welcome and is
tracked as open work rather than shipped and disabled. See
[Contributing access control](#contributing-access-control).

## What this repository does about it

Two things, and neither asks the caller who they are.

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
prompts most of this page - a domain attached to port 8000 - the binding is
worth nothing. It closes host-port scanning. That is a real path and a smaller
one.

**The binding lives in `docker-compose.yml` only.** Run the published image
directly and it does not apply: `docker run -p 8000:8000` puts the API back on
every interface. Publish it the same way Compose does:

```bash
docker run -p 127.0.0.1:8000:8000 <image>
```

**The analysis routes check where the request came from.** A request whose
`Origin` is not in `CORS_ALLOWED_ORIGINS` is refused with a fixed `403` before
its body is read. What this closes is one specific thing: another site driving
`POST /api/analyze` from a visitor's browser and spending your compute on
documents of its choosing. CORS alone did not stop that - it withholds the
answer from the attacking page, but the request was still analysed.

It constrains browsers and nothing else. A scripted caller writes whatever
`Origin` it likes, and a request carrying none is let through, because a proxy
in front sends none and neither does the healthcheck. A browser reporting
`Sec-Fetch-Site: same-origin` is let through too, which is why the one-domain
shape below works without you listing your own origin; a page cannot set that
header.

**Your proxy must forward `Origin` and the `Sec-Fetch-*` headers unmodified.**
The whole check rests on them arriving as the browser wrote them. A `header_up`
line that strips `Origin`, or a WAF that normalises it away, does not tighten
this control - it disables it, silently, with nothing in the log or at startup
to say so.

Treat `CORS_ALLOWED_ORIGINS` as public: the CORS preflight is answered outside
the gate, so an `OPTIONS` naming an origin already reveals whether that origin
is allowed.

The gate covers the `/api` prefix, so **everything outside it is open**:
`/healthz`, `/readyz`, `/`, and FastAPI's `/docs`, `/redoc` and `/openapi.json`.
The health pair is deliberate - the container healthcheck calls readiness from
inside the container, the interface polls it from a browser, and what they
disclose is whether a process is up. The schema endpoints are incidental, and
the Caddy example keeps them off the proxy by routing only `/api`, `/healthz`
and `/readyz` to this service. A deployment that routes the backend more broadly
serves its own API schema to anyone.

## The warning banner

`UNSECURED_DEPLOYMENT=true` on the frontend service puts a banner on every
screen: this installation is open, anyone can reach it, documents sent through
it may be read by a third party, use fictional documents. It is off by default,
because on the machine it was built for it would be noise.

It is read at request time rather than baked into the bundle, so turning it on
is one variable and a restart - no rebuild, which is what stops it from being
the step that gets skipped.

**It is not a control.** It changes what a clinician does, not what the service
accepts. Setting it does not make a public deployment safe; it makes a public
deployment honest.

## Putting authentication in front

There is none in the application, so it goes in a proxy. The proxy
authenticates the person; the application behind it still authenticates nobody,
which means the proxy is the whole control and anything that reaches the
container around it is inside.

    browser --TLS--> proxy --> backend  (loopback / docker network)
                       \-----> frontend

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
UNSECURED_DEPLOYMENT=true                            # unless the proxy is the whole audience
```

The two URLs are not secrets, but they have to move together or the browser
drops every answer.

### The cost of basic auth in this shape

Basic auth is ambient: once the browser has cached the credentials for the
domain, it attaches them to *any* request to it, including one started by
another site. So a page a clinician visits elsewhere can drive a cross-origin
`POST /api/analyze` at your deployment, and it will be authenticated - the
browser supplies the password and Caddy accepts it. The attacker cannot read the
answer, because CORS blocks that and the origin list is explicit, and nothing is
stored, so this is compute abuse and documents of their choosing being pushed
through your deployment - not a confidentiality breach.

**The backend's origin check closes it.** The forged request carries the
attacking page's `Origin`, which is not in `CORS_ALLOWED_ORIGINS`, so the backend
answers `403` and reads no body - after Caddy has authenticated the visitor, and
regardless of it. That is the reason the check exists on the server rather than
being left to the browser's CORS enforcement, which only withholds the answer.

It is a backstop, not a licence to skip the rest. It relies on the browser
setting `Origin` honestly, so it does nothing against a caller that is not a
browser. Replacing the `basic_auth` block with `forward_auth` to an identity
provider that issues `SameSite=Lax` session cookies removes the
ambient-credential problem at its source, and is still the better shape.

## Coolify, specifically

Coolify will happily attach a public domain to whichever service you point it
at, and its proxy reaches containers over the Docker network. Four things
follow:

- **Give the domain to the frontend, not to the backend.** A domain on port 8000
  is the exact hole this page is about. If you route the API at all, route it as
  a path on the frontend's domain, the way the Caddy example does.
- **Set `UNSECURED_DEPLOYMENT=true`.** A Coolify deployment is by definition
  reachable by someone other than you.
- **The loopback binding will not save you here.** Coolify's proxy does not use
  the published host port, so the API stays reachable at whatever domain you
  configured and unreachable at `your-host:8000`. The second half is the win;
  the first half means the binding does nothing at all about a domain you point
  at the backend.
- **Coolify's proxy does not authenticate anyone by default.** Nothing else
  does either. If the instance should not be open to the whole internet, add
  basic auth or a `forward_auth` to your identity provider on the domain.

## Contributing access control

This is the gap, stated plainly so nobody has to discover it: **Med-Assist has
no accounts, no login, no sessions, no per-caller rate limiting and no audit
trail.** A shared bearer credential existed briefly and was removed - it
identified nobody, could not be revoked for one client, and the browser
interface could not present it, so every deployment that set it turned its own
interface off.

Contributions that would change this, roughly in the order they would help:

- Sign-up and sign-in, with sessions the interface can actually use.
- Per-caller rate limiting on the analysis routes. Nothing bounds concurrent
  work today except the container's CPU limit and 50 MB per request.
- An audit trail somebody has scoped. The deliberate absence of one is why
  there is no record of who submitted what; adding it means deciding what a log
  of clinical activity may contain and how long it is kept, which is a decision
  entry before it is code.

Open an issue before building one of these - the storage boundary in
[`AGENTS.md`](../AGENTS.md) section 9 says the service persists nothing, and an
account system is the first thing that would change that.

## What is still true afterwards

Even with a proxy, the banner and the loopback binding all in place:

- Anyone who reaches the container on the Docker network reaches the API, with
  no credential of any kind. A compromised neighbour container on the same host
  is inside the boundary.
- Nothing here rate-limits. A caller can hold the model busy indefinitely; the
  only ceilings are 50 MB per request and the container's CPU limit.
- Nothing here is an audit trail. An access log records paths and statuses, not
  who submitted what, and deliberately so - the alternative is a log of clinical
  activity that nobody scoped, sized or agreed to keep.
