# Deploying Med-Assist somewhere other than your own machine

`POST /api/analyze` takes clinical documents from whoever asks, and asks the
caller for nothing. Read that sentence again before you attach a domain to
this stack.

Med-Assist is a research project built to run on one machine, for the person
running it — and it authenticates nobody, because on that machine there was
nobody to authenticate. Nothing is stored, nothing leaves the host, and the
model is local, so the risk isn't a database anyone can read. It's narrower
and still real:

- **Anyone who can reach the API can use it.** They get their own summary
  back and can't read anyone else's — the service keeps nothing. What they
  *can* do is spend your CPU, for as long as they like, on a service a
  clinician is waiting for.
- **You're running an open document intake on the internet.** What arrives
  is your problem once it arrives.
- **There's no record of who did any of it.** No caller is identified, so
  there's no audit trail worth the name.

CORS doesn't help with most of this — it's enforced by browsers, and `curl`
has never read an `Access-Control-Allow-Origin` header. The origin check
below is a server-side control that reuses the same list and constrains
browsers only, which is the point: the attack it closes needs a browser.

## The short version

- **Run it locally.** That's the deployment this project is built for, and
  none of the above applies on localhost.
- **If you publish it, publish it as a demonstration.** Set
  `UNSECURED_DEPLOYMENT=true` so every screen warns against submitting real
  documents, and put an authenticating proxy in front if the audience is
  narrower than everybody. Don't point clinicians at a public instance.
