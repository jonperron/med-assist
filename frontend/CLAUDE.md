# CLAUDE.md - frontend

Claude Code loads this file when a file under `frontend/` enters context. It
carries the TypeScript and React rules for this repo. AGENTS.md stays the source
of truth for the stack, the boundaries and the definition of done; where this
file and AGENTS.md disagree, AGENTS.md wins.

Path-scoped memory backstops the rules, it does not deliver them: this file
loads once a frontend file is already in context, which is usually after you
have decided what to write. Read it before editing, not after.

## Gates for a frontend change

```bash
cd frontend
npm run lint
npm run build
npm test
```

`npm test` runs vitest. `.github/workflows/frontend-ci.yml` runs only lint and
build, so a broken test reaches `main` unless it is caught here. Run all three.

## Code organization

- Many small files over few large files
- High cohesion, low coupling
- 200-400 lines typical, 800 max per file
- One component per file, named after the file (`app/components/FileDropzone.tsx`)
- Tests colocated in `__tests__/` beside the code they cover
- No circular import

## Code style

- No emojis in code, comments, or documentation
- Immutability always: never mutate props, state, objects, or arrays. Use
  spread, `map`, `filter`, and setter callbacks.
- TypeScript `strict` is on. No `any`, and no `@ts-expect-error` or non-null
  assertion without a comment saying why it holds.
- Meaningful, descriptive names. Avoid abbreviations.
- camelCase for variables and functions, PascalCase for components and types,
  UPPER_CASE for module-level constants
- Prefer named exports; default-export only what Next.js requires (pages,
  layouts)
- Type props explicitly with an interface or type alias; do not infer them from
  usage
- Function components with hooks. No class components.
- Keep `"use client"` at the leaf that needs it, not at the top of a tree

## Data and API access

- Reach the backend through the configured API base URL. Never hardcode a host
  or port in a component; a wrong fallback is how a fresh clone ends up unable
  to reach its own backend.
- API errors arrive as `{"detail": {"message": ...}}`. Read that shape before
  falling back to a generic message.
- Document text and entity offsets are optional by design. The default analysis
  path stores nothing, and a stored document usually carries entities without
  the prose they were extracted from. Rendering that assumes either is present
  breaks on the common case, not the rare one.
- Nothing clinical goes into `localStorage`, `sessionStorage`, a cookie, a URL,
  or any analytics or logging sink. Page state only.
- Strip untrusted text at the render boundary with `lib/safeText`. A finding,
  the patient line and a filename are all spans somebody else wrote, and an
  invisible formatting character in one displays it in an order the document
  does not say.
- Run the dev server against synthetic documents only, never a real one.
  `app/error.tsx` keeps a render throw off the production screen, but Next
  reports a handled error to the development overlay and React logs it to the
  console in both modes - and on these screens the value in that trace is
  patient-derived. That one is an operational rule, not something the code can
  enforce.
