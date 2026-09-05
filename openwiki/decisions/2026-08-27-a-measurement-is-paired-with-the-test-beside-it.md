---
type: decision
title: 2026-08-27 - A measurement is paired with the test beside it, or dropped
description: A value reaches the summary only by being attached to an examination within MEASUREMENT_GAP characters, claimed by the nearest preceding test; weight and height are never paired.
tags: [backend, summary, safety]
---

# 2026-08-27 - A measurement is paired with the test beside it, or dropped

## What was decided

"Troponine I" and "1,10 ng/mL" are two spans in two categories, and either alone
is worth less to a clinician than the pair: a test with no result, or a number
with no test. `pair_measurements` joins them, and that join is the only way a
measurement reaches the summary at all - loose values stay out, for the reason
[[2026-08-26-the-summary-keeps-five-categories-and-drops-three]] gives.

The rule is positional, not semantic:

- A value is attached only when it **starts within `MEASUREMENT_GAP` (12)
  characters** after the end of an examination span. A value that belongs to a
  test sits right against its name - `Troponine I : 1,10 ng/mL`, `TA 148/92
  mmHg` - with punctuation and a space or two between. Past that the next clause
  has begun, and the pairing would be a guess about which number belongs to
  which test. That guess is the reason loose measurements are kept out in the
  first place; making it here would only move it.
- **Only one test can claim a value**, and tests are served latest-ending first.
  In "Troponine, BNP : 900 pg/mL" the value goes to BNP. Served the other way
  round, Troponine is inside the gap too and claims it first, and the summary
  then states a result against a test that did not produce it.
- **A span with no offsets is never paired.** The offsets are optional on the
  model and unset for a span the extractor did not locate. They are read here
  and nowhere else - `EntityDetail` excludes them from serialisation, per
  [[2026-08-28-entity-offsets-do-not-leave-the-server]] - so this runs before
  their only consumer.
- **`poids` and `taille` are never paired.** They sit in the measurements
  category and are patient attributes rather than results of an investigation. A
  weight that happens to sit near an examination name is a wrong pairing, and
  either one in the summary adds a quasi-identifier to the one page a clinician
  exports.

The attribute rule is written as a deny-list rather than as an allow-list naming
the one label that is a result, because the two fail in opposite directions
across label mappings. `fr.json` files `valeur`, `poids` and `taille` in this
category; `es.json` files `valor` and `medida`, both results. An allow-list
naming the French label would pair nothing at all under the Spanish mapping -
every value gone from every summary, with nothing in the response to say so.
Excluding the attributes leaves a mapping that names neither of them fully
working.

## The alternative that was rejected

**Pairing by meaning - a unit table, or a model that knows a troponin value from
a blood pressure.** It is the correct answer to the question and it is a second
model, with its own failure modes, inside a pipeline whose whole claim is that
it states nothing the documents did not.

**Widening the gap so fewer values are dropped.** Every character of width buys
recall and pays for it in wrong attributions, and a wrong attribution here is a
confident, readable, false clinical sentence - strictly worse than a missing
value, which the clinician can find in the document.

**Nearest-following rather than nearest-preceding.** A document enumerating its
tests before the value - "TA et FC : 148/92 mmHg" - reads the same way and means
the opposite, and no single ordering answers both. `Test : valeur` is the
dominant layout, so nearest-preceding is the better default. It is a default,
not a proof.

## What it costs

- **Values are silently dropped.** A value nothing claims does not appear
  anywhere in the summary, and the summary does not say a number was seen and
  left out. The `documents` payload still carries it; nobody reading the summary
  is looking there.
- **A wrong pairing is invisible.** The paired text is one string - "Troponine I
  1,10 ng/mL" - with no marker saying the two halves came from two spans joined
  by a distance rule. A reader cannot tell a pairing from a span the model
  marked whole.
- **It inherits the extractor's per-document deduplication.** A repeated span
  keeps its first occurrence and that occurrence's offsets, so a test named once
  in prose and again beside its result is held at the first position. The value
  then goes unclaimed - the safe direction, and still a lost value.
- **Twelve characters is a judgement about typography.** It was chosen against
  the layouts in the corpus at hand, not tuned, and a document that separates a
  test from its result by a longer separator (a padded table column, a tab run)
  loses the pairing.

---

Written down on 2026-09-05 from `backend/README.md`, which carried the reasoning
inline. The change itself is `1b42313` (2026-08-27).
