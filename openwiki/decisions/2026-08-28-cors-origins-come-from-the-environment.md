---
type: decision
title: 2026-08-28 - The allowed CORS origins come from the environment
description: CORS_ALLOWED_ORIGINS replaces the hardcoded frontend origin, defaults to localhost, validates each entry at startup and refuses a wildcard.
tags: [backend, deployment, cors, security]
---

# 2026-08-28 - The allowed CORS origins come from the environment

## What was decided

`create_app` pinned CORS to a literal:

```python
allow_origins=["http://localhost:3000"],  # Frontend origin
```

The frontend, meanwhile, has always found the backend through
`NEXT_PUBLIC_API_URL`. Two ends of one connection, configured by two different
mechanisms: any deployment that was not exactly `localhost:3000` needed a source
edit on one side and an environment variable on the other. AGENTS.md section 9
asks for CORS that is strict *and* environment-aligned; it was strict only.

`CORS_ALLOWED_ORIGINS` now supplies the list, read by a `CORSConfiguration`
settings class next to `NERModelConfiguration` rather than by an `os.getenv` in
`main`. Four properties of it are deliberate.

**It is a comma-separated string, not JSON.** pydantic-settings decodes a
variable typed as a collection by running `json.loads` on it first, so
`CORS_ALLOWED_ORIGINS=http://localhost:3000` would have failed before any
validator ran and the only spelling that worked would have been a JSON array -
a trap that surfaces as a startup crash on the most obvious possible value. The
field carries `NoDecode` to turn that off and splits on commas itself.

**Unset, empty, or all-blank falls back to the local frontend origin.** Never to
`["*"]`. An empty allow-list would be the strictest reading of an empty
variable, but it refuses the local frontend and looks like a broken service
rather than a configuration mistake.

**`*` is refused at startup, not merely avoided.** This app sets
`allow_credentials=True`, and that pairing is both a spec violation and, on a
server that echoes the origin back, a real hole. Since a browser rejects a
credentialed response allowed to `*` anyway, the wildcard would not widen access
- it would remove it, silently, in every browser. Refusing it early turns that
into an error at the moment someone writes it.

**Each entry is validated as an origin, and the two forgiving cases are
rewritten rather than accepted as written.** Starlette compares the browser's
`Origin` header against these strings literally, so an entry that is not exactly
what the browser sends allows nothing and reports nothing - the silent failure
this change exists to remove. A path, a query, a fragment, embedded credentials,
a wildcard in the host, a space, a port that is not a number or is out of range,
an unbalanced IPv6 bracket, and an international domain outside its punycode
form all stop the process at startup. Two spellings have exactly one sensible
reading and are rewritten into the browser's own: a single trailing slash is
dropped, and so is a port the scheme already implies, since a browser sends
`https://host:443` as `https://host`. The host arrives lowercased for the same
reason.

The refusal names the entry by its position and never quotes it. A deployment's
origins are configuration, not patient data, but they can name an internal host
and the message ends up in a container log; the position is enough to fix it.
That is also why `urlsplit` is called inside the guarded block rather than
before it: it raises `ValueError` on some inputs itself, with the offending text
in the message, and a `ValueError` escaping the validator is precisely what
pydantic turns into a `ValidationError` that echoes the whole variable.

## The narrow exception to "do not touch deployment config"

AGENTS.md section 9 says never to modify production deployment configs as part
of routine feature work. `docker-compose.yml` gains one line:

```yaml
- CORS_ALLOWED_ORIGINS=${CORS_ALLOWED_ORIGINS:-http://localhost:3000}
```

That is called out rather than slipped in. This compose file is the local
development stack; the passthrough carries a default identical to the previous
hardcoded literal, so `docker compose up` behaves exactly as before, and without
it the setting would exist in code and be unreachable from the way the stack is
actually run. No other service, port, limit or credential was touched.

## The alternative that was rejected

**Leaving the literal.** It works for the only deployment that exists today and
costs nothing to keep. Rejected because "edit a source file and rebuild the
image" is not a deployment step anyone should have, and because the mismatch
with `NEXT_PUBLIC_API_URL` is the kind that is discovered in a browser console
rather than in a config review.

**Allowing `*`, at least in development.** Tempting - it removes the whole class
of misconfiguration during local work. Rejected because it does not actually
work here (credentials), because a development-only escape hatch is exactly the
setting that reaches a deployment, and because the value would then be one
`APP_ENV` mistake away from an API that answers any page on the internet.

## What it costs

- A misconfigured origin now fails in the browser at runtime rather than being
  impossible to get wrong at build time. The failure mode is a request that
  reaches the API and whose answer the browser discards; it looks like a network
  error, not like a refusal. The README says so in the one place someone
  changing the host will look, and the two variables are documented as a pair.
- One more thing a deployment must set, and it must be kept in step with
  `NEXT_PUBLIC_API_URL` - which is baked into the frontend bundle at build time,
  so the two are not even changed at the same moment.
- The startup validation is strict enough to reject values that a browser would
  in fact have tolerated in some other server's implementation - a host with a
  wildcard label, an IDN written in Unicode. That is the intended trade: a loud
  refusal at startup over a silent mismatch later. Under Compose the refusal
  arrives as a container that keeps restarting rather than as an unhealthy one,
  because the process exits before the port opens and the healthcheck never
  runs; the message is in the log on every attempt.
- None of this is access control. CORS is a browser-side mechanism, and the API
  remains unauthenticated: any client that is not a browser reaches it whatever
  this variable says. Making the setting configurable makes a non-localhost
  deployment easy, which makes that pre-existing gap easier to walk into, so the
  README now says it in the section an operator reads when moving off localhost.
  Fixing it is a separate decision - authentication, or a proxy in front of the
  port - not something this entry claims to have done.
