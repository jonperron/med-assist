---
type: decision
title: 2026-08-28 - The local-first claim is enforced by a Content-Security-Policy
description: The frontend serves a CSP whose connect-src names only the page origin and the configured API origin, so the browser refuses the egress the interface promises not to make.
tags: [frontend, security, egress]
---

# 2026-08-28 - The local-first claim is enforced by a Content-Security-Policy

## What was decided

`frontend/next.config.ts` serves a Content-Security-Policy and three companion
headers on every response, built by `frontend/app/lib/contentSecurityPolicy.ts`.

The directive that matters is `connect-src 'self' <API origin>`. The origin is
derived from `NEXT_PUBLIC_API_URL` at build time, and only its origin - scheme,
host, port - is used; a path in the value would otherwise become a path
restriction on every request the page makes. A value that is not an absolute
`http(s)` URL fails the build, because a policy assembled from a broken value
would ship a page that cannot reach its own backend and would say so only in a
browser console, in front of a clinician, mid-analysis. An unset value falls
back to `http://localhost:8000`, matching `.env.example` and the fallback
`app/page.tsx` already uses for the fetch itself.

The host is validated beyond what the URL parser does. `*` and `;` are not
forbidden domain code points, so `http://*.example.org` and `http://host;sandbox`
both parse and both reach `URL.origin` verbatim - the first authorising every
subdomain, the second ending `connect-src` early and appending a directive the
policy never intended (`sandbox` and `upgrade-insecure-requests` are valueless,
so both are complete on their own). A hostname must therefore be dot-separated
letter-digit-hyphen labels or a bracketed IPv6 literal, or the build stops. An
environment variable is an injection surface for whatever can set it, and this
one is interpolated into a security header.

The rest of the policy is `default-src 'self'`, `base-uri 'self'`,
`form-action 'self'`, `frame-ancestors 'none'`, `object-src 'none'`,
`img-src 'self' data:` and `font-src 'self'`. Alongside it:
`X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, and
`X-Frame-Options: DENY` for agents that do not implement `frame-ancestors`.
No `Strict-Transport-Security`: the stack is served over plain HTTP, and an
HSTS header would pin a clinician's browser to HTTPS for `localhost` long after
this application is gone.

`next dev` gets a variant that adds `'unsafe-eval'` to `script-src`, for Fast
Refresh, and the hot-reload socket to `connect-src`. That socket is named as
`ws://localhost:*`, `ws://127.0.0.1:*` and `ws://[::1]:*` rather than as a bare
`ws:` scheme source: a bare scheme matches every host on that scheme, which
would have reopened, in the development policy, exactly the egress the whole
change exists to refuse. The port is wildcarded because the dev server picks it.

Which variant is served is keyed on the phase Next passes to the config, not on
`NODE_ENV`. `next build` only defaults `NODE_ENV` and preserves an inherited
value, so a build environment that exported `NODE_ENV=development` for an
unrelated reason would otherwise have baked `'unsafe-eval'` into a shipped image
with nothing in the output to signal it. The `development` flag also defaults to
false in the module, so a caller that forgets it gets the strict policy: the
relaxations have to be asked for and cannot be inherited.

The policy construction lives in its own module rather than inline in the config
so it can be unit-tested; the config imports it.

Two directives had to be loosened, each against an observed production build
rather than pre-emptively:

- `script-src 'self' 'unsafe-inline'`. The prerendered HTML contains two inline
  `<script>` elements carrying the React flight payload
  (`(self.__next_f=self.__next_f||[]).push(...)`, ~5 KB on the index route).
  With `script-src 'self'` alone the browser blocks them and the page never
  hydrates. `'unsafe-eval'` is not granted.
- `style-src 'self' 'unsafe-inline'`. The not-found and global-error routes
  ship a `<style>` element and inline `style` attributes, and the reading
  progress bar sets its width through an inline `style` at runtime, so the
  attribute form is needed in normal operation and not only on an error screen.

`font-src 'self'` needed no exception: both faces are self-hosted by
`next/font`, and the built HTML references no external origin at all.

## The alternative that was rejected

Two were.

Leaving the claim conventional - the privacy badge, the README section, and
nothing in the browser behind them. Rejected because the claim is the product's
main promise to a clinician, and until today the only thing stopping a
dependency, a compromised build or an injected span from opening a socket to a
third party was that none of them had tried. A promise a user cannot verify and
the runtime does not enforce is a documentation artefact.

