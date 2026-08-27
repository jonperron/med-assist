---
type: decision
title: 2026-08-27 - A finding from several documents is counted, not named
description: The source label on a finding names one document and counts more than one.
tags: [frontend, summary, provenance]
---

# 2026-08-27 - A finding from several documents is counted, not named

## What was decided

`Finding.documents` holds every submission index a finding was found in. The
row on screen names the document when there is exactly one, and says
"3 documents" when there are more. The name comes from the clinician's own
selection, resolved by index.

## The alternative that was rejected

Naming all of them, as a list or as a stack of chips per row.

Down a column of findings that is four names against every row, which is not
something a clinician reads - and it is the same four names repeated, since a
batch is one patient. The count carries the clinical fact that matters here:
whether the finding is agreed on across documents or appears once.

Also rejected: showing the count as a number of mentions rather than of
documents. The API tracks both, and mentions measure how often a span was
written, which is a property of the documents' prose rather than of the
patient.

## What it costs

- A finding several documents agree on cannot be traced from the summary to
  which ones without going back to the documents. The chips above the summary
  say what was read, not what each row came from.
- The label depends on page state. An index the selection cannot resolve is
  dropped, and a row with no resolvable index is left unlabelled rather than
  numbered - the pairing of indices to names only holds because this page is
  the uploader, and a summary arriving any other way would have no names to
  resolve against.
