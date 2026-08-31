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

## Version and footer

Both screens carry `app/components/AppFooter.tsx`: the build version, a link to
the public issue tracker, and one sentence on what becomes of a submitted
document.

The version comes from `package.json`, which stays the only place it is written
down. `next.config.ts` reads the manifest at build time and injects it through
Next's `env` option, so `app/lib/version.ts` reads a string literal that the
bundler has already substituted; the manifest itself never reaches the bundle.
`vitest.config.ts` defines the same value from the same file, so the footer
under test shows the version it would ship with rather than the `dev` fallback.
Bumping a release therefore means bumping `package.json` and nothing else.

The issue link is the only off-origin navigation this interface offers. No CSP
directive governs a user-initiated navigation, so what makes it safe is where it
goes: a public repository holding no patient data. It carries
`rel="noopener noreferrer"`, and `Referrer-Policy: no-referrer` keeps the
address of the page the clinician was on out of the request.

The privacy sentence says the documents live in temporary storage for the length
of the request rather than claiming they never touch a disk, because the HTTP
server spools a multipart part above 1 MB. Both halves of it hold on any
filesystem — the spool is an unnamed inode, unlinked at creation — but only
`docker-compose.yml` makes that spool RAM-backed, by mounting a `tmpfs` at `/tmp`
and setting `TMPDIR`. A deployment that does not (a bare `uvicorn` run, a plain
`docker run`, a k8s manifest) still erases the file with the response, but on a
disk-backed `/tmp` the freed blocks are recoverable from the raw device. Backing
`TMPDIR` with RAM is therefore a precondition for the strongest reading of the
sentence, and belongs in any deployment that is not the Compose file.

It is the badge's claim spelled out; if either is reworded, reword both.

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
