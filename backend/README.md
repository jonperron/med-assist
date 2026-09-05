# Med-Assist Backend

This is the backend for the Med-Assist application, built with FastAPI and uv.

## Features

* Document upload (PDF, DOC, DOCX, TXT)
* Text extraction from medical documents
* Named Entity Recognition (NER) for medical terms
* Clinical summaries built from the extracted entities, one or many documents at a time
* Stateless analysis in a single request, storing nothing
* RESTful API with automatic OpenAPI documentation

This file says what the service does and how to run it. **Why it does it that
way - what was rejected, and what each choice costs - is in
[`openwiki/decisions/`](../openwiki/decisions/), one page per decision.** Each
section below links to the entries behind it.

## Getting Started

These instructions will get you a copy of the project up and running on your local machine for development and testing purposes.

### Prerequisites

* Python 3.12+
* [uv](https://docs.astral.sh/uv/getting-started/installation/)

### Configuration

The application reads its configuration from the environment. None of it is
secret: the service stores nothing and authenticates nobody, so there is no
datastore to reach and no key to hold. Anyone who can reach the port can use the
analysis routes - see [`deploy/README.md`](../deploy/README.md) before serving
this anywhere but your own machine.

**Environment Variables:**

* `NER_MODEL_NAME`: Path to the local model directory. Required.
* `APP_ENV`: Environment mode for the backend. Defaults to `production`. Set to `development` to enable development-only features such as mock endpoints; they are never mounted unless you opt in explicitly.
* `MAX_BATCH_FILES`: Largest number of documents accepted in one request (default: `20`). The per-file size ceiling bounds bytes, not inference time, so lower this on a small deployment.
* `NER_INFERENCE_THREADS` and `NER_MAX_CONCURRENT_INFERENCES`: see [Inference runs on the CPU](#inference-runs-on-the-cpu).
* `CORS_ALLOWED_ORIGINS`: Comma-separated browser origins allowed to call the
  API, each written as `scheme://host[:port]` with no trailing slash (default:
  `http://localhost:3000`). The list is enforced server-side as well as sent to
  browsers: a request to `/api` carrying an `Origin` outside it is refused with a
  fixed `403` before its body is read. A request carrying no `Origin` is let
  through; when there is none but a `Sec-Fetch-Site` header is present, that is
  used instead. Unset or empty keeps the default rather than widening. `*` is
  refused at startup, as is anything that is not an origin - a path, a query, a
  space in the host, a wildcard, a port that is not a number, an international
  domain outside its punycode form - naming the offending entry by position and
  never quoting it. A single trailing slash and a port the scheme implies
  (`:443` on https, `:80` on http) are dropped rather than refused.

`API_ACCESS_TOKEN` is no longer read. It is not in this list because nothing
consumes it; a deployment that still sets it gets a warning at startup saying
so, and an upgrading operator should read
[`deploy/README.md`](../deploy/README.md) before treating a proxy rule that
injects the header as access control.

Why this API authenticates nobody, and why the origin is nonetheless checked
server-side:
[the credential is removed and the deployment warns instead](../openwiki/decisions/2026-09-05-the-credential-is-removed-and-the-deployment-warns-instead.md)
and [the allowed CORS origins come from the environment](../openwiki/decisions/2026-08-28-cors-origins-come-from-the-environment.md).

**Example:**

```bash
export NER_MODEL_NAME="/app/models/"
export APP_ENV=production
```

### What is stored

Nothing. There is no datastore behind this service and no endpoint that writes
one:

* `POST /api/analyze` extracts text, runs NER and returns the merged summary - plus
  the per-document entities behind it - in the same response. It issues no file id,
  and leaves nothing to delete.
* `POST /api/analyze/stream` does the same work and stores no more, reporting each
  document as it is read so a caller can show progress. Nothing is held between
  events: the batch is one request from start to finish.
* The document text is never echoed back, and entity `start`/`end` offsets do not
  leave the server: `EntityDetail` excludes them from serialisation, which keeps
  them out of the response body and out of `openapi.json` while the summarizer
  still reads them to pair an examination with its value.
* Uploaded files above 1 MB are spooled to `TMPDIR` by the HTTP server before any route
  code runs. `docker-compose.yml` mounts a `tmpfs` at `/tmp` so those parts never reach
  the container's writable layer; a bare `uvicorn` run does not, and will write them to
  disk. This is the only place a submitted document touches a filesystem, and it is
  the reason `TMPDIR` is worth checking on any other deployment. The spooled file is
  unlinked as the request ends, so nothing accumulates - but it is invisible to `ls`
  while it exists, since it is an unnamed inode.
* How much can be spooled is bounded by `LimitRequestSize`, which refuses a body over
  50 MB. It checks `Content-Length` where one is declared and counts bytes on the
  receive channel where one is not, so a chunked upload cannot write past the ceiling
  and be refused afterwards.

A document is therefore analysed once per request. There is no analyse-once,
read-later flow: summarising the same document again means submitting it again,
at the cost of a fresh inference.

Behind this:
[the API stores nothing, and Redis is gone](../openwiki/decisions/2026-08-28-the-api-stores-nothing-and-redis-is-gone.md),
[entity offsets do not leave the server](../openwiki/decisions/2026-08-28-entity-offsets-do-not-leave-the-server.md),
and [the request ceiling and the container are both bounded](../openwiki/decisions/2026-08-28-the-request-ceiling-and-the-container-are-both-bounded.md).

### Summaries

`POST /api/analyze` takes one or more documents and answers a `summary`: the
readable product the rest of the pipeline exists for.

Several documents in one request are taken to be **about the same patient**. A
finding named in three of them is reported once, and findings are ordered by how
many documents support them. Each finding carries the indices of the documents it
was found in - the index is into the request's own file order, and this path never
needs a filename: no endpoint issues an id, and none echoes a filename back.

The summary is assembled, not generated. Every word in it is either a fixed heading
or a span the model marked in the submitted documents, so it cannot state anything
the documents did not - and no text leaves the process for a language model.

What `app/services/summarizer.py` produces:

* Five sections, in reading order: pathologies, signs and symptoms, examinations,
  treatments, localisations. `temporal`, `measurements` and `other` are left out
  of the summary and stay in the `documents` payload.
* A measurement reaches the summary only when it can be attached to the
  examination it sits beside: "Troponine I" and "1,10 ng/mL" become one finding
  under Examens. The value must start within `MEASUREMENT_GAP` characters of the
  end of the test's span, and only the nearest test before it can claim it. A
  value nothing claims stays out, and `poids` and `taille` are never paired.
* An opening demographic line built from the model's `age` and `genre` labels.
  The first mention of each wins.
* Deduplication that folds case, accents, inner spacing and edge punctuation,
  reporting the first surface form seen.
* A confidence floor of `MIN_CONFIDENCE`. This is the only use the model's score
  has, and it is never displayed.

Behind this:
[the summary keeps five categories and drops three](../openwiki/decisions/2026-08-26-the-summary-keeps-five-categories-and-drops-three.md)
and [a measurement is paired with the test beside it, or dropped](../openwiki/decisions/2026-08-27-a-measurement-is-paired-with-the-test-beside-it.md).

### Partial summaries

A document of a supported type that yields no text — a scan, or a file the parser
cannot open — does not cost the batch its summary. The request answers `200`, the
other documents are summarised, and `documents[i].read` is `false` for the one that
failed, with `unreadable_reason` naming why. `summary.document_count` then counts what
was read, not what was sent.

The whole batch is refused with `400` only when nothing at all could be read. Either
way the refusal and the partial answer name the failed document by its **position**,
never by its filename: `documents` is in submission order, and the caller already
holds the names it posted. Behind this:
[an unreadable document costs its position, not the batch](../openwiki/decisions/2026-08-27-an-unreadable-document-costs-its-position-not-the-batch.md).

### Watching a batch being read

A batch of four documents takes about half a minute on a CPU.
`POST /api/analyze/stream` takes the same body and does the same work, sending
Server-Sent Events as it goes:

* `batch` — how many documents were accepted. This is what a "2 of 4" counter divides by.
* `document` — one per document, in submission order, as each is read: its `index`, and
  whether it could be `read` at all.
* `result` — exactly the body `POST /api/analyze` would have returned for the same batch.
* `error` — the batch ended without a summary. `reason` says which kind of failure it
  is: `unreadable_batch` is the caller's document, the streamed equivalent of the `400`
  the other endpoint answers, and `server_error` is the service's own failure, its `500`.
  Branch on `reason`, not on `message` — the wording is for display and may be
  translated.

Each event's `data` is one JSON object tagged by `stage`, so a client narrows on the tag
rather than guessing. The endpoint is a `POST` because it carries the documents, so a
browser reads it with `fetch` and a `ReadableStream`; `EventSource` only issues `GET`.

Validation and the model-readiness check run as dependencies, before the stream
opens, so a rejected file type, an oversized batch and an unloaded model answer
`400`, `413` and `503` as JSON with no events at all. Only a failure that cannot
be known until documents are being read arrives as an `error` event.

Three things a client has to get right:

* **Skip frames that are not `data:`.** When the generator is idle longer than 15
  seconds, FastAPI inserts a `: ping` comment frame to hold the connection open through
  a proxy's idle timeout. A single large PDF can exceed that, so this is ordinary, not
  exotic. A reader that splits on a blank line and parses every frame will throw on the
  first ping.
* **Treat a stream that ends without `result` or `error` as a failure.** Once the first
  event is written the response is committed at `200`, so a fault in the transport layer
  below the endpoint - or a dropped connection - can only appear as a stream that stops.
  There is no status code left to send.
* **Read the event types from `components.schemas.AnalysisEvent`.** The generated client
  types the response body as `unknown`: `openapi-typescript` reads only `schema` from a
  media type, and an SSE payload is described by `itemSchema`. The union itself is
  generated, and is what a client narrows on `stage`.

Nothing is stored on this path either: no job id, nothing to poll, nothing to come
back for. Behind this:
[progress is a stream, because a job would have to be stored](../openwiki/decisions/2026-08-27-progress-is-a-stream-because-a-job-would-have-to-be-stored.md)
and, on the client side,
[the stream is the only analysis path the client takes](../openwiki/decisions/2026-08-27-stream-is-the-only-analysis-path-the-client-takes.md).

### Document dates

`documents[i].document_date` carries the date each document itself carries, and
`summary.date_range` the stretch from the earliest to the latest of them. Both are
`null` when nothing could be dated, which is a common answer and not an error.

The date is read from the document's text by `app/services/document_date.py` — not
from the file's timestamp, and not from the `temporal` entities. The rules:

* Only the head of the document is read (`HEAD_CHARACTERS`).
* Only a complete calendar date counts — day, month and a four-digit year, on the
  calendar. A two-digit year is refused.
* Numeric dates are read day-first. `03/13/2024` is refused rather than swapped.
* The first complete date in the head wins.
* A date a birth marker points at — "Née le 12/05/1948", "Date de naissance",
  "D.D.N." — is skipped. The lookback stops at the previous date in the text.
* A date in the future, or older than `EARLIEST_YEAR`, is skipped.

Nothing about this widens what is stored, and the date is never rendered into the
summary's wording — it is metadata beside it. Why each rule prefers no date to a
guess, and what that costs:
[a document is dated from its head, or not at all](../openwiki/decisions/2026-08-27-a-document-is-dated-from-its-head-or-not-at-all.md).

### Logging

No identifier is minted for a submitted document, so none is logged. Error paths log
the exception type and, where one applies, the document's position in the batch —
never the filename, the parser's message or a traceback.

### NER Model Configuration

The application uses Hugging Face transformers for Named Entity Recognition. Configure the following:

**Environment Variables:**

* `NER_MODEL_NAME`: Name of the Hugging Face model to use for NER
* `NER_INFERENCE_THREADS`: Threads torch may use for one inference (default: `0`, which keeps torch's own default of one thread per core). Set it to the container's CPU quota when there is one — torch reads the host's core count, not the quota, and spends the difference on contention.
* `NER_MAX_CONCURRENT_INFERENCES`: How many documents may be inside the model at once (default: `1`). Peak memory is then a function of the largest document rather than of how many arrived together.

**Example:**

```bash
export NER_MODEL_NAME="dbmdz/bert-large-cased-finetuned-conll03-english"
export NER_INFERENCE_THREADS=2
```

### Where the model comes from

The served model is `Dr-BERT/DrBERT-7GB` fine-tuned for token classification on
the DEFT 2021 corpus of French clinical cases. The training project builds it and
writes the weights, the fast tokenizer and a `metrics.json` into
`backend/models/`; it lives in its own repository, whose README covers how to
obtain the corpus and reproduce the model.

Those files are not in this repository and not in the image. `docker-compose.yml`
bind-mounts the directory read-only at `/app/models`, which is what
`NER_MODEL_NAME` points at; `MODEL_DIR` in `.env` moves the host side of that
mount. A retrained model is therefore a restart rather than a rebuild, and an
image run without the mount still starts, answering `503` on `/readyz` and on the
analysis routes.

The model emits fifteen entity types: the thirteen fine-grained DEFT 2020 types
(`anatomie`, `sosy`, `examen`, `traitement`, `substance`, `dose`, `mode`,
`frequence`, `duree`, `moment`, `date`, `pathologie`, `valeur`) plus `age` and
`genre`. Every one of them is categorised by
`app/services/entity_extractor/label_mappings/fr.json`; a label the mapping does
not know is reported at startup and lands in `other`. `age` and `genre` belong to
`patient_info`, which is what the summary's opening line is built from.

Behind this:
[the training project lives in its own repository](../openwiki/decisions/2026-08-26-the-training-project-lives-in-its-own-repository.md)
and [the model is mounted, not baked into the image](../openwiki/decisions/2026-08-31-the-model-is-mounted-not-baked-into-the-image.md).

### Inference runs on the CPU

The service never uses a GPU, and three things hold that to be true rather than
assume it:

* `pyproject.toml` pins `torch` to the PyTorch CPU wheel index. Check what a
  resolution actually gives you with `uv tree --package torch`.
* The pipeline is built with `device="cpu"`.
* Inference runs on a worker thread behind a semaphore
  (`NER_MAX_CONCURRENT_INFERENCES`), so a long document does not hold the event
  loop and concurrent uploads do not multiply the model's peak memory.

Note the queue in front of that semaphore is unbounded and has no acquisition
timeout, and a value above one shares a single transformers pipeline across
threads — prefer more worker processes. The measurements and the trade-offs are
in
[inference is CPU-only, and one document at a time](../openwiki/decisions/2026-08-18-inference-is-cpu-only-and-one-document-at-a-time.md).

### Long documents are read whole

A transformer reads a fixed window — 512 tokens for this model — and the pipeline
drops whatever does not fit without saying so. The extractor passes the pipeline a
`stride` of a quarter of that window, so it slides the window across the whole
document and reconciles the overlapping spans itself.

The stride needs a fast tokenizer and a declared window. When either is missing the
old behaviour applies — truncation, which cannot be seen in the response — and the
extractor logs a warning at load time saying so. Behind this:
[long documents are read with a sliding window](../openwiki/decisions/2026-08-18-long-documents-are-read-with-a-sliding-window.md).

### Startup and health

The model is loaded once, by the lifespan handler, before the first request.
Uvicorn opens its listening sockets only after that handler returns, so during
the load the port is closed rather than slow — a connection is refused, not
queued.

* `GET /healthz` is liveness: the process is up and the loop is answering. It
  says nothing about the model.
* `GET /readyz` is readiness. It answers `200 {"status": "ready"}` once the
  weights are in memory, and otherwise refuses with the same
  `{"detail": {"message": ...}}` envelope as every other route.
* A model that fails to load leaves the service up and permanently unready. The
  exception type is logged; the model path is not.
* The routes that need the model — `/api/analyze` and `/api/analyze/stream` —
  answer `503` while it is unloaded.

`docker-compose.yml` gives the backend a healthcheck on `/readyz` with a
`start_period` long enough to cover the load. Behind this:
[the model loads once, and a failed load stays unready](../openwiki/decisions/2026-08-31-the-model-loads-once-and-a-failed-load-stays-unready.md).

### Installation

1. **Clone the repository:**

    ```bash
    git clone https://github.com/your-username/med-assist.git
    cd med-assist/backend
    ```

2. **Install dependencies:**

    This command will install all the dependencies required for the project, including development dependencies.

    ```bash
    uv sync
    ```

## Running the Application

To run the application in a development environment, use the following command:

```bash
uv run uvicorn main:app --reload
```

The application will be available at `http://127.0.0.1:8000`.

## Running Tests

To run the automated tests for this system, use the following command:

```bash
uv run pytest
```

## API schema

`openapi.json` is the document the frontend generates its TypeScript types from. After
changing a route or a response model, re-export it:

```bash
uv run python scripts/export_openapi.py
```

`tests/test_openapi_contract.py` fails while the checked-in document differs from the
application, so a client cannot drift from the API unnoticed. Regenerate the frontend
types afterwards with `npm run generate:types` in `frontend/`.

## Contributing

Contributions are what make the open-source community such an amazing place to learn, inspire, and create. Any contributions you make are **greatly appreciated**.

This repository uses `pre-commit` to enforce code quality and style. Before committing, please make sure to install the pre-commit hooks:

```bash
uv run pre-commit install
```

Every choice between two defensible options gets a page in
[`openwiki/decisions/`](../openwiki/decisions/) — state the alternative that was
rejected and what the choice costs, not only what was chosen. Do not add that
reasoning back into this file.

If you have a suggestion that would make this better, please fork the repo and create a pull request. You can also simply open an issue with the tag "enhancement".

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request
