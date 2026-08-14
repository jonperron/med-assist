# Med-Assist Backend

This is the backend for the Med-Assist application, built with FastAPI and uv.

## Features

* Document upload (PDF, DOC, DOCX, TXT)
* Text extraction from medical documents
* Named Entity Recognition (NER) for medical terms
* Stateless analysis in a single request, storing nothing
* Encrypted, entity-only Redis storage for documents kept for later
* Optional pseudonymisation of detected patient identifiers
* RESTful API with automatic OpenAPI documentation

## Getting Started

These instructions will get you a copy of the project up and running on your local machine for development and testing purposes.

### Prerequisites

* Python 3.12+
* [uv](https://docs.astral.sh/uv/getting-started/installation/)

### Configuration requirements

The application requires two main configurations to be set up properly:

#### Redis Configuration

The application uses Redis for storing extracted text and processing results. Configure the following:

**Environment Variables:**

* `APP_ENV`: Environment mode for the backend. Defaults to `production`. Set to `development` to enable development-only features such as mock endpoints; they are never mounted unless you opt in explicitly.
* `REDIS_URL`: Redis connection URL (default: `redis://localhost:6379`). Include the password when Redis requires one: `redis://:<password>@localhost:6379/0`.
* `RETENTION_TTL_SECONDS`: Lifetime of every stored value, in seconds (default: `3600`). Every key written by the application carries this expiry, so stored documents are deleted automatically.
* `STORAGE_ENCRYPTION_KEY`: Fernet key used to encrypt every value before it is written. When unset, an ephemeral key is generated at startup: values stay encrypted, but stored documents become unreadable after a restart. Generate one with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.
* `STORE_DOCUMENT_TEXT`: Keep the extracted text next to the entities (default: `false`).
* `PSEUDONYMIZE_ENTITIES`: Mask detected patient identifiers (default: `true`). A request may ask for masking but cannot turn it off; setting this to `false` is a deliberate decision to handle identifiable patient data.

**Example:**

```bash
export REDIS_URL="redis://localhost:6379"
export RETENTION_TTL_SECONDS=3600
export STORAGE_ENCRYPTION_KEY="<fernet key>"
```

### What is stored

The default is to store nothing at all:

* `POST /api/analyze` extracts text, runs NER and returns the entities in the same
  response. It never touches Redis, issues no file id, and leaves nothing to delete.
* `POST /api/upload_document/` is for documents that must be reopened later. It stores
  the categorised entities under `doc:{file_id}:entities` and, only when
  `STORE_DOCUMENT_TEXT=true`, the text under `doc:{file_id}:text`.
* Entities are extracted once, at upload. Reading a document never runs the model again.
* When the text is not stored, entity `start`/`end` offsets are dropped: an offset
  means nothing without the text it indexes.
* Every value is encrypted before it reaches Redis.
* Entity text is stored after masking, so a stored document carries placeholders rather
  than the identifiers that were found. Setting `PSEUDONYMIZE_ENTITIES=false` stores them
  verbatim instead.
* Uploaded files above 1 MB are spooled to `TMPDIR` by the HTTP server before any route
  code runs. `docker-compose.yml` mounts a `tmpfs` at `/tmp` so those parts never reach
  the container's writable layer; a bare `uvicorn` run does not, and will write them to
  disk.
* With an unset `STORAGE_ENCRYPTION_KEY`, each worker generates its own key — run a
  single worker, or configure a key.

### Data retention

Stored documents are never kept indefinitely:

* Every key is written with an expiry of `RETENTION_TTL_SECONDS`.
* `GET /api/get_extracted_text/{file_id}` and `POST /api/upload_document/` return `expires_in_seconds` so a client can show the remaining time.
* `DELETE /api/documents/{file_id}` removes a document — text and entities — before its window closes. It answers `204` on success and `404` when nothing was stored.

### Pseudonymisation

**On by default** (`PSEUDONYMIZE_ENTITIES=true`). Every occurrence of a detected
identifier is replaced with a stable placeholder — `[NOM_1]`, `[DATE_1]`, `[AGE_1]` — in
the text and in the returned entities, and the offsets of the surviving entities are
remapped onto the masked text. An entity from another category that overlaps a masked
span reports the placeholder too: the characters are gone from the text, so repeating
them would defeat the mask.

Two detectors feed the pass:

1. The model's `patient_info` category (`app/services/entity_extractor/label_mappings/fr.json`).
   With the shipped French mapping that is `age`, `genre`, `homme` and `femme`.
2. `app/services/identifier_detector.py`, a pattern detector for the direct identifiers
   the model has **no label for**: names behind a civility or a field label
   (`M. Dupont`, `Patient : Jean Martin`), social-security numbers, record numbers
   (`IPP`, `NIP`, `NDA`), phone numbers, email addresses, dates, and postal codes
   followed by a town.

Once an identifier is found anywhere, every later occurrence of the same surface form is
masked with it — so a surname introduced as `M. Martin` is also masked where it appears
alone. Detected identifiers are reported in the `patient_info` category (as placeholders,
never as their original text), so a reader can audit what was masked.

`POST /api/analyze` and `POST /api/upload_document/` accept a `pseudonymize` form field.
A request can only turn masking **on**: it cannot switch off a deployment that sets
`PSEUDONYMIZE_ENTITIES=true`, since the caller is not the party that sets the policy.

#### What this does and does not mean for GDPR

Pseudonymisation is defined in Art. 4(5) and is an explicit Art. 32 security measure,
and this implementation keeps no re-identification mapping at all — the placeholders are
one-way, so there is no "additional information" to hold separately.

It does not make the data non-personal. Recital 26 is explicit that pseudonymised data
remains personal data, so the whole regulation still applies: lawful basis, records of
processing, a data protection impact assessment for health data, data subject rights,
and access control. Note in particular that **the API is still unauthenticated** — see
Phase 4 of the roadmap. Treat this feature as one control among the several compliance
requires, not as compliance.

Two limits worth stating plainly:

* Masking covers what the model labels and what the patterns match. A name written with
  no civility and no field label — a bare `Dupont` never introduced as `M. Dupont` — is
  not detected. Free-text clinical notes are adversarial in this respect.
* `pseudonymized: true` reports that the pass ran over every detected identifier, not
  that no identifier remains. An identifier that is missed is an identifier that
  survives, so a document that leaves the premises still deserves a human read.

### Logging

The file id is the only identifier that may be logged. Clinical filenames routinely carry
patient names, and parser errors quote the bytes that failed to parse, so error paths log
the file id and the exception type — never the filename, the message or a traceback.

### NER Model Configuration

The application uses Hugging Face transformers for Named Entity Recognition. Configure the following:

**Environment Variables:**

* `NER_MODEL_NAME`: Name of the Hugging Face model to use for NER

**Example:**

```bash
export NER_MODEL_NAME="dbmdz/bert-large-cased-finetuned-conll03-english"
```

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
