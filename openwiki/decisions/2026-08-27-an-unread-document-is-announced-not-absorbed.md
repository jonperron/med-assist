---
type: decision
title: 2026-08-27 - An unread document is announced, not absorbed
description: A partial batch shows a caution above the summary and keeps the skipped document in the source chips.
tags: [frontend, summary, safety]
---

# 2026-08-27 - An unread document is announced, not absorbed

## What was decided

When `AnalysisResponse.documents[i].read` is false, the interface shows a
caution notice above the summary naming what was left out, and keeps the
skipped document in the source chips marked "non lu". Both stay in the printed
copy.

## The alternative that was rejected

Rendering the partial summary as an ordinary one. The API answers 200, the
summary is valid, and `document_count` already reports how many documents were
read - a reader comparing it against what they submitted would notice.

They would not. The count reads as a fact about the summary, not as a
discrepancy, and there is nothing on screen to compare it against. Since #66
made a batch survive a document it cannot read, the failure mode is a summary
that looks complete and is not: a clinician acting on it is acting on less than
they think, and the interface is the only place that can say so. The backend's
own security pass named this the cost of the change, and logging a warning
server-side does not reach the person reading the summary.

Also rejected: dropping the skipped document from the source chips. The chips
answer "what is this summary built from", and a missing chip makes the summary
look as though it covered a document it does not.

## What it costs

- A caution bar on a screen that is otherwise the answer. It is the second one
  on that screen, after the standing caveat, and two cautions dilute each
  other.
- The notice names documents from page state, so a position the selection
  cannot resolve is reported as "Document 3". That is worse than a name and
  better than silence.
- A response carrying fewer documents than were submitted is read as saying
  nothing about the missing positions rather than as failing them. A truncated
  body therefore under-reports rather than inventing skips - the safer of two
  wrong answers, but still a wrong one.
