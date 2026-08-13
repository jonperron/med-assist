# CLAUDE.md - Med-Assist

The project spec lives in AGENTS.md and is the single source of truth for
commands, stack, structure, security boundaries, and definition of done.

@AGENTS.md

Everything below is the Claude-Code-specific delta. If a rule here conflicts
with AGENTS.md, AGENTS.md wins — except where noted as Claude-only mechanics.

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

- Passes 1 and 2 write and must run in order. Passes 3 and 4 are read-only and
  independent — launch both in a single message so they run concurrently.
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
