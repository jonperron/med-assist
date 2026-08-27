# CLAUDE.md - Med-Assist

The project spec lives in AGENTS.md and is the single source of truth for
commands, stack, structure, security boundaries, and definition of done.

@AGENTS.md

Everything below is the Claude-Code-specific delta. If a rule here conflicts
with AGENTS.md, AGENTS.md wins — except where noted as Claude-only mechanics.

## Coding Rules

AGENTS.md section 6 holds the summary. The detail lives in four files, each
loaded by a different mechanism at the point listed in the third column:

| Rules | Where | Loaded when |
| --- | --- | --- |
| Python, layering, error handling | `backend/CLAUDE.md` | a file under `backend/` enters context |
| TypeScript, React, API access | `frontend/CLAUDE.md` | a file under `frontend/` enters context |
| Patient data, secrets, retention | `data-boundaries` skill | storage, logging, uploads, CORS, deploy config |
| Conventional commits, PR bodies | `commit-messages` skill | writing a commit message or PR body |

Each also carries the gate commands or Claude-only mechanics for its scope, so
the rule and the way to check it sit together.

Path-scoped memory backstops the rules, it does not deliver them: a nested
`CLAUDE.md` loads once a file in its directory is already in context, which is
usually after you have decided what to write. Read it before editing.

## Subagent Mapping

AGENTS.md section 8 defines four mandatory review passes. In Claude Code they
map to project subagents in `.claude/agents/`. Invoke them with the Agent tool
using the `subagent_type` below.

| Pass | `subagent_type` | Writes? | Fallback |
| --- | --- | --- | --- |
| 1. Lint | `lint` | yes | `Explore`, lint-focused prompt |
| 2. Test | `test` | yes | `Explore`, test-focused prompt |
| 3. Review | `review` | no | `/code-review high` |
| 4. Security | `security` | no | `/security-review` |

`docs` is also available for documentation work. It is not one of the four gates.

Claude-only mechanics:

- Passes 1 and 2 write, so run them in order: lint, then test.
- Passes 3 and 4 are read-only and independent. Launch both in a single message
  so they run concurrently.
- `review`, `security` and `docs` have no Bash tool. They cannot run the quality
  gates; they report which ones you should run.
- Subagent reports are not shown to the user. Relay the findings that matter in
  your own response, and never predict or fabricate the result of a pass that
  has not returned yet.

## Claude-Specific Notes

- Node.js is 24.x. The files under `.github/agents/` still say 20.19+; AGENTS.md
  is correct.
- `.claude/agents/` and `.github/agents/` are parallel definitions of the same
  four roles in incompatible frontmatter formats. Change both or neither.
- The coding rules above are Claude Code config and have no `.github/`
  counterpart. If GitHub tooling ever needs them, add `.github/instructions/`
  files and keep them in sync the same way `agents/` is kept in sync — do not
  point one tool at the other's paths.

<!-- OPENWIKI:START -->

## OpenWiki

See [AGENTS.md](AGENTS.md) for OpenWiki agent instructions.

<!-- OPENWIKI:END -->