- **Real access control is a contribution, not a setting.** There's no
  account system, no login, no per-user anything. Adding one is welcome and
  tracked as open work — see [Contributing access control](#contributing-access-control).

## What this repository does about it

Two things, and neither asks the caller who they are.

**The backend's port is published on loopback.** `docker-compose.yml` binds
`${BACKEND_BIND_ADDRESS:-127.0.0.1}:8050:8000` rather than `8050:8000` on
every interface. A browser on the host still reaches
`http://localhost:8050`, and a reverse proxy on the Docker network still
reaches the container — what's gone is the path from the host's public
address straight into the API, which matters because Docker's port
publishing writes its own firewall rules regardless of `ufw`.
`BACKEND_BIND_ADDRESS` undoes this, deliberately, by name.

This does **not** cover a platform that attaches a domain: that routes over
the Docker network and never touches the host port, so a public domain
pointed at the backend bypasses the loopback binding entirely — so does any
other container on the same network. Against that scenario the binding is
worth nothing; it only closes host-port scanning, a real but smaller path.

**The binding lives in `docker-compose.yml` only.** Run the published image
directly and it does not apply: `docker run -p 8000:8000` puts the API back on
every interface, and the port exposure is yours to reproduce. So is the tmpfs,
and that one is easier to miss: a multipart part above 1MB is spooled to a file
under `TMPDIR` before any route code runs, so without the mount below clinical
documents are written to the container's writable layer instead of to memory.
Reproduce both the way Compose does:

```bash
docker run \
  -p 127.0.0.1:8000:8000 -p 127.0.0.1:3000:3000 \
  --tmpfs /tmp:size=256m,mode=1777,noexec,nosuid,nodev \
  --cap-drop ALL --security-opt no-new-privileges \
  -v /path/to/weights:/app/models:ro \
  ghcr.io/jonperron/med-assist:<version>
```

That is the port exposure, the tmpfs and the weights. It is not the whole of
what `docker-compose.yml` gives the two services, and the rest does not travel
with a published tag: the memory and CPU limits, `restart: unless-stopped`, and
the log rotation that stops uvicorn's per-request access line from filling a
disk. Add `--memory`, `--cpus`, `--restart unless-stopped` and
`--log-opt max-size=10m --log-opt max-file=3` if you want them, and pair any
`--cpus` with `-e NER_INFERENCE_THREADS=<the same number>`: torch otherwise
reads the host's core count, oversubscribes the quota it was given, and the
README's own measurements are the difference that makes.

Core dumps are the one item on that list you do not have to reproduce. Compose
sets `ulimits: core: 0` because a crash in the PDF or DOCX parser - C code, on
attacker-supplied input - dumps document text and extracted entities, and a
host whose `core_pattern` pipes to `systemd-coredump` writes that dump to host
storage, outside the tmpfs and outside anything the container controls. The
image's entrypoint sets `ulimit -c 0` for both processes itself, so it holds
however the container is started.

Two ports because the published image is one container running both the API and
the interface - see
[`openwiki/decisions/2026-09-05-the-release-image-is-one-container.md`](../openwiki/decisions/2026-09-05-the-release-image-is-one-container.md).
The processes run as uid 1001, so the weights have to be readable by it: a
directory whose files are `chmod 600` and owned by your account produces a
container that starts, serves the interface, and answers `503` everywhere with
nothing in the log to say why. Either make them group- or world-readable, or add
`--user "$(id -u):$(id -g)"`.

**The published image only serves a browser on the Docker host.** The two
published ports above are bound to loopback because that is the deployment this
image is for, and the interface inside it cannot serve any other one as built:
`NEXT_PUBLIC_API_URL` is inlined into the client bundle when the image is built,
and the release build has no address to use but `http://localhost:8000`. That
address is resolved by the *browser*, not by the container, so publishing port
8000 on a public interface does not make it work from another machine - it
resolves to the reader's own computer, and every analysis fails as a network
error while `curl http://<host>:8000/readyz` from that same computer answers
normally. Co-locating the two processes makes the default correct for a browser
on the Docker host and for nothing else.

The value is frozen at build time, so the image cannot be reconfigured into a
remote deployment; that deployment builds its own:

```bash
docker build \
  --build-arg NEXT_PUBLIC_API_URL=https://med-assist.example.org \
  -t med-assist:1.0.0-example .
```

and runs it with the two variables that describe the same deployment - neither
of which has a home in a single container the way it has a compose service or
an `.env`, so both are `-e` here:

```bash
docker run \
  -p 127.0.0.1:8000:8000 -p 127.0.0.1:3000:3000 \
  --tmpfs /tmp:size=256m,mode=1777,noexec,nosuid,nodev \
  --cap-drop ALL --security-opt no-new-privileges \
  -v /path/to/weights:/app/models:ro \
  -e CORS_ALLOWED_ORIGINS=https://med-assist.example.org \
  -e UNSECURED_DEPLOYMENT=true \
  med-assist:1.0.0-example
```

`CORS_ALLOWED_ORIGINS` is read from the environment; a published image has no
`.env` in `/app` for it to fall back to, so left unset it stays at the
`http://localhost:3000` default and the origin check refuses every analysis your
domain sends. `UNSECURED_DEPLOYMENT` is the banner described below, and every
instruction on this page that says to put it "on the frontend service" or in
`.env` means this flag for this image. Both are read at start, so neither is a
rebuild - unlike `NEXT_PUBLIC_API_URL` above, which is. That rebuild is not a cost this image adds: a separately published
frontend image would be pinned to a build-time address in exactly the same way.
What is published here is the local case, correct by default, and everything
else on this page - the banner, the proxy, the origin check - applies to the
rebuild rather than to the tag.

**The analysis routes check where the request came from.** A request whose
`Origin` isn't in `CORS_ALLOWED_ORIGINS` is refused with a fixed `403` before
its body is read. This closes one specific thing: another site driving
`POST /api/analyze` from a visitor's browser to spend your compute on
documents of its choosing — CORS alone doesn't stop that, it only withholds
the answer from the attacking page.

It constrains browsers and nothing else: a scripted caller writes whatever
`Origin` it likes. A request with neither `Origin` nor `Sec-Fetch-Site` is
let through (a proxy or healthcheck sends neither); a browser reporting
`Sec-Fetch-Site: same-origin`/`none` is let through too, before the list is
consulted — which is why the one-domain shape below works without listing
your own origin. A request with no `Origin` but `Sec-Fetch-Site` naming any
other site is refused, `same-site` included.

**Your proxy must forward `Origin` and `Sec-Fetch-*` unmodified.** A
`header_up` line that strips `Origin`, or a WAF that normalises it away,
disables this check silently — nothing logs it.

Treat `CORS_ALLOWED_ORIGINS` as public: the CORS preflight is answered
outside the gate, so an `OPTIONS` naming an origin already reveals whether
it's allowed.

The gate covers only the `/api` prefix — **everything else is open**:
`/healthz`, `/readyz`, `/`, `/docs`, `/redoc`, `/openapi.json`. The health
pair is deliberate (the container healthcheck and the browser both poll it,
disclosing only whether a process is up); the schema endpoints are
incidental, and the Caddy example keeps them off the proxy by routing only
`/api`, `/healthz` and `/readyz`. Routing the backend more broadly serves its
API schema to anyone.

## The warning banner

`UNSECURED_DEPLOYMENT=true` on the frontend puts a banner on every screen:
this installation is open, anyone can reach it, documents sent through it may
be read by a third party, use fictional documents. Off by default — on the
machine it was built for, it would be noise.

It's read at request time rather than baked into the bundle, so turning it on
is one variable and a restart, not a rebuild — which is what keeps it from
being the step that gets skipped.

**It's not a control.** It changes what a clinician does, not what the
service accepts. Setting it makes a public deployment honest, not safe.

## Putting authentication in front

There's none in the application, so it goes in a proxy. The proxy
authenticates the person; the application still authenticates nobody, so the
proxy is the whole control and anything that reaches the container around it
is inside.

    browser --TLS--> proxy --> backend  (loopback / docker network)
                       \-----> frontend

[`caddy/Caddyfile.example`](./caddy/Caddyfile.example) is that, in about
thirty lines. Copy it, replace the placeholders, and keep the one design
detail that matters: **one domain, not two.** Serving the interface and the
API from the same origin means a browser authenticated to the domain sends
its credentials on the interface's own calls. Split them across `app.` and
`api.` and the browser prompts on the page, then silently fails every fetch —
it won't volunteer credentials cross-origin.

```bash
# In .env
NEXT_PUBLIC_API_URL=https://med-assist.example.org   # rebuild the frontend after
CORS_ALLOWED_ORIGINS=https://med-assist.example.org
UNSECURED_DEPLOYMENT=true                            # unless the proxy is the whole audience
```

These two URLs aren't secrets, but they have to move together or the browser
drops every answer.

### The cost of basic auth in this shape

Basic auth is ambient: once the browser has cached credentials for the
domain, it attaches them to *any* request there, including one started by
another site. So a page a clinician visits elsewhere can drive a
cross-origin `POST /api/analyze` at your deployment, authenticated — Caddy
accepts the browser-supplied password. The attacker can't read the answer
(CORS blocks that) and nothing is stored, so this is compute abuse and
unwanted documents being pushed through your deployment, not a
confidentiality breach.

**The backend's origin check closes it.** The forged request carries the
attacking page's `Origin`, not in `CORS_ALLOWED_ORIGINS`, so the backend
answers `403` and reads no body — after Caddy has already authenticated the
visitor, regardless. That's why the check lives on the server rather than
relying on the browser's CORS enforcement, which only withholds the answer.

It's a backstop, not a licence to skip the rest — it relies on the browser
setting `Origin` honestly, so it does nothing against a non-browser caller.
Replacing `basic_auth` with `forward_auth` to an identity provider issuing
`SameSite=Lax` session cookies removes the ambient-credential problem at its
source, and is still the better shape.

## Coolify, specifically

Coolify attaches a public domain to whichever service you point it at, over
the Docker network. Five things follow:

- **Give the domain to the frontend, not the backend.** A domain on port
  8050 is the exact hole this page is about; route the API as a path on the
  frontend's domain, the way the Caddy example does.
- **Set `UNSECURED_DEPLOYMENT=true`.** A Coolify deployment is by definition
  reachable by someone other than you.
- **The loopback binding won't save you here.** Coolify's proxy doesn't use
  the published host port, so the API stays reachable at whatever domain you
  configured (though unreachable at `your-host:8050`).
- **The backend's host port is 8050, not 8000, so it doesn't collide with
  itself on redeploy.** Coolify creates a redeploy's replacement container
  before it removes the old one, so a fixed host port that the previous
  deployment already holds fails with "port is already allocated" until
  that old container is gone. `docker-compose.yml` moved the backend's
  published port off the common `8000` for exactly this reason. It's still
  a fixed number, though - if `8050` is ever also taken on your host, the
  fix is to edit `docker-compose.yml` and pick a different one; it has no
  effect on the domain Coolify routes either way, since that goes over the
  internal Docker network regardless of the published port.
- **Coolify's proxy authenticates nobody by default**, and neither does
  anything else. Add basic auth or `forward_auth` to your identity provider
  on the domain if the instance shouldn't be open to the whole internet.

## Upgrading from a version that required a credential

Between 2026-08-31 and 2026-09-05 this service could require a shared
credential in `API_ACCESS_TOKEN`. If you configured one:

- **`API_ACCESS_TOKEN` is ignored.** Nothing reads it. The backend logs a
  startup warning if it's still set — that warning is the only signal you
  get. Remove it from every `.env`, secret store and deployment platform.
- **A proxy rule injecting `Authorization: Bearer` is now decorative.** If
  that rule was your access control, nothing stands there now — replace it
  with `basic_auth` or `forward_auth` on the proxy itself before treating the
  deployment as protected.
- **Compose no longer refuses to start without it.** The
  `${API_ACCESS_TOKEN:?}` guard is gone, so a stale `.env` starts silently.

Set `UNSECURED_DEPLOYMENT=true` at the same time, unless your proxy's own
authentication is the whole audience.

## Contributing access control

Stated plainly: **Med-Assist has no accounts, no login, no sessions, no
per-caller rate limiting and no audit trail.** A shared bearer credential
existed briefly and was removed — it identified nobody, couldn't be revoked
per client, and the browser interface couldn't present it, so any deployment
that set it turned its own interface off.

Contributions that would help, roughly in order:

- Sign-up and sign-in, with sessions the interface can actually use.
- Per-caller rate limiting on the analysis routes — every existing bound is
  global, not per caller: `NER_MAX_CONCURRENT_INFERENCES` (documents inside
  the model at once, per backend process — so more worker processes multiply
  it), uvicorn's `--limit-concurrency 8`, `MAX_BATCH_FILES`, the 50 MB
  ceiling, and the container's CPU limit.
- An audit trail somebody has scoped — deciding what a log of clinical
  activity may contain and how long it's kept is a decision entry before
  it's code.

Open an issue before building one of these — [`AGENTS.md`](../AGENTS.md)
section 9 says the service persists nothing, and an account system is the
first thing that would change that.

## What is still true afterwards

Even with a proxy, the banner and the loopback binding all in place:

- Anyone who reaches the container on the Docker network reaches the API
  with no credential of any kind — a compromised neighbour container on the
  same host is inside the boundary.
- Nothing rate-limits *per caller* — every ceiling is global (50 MB per
  request, `MAX_BATCH_FILES` per batch, `NER_MAX_CONCURRENT_INFERENCES` per
  process, the container's CPU limit), so one caller can hold the model busy
  indefinitely.
- Nothing here is an audit trail. An access log records paths and statuses,
  not who submitted what — deliberately, since the alternative is a log of
  clinical activity nobody scoped, sized or agreed to keep.
