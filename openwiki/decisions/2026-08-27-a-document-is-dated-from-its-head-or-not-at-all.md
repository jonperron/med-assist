---
type: decision
title: 2026-08-27 - A document is dated from its head, or not at all
description: document_date.py reads the document's own date out of the first 500 characters under rules that all prefer None to a guess, and skips a date a birth marker points at.
tags: [backend, dates, privacy, safety]
---

# 2026-08-27 - A document is dated from its head, or not at all

## What was decided

A date is what a clinician places a document by: a letter written last week and
a letter written in 2019 mean different things, and a stack of documents about
one patient is read along the time it covers. `documents[i].document_date`
carries the date each document itself carries, and `summary.date_range` the
stretch from the earliest to the latest. Both are `null` when nothing could be
dated, which is a common answer and not an error.

Neither of the two sources already at hand answers this.
`ExtractedEntities.temporal` is every date-like span found anywhere in the text,
mixed with durations and relative moments; the file's own timestamp dates a 2019
letter to the day it was downloaded. So `app/services/document_date.py` reads the
text, and a wrong date is worse than no date - it silently moves a document on
the timeline the clinician is reading. Every rule is therefore a reason to
answer nothing rather than to guess:

- **Only the head is read** (`HEAD_CHARACTERS`, 500). A letter is dated in its
  letterhead; a date deep in the body belongs to what the document reports. Wide
  enough for a letterhead, an address block and a subject line, short enough
  that the first line of the narrative is out of reach.
- **Only a complete calendar date counts** - day, month and a four-digit year,
  on the calendar. A bare year, a month with no year, a two-digit year and "il y
  a trois jours" are all things this refuses rather than resolves.
- **Numeric dates are read day-first**, the convention the documents are written
  in. `03/13/2024` is refused rather than swapped.
- **The first complete date in the head wins.** In "Hospitalisation du 2 mars
  2024 au 5 mars 2024" that is the start of what the document reports.
- **A date a birth marker points at is skipped.** "Née le 12/05/1948" or "Date
  de naissance" would otherwise date the document to 1948, and a date of birth
  is a patient identifier rather than document metadata. The lookback
  (`BIRTH_CONTEXT`, 120 characters) is matched against folded,
  whitespace-collapsed, dot-stripped text, so padded table columns, a label and
  its value on two lines, tabs and "D.D.N." all read the same. It is only looked
  for *before* the date, and never past the previous date in the text.
- **A date in the future, or older than `EARLIEST_YEAR` (1900), is skipped.**

No span from the document is returned with the date. The caller renders it in
its own locale - see
[[2026-08-27-dates-are-formatted-in-utc-or-not-at-all]] - and the summary stays
made of headings and marked spans. Nothing about this widens what is kept: the
date is read from the text and the text is dropped with the request.

## The alternative that was rejected

**Taking the file's `lastModified`.** It is always present, needs no parsing,
and is wrong for exactly the documents that matter: a scanned or re-exported
2019 letter is dated to the day it was copied. A date that is always available
and sometimes years wrong is worse than one that is often absent.

**Using the `temporal` entities the model already marks.** They are every
date-like span in the document, including the dates of the events the document
reports. Picking the document's own out of them is the judgement this module
makes; the entity list does not make it.

**Resolving the elided range form, "du 2 au 5 mars 2024".** It holds one
complete date, its last, so such a document is placed at the end of the stay it
reports rather than at the start. Reading the elided form would mean inferring a
month for a bare number from the number after it, which is the kind of inference
the rest of the module refuses.

**Looking for a birth marker after the date as well as before it.** It would
catch "12/05/1948, date de naissance" - and it would cost the common one-line
header its real date, because any marker later on that line would suppress it.
The asymmetry is deliberate.

## What it costs

- **Undated documents are common, and the interface has to live with it.** A
  letterhead the parser flattens badly, a date past character 500, a date
  written in a form these rules refuse - all produce `null`, and the batch's
  `date_range` narrows or disappears with them.
- **The birth guard is a list of markers, not an understanding.** A birth date
  introduced by wording it does not know is published as the document's date -
  off by decades, and a patient identifier surfaced as metadata. That is the
  accepted cost of dating documents whose letterhead carries a bare date with no
  wording at all.
- **A document reporting a range is placed at one end of it**, and which end
  depends on how the range was written. Nothing in the response says the date
  came from a range.
- **Day-first is a locale assumption in code.** The corpus is French clinical
  text; a deployment reading US-formatted documents gets refusals where the day
  is above 12 and, worse, silently transposed dates where it is not - the one
  place these rules can be confidently wrong rather than absent.
- **500 characters is a typographic guess.** A document with a long structured
  header can push its date out of reach.

---

Written down on 2026-09-05 from `backend/README.md`, which carried the reasoning
inline. The change itself is `fbcbc89` (2026-08-27).
