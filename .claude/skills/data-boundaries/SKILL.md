---
name: data-boundaries
description: Use when touching upload handling, text extraction, Redis storage, logging, error payloads, CORS, or deployment config in Med-Assist. Covers patient-data confidentiality, secrets, input validation, and retention.
---

# Data boundaries

AGENTS.md section 9 lists the boundaries that are never crossed. This skill is
the working detail behind them and does not override them: on any conflict,
AGENTS.md wins.

## Input

- No hardcoded secrets. Secrets come from environment variables only, and
  `.env.example` carries placeholders, never real values.
- Validate all external input: MIME type, file extension, declared content
  length, and ID format. Refuse an oversized body on its declared length, before
  the server spools it to disk.
- Validate at the boundary, and again where an assumption is load-bearing. A
  check in the frontend is a convenience, not a control.

## Patient data

- Patient content never leaves the machine. No external API, no cloud service,
  no telemetry, no crash reporter. Model weights load offline.
- Never use a patient-identifiable value as a Redis key. Keys are UUIDs.
- Never write document content, filenames, or extracted entities into logs,
  error payloads, traces, test fixtures, screenshots, commit messages, or
  subagent reports. File id and exception type only.
- Persist as little as possible and justify any new persisted field. Stored
  values are encrypted before they reach Redis and every key carries a TTL.
- Responses carrying clinical content must be uncacheable.
- Pseudonymisation reduces risk; it does not make the data non-personal. Do not
  describe masked output as anonymised, and do not describe any change as making
  the system compliant with a regulation.

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
than assuming it does: every key written on this path has a TTL, every value is
encrypted, no new field is persisted without a reason that survives being
written down, nothing clinical reaches a log or an error payload, model loading
stays offline, no new dependency phones home, and mock routes stay out of
production.
