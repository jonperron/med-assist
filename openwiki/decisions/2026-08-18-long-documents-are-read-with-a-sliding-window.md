---
type: decision
title: 2026-08-18 - Long documents are read with a sliding window
description: The extractor passes the pipeline a stride of a quarter of the model's window so a document longer than 512 tokens is read whole, and warns at load time when the tokenizer cannot support one.
tags: [backend, model, correctness]
---

# 2026-08-18 - Long documents are read with a sliding window

## What was decided

A transformer reads a fixed window - 512 tokens for the BERT family this model
belongs to - and the transformers pipeline drops whatever does not fit without
saying so. The response still looks complete: the entities that come back are
real, and the ones from the tail of the document were never looked for. On a
real discharge summary that is most of the document.

`EntityExtractor.sliding_window_arguments` computes a `stride` of
`model_max_length // WINDOW_OVERLAP_DIVISOR`, with the divisor at `4`, and
passes it on every call. The pipeline then slides the window across the whole
document and reconciles the overlapping spans itself. A quarter-window overlap
is what keeps an entity lying across a chunk boundary whole in at least one of
the two chunks it appears in.

The stride needs two things the tokenizer may not have: it must be a fast
tokenizer, because transformers refuses a stride otherwise, and it must declare
a real window - `model_max_length` doubles as a sentinel for "no limit", so a
value at or above `UNBOUNDED_WINDOW` (100 000) is read as no window rather than
as a very large one. When either is missing the arguments are empty, the old
behaviour applies, and `report_truncation_risk` logs a warning at load time
saying the tail of a long document is not analysed.

## The alternative that was rejected

**Chunking the text ourselves before calling the pipeline.** Splitting on
sentence or paragraph boundaries, running each piece and concatenating the
entities. It is more control and it is more code that has to be right: offsets
have to be rebased onto the original text (the summarizer pairs measurements by
them), spans crossing a boundary have to be merged, and duplicate mentions from
the overlap have to be folded. The pipeline already does all of that for a
stride, and it does it against the tokenizer's own view of the window rather
than against a character count that approximates it.

**Truncating loudly instead - refusing a document longer than the window.** It
is honest, and it makes the product useless for the documents it exists for. A
discharge summary is routinely several times 512 tokens.

**Leaving the truncation and documenting the limit.** That is the state this
change ended. The limit was invisible in the response, which is the property
that made it unacceptable: nothing distinguishes "no pathology in the tail" from
"the tail was never read".

## What it costs

- **Inference time grows with document length.** Every window costs a forward
  pass, and the overlap means a quarter of the document is read twice. On CPU
  that is the dominant cost of a long document, and it is why a batch takes the
  time it does.
- **The fallback is a log line, not a response field.** A deployment whose
  tokenizer is slow or unbounded gets truncated analysis and one warning at
  startup. Nothing in the response, and nothing in the interface, says the
  document was cut. An operator who misses the line has no second chance to
  notice.
- **The reconciliation is the library's.** How overlapping spans are merged is
  transformers' behaviour under `aggregation_strategy="max"`, not this
  repository's. A version bump can change where a boundary-spanning entity is
  reported without any test here failing, because the tests assert that a long
  document yields entities past the window, not how the overlap was resolved.
- **A quarter is a choice, not a measurement.** It keeps entities of up to a
  quarter-window whole, which covers every clinical span seen so far by a wide
  margin. It was not tuned against a corpus.

---

Written down on 2026-09-05 from `backend/README.md`, which carried the reasoning
inline. The change itself is `03d115b` (2026-08-18).
