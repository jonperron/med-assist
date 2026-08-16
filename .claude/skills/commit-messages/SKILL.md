---
name: commit-messages
description: Use when writing a git commit message, a PR title, or a PR body for Med-Assist. Covers conventional commit format, the scopes in use, body structure, and what must be called out.
---

# Commit messages

## Format

- Conventional Commits: `type(scope): summary`
- Types: feat, fix, chore, refactor, test, docs
- Scopes in use: `backend`, `frontend`, `ci`, `deps`, `docs`, `security`,
  `model`, `tests`, `claude`. Omit the scope when a change spans the repo.
- Subject line: lowercase, imperative, no period, max 72 chars
- Blank line between subject and body

## Body

- Open with a sentence or two on why the change exists, not a restatement of the
  diff
- Then a bullet list of what changed. Wrap at 72 characters and indent
  continuation lines with 2 spaces.
- Reference API surface changes: new or removed endpoints, renamed repository
  methods, changed response fields
- Call out anything that changes what is stored, logged, or returned, and any
  new environment variable or default
- Never quote patient data, document content, or a real filename. Commit
  messages are the one artifact that leaves the machine on every push, and
  unlike a log line nobody rotates them. Describe the sample that reproduced a
  bug; do not paste it.

## Claude-only mechanics

- Commit only when asked. If the checkout is on `main`, branch first —
  `feature/<scope>` or `fix/<scope>`, per AGENTS.md section 7.
- End the message with the `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`
  trailer after a blank line. This is what the existing history uses.
- PR bodies end with the Claude Code generation footer, with the structure above
  it unchanged.
- The four review passes in AGENTS.md section 8 run before the PR, not after. Do
  not describe a gate as passing unless it ran in this session and its output
  was read.
