---
type: decision
title: 2026-08-27 - An unreadable document costs its position, not the batch
description: A document that yields no text is skipped and marked unread rather than failing the request; the batch is refused only when nothing at all could be read, and the failure is always named by position.
tags: [backend, api, summary, privacy]
---

# 2026-08-27 - An unreadable document costs its position, not the batch

## What was decided

A document of a supported type that yields no text - a scan, or a file the
parser cannot open - no longer costs the batch its summary. `read_documents`
yields it in place with both halves `None` rather than raising, the request
answers `200`, the other documents are summarised, `documents[i].read` is
`false` for the one that failed with `unreadable_reason` naming why, and
`summary.document_count` counts what was read rather than what was sent.

**The whole batch is refused with `400` only when nothing at all could be
read**, because there is then no summary to degrade to. A summary of three
documents out of four, marked as such, is worth more to a clinician than a
refusal; a summary of nothing is not.

**The failure is named by position, never by filename.** `documents` is in
submission order, and the caller already holds the names it posted - so
resolving an index to a name is the caller's job and the index is all that
crosses. The same rule governs the log: one warning per skipped document
carrying its position, which is the only operational signal that a document was
dropped, and never the filename or the text.

**`UnreadableReason` is a closed, content-free enum.** Today its single member
is `no_text`. More members may be added as more ways to fail are told apart, and
none of them will ever be a parser message: those quote the bytes that failed to
parse, and those bytes are patient data.

What the interface does with a partial batch is
[[2026-08-27-an-unread-document-is-announced-not-absorbed]]; how a finding
reports which positions it came from is
[[2026-08-27-several-sources-are-counted-not-named]].

## The alternative that was rejected

**Failing the whole request when any document cannot be read.** It is the
simplest contract and it is the wrong trade for a stack of documents about one
patient: one unscannable page discards the analysis of everything submitted with
it, and the clinician's only recourse is to resubmit the batch minus the file
they have to identify by trial.

**Skipping it silently and answering an ordinary summary.** That is the
dangerous version of this change - a summary that looks complete and is not.
Everything else here (the `read` flag, the reason, the count of what was read,
the warning in the log, and the caution the interface shows) exists to make the
gap visible.

**Naming the document in the response or the log.** Clinical filenames routinely
carry patient names, so the filename is patient data leaving the boundary in the
response and sitting in a log file afterwards. The position costs the caller a
lookup it can always perform.

**Reading the batch concurrently, so one slow document does not hold the
others.** The model admits one document at a time by configuration, so gathering
them would queue on the same semaphore while holding every extracted text in
memory at once. Sequential reading is also what makes document-by-document
progress reportable at all.

## What it costs

- **A `200` can now mean "less than you asked for".** Any client that reads
  `summary` and ignores `documents[i].read` shows a clinician a partial answer
  as a complete one. The API cannot enforce that; the frontend entry above is
  the mitigation, and a third-party client has only the documentation.
- **`document_count` changed meaning.** It counts documents read, not documents
  submitted. A caller comparing it against its own upload count sees a
  discrepancy, which is the point - and a caller that treats it as an echo of
  the request is silently wrong.
- **The reason is coarse.** Every failure on this path is `no_text`, so a
  password-protected PDF, a scan with no text layer and a corrupt file are
  indistinguishable to the caller. Telling them apart is what the enum is left
  open for.
- **The log line is the only server-side trace.** It carries a position, so an
  operator investigating "which document failed" cannot answer it from the logs
  alone - by design, and still a real limit on diagnosis.

---

Written down on 2026-09-05 from `backend/README.md`, which carried the reasoning
inline. The change itself is `1b42313` (2026-08-27).
