---
type: decision
title: 2026-08-27 - The stream is the only analysis path the client takes
description: The interface calls POST /api/analyze/stream and no longer calls POST /api/analyze at all.
tags: [frontend, api, progress]
---

# 2026-08-27 - The stream is the only analysis path the client takes

## What was decided

The browser posts every batch to `POST /api/analyze/stream` and reads the
result off the stream's final event. `POST /api/analyze` is no longer called
from the interface.

## The alternative that was rejected

Keeping both: the plain endpoint as the default, the stream used only for
batches above some size, or as a progressive enhancement with the plain
endpoint as the fallback.

Two paths would have to be kept honest against each other. The stream's
`result` event carries exactly the body the plain endpoint returns, so the two
would render identically today - and the next field either one gains is a place
they can stop doing so. A fallback also only earns its keep if something can
fail in the stream that does not fail in the plain call, and the two share a
route module, a validation dependency and a use case; the failure they do not
share is the connection dropping mid-body, which a retry of either fixes.

## What it costs

- The interface now depends on a response the browser has to read incrementally.
  A proxy that buffers `text/event-stream` turns the progress card into the
  sweeping bar it replaced - worse than before, because the bar now claims a
  count. Nothing in the client can detect that.
- `POST /api/analyze` keeps a published contract with no first-party caller.
  It is still the simpler endpoint for anything that is not a browser, and it
  is what the stream's own result is defined against, so it is not dead - but
  a regression in it will not be caught by using the app.
- `axios` left the frontend with the last call that used it. A future caller
  wanting interceptors or retries has to bring it back or write them.

## What it does not change

Nothing is stored on either path. The progress events carry a position, a
boolean and a closed reason code; no filename and nothing the model marked
travels before the final result.