A `<meta http-equiv="Content-Security-Policy">` tag in `app/layout.tsx`.
Rejected because a meta-tag policy cannot express `frame-ancestors` at all, so
the clickjacking boundary would be lost; it applies only from the point in the
document where the parser reaches it, leaving everything above it ungoverned;
and it covers the HTML document only, not the 404, the error routes or static
assets, which the header block does cover.

A third option was considered and not taken: a per-request nonce, which is how
Next intends `script-src 'self'` to be reached without `'unsafe-inline'`. It
requires middleware on every route, which opts the whole application out of
static generation. Paying for dynamic rendering on a single-page interface was
judged not worth it, because the nonce would not change the outcome much: it
would stop injected script from running, but the channels that remain open to
script here - a top-level navigation, `window.open`, a DNS prefetch, WebRTC -
are not ones any CSP directive closes, and the channels a nonce would add
nothing to are already refused by `connect-src`, `form-action`, `img-src` and
`object-src`. What the current policy buys is that the exfiltration surface is
reduced to a user-visible one. If middleware is added for another reason, the
nonce should come with it.

## What it costs

- `connect-src` couples the header block to deployment configuration. The
  frontend already baked `NEXT_PUBLIC_API_URL` into its bundle at build time,
  so an operator who moves the API always had to rebuild; what changes is the
  failure mode when they do not. Before, a stale bundle called the old address
  and failed at the network. Now the policy names the old origin too, so a
  deployment whose API origin changed without a frontend rebuild gets a page
  that cannot reach its backend and reports it only as a blocked request in the
  browser console. The build-time refusal of a malformed value catches
  nonsense, not a value that is well-formed and wrong.
- That coupling now has three ends, not two, and this entry is the only place
  they are written down together: the fetch URL baked into the bundle, the CSP
  origin baked into the header block, and the backend's CORS allowlist, which is
  still a hardcoded literal in `backend/app/main.py` rather than configuration.
  An operator who moves a service and follows the "rebuild the frontend" advice
  above still gets a broken deployment, because the third one cannot be moved
  without a code change. Making it configurable is a separate change and needs
  its own entry.
- The policy is deliberately more forgiving of the API URL than the fetch is.
  `apiOrigin` reduces `http://host/api` to `http://host`, so the header is
  correct while `app/page.tsx` concatenates the raw value and requests
  `http://host/api/api/analyze/stream`. The request is allowed by the policy and
  then 404s, surfacing as a transport failure. The concatenation predates this
  change and was left alone, but the build gate added here is now the natural
  place to catch it; the fix is for the fetch and the policy to derive from the
  same parse.
- `'unsafe-inline'` in `script-src` means the policy is not a defence against
  script injection. It is a defence against *silent* egress. An attacker who
  gets script into the page can still run it; what they cannot do is `fetch` a
  third party, open a websocket, send a beacon, load a remote image as a beacon,
  post a form off-origin, embed a plugin, or reframe the app.
  What they can still do, and what no deployed CSP directive prevents, is
  navigate: `location.href` or `window.open` to a third-party URL carrying the
  rendered summary in its query string. `navigate-to` was dropped from CSP3 and
  ships in no browser, and `Referrer-Policy: no-referrer` addresses passive
  leakage, not this. A DNS prefetch and a WebRTC peer connection are two further
  channels `connect-src` does not cover. So the list above is not a closed set,
  and this change should not be described as XSS mitigation. The claim it
  supports is that nothing leaves without the clinician's tab visibly going
  somewhere else.
- The boundary the policy actually enforces is "only the configured API origin",
  not "only this machine". Nothing constrains `NEXT_PUBLIC_API_URL` to a
  loopback or private address; an operator who points it at a public host gets a
  policy that dutifully authorises it. That is the operator's call to make, but
  it is a weaker statement than the badge in the interface, and the READMEs now
  say so.
- `style-src 'unsafe-inline'` keeps CSS-based exfiltration techniques
  theoretically open. They need an external fetch to be useful, which
  `default-src 'self'` and `font-src 'self'` refuse.
- Every response now carries roughly 250 bytes of header, including responses
  for static assets. Irrelevant locally; worth knowing if this is ever put
  behind a CDN.
- The policy is tested in isolation, not in a browser. The unit tests prove the
  string is built correctly, and the header was confirmed on a real response
  from the standalone server; that every resource the running page requests is
  allowed was established by reading the built output, not by loading the page
  in a browser and watching the console. The streaming path is the one that
  needed the most care and is the least at risk: it is a `fetch` POST rather
  than an `EventSource`, because the documents travel in the request body, so
  `connect-src` governs it and it goes to exactly the origin named there.
