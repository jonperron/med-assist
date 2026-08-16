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
