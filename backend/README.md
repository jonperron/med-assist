# Med-Assist Backend

This is the backend for the Med-Assist application, built with FastAPI and uv.

## Features

* Document upload (PDF, DOC, DOCX, TXT)
* Text extraction from medical documents
* Named Entity Recognition (NER) for medical terms
* Redis-based storage for processed documents
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
* `RETENTION_TTL_SECONDS`: Lifetime of every stored value, in seconds (default: `3600`). Every key written by the application carries this expiry, so extracted text is deleted automatically.

**Example:**

```bash
export REDIS_URL="redis://localhost:6379"
export RETENTION_TTL_SECONDS=3600
```

### Data retention

Extracted text is never stored indefinitely:

* Every key is written with an expiry of `RETENTION_TTL_SECONDS`.
* `GET /api/get_extracted_text/{file_id}` and `POST /api/upload_document/` return `expires_in_seconds` so a client can show the remaining time.
* `DELETE /api/documents/{file_id}` removes a document before its window closes. It answers `204` on success and `404` when nothing was stored.

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
