This is a [Next.js](https://nextjs.org) project for the Med-Assist frontend.

## Requirements

- Node.js 24.x.

## Getting Started

First, run the development server:

```bash
npm run dev
# or
yarn dev
# or
pnpm dev
# or
bun dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

Frontend quality gates:

```bash
npm run lint
npm run build
npm test
```

You can start editing the page by modifying `app/page.tsx`. The page auto-updates as you edit the file.

This file says how to run and change the interface. **Why it behaves the way it
does - what was rejected, and what each choice costs - is in
[`openwiki/decisions/`](../openwiki/decisions/), one page per decision.**

## Security headers

`next.config.ts` serves a Content-Security-Policy on every response, built by
`app/lib/contentSecurityPolicy.ts`. Its `connect-src` names only the page's own
origin and the backend origin taken from `NEXT_PUBLIC_API_URL`, so the browser
refuses every silent connection anywhere else: fetch, websocket, beacon, remote
image, off-origin form post. `X-Content-Type-Options`, `Referrer-Policy` and
`X-Frame-Options` are served alongside it, and there is no HSTS header.

`NEXT_PUBLIC_API_URL` is read at build time, and only its origin reaches the
policy — a path, query or fragment in the value is dropped. A value that is not
an absolute `http(s)` URL, or whose host is not a plain hostname or bracketed
IPv6 address, fails the build. Because the value is baked in, a deployment that
moves the API has to rebuild this image.

`next dev` gets a variant that also allows `'unsafe-eval'` and a hot-reload
websocket to `localhost`, `127.0.0.1` and `[::1]` on any port, which Fast
Refresh and HMR need. The variant is selected from the phase Next passes to the
config, not from `NODE_ENV`.

What the policy enforces, what it cannot stop, and why each directive is written
the way it is:
[the local-first claim is enforced by a Content-Security-Policy](../openwiki/decisions/2026-08-28-the-local-first-claim-is-enforced-by-a-csp.md).

## Version and footer

Both screens carry `app/components/AppFooter.tsx`: the build version, a link to
the public issue tracker, and one sentence on what becomes of a submitted
document.

The version comes from `package.json`, which stays the only place it is written
down. `next.config.ts` reads the manifest at build time and injects it through
Next's `env` option, so `app/lib/version.ts` reads a string literal that the
bundler has already substituted; the manifest itself never reaches the bundle.
`vitest.config.ts` defines the same value from the same file. **Bumping a
release therefore means bumping `package.json` and nothing else.**

The privacy sentence and the badge are no longer the same claim, so reword them
independently: the sentence is about retention and holds on every deployment,
the badge is about *where* and is shown only when the deployment is not open.
Why the sentence says temporary storage rather than "never touches a disk", why
the issue link is the one off-origin navigation on offer, and what the version
injection costs:
[the footer states the version, the address and what is kept](../openwiki/decisions/2026-08-31-the-footer-states-the-version-the-address-and-what-is-kept.md).

## The unsecured-deployment banner

`UNSECURED_DEPLOYMENT` is a plain environment variable, deliberately not a
`NEXT_PUBLIC_` one, read at request time in `app/layout.tsx` - which is why that
file declares `export const dynamic = 'force-dynamic'`. Set, it renders
`app/components/UnsecuredDeploymentNotice.tsx` above the header on every screen
and renders `app/components/PrivacyBadge.tsx` as nothing; the value reaches the
badge through `app/lib/deploymentContext.tsx`, since the layout is a server
component and the badge is not.

Parsing is in `app/lib/deployment.ts` and is asymmetric: unset and blank are
off, and once the variable is set only `0`, `false`, `no` and `off` turn it off
- every other value, a misspelling included, is on.

**Two things here cannot be covered by a test that runs.** The flag must be read
as a literal `process.env.UNSECURED_DEPLOYMENT`, not a computed key, and
`force-dynamic` must stay declared; either one, changed, silently turns the
banner off in every deployment while the suite stays green. Both are guarded by
source-text assertions in `app/__tests__/layout.test.tsx`. If you change how the
flag is read, check it against a built server - `npm run build`, then
`UNSECURED_DEPLOYMENT=true node .next/standalone/server.js` - and not only
against `npm test`.

Why there is a banner rather than a credential, and what it does not do:
[the credential is removed and the deployment warns instead](../openwiki/decisions/2026-09-05-the-credential-is-removed-and-the-deployment-warns-instead.md).

## API types

`app/types/api.ts` is generated from the backend's OpenAPI document and is not
edited by hand. `app/types/extraction.ts` gives its schemas the names the
components use.

After a backend response model changes:

```bash
cd ../backend && uv run python scripts/export_openapi.py
cd ../frontend && npm run generate:types
```

A backend test fails when `backend/openapi.json` no longer matches the app, so
the export cannot be forgotten silently.

When changing framework dependencies, regenerate the lockfile with the same Node.js major version used for validation.
