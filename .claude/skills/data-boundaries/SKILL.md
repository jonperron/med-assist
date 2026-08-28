---
name: data-boundaries
description: Use when touching upload handling, text extraction, logging, error payloads, CORS, or deployment config in Med-Assist. Covers patient-data confidentiality, secrets, input validation, and the no-storage boundary.
---

# Data boundaries

AGENTS.md section 9 lists the boundaries that are never crossed. This skill is
the working detail behind them and does not override them: on any conflict,
AGENTS.md wins.

## Input

- No hardcoded secrets. Secrets come from environment variables only, and
  `.env.example` carries placeholders, never real values.
- Validate all external input: MIME type, file extension, declared content
  length, and batch size. Refuse an oversized body on its declared length,
  before the server spools it to disk. No endpoint accepts an identifier today;
  one that does must validate its format at the boundary.
- Validate at the boundary, and again where an assumption is load-bearing. A
  check in the frontend is a convenience, not a control.

## Patient data

- Patient content never leaves the machine. No external API, no cloud service,
  no telemetry, no crash reporter. Model weights load offline.
- The API stores nothing. Reintroducing persistence of patient data is a design decision with its own entry under `openwiki/decisions/`, not an implementation detail.
- Never write document content, filenames, or extracted entities into logs,
  error payloads, traces, test fixtures, screenshots, commit messages, or
  subagent reports. Exception type and submission position only - no
  identifier is minted for a document, and none should be.
- Persist nothing. If persistence is ever reintroduced, values are encrypted
  at rest, every key carries a TTL, and every field is justified.
- Responses carrying clinical content must be uncacheable.
- Extracted entities are patient data in their own right. Categorising a span
  does not de-identify it, and neither does dropping the surrounding text. Do
  not describe extraction output as anonymised, and do not describe any change
  as making the system compliant with a regulation.

## Boundaries and config

- Keep CORS strict and environment-aligned. Mock routes mount outside production
  only.
- Do not modify production deployment configs or credentials as part of feature
  work.
- Do not edit `backend/models/` or any `__pycache__/` directory unless asked.
- Any change that widens what is stored, logged, returned, or reachable from
  outside the compose network gets called out explicitly for review rather than
  slipped in.

## Claude-only mechanics

- Such a change gets the `security` subagent before it is finalized, per
  AGENTS.md section 8 pass 4. `/security-review` is the fallback.
- The `security` and `review` subagents are read-only and independent. Launch
  both in one message so they run concurrently.
- Their reports are not shown to the user. Relay what matters yourself, and
  never state the outcome of a pass that has not returned.

## Before calling a change safe

The README's claims are behavioural, and each has a mechanism behind it. When a
change lands near storage or egress, confirm the mechanism still holds rather
than assuming it does: the change opens no write path and adds no persisted
field, the multipart spool still lands on a `tmpfs` under `TMPDIR`, nothing
clinical reaches a log or an error payload, model loading stays offline, no new
dependency phones home, and mock routes stay out of production.
