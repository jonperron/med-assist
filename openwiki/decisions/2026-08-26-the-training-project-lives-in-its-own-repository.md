---
type: decision
title: 2026-08-26 - The training project lives in its own repository
description: The served model is DrBERT fine-tuned on DEFT, and the project that trains it is kept out of this repository because it holds a clinical corpus and a CUDA environment.
tags: [model, deployment, privacy, backend]
---

# 2026-08-26 - The training project lives in its own repository

## What was decided

The served model is not a Hub artifact picked off the shelf. It is
`Dr-BERT/DrBERT-7GB` fine-tuned for token classification on the DEFT 2021 corpus
of French clinical cases. The training project builds it and writes the weights,
the fast tokenizer and a `metrics.json` into `backend/models/`.

That project is a separate repository, private, and only its output is consumed
here. Two reasons, and either alone would be enough:

- **Its corpus is clinical data.** DEFT is French clinical cases under its own
  terms; it cannot be redistributed from a public repository, and the boundary
  in AGENTS.md section 9 does not have an exception for training material.
- **Its dependencies are the opposite of this service's.** Training wants the
  CUDA build of `torch`; this service pins the CPU wheel index precisely so that
  build cannot be installed - see
  [[2026-08-18-inference-is-cpu-only-and-one-document-at-a-time]]. One
  `pyproject.toml` cannot hold both without one of them being wrong.

Both exclusions are enforced rather than assumed. `.gitignore` carries
`backend/training/` and `models/`; `backend/.dockerignore` carries `training/`
first, because the build context is uploaded to the Docker daemon and cached
there whether or not any `COPY` mentions it - `.gitignore` does not apply to a
build context. The weights themselves are mounted rather than copied, per
[[2026-08-31-the-model-is-mounted-not-baked-into-the-image]].

**What the model emits is a contract this repository holds.** Fifteen entity
types: the thirteen fine-grained DEFT 2020 types (`anatomie`, `sosy`, `examen`,
`traitement`, `substance`, `dose`, `mode`, `frequence`, `duree`, `moment`,
`date`, `pathologie`, `valeur`) plus `age` and `genre`. Every one is categorised
by `app/services/entity_extractor/label_mappings/fr.json`, and a label the
mapping does not know is reported at startup and lands in `other`. `age` and
`genre` are the reason the summary can open with the patient's age and sex from
the model itself rather than from a pattern match over the text.

## The alternative that was rejected

**Keeping training in this repository, with the corpus fetched at build time.**
It is one repository, one history, and a model whose provenance can be read
beside the code that serves it. It also puts a clinical corpus one wrong
`.gitignore` line away from a public repository, and a wrong line there is not
recoverable by a later commit. The distribution terms settle it independently.

**Serving a stock Hub model and dropping the fine-tune.** A general French NER
model marks people, places and organisations, which is the opposite of what this
product needs, and a biomedical model with no fine-tune does not emit the
fine-grained DEFT types the categories are built from. The label mapping - and
with it the five summary sections - would have to be rewritten around whatever
the stock model happened to emit.

**Publishing the trained weights alongside the code.** They are ~420 MB of
derived artifact whose licence follows the corpus it was trained on. Not settled
here, and not this repository's to settle.

## What it costs

- **The model cannot be reproduced from this repository.** A contributor with a
  clone has code, tests and no weights, and nothing here tells them how the
  model was trained beyond a citation. The training project's README covers
  obtaining the corpus and reproducing the model; that README is not public
  either.
- **The two repositories can drift.** The label mapping here is written against
  what the model emits, and nothing links a mapping version to a weights
  version. A retrained model with a renamed label degrades quietly: the affected
  spans land in `other` and disappear from the summary, with one startup log
  line as the only signal.
- **A private dependency is a bus factor.** Whoever holds the training
  repository holds the ability to produce a new model; nobody else can, and the
  public artifact gives no way to verify the one they are running is the one
  described here.
- **The citation is the only provenance a reader gets.** The root README's
  references name DrBERT and the DEFT campaigns, which says what the model is
  and not which run produced the file in `backend/models/`.

---

Written down on 2026-09-05 from `backend/README.md`, which carried the reasoning
inline. The model change itself is `35b58bd` (2026-08-26).
