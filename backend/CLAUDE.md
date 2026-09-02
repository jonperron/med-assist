# CLAUDE.md - backend

Claude Code loads this file when a file under `backend/` enters context. It
carries the Python rules for this repo. AGENTS.md stays the source of truth for
the stack, the boundaries and the definition of done; where this file and
AGENTS.md disagree, AGENTS.md wins.

Path-scoped memory backstops the rules, it does not deliver them: this file
loads once a backend file is already in context, which is usually after you have
decided what to write. Read it before editing, not after.

## Gates for a backend change

```bash
cd backend
uv run pytest -v
uv run pre-commit run --all-files
```

`--all-files` means the whole repository, wherever you run it from. pre-commit
resolves the git toplevel before collecting anything, so `cd backend` does not
narrow it: a run started here will lint, and fail on, a file at the repository
root. The hooks live in the repo-root `.pre-commit-config.yaml` and the pylint
hook is pinned to `backend/app`, which is the only part of this that is scoped.

Two consequences worth knowing before you trust a green run:

- A file nobody on your branch touched can turn this red. `end-of-file-fixer`
  and `trailing-whitespace` police the whole tree, including files written by
  bots, so the gate can fail for reasons that are not in your diff. Check what
  the hook names before assuming it is yours.
- **Those two hooks rewrite files and then exit non-zero.** The first run is
  red and leaves the fix in your working tree; the second run is green because
  the first one already edited it. So "pre-commit passed locally" can be a
  second-run artifact over an unstaged change, while CI - which gets a clean
  checkout and one run - stays red. If a hook reports `files were modified by
  this hook`, that is a failure you still have to commit, not a pass.

## Code organization

- Many small files over few large files
- High cohesion, low coupling
- 200-400 lines typical, 800 max per file
- Organize by feature/domain, not by type
- No circular import
- Respect the layering: `api/routes/` holds HTTP concerns, `use_cases/`
  orchestrates, and `services/` does extraction, parsing and model work behind
  the protocols in `interfaces/`. A route that reaches straight into a service's
  internals is a review finding, not a shortcut. There is no persistence layer:
  the API stores nothing, and adding one is a decision entry before it is code.

## Code style

- No emojis in code, comments, or documentation
- Immutability by default: build new values rather than mutating arguments,
  module-level containers, or shared state
- Follow PEP 8
- 4 spaces for indentation, never tabs
- Meaningful, descriptive names. Avoid abbreviations.
- snake_case for functions and variables, PascalCase for classes, UPPER_CASE for
  constants
- Line length follows the ruff formatter default of 88. `.pylintrc` allows 120
  so that a string the formatter cannot split does not fail the build; that
  headroom is not a licence to write 120-character lines.
- No "fake" privacy: do not prefix functions, methods, classes, module-level
  values, `self` attributes, or import aliases with a leading underscore. Python
  does not enforce privacy — the underscore only hides names from `import *` and
  adds noise. It is reserved for intentionally-unused names (`*_args`,
  `**_kwargs`, `for _key, value in ...`). `scripts/check_naming.py` enforces
  this in pre-commit and dunders are exempt. Rename rather than adding an
  exemption.

## Typing and async

- Annotate every function signature. mypy runs in pre-commit and in CI.
- Prefer Pydantic models in `schemas/` over dicts at API and service boundaries.
- Do not block the event loop with synchronous I/O inside a coroutine, and keep
  CPU-bound model work off the request path where that is avoidable.

## Error handling

- Validate at the boundary: file type, extension, declared size, and ID format
  before any work happens.
- Raise `HTTPException` with a `{"message": ...}` detail payload and nothing
  else. Chain the cause with `from exc` so the traceback survives in the logs.
- Never let a parser error, stack trace, filename, or document content reach the
  client. Parser libraries quote the bytes that failed to parse, and those bytes
  are patient data. Log the file id and the exception type.
- Do not catch `Exception` broadly to make a check pass; catch what you handle.
