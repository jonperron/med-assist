---
type: decision
title: 2026-08-27 - Document dates are formatted in UTC, or not at all
description: Calendar dates are parsed and rendered in UTC, and anything that is not a complete calendar date is dropped.
tags: [frontend, dates]
---

# 2026-08-27 - Document dates are formatted in UTC, or not at all

## What was decided

`document_date` and `date_range` are parsed as UTC calendar dates and rendered
with `timeZone: 'UTC'`. A value that is not a complete `YYYY-MM-DD`, or names a
day that does not exist, is rendered as no date rather than as an approximation.
A range that reads backwards is dropped entirely.

## The alternative that was rejected

`new Date(value)` and the browser's local zone, which is what any date in an
interface would normally use.

A date-only string parsed that way is midnight UTC, which is the previous day
everywhere west of Greenwich. The document would sit one day earlier on the
timeline a clinician is reading, silently. #67 spent its rules refusing to guess
a date rather than risk exactly that - a two-digit year refused, `03/13/2024`
refused rather than swapped - and re-introducing the error in the browser would
waste all of it.

## What it costs

- The date shown is the document's own calendar date, not a moment in the
  reader's zone. A reader who thinks of dates as instants will find it does not
  shift when they travel. That is correct here and is not what a date field in
  most interfaces does.
- Defensive parsing means a backend that starts sending a datetime, or a date in
  another format, degrades to "no date" with nothing on screen to say why. Null
  is the common and legitimate answer, so the failure is indistinguishable from
  a document that simply carries no date.
