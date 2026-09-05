---
type: decision
title: 2026-08-18 - Inference is CPU-only, and one document at a time
description: torch is pinned to the CPU wheel index, the pipeline is built with device="cpu", and a semaphore admits one document to the model at a time.
tags: [backend, footprint, model, privacy]
---

# 2026-08-18 - Inference is CPU-only, and one document at a time

## What was decided

Three separate mechanisms hold "this service never uses a GPU, and its memory
does not scale with traffic" to be true rather than assume it.

**The runtime cannot install a GPU build.** `backend/pyproject.toml` declares
the PyTorch CPU wheel index as an explicit source and pins `torch` to it:

```toml
[[tool.uv.index]]
name = "pytorch-cpu"
url = "https://download.pytorch.org/whl/cpu"
explicit = true

[tool.uv.sources]
torch = { index = "pytorch-cpu" }
```

The default PyPI `torch` resolves to the CUDA build on Linux and pulls the whole
`nvidia-*` wheel set with it. Measured: the pin takes the installed backend
environment from 4.6 GB to 1.2 GB, all of it code that would never have been
executed. `uv tree --package torch` is what says which resolution you actually
got.

**The pipeline names the device anyway.** `entity_extractor.py` builds the
transformers pipeline with `device=INFERENCE_DEVICE`, which is `"cpu"`. With the
CPU wheel installed this is what would happen regardless; saying it means a host
that happens to carry an accelerator does not silently start copying clinical
text onto it. The pin is a packaging fact and can be undone by an environment
built another way; this line travels with the code.

**One document is inside the model at a time.** `extract_entities` takes an
`anyio.Semaphore` slot and then runs the blocking work through
`run_in_threadpool`, so the event loop keeps answering while a long document is
being read, and peak memory is a function of the largest document rather than of
how many arrived together. `NER_MAX_CONCURRENT_INFERENCES` sets the number of
slots and defaults to `1`. The semaphore is anyio's rather than asyncio's
because the extractor is a process-wide singleton and asyncio's binds itself to
the first loop that awaits it, which turns a second loop in the same process
into a `RuntimeError`.

`NER_INFERENCE_THREADS` caps the threads torch spends on one inference, and
defaults to `0`, which leaves torch's own default alone. What it is for, and the
20x measurement behind setting it to the container's CPU quota, is in
[[2026-08-28-the-request-ceiling-and-the-container-are-both-bounded]].

## The alternative that was rejected

**Taking `torch` from PyPI and letting the deployment decide.** That is the
smaller diff, and it is what makes a GPU deployment a configuration change
rather than a fork. It also puts several gigabytes of CUDA runtime into every
image built for a service that has no GPU code path, and it makes "does clinical
text ever reach an accelerator" a question about the host rather than about this
repository. A product whose claim is that documents stay on one machine should
not ship the machinery for moving them somewhere faster.

**Letting inference run concurrently and sizing the container for the peak.**
Transformers holds activations per call, so N concurrent documents cost N times
the largest one. Sizing for that means a memory limit set for a burst that
almost never happens, and an OOM kill when it does; serialising means the second
document waits. Waiting is the failure that can be explained to the person
watching the progress card.

**A queue with a depth limit and a fast refusal.** Rejected for now, and it is
the honest fix for the cost below. It needs a refusal shape, a status code and a
frontend branch, none of which existed in this change.

## What it costs

- **The queue in front of the semaphore is unbounded, and has no acquisition
  timeout.** A request waiting for a slot holds the text it extracted in memory
  the whole time. Enough concurrent batches therefore grow memory while
  `NER_MAX_CONCURRENT_INFERENCES` is doing exactly what it was set to do.
  `--limit-concurrency` on uvicorn is the only thing bounding this today, and it
  bounds connections rather than queued documents.
- **Raising the setting above one is not obviously safe.** It shares a single
  transformers pipeline across worker threads, which transformers does not
  document as thread-safe. More worker processes is the supported way to use
  more cores; the setting stays because the deployment that wants it should be
  able to try it, not because it is endorsed.
- **A batch of long documents is slow, and visibly so.** CPU inference on a
  two-core quota takes minutes for a stack of discharge summaries. That latency
  is why the streaming endpoint exists at all.
- **The pin is a resolution instruction, not an enforcement.** Nothing at
  startup checks which build of torch is installed. An environment built with
  plain `pip install torch` gets the CUDA wheel, and only `device="cpu"` then
  stands between the model and an accelerator.

---

Written down on 2026-09-05 from `backend/README.md`, which carried the reasoning
inline. The change itself is `03d115b` (2026-08-18).
