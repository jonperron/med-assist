# AGENTS Guide - Med-Assist

## 1) Quick Commands (Run These First)

Run commands from the project root unless stated otherwise.

```bash
# Backend quality gates
cd backend
uv run pytest -v
uv run pre-commit run --all-files

# Frontend quality gates
cd ../frontend
npm run lint
npm run build
npm test
```

Notes:
- If `npm test` is not configured yet, treat it as a required future gate and do not invent fake passing results.
- Never mark a task as complete without running the relevant checks for touched code.

## 2) Product Mission

Med-Assist helps clinicians obtain an actionable summary from one or multiple medical documents.

The system must prioritize:
- Clinical clarity of outputs.
- Patient data confidentiality.
- Technical robustness in local environments.

## 3) Tech Stack

- Backend: Python 3.12+, FastAPI `0.128.0`, Redis async client `7.1.0`, Transformers `4.x`, PyTorch `2.x`.
- Frontend: Next.js `15.x`, React `19.x`, TypeScript `5.x`, ESLint `9.x`.
- Storage: local Redis only, UUID-based keys, limited retention footprint.
- Infra: Docker Compose with `redis`, `backend`, and `frontend` services.

## 4) Project Structure

- `backend/app/api/routes/`: HTTP routes (`uploads`, `extractions`, `health`, `mock`).
- `backend/app/services/`: extraction and file processing logic.
- `backend/app/repositories/` and `backend/app/db/`: Redis-backed persistence layer.
- `backend/tests/` + root-level backend tests: unit/integration tests.
- `frontend/app/`: Next.js app router pages and components.

Nominal flow:
1. Upload one or multiple medical files (PDF, DOC, DOCX, TXT).
2. Validate MIME type and extension.
3. Extract text.
4. Store extracted content and batch references in local Redis using UUID keys.
5. Extract medical entities and return API response.

## 5) Testing and Validation Rules

- Add or update tests for every functional change.
- Prefer focused tests first, then full suite.
- Keep backend lint/type checks green: Ruff, mypy, pylint, pre-commit.
- Keep frontend lint/build green: ESLint and Next.js build.
- Do not silently skip failing checks; report failures with likely root cause.

## 6) Code Style and Output Expectations

- Make small, reversible, testable changes.
- Preserve public API contracts unless explicitly asked to change them.
- Keep error messages safe: no stack traces, secrets, or patient identifiers in responses.
- Validate external input boundaries (file type, extension, ID format).

One concrete example of expected backend style:

```python
from uuid import UUID

from fastapi import HTTPException


def parse_file_id(raw_file_id: str) -> UUID:
	"""Validate and convert a file id to UUID without leaking internals."""
	try:
		return UUID(raw_file_id)
	except ValueError as exc:
		raise HTTPException(
			status_code=400,
			detail={"message": "Invalid file ID format. Expected UUID."},
		) from exc
```

Expected behavior:
- Deterministic validation.
- Explicit user-safe error payload.
- No internal traceback exposure in API response.

## 7) Git Workflow

- Use short-lived branches: `feature/<scope>` or `fix/<scope>`.
- Commit in logical units with clear messages.
- Run quality gates before opening a PR.
- Do not rewrite shared history unless explicitly requested.
- In reviews, prioritize security, regressions, and missing tests over style-only comments.

## 8) Mandatory Subagent Review Workflow

For any non-trivial change, run two separate subagent passes before finalizing:

1. Review pass (behavior and regressions)
- Preferred subagent: `Review Agent` in `.github/agents/review.agent.md`.
- Fallback subagent: `Explore` with a review-focused prompt.
- Goal: find functional bugs, regressions, API contract breaks, and missing tests.
- Expected output: prioritized findings with file paths, risk level, and proposed fixes.

Recommended prompt template:

```text
Review this change set in medium/thorough mode.
Focus on behavior regressions, edge cases, API/schema compatibility, and missing tests.
Return findings ordered by severity with concrete file references and fix suggestions.
```

2. Security pass (privacy and boundaries)
- Preferred subagent: `Security Agent` in `.github/agents/security.agent.md`.
- Fallback subagent: `Explore` with a security-focused prompt.
- Goal: detect confidentiality leaks, unsafe error handling, weak input validation, and boundary violations.
- Expected output: security findings with CWE-style category when relevant, impact, and mitigation.

Recommended prompt template:

```text
Perform a security review of this change set in thorough mode.
Focus on patient data exposure, secret handling, input validation, Redis key safety,
external data egress, and production config boundaries.
Return only actionable findings with severity, affected files, and remediation steps.
```

Required merge condition:
- No unresolved high-severity review or security findings.
- If findings exist, either fix them or document an explicit risk acceptance.

Invocation examples:
- `@Review Agent Review this change set in medium mode. Focus on behavior regressions, API compatibility, and missing tests.`
- `@Security Agent Perform a thorough security review focused on patient data exposure, input validation, and Redis key safety.`

## 9) Security and Data Boundaries (Never Cross)

Never do any of the following:
- Never expose patient data in logs, error payloads, traces, fixtures, or screenshots.
- Never hardcode secrets or tokens in code, tests, or docs.
- Never send patient content to external APIs or cloud services.
- Never use patient-identifiable values as Redis keys.
- Never modify production deployment configs or credentials as part of routine feature work.
- Never edit dependency/vendor/model artifact directories unless explicitly requested:
  - `backend/models/`
  - `**/__pycache__/`

Always do:
- Keep secrets in environment variables only.
- Keep CORS strict and environment-aligned.
- Minimize persisted data and justify any new persistent field.
- Prefer explicit Redis TTLs when retention is introduced.

## 10) Definition of Done

A task is complete only when:
- Requested behavior is implemented.
- Related tests pass.
- Lint/type checks pass for touched areas.
- Security and privacy requirements above are preserved.
- Documentation is updated when behavior or constraints change.
