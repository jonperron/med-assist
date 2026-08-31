---
type: decision
title: 2026-08-31 - An unavailable service is announced before the batch
description: The interface polls GET /readyz and warns that Med-Assist is unavailable before the clinician gathers documents, instead of refusing them afterwards.
tags: [frontend, readiness, ux, deployment]
---

# 2026-08-31 - An unavailable service is announced before the batch

## What was decided

The backend reads the weights once at startup and answers 503 on `/readyz` and
on both analysis routes until they are in memory. Until now the interface never
asked: a clinician learned the service was down by selecting their documents,
submitting them, and reading a refusal - which arrives in the same card as
"aucun résumé n'a pu être établi" and reads as their scans having failed.

`app/lib/serviceStatus.ts` asks `GET /readyz` and reduces the answer to one of
four states. `app/page.tsx` polls it from mount, 5 seconds while down and 30
while ready, each check scheduling the next.

**Two failing states, because they justify different amounts of interference.**

- `unavailable` is the service answering for itself: a 5xx, which is what the
  readiness gate sends while the model is not loaded. That is authoritative, so
  the notice goes up *and* the submit button is disabled.
- `unreachable` is the absence of an answer - a network error, a check that ran
  out of time, a 404 from a deployment that does not route `/readyz`, a proxy's
  405. The notice goes up with different wording, and the button stays enabled.

The split exists because collapsing the two disables a working service on the
strength of a broken probe. `NEXT_PUBLIC_API_URL` points the browser at the
backend origin and `/readyz` is mounted at the root while analysis is under
`/api`, so any deployment that forwards only `/api/*` 404s the check while the
analysis path works perfectly. `canAnalyse` is the one place that decides, and
it closes the door only on a refusal.

**Every check carries a deadline.** The poll schedules its next run only once
the previous one has answered, so a request that never settles would stop the
loop for good and freeze whatever was last on screen - and if that is the
warning, nothing short of a reload clears it. `checkService` composes the
caller's signal with a 4-second timeout, kept under the 5-second poll so two
checks are never in flight at once. A timeout reads as `unreachable`: a backend
too busy to answer a probe has not refused anything.

**A failed analysis re-checks immediately.** A `server_error` or `transport`
failure already carries an answer about the service, so the page asks now rather
than up to 30 seconds later. A batch that could not be read does not, and does
not trigger one.

**The retry is gated with the submit button.** `AnalysisFailure` takes
`canRetry`; while the service is refusing, the card keeps "choisir d'autres
documents" and drops "réessayer", which would otherwise re-upload the same batch
to a backend known to refuse it, sitting beside a submit button already disabled.

**Returning to the tab re-checks.** A hidden tab has its timers throttled to
roughly a minute, and the notice promises the screen updates by itself.

Three rules the notice follows:

- **It names no mechanism.** No model, no version, no timing, no status code,
  no path - the same rule the rest of the interface follows. `/readyz` answers a
  fixed string carrying none of that either, and the notice renders its own
  copy rather than any string from the wire, so unlike `AnalysisFailure` there
  is nothing upstream to sanitise.
- **It is `role="status"`, not `role="alert"`, and it is named.** This is the
  state of the machine on arrival, not the result of something the clinician
  just did. Three other components on these screens are also `role="status"`,
  so it carries an `aria-label`.
- **`unknown` shows nothing.** A warning rendered during the first round trip
  would flash on every load of a healthy deployment.

## The alternative that was rejected

Leaving readiness to the analysis path and improving the refusal instead.

The 503 already carries a distinct message, and `AnalysisFailure` could have
been given a fourth headline for it. That fixes the wording and not the order:
the clinician has already chosen files, waited for the upload, and been told
something went wrong with a request they had reason to expect would work. Cheap
to build, and it leaves the one piece of information that would have saved the
trip - the service is down - available only after the trip.

Server-side rendering the readiness state was also rejected. It is one fetch at
request time with no polling, but the state it reports is exactly the one that
changes seconds later, and a page rendered "unavailable" would stay that way
until reloaded, which is the behaviour this is meant to remove.

## What it costs

- **A background request every 5 or 30 seconds per open tab.** `/readyz` reads
  a boolean, so the cost is a connection rather than work, but it is charged
  against uvicorn's `--limit-concurrency 8` alongside real analyses. On a busy
  deployment a check can queue behind a batch and time out, which puts the
  `unreachable` notice up for a service that is merely working hard. It does
  not disable anything, which is why that state does not.
- **The banner is only as fresh as the last check.** A backend that goes away
  between polls leaves an enabled button for up to 30 seconds. The re-check on
  failure narrows that to one attempt; it does not close it.
- **Two states, one of which is a judgement call.** Treating every 5xx as the
  service refusing is right for the 503 the gate sends and merely plausible for
  a 500 from a proxy. The cost of being wrong is a disabled button on a service
  that might have worked, which is the safer direction of the two.
- **The page tests now route two mocks.** `fetch` is dispatched on URL in
  `app/__tests__/page.test.tsx` so a test can set the analysis response without
  setting readiness, and every test renders through a helper that flushes the
  mount-time check inside `act`. A test that renders the page directly will
  warn unless its readiness promise never settles.
- **`NEXT_PUBLIC_API_URL` is now resolved in one place.** `page.tsx` took the
  raw value behind a falsy check while the CSP trimmed it, so a whitespace-only
  value built a policy for the default origin while `fetch` got a blank base and
  resolved the analysis POST against the frontend's own origin. Both now call
  `apiBaseUrl`. Adjacent and *not* fixed: `apiOrigin` accepts a URL carrying
  userinfo, and since `NEXT_PUBLIC_*` is inlined into the client bundle, a value
  like `http://user:token@host` publishes that token to every visitor while
  `fetch` refuses the URL outright. It predates this change and wants its own
  entry, but it is worth knowing about while this file is open.
