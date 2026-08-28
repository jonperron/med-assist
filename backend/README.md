# Med-Assist Backend

This is the backend for the Med-Assist application, built with FastAPI and uv.

## Features

* Document upload (PDF, DOC, DOCX, TXT)
* Text extraction from medical documents
* Named Entity Recognition (NER) for medical terms
* Clinical summaries built from the extracted entities, one or many documents at a time
* Stateless analysis in a single request, storing nothing
* RESTful API with automatic OpenAPI documentation

## Getting Started

These instructions will get you a copy of the project up and running on your local machine for development and testing purposes.

### Prerequisites

* Python 3.12+
* [uv](https://docs.astral.sh/uv/getting-started/installation/)

### Configuration

The application reads its configuration from the environment. None of it is
secret: the service stores nothing, so there is no datastore to reach and no
key to hold.

**Environment Variables:**

* `NER_MODEL_NAME`: Path to the local model directory. Required.
* `APP_ENV`: Environment mode for the backend. Defaults to `production`. Set to `development` to enable development-only features such as mock endpoints; they are never mounted unless you opt in explicitly.
* `MAX_BATCH_FILES`: Largest number of documents accepted in one request (default: `20`). The per-file size ceiling bounds bytes, not inference time, so lower this on a small deployment.
* `NER_INFERENCE_THREADS` and `NER_MAX_CONCURRENT_INFERENCES`: see [Inference runs on the CPU](#inference-runs-on-the-cpu).

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
* The document text is never echoed back. The summary is the product, and returning
  the text would widen what leaves the server for no gain.
* Entity `start`/`end` offsets index the text the document yielded, which the API
  does not return. They locate a span only for a caller that still holds the
  document.
* Uploaded files above 1 MB are spooled to `TMPDIR` by the HTTP server before any route
  code runs. `docker-compose.yml` mounts a `tmpfs` at `/tmp` so those parts never reach
  the container's writable layer; a bare `uvicorn` run does not, and will write them to
  disk. This is the only place a submitted document touches a filesystem, and it is
  the reason `TMPDIR` is worth checking on any other deployment.

A document is therefore analysed once per request. There is no analyse-once,
read-later flow: summarising the same document again means submitting it again,
at the cost of a fresh inference. The endpoints that once stored documents were
removed on 2026-08-28 - see the decision entry in `openwiki/decisions/`.


### Summaries

`POST /api/analyze` takes one or more documents and answers a `summary`: the
readable product the rest of the pipeline exists for.

Several documents in one request are taken to be **about the same patient**, which
is what makes merging them meaningful. A finding named in three of them is reported
once, and findings are ordered by how many documents support them. Each finding
carries the indices of the documents it was found in, so a caller can name the source
beside it — the index is into the request's own file order, and this path never needs
a filename to travel: no endpoint issues an id, and none echoes a filename back.

The summary is assembled, not generated. Every word in it is either a fixed heading
or a span the model marked in the submitted documents, so it cannot state anything
the documents did not — and no text leaves the process for a language model.

What shapes it, in `app/services/summarizer.py`:

* Five sections, in reading order: pathologies, signs and symptoms, examinations,
  treatments, localisations. `temporal`, `measurements` and `other` are deliberately
  left out — a bare list of durations or loose values carries no clinical meaning
  once separated from its sentence. They stay in the `documents` payload.
* A measurement does reach the summary when it can be attached to the examination it
  sits beside: "Troponine I" and "1,10 ng/mL" become one finding under Examens. The
  attachment is positional — the value must start within `MEASUREMENT_GAP` characters
  of the end of the test's span, and only the nearest test before it can claim it —
  because past that distance, which number belongs to which test is a guess, and that
  guess is what keeps loose values out in the first place. A value nothing claims
  stays out. `poids` and `taille` are never paired: they sit in the same category but
  are patient attributes rather than results, and belong no more in an exported
  summary than the demographic line already there.
* An opening demographic line built from the model's `age` and `genre` labels. The
  first mention of each wins, so a relative's age quoted further down does not
  overwrite the patient's.
* Deduplication that folds case, accents, inner spacing and edge punctuation, keeping
  the longest surface form seen — the model truncates outer mentions, so the longest
  is the most complete one (see the decision log on the local wiki).
* A confidence floor of `MIN_CONFIDENCE`. This is the only use the model's score has,
  and it is never displayed: a percentage next to a clinical finding invites a reader
  to weigh it, which is not a judgement a token classifier's softmax supports.

`POST /api/analyze` does not echo the document text back. The summary is the product,
and returning the text would widen what leaves the server for no gain.

### Partial summaries

A document of a supported type that yields no text — a scan, or a file the parser
cannot open — no longer costs the batch its summary. The request answers `200`, the
other documents are summarised, and `documents[i].read` is `false` for the one that
failed, with `unreadable_reason` naming why. `summary.document_count` then counts what
was read, not what was sent.

The whole batch is refused with `400` only when nothing at all could be read, since
there is no summary to degrade to. Either way the refusal and the partial answer name
the failed document by its **position**, never by its filename: `documents` is in
submission order, and the caller already holds the names it posted.

### Watching a batch being read

A batch of four documents takes about half a minute on a CPU, and one spinner over the
lot says nothing about whether it is progressing. `POST /api/analyze/stream` takes the
same body and does the same work, sending Server-Sent Events as it goes:

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

Two properties are worth stating, because both are easy to lose:

* **Progress carries no clinical content.** A `document` event is a position, a boolean
  and a reason code. Nothing the model marked, and no filename, travels before the
  `result` event - which carries exactly what the other endpoint would have sent, and
  nothing more.
* **A refusal is still a status code.** Validation and the model-readiness check run as
  dependencies, before the stream opens, so a rejected file type, an oversized batch and
  an unloaded model answer `400`, `413` and `503` as JSON with no events at all. Only a
  failure that cannot be known until documents are being read - a batch nothing could be
  read from, or a server fault - arrives as an `error` event, because by then the
  response is already committed at `200`.

Nothing is stored on this path either. There is no job id, nothing to poll and nothing
to come back for, which is the reason it is a stream rather than a job: a pollable job
would have to hold a patient's summary on the server between requests.

### Document dates

A date is how a clinician places a document: a letter from last week and a letter from
2019 mean different things, and a stack of documents about one patient is read along the
time it covers. `documents[i].document_date` carries the date each document itself
carries, and `summary.date_range` the stretch from the earliest to the latest of them.
Both are `null` when nothing could be dated, which is a common answer and not an error.

The date is read from the document's text by `app/services/document_date.py` — not from
the file's timestamp, which dates a 2019 letter to the day it was downloaded, and not
from the `temporal` entities, which are every date-like span found anywhere in the text.
Picking the document's own date out of that is a judgement, and a date that is wrong
moves the document on the timeline the clinician is reading without saying so. Every
rule below therefore prefers no date to a guess:

* Only the head of the document is read (`HEAD_CHARACTERS`). A letter is dated in its
  letterhead; a date deep in the body belongs to what the document reports.
* Only a complete calendar date counts — day, month and a four-digit year, on the
  calendar. A two-digit year is refused rather than given a century.
* Numeric dates are read day-first, the convention the documents are written in.
  `03/13/2024` is refused rather than swapped.
* The first complete date in the head wins. In "Hospitalisation du 2 mars 2024 au 5
  mars 2024" that is the start of what the document reports. A range written the elided
  way — "du 2 au 5 mars 2024" — holds only one complete date, its last, so the document
  is placed at the end of the stay rather than at the start.
* A date a birth marker points at — "Née le 12/05/1948", "Date de naissance" — is
  skipped. It would be wrong by decades, and a date of birth is a patient identifier,
  not document metadata. The lookback survives the layouts a header arrives in — padded
  columns, a label and its value on two lines, tabs, "D.D.N." — and stops at the
  previous date in the text, so a birth date does not suppress the real date behind it.
  It is a list of markers, though: a birth date introduced by wording it does not know
  is published as the document's date.
* A date in the future, or older than `EARLIEST_YEAR`, is skipped.

Nothing about this widens what is stored: `POST /api/analyze` still stores nothing, and
the date is read from the text and returned while the text itself is dropped as before.
The date is never rendered into the summary's wording — it is metadata beside it.

### Logging

The file id is the only identifier that may be logged. Clinical filenames routinely carry
patient names, and parser errors quote the bytes that failed to parse, so error paths log
the file id and the exception type — never the filename, the message or a traceback.

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

The served model is not a Hub artifact picked off the shelf: it is
`Dr-BERT/DrBERT-7GB` fine-tuned for token classification on the DEFT 2021
corpus of French clinical cases. The training project builds it and writes the
weights, the fast tokenizer and a `metrics.json` into `backend/models/`, which
`docker-compose.yml` mounts as `NER_MODEL_NAME`.

That project lives in its own repository — the training corpus is clinical data
and cannot be distributed here, and training wants the CUDA build of `torch`
while this service pins the CPU build. Its README covers how to obtain the
corpus and reproduce the model.

The model emits fifteen entity types: the thirteen fine-grained DEFT 2020 types
(`anatomie`, `sosy`, `examen`, `traitement`, `substance`, `dose`, `mode`,
`frequence`, `duree`, `moment`, `date`, `pathologie`, `valeur`) plus `age` and
`genre`. Every one of them is categorised by
`app/services/entity_extractor/label_mappings/fr.json`; a label the mapping does
not know is reported at startup and lands in `other`.

`age` and `genre` matter beyond their category. They belong to `patient_info`,
which is what the summary's opening line is built from — so the model supplies
the patient's age and sex itself rather than leaving them to a pattern match.

### Inference runs on the CPU

The service never uses a GPU, and three things hold that to be true rather than
assume it:

* `pyproject.toml` pins `torch` to the PyTorch CPU wheel index. The default PyPI
  `torch` resolves to the CUDA build on Linux and pulls the whole `nvidia-*` wheel
  set with it; the pin takes the installed environment from 4.6 GB to 1.2 GB.
  Check what a resolution actually gives you with `uv tree --package torch`.
* The pipeline is built with `device="cpu"`, so a host that happens to carry an
  accelerator does not start copying clinical text onto it.
* Inference runs on a worker thread behind a semaphore, so a long document does
  not hold the event loop and concurrent uploads do not multiply the model's
  peak memory. Note the queue itself is unbounded: requests waiting for the slot
  hold their extracted text in memory, and there is no acquisition timeout.
  Above one, the setting shares a single transformers pipeline across threads,
  which transformers does not document as safe — prefer more worker processes.

### Long documents are read whole

A transformer reads a fixed window — 512 tokens for this model — and the
pipeline drops whatever does not fit without saying so, which loses the tail of
a real discharge summary while the response still looks complete. The extractor
passes the pipeline a `stride` of a quarter of that window, so it slides the
window across the whole document and reconciles the overlapping spans itself. A
quarter-window overlap keeps an entity lying across a boundary whole in one of
the two chunks it appears in.

The stride needs a fast tokenizer and a declared window. When either is missing
the old behaviour applies, and the extractor logs a warning at load time saying
so — truncation cannot be seen in the response.

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
  answer `503` while it is unloaded, so a failed load costs one refusal per
  request rather than a fresh multi-second load attempt each time
  (`functools.lru_cache` does not memoise an exception).

`docker-compose.yml` gives the backend a healthcheck on `/readyz` with a
`start_period` long enough to cover the load.

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

If you have a suggestion that would make this better, please fork the repo and create a pull request. You can also simply open an issue with the tag "enhancement".

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request
