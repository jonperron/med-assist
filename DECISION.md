# Decisions

Why the code looks the way it does, where the reason is not visible in the code
itself. Rule 10 of AGENTS.md: every deviation from the coding rules, and every
choice between two defensible options, is written down here.

## 2026-08-25 — The product is a summary, not an entity dump

The mission has always been "an actionable summary for clinicians". What the code
delivered was every span the model marked, ungrouped, undeduplicated, each with a
confidence percentage beside it. Five decisions turn that back into the product.

### Confidence percentages are gone from the interface

A percentage beside a clinical finding invites the reader to weigh it. A token
classifier's softmax does not support that judgement: it is a calibration
artefact of the training distribution, not a probability that the finding is
clinically real. A physician reading "carcinome hépatocellulaire (87%)" has been
handed a number that looks like evidence and is not.

The score is kept in the API payload and used for exactly one thing: a noise
floor, `MIN_CONFIDENCE` in `summarizer.py`, below which a span is dropped rather
than shown weakly. Nothing renders it.

### Pseudonymisation was removed

Masking existed to make output safe to send somewhere. Nothing is sent anywhere:
inference is local, there is no language model in the pipeline, and the whole
project is built around the document not leaving the machine. So the pass was
masking patient data from the clinician treating the patient — the one reader
who needs it — while adding 374 lines across two services, a config flag, two
route parameters, a response field and a frontend checkbox.

Removing it does not waste the training work. DECISION.md's earlier entry notes
that `age` and `genre` were trained in partly to feed the pseudonymizer; they now
supply the summary's opening line instead, which is a better use of them.

Two things this loses, stated plainly: output is no longer safe to paste into an
external tool, and the `identifier_detector.py` patterns (names behind a civility,
NIR, IPP/NIP/NDA, phone, email, postal codes) are gone with it. If output ever
needs to leave the premises, this is the commit to read — but it should come back
as an export-time concern, not as a pass over every response.

The `homme`/`femme` mis-mapping described above is now inert rather than
dangerous: `fr.json` still files those MeSH axes under `patient_info`, but nothing
masks on that basis any more. The model is not trained on MeSH axes, so it does
not emit them. The mapping is still wrong and still must be fixed before any MeSH
axis is trained.

### Several documents are one patient

`POST /api/analyze` now takes a list and merges it. The alternative — a summary
per document, side by side — leaves the reader to do the deduplication, which is
the work the tool exists to do.

The assumption this rests on is explicit and unverified: documents submitted
together are about the same patient. Nothing checks it, because nothing can
without identifiers the project deliberately does not extract or store. It is
stated in the API docs, the README and the upload control rather than enforced.

Findings are ordered by how many documents support them, and the count is not
displayed — it orders the list, it is not a second number for the reader to weigh.

### `temporal`, `measurements` and `other` are not sections

A bare list of durations ("trois jours, la veille, six mois"), of loose values
("12 g/dL, 3 cm") or of unclassified spans carries no clinical meaning once
separated from the sentence it came from. Rendering them would restore exactly
the noise this change removes.

They are still in the `documents` payload, so no data is lost — only the claim
that they read as a summary. A chronological summary is the obvious next step and
needs the temporal spans *anchored* to the findings they modify, which the current
flat category output cannot express.

### The analyse endpoint no longer echoes the document text

`AnalysisResponse.text` returned the whole document to the caller. With no masking
pass to demonstrate, it was echoing the input back: the summary is what was asked
for, and the text is the largest thing that could leave the server. It is gone
from the response.

This is a breaking API change, taken deliberately: `/api/analyze` now answers
`{summary, documents, mapping_info, retained}` and accepts `files` rather than
`file`. The storing endpoints keep their shape.

## 2026-08-25 — The served NER model is trained in this project

Until now `backend/models/` held an artifact nobody in the repository could
reproduce: mounted, undocumented, unimprovable. It is now built by fine-tuning
[`Dr-BERT/DrBERT-7GB`](https://huggingface.co/Dr-BERT/DrBERT-7GB) — a French
biomedical RoBERTa, Apache-2.0, pretrained on the open NACHOS corpus — for token
classification on the DEFT 2021 corpus of French clinical cases.

Four decisions were taken along the way.

### Nested mentions are resolved innermost-first

58% of the corpus's mentions are nested — `anatomie` inside `sosy`, `valeur`
inside `examen` — and a token classifier gives each token exactly one label.
Each character is assigned to the **shortest** mention covering it, so the inner
mention survives whole and the outer one is trained as the runs it keeps.

Measured over the corpus: 76% of mentions keep their exact boundaries, 24% are
truncated (`sosy` 63%, `traitement` and `pathologie` 43%), and 8 of 22,224
disappear.

The alternative, letting the longest mention win, keeps clean outer boundaries
and costs 92% of `anatomie` and 82% of `valeur` — the anatomy category would
arrive almost empty, and anatomy is one of the categories the interface shows.

Two layered models, or one encoder with two tagging heads, would keep both
mentions whole. Both were rejected for a first version: a second encoder doubles
memory and CPU per document, against the footprint the project claims, and a
two-head model means rewriting `EntityExtractor` away from
`transformers.pipeline("ner")` and the sliding-window aggregation that comes
with it. If truncation proves too expensive in practice, a second tagging layer
is the next step — not a different priority rule.

### The model learns fifteen types, not forty-six

The thirteen fine-grained DEFT 2020 types, plus `age` and `genre`. All fifteen
were already categorised by `fr.json`, so the API contract did not move, and
`age`/`genre` give the pseudonymizer a model-based source for patient
demographics instead of leaving them to `identifier_detector.py`.

The 23 MeSH disease axes in the corpus were left out. Several have fewer than
fifty examples, and — worth knowing — `fr.json` files the axes `homme` and
`femme` under `patient_info`. Those axes are *male and female urogenital
diseases*, not demographics, so a model emitting them would have the
pseudonymizer mask disease mentions as patient identifiers and, worse, mask
every later occurrence of the same word. That mis-mapping predates this work and
was deliberately left untouched (Rule 3). It must be fixed before any MeSH axis
is trained.

### Only 275 of the corpus's 717 documents are used

The corpus was annotated in three passes. Only the 2021 pass covers every label
this model learns; the other 442 documents carry demographic annotation alone,
so their symptoms and treatments are unmarked. Training on them would teach the
model that a symptom is not a symptom. The official 2021 split is kept as it
stands — 167 train, 108 test — so the numbers can be read beside published ones.

### Training is a separate repository, not a dependency group

The plan of record was a `training` dependency group inside `backend/`. It
cannot work: `backend/pyproject.toml` pins `torch` to the PyTorch CPU wheel
index for the whole project, uv resolves one `torch` per project, and training
wants the CUDA build. Making that pin conditional would risk the runtime
resolving the CUDA wheels again — the 4.6 GB to 1.2 GB regression the project
fought for deliberately.

So `backend/training/` is its own git repository with its own lockfile, ignored
by this one, versioned privately because the corpus is clinical data. The
backend's resolution is provably untouched: `backend/uv.lock` has no diff.

It is not a submodule. This repository is public and that one is private; a
gitlink would leave contributors pointing at something they cannot fetch.

One consequence to know about: `git clean -xfd` run here deletes ignored paths,
and that now includes the training repository and the corpus inside it.
