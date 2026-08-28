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

## Security headers

`next.config.ts` serves a Content-Security-Policy on every response, built by
`app/lib/contentSecurityPolicy.ts`. Its point is `connect-src`, which names only
the page's own origin and the backend origin taken from `NEXT_PUBLIC_API_URL`,
so the browser refuses every silent connection anywhere else: fetch, websocket,
beacon, remote image, off-origin form post. It enforces "only the configured API
origin", which is narrower than the "reste sur cette machine" badge if that
origin is not local, and it cannot stop a deliberate navigation carrying data in
a URL — no CSP can. `X-Content-Type-Options`, `Referrer-Policy` and
`X-Frame-Options` are served alongside it. There is no HSTS header: the stack is
served over plain HTTP and pinning `localhost` to HTTPS would outlive it.

`NEXT_PUBLIC_API_URL` is read at build time, and only its origin reaches the
policy — a path, query or fragment in the value is dropped. A value that is not
an absolute `http(s)` URL, or whose host is not a plain hostname or bracketed
IPv6 address, fails the build rather than shipping a page that cannot reach its
backend or a directive wider than intended. Because the value is baked in, a
deployment that moves the API has to rebuild this image, exactly as it already
had to for the fetch URL itself.

`next dev` gets a variant that also allows `'unsafe-eval'` and a hot-reload
websocket to `localhost`, `127.0.0.1` and `[::1]` on any port, which Fast
Refresh and HMR need. The variant is selected from the phase Next passes to the
config, not from `NODE_ENV`, so an inherited environment variable cannot put it
in a production build.

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
