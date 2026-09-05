---
type: decision
title: 2026-08-26 - The summary keeps five categories and drops three
description: The summary is assembled from marked spans under five headings; temporal, measurements and other stay out of it, findings are deduplicated on a folded key, and the confidence score is a floor nobody sees.
tags: [backend, summary, safety]
---

# 2026-08-26 - The summary keeps five categories and drops three

## What was decided

`app/services/summarizer.py` turns categorised NER output into the summary, and
generates nothing. Every word in the result is either a fixed heading or a span
the model marked in a submitted document, so the summary cannot state anything
the documents did not, and no text leaves the process for a language model.

**Five sections, in reading order.** `SECTION_ORDER` is pathologies, signs and
symptoms, examinations, treatments, localisations.

**Three categories are deliberately absent.** `temporal`, `measurements` and
`other` do not get a heading. A bare list of durations, of loose values, or of
unclassified spans carries no clinical meaning once it is separated from the
sentence it came from - "3 jours", "148", "1,10" under a heading is noise a
reader has to reconcile against documents they are not looking at. All three
stay in the per-document `documents` payload for a caller that wants them.
A measurement does reach the summary when it can be attached to the examination
it belongs to; that pairing is
[[2026-08-27-a-measurement-is-paired-with-the-test-beside-it]].

**An opening demographic line.** `demographic_line` reads only the `age` and
`genre` labels out of the `patient_info` category and renders "Patient, 67 ans,
femme." The first mention of each wins, so a relative's age quoted further down
does not overwrite the patient's. Only those two labels are read, not the whole
category: `fr.json` also files the MeSH axes `homme` and `femme` under patient
information and those are urogenital *diseases*, so an open-ended branch would
print a disease as a patient attribute in the summary's first line. The served
model does not emit those axes; the guard is in the code anyway, because the
weights can be replaced and this file cannot be replaced by accident.

**One finding per thing found.** `comparison_key` folds case, accents, inner
spacing and edge punctuation, and two mentions that fold to the same key are one
finding. The first surface form seen is the one reported - a later mention
cannot be a better one, since everything the two could differ by is exactly what
the key already folded away. Findings are ordered by how many documents support
them, then by how many mentions, then alphabetically, so a finding three
documents agree on sits above one that appears once. What the row then says
about its sources is
[[2026-08-27-several-sources-are-counted-not-named]].

**A confidence floor, and nothing else.** `MIN_CONFIDENCE` is `0.5`, and it is
the only use the model's score has. Below it the model is guessing, and a guess
in a clinical summary costs more than the recall it buys. The number is never
rendered: a percentage next to a clinical finding invites a reader to weigh it,
which is not a judgement a token classifier's softmax supports.

## The alternative that was rejected

**Listing every entity with its score, which is what the product did before.**
That is a faithful view of what the model produced and a bad answer to the
question the clinician asked. It makes the reader do the merging, the ranking
and the judging, and it puts a number next to each item that looks like a
probability the finding is correct and is not one.

**Giving the three dropped categories their own sections anyway, since the data
is there.** Rejected for the reason above: the sections would be the two nobody
can act on. `other` is worse than useless - it is whatever the label mapping did
not recognise, so its contents change when the model changes.

**Reporting the longest surface form rather than the first.** Considered on the
grounds that the model truncates some outer mentions. It buys nothing here: two
mentions only merge when they share a folded key, and spans that differ in
length do not share one - they are separate findings either way. `backend/README.md`
described this rule as implemented for a time; it never was, and the description
is removed rather than the code changed.

**Showing the score, or a "high/medium/low" rendering of it.** The floor exists
because the score is meaningful in aggregate. Displaying it per finding asks the
reader to treat it as a per-item confidence, which is precisely the reading it
does not support.

## What it costs

- **A summary can be confidently incomplete.** Everything below the floor is
  gone with no trace in the response, and the floor is a constant rather than a
  measured operating point. Nothing tells a reader that a finding was seen and
  dropped.
- **Deduplication across documents hides disagreement.** Two documents saying
  the same thing differently - one truncated span, one complete - fold to two
  findings when they differ and to one when they do not, and the reader cannot
  tell which happened. The count of supporting documents is the only signal.
- **The five headings are a clinical judgement encoded once.** They came from
  what a clinician reads first, not from a study, and changing them changes
  every summary the product has ever produced with no versioning anywhere.
- **The demographic line depends on the label mapping agreeing with two string
  constants.** A mapping that files demographics elsewhere, or a model that
  emits a different label for age, costs every summary its opening line
  silently. The category name is a named constant to make that dependency
  greppable; nothing checks it at startup.
- **`other` is a growing pile nobody reads.** A label the mapping does not know
  lands there and is reported once at startup. It is in the payload, out of the
  summary, and effectively invisible.

---

Written down on 2026-09-05 from `backend/README.md`, which carried the reasoning
inline. The change itself is `35b58bd` (2026-08-26) - the entry titled "The
product is a summary, not an entity dump" that `DECISION.md` records as having
moved to a wiki this repository does not contain.
