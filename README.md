# 🩺 Med-Assist

[![Build Status](https://img.shields.io/github/actions/workflow/status/jonperron/med-assist/backend-ci.yml?branch=main)](https://github.com/your-org/med-assist/actions)

**Med-Assist** summarises clinical documents for the people who have to read them. Point it at one document or at a stack of them for the same patient, and it answers a short, readable summary — pathologies, symptoms, examinations, treatments, localisations — built from what a medical NER model found in the text.

No language model is involved and nothing leaves the machine: the summary is assembled from the spans the model marked, so it cannot state anything the documents did not.

---

## ⚠️ Disclaimer

> **Med-Assist is under active development.**
It is not intended for use in clinical decision-making and should not replace professional medical advice or diagnosis.

---

## 🔐 Privacy & Data Control

- **Local-first by design**
  Med-Assist runs entirely on your infrastructure—no external APIs or cloud dependencies.

- **Nothing stored by default**
  `POST /api/analyze` reads a document, extracts its entities and answers in a single request. Nothing reaches storage, so there is no file id to come back for and nothing to delete.

- **Entities, not prose**
  When a document is uploaded for later, only the categorised entities are kept — a few hundred bytes of clinical vocabulary rather than a complete patient record. Set `STORE_DOCUMENT_TEXT=true` to keep the text as well.

- **Secure storage**
  All data is stored in a local Redis instance that is reachable only from the internal Docker network, requires a password, and never writes to disk. Every value is encrypted with `STORAGE_ENCRYPTION_KEY` before it is written.

- **Automatic deletion**
  Every stored document expires after `RETENTION_TTL_SECONDS` (one hour by default). `DELETE /api/documents/{file_id}` removes a document immediately.

- **No language model, no egress**
  Summaries are assembled from NER output by fixed rules, not generated. Document text is never sent anywhere, and `POST /api/analyze` does not even echo it back to the caller.

  This is a local-processing guarantee, not a compliance claim. The extracted entities are health data and remain personal data under GDPR, the API is still unauthenticated, and clinical text is adversarial: read a summary before you rely on it. [`backend/README.md`](./backend/README.md) states the scope and the known gaps.

---

## 🚀 Running Locally

```bash
cp .env.example .env      # then set REDIS_PASSWORD to a long random value
docker compose up --build
```

The interface is served at [http://localhost:3000](http://localhost:3000) and the API at [http://localhost:8000](http://localhost:8000).

---

## 🌱 Green Impact

Med-Assist is built to run on minimal hardware, with a small footprint. It’s optimized to reduce energy usage and maximize sustainability—making it ideal for edge devices or local hospital servers.

Concretely, inference is CPU-only and the image carries nothing else:

- `torch` is pinned to the PyTorch CPU wheel index. The default PyPI package resolves to the CUDA build on Linux and drags the `nvidia-*` wheel set with it: pinning to the CPU build takes the installed backend environment from 4.6 GB to 1.2 GB, all of it GPU runtime that would never have been executed.
- The NER pipeline is built with `device="cpu"`, and `NER_INFERENCE_THREADS` caps what one inference spends.
- One document is inside the model at a time by default (`NER_MAX_CONCURRENT_INFERENCES`), so the model's peak memory follows the largest document rather than the number of concurrent uploads.
- Documents longer than the model's 512-token window are read through a sliding window rather than truncated, so the end of a long discharge summary is analysed like the beginning.
- The model is read once at startup, off the request path. `GET /readyz` answers `503` until it is in memory, and so do the routes that need it, so nothing reports healthy before it can actually analyse a document.

---

## 🧩 Project Structure

- [`backend/`](./backend/README.md) – FastAPI-based backend for processing and text extraction.
- [`frontend/`](./frontend/README.md) – Web interface to upload, manage, and visualize documents.

---

## 🤝 Contributing

We welcome community contributions!

---

## 📜 License

This project is licensed under the **Apache 2.0 License**.

---

## 📚 References

This project builds upon the following resources:

- Labrak, Y., Bazoge, A., Dufour, R., Rouvier, M., Morin, E., Daille, B., & Gourraud, P.-A. (2023).
  **DrBERT: A Robust Pre-trained Model in French for Biomedical and Clinical domains.**
  *Proceedings of the 61st Annual Meeting of the Association for Computational Linguistics (ACL'23), Long Paper*, Toronto, Canada.
  [ACL Anthology](https://aclanthology.org/)

- Grabar, N., Dalloux, C., & Claveau, V. (2020).
  **CAS: corpus of clinical cases in French.**
  *Journal of Biomedical Semantics, 11*, 7.
  [https://doi.org/10.1186/s13326-020-00225-x](https://doi.org/10.1186/s13326-020-00225-x)

- Cardon, R., Grabar, N., Grouin, C., & Hamon, T. (2020).
  **Presentation de la campagne d'evaluation DEFT 2020 : similarite textuelle en
  domaine ouvert et extraction d'information precise dans des cas cliniques.**
  *Actes de DEFT 2020*, Nancy, France.
  The fine-grained annotation the served model is trained on.

- Grouin, C., Grabar, N., & Illouz, G. (2021).
  **Classification de cas cliniques et evaluation automatique de reponses
  d'etudiants : presentation de la campagne DEFT 2021.**
  *Actes de DEFT 2021*, Lille, France.
  The train/test split the model is evaluated on.
