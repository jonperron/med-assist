# 🩺 Med-Assist

[![Build Status](https://img.shields.io/github/actions/workflow/status/jonperron/med-assist/backend-ci.yml?branch=main)](https://github.com/jonperron/med-assist/actions)

**Med-Assist** summarises clinical documents for the people who have to read
them. Point it at one document or at a stack of them for the same patient, and
it answers a short, readable summary — pathologies, symptoms, examinations,
treatments, localisations — built from what a medical NER model found in the
text.

No language model is involved and nothing leaves the machine: the summary is
assembled from the spans the model marked, so it cannot state anything the
documents did not.

---

## ⚠️ Disclaimer

> **Med-Assist is under active development.**
It is not intended for use in clinical decision-making and should not replace
professional medical advice or diagnosis.

---

## 🔐 Privacy & Data Control

- **Local-first.** Runs entirely on your own infrastructure. No external APIs,
  no cloud dependencies.
- **Nothing stored.** `POST /api/analyze` and `POST /api/analyze/stream` are the
  whole API. Each reads a document, extracts its entities and answers in a
  single request. There is no datastore behind the service, no file id to come
  back for, and nothing to delete.
- **No language model, no egress.** Summaries are assembled from NER output by
  fixed rules, not generated. Document text is never sent anywhere and is not
  echoed back to the caller.
- **The browser enforces it too.** The interface serves a
  Content-Security-Policy whose `connect-src` names only the page itself and the
  configured API origin, which closes every silent channel out of it.

This is a local-processing guarantee, not a compliance claim. The extracted
entities are health data and remain personal data under GDPR, **the API is
unauthenticated**, and clinical text is adversarial: read a summary before you
rely on it. [`backend/README.md`](./backend/README.md) states the scope and
[`frontend/README.md`](./frontend/README.md) the policy;
[`openwiki/decisions/`](./openwiki/decisions/) holds the known gaps and what
each boundary does not stop.

---

## 🚀 Running Locally

```bash
cp .env.example .env      # no secrets to fill in; the defaults run as-is
docker compose up --build
```

The interface is at [localhost:3000](http://localhost:3000) and the API at
[localhost:8000](http://localhost:8000).

### The model

The weights are not in this repository and not in the image. They are mounted
read-only from `MODEL_DIR`, which defaults to `./backend/models` — put
`config.json`, `model.safetensors`, `tokenizer.json` and `tokenizer_config.json`
there, or point `MODEL_DIR` at wherever they already are. Swapping in a
retrained model is then `docker compose restart backend`, with no rebuild.

Start the stack without them and nothing crashes: the backend comes up and
answers `503` on `GET /readyz` and on both analysis routes, and the interface
says the service is unavailable rather than blaming the documents. It rechecks
every few seconds and clears itself. If that warning is on screen, check
`MODEL_DIR` first, then `docker compose logs backend`.

### The published image

Every release publishes one image, `ghcr.io/jonperron/med-assist:<version>`,
holding the API and the interface in a single container. It is the artifact for
running a tagged version without a checkout; `docker compose up` above still
builds the two services separately, and that is what a working copy uses.

```bash
docker run \
  -p 127.0.0.1:8000:8000 -p 127.0.0.1:3000:3000 \
  --tmpfs /tmp:size=256m,mode=1777,noexec,nosuid,nodev \
  -v "$PWD/backend/models:/app/models:ro" \
  -e API_ACCESS_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')" \
  ghcr.io/jonperron/med-assist:<version>
```

The weights are not in it, for the same reason they are not in the compose
build, and the `--tmpfs` is not decoration: without it uploaded documents are
spooled to the container's writable layer rather than to memory.
[`deploy/README.md`](./deploy/README.md) has the rest, including why the
interface needs a proxy in front of it to reach an API that now requires a
credential.

### Serving it from somewhere other than localhost

Two variables describe the same connection and have to move together:

- `NEXT_PUBLIC_API_URL` — where the browser looks for the API. It is baked into
  the frontend bundle at build time, so changing it means rebuilding that image.
- `CORS_ALLOWED_ORIGINS` — which pages the API will answer. Comma-separated,
  each entry `scheme://host[:port]` with no trailing slash.

Change one without the other and the API is reachable but every answer is
dropped by the browser, which looks like a network error rather than a refusal.
A value that is not an origin stops the backend at startup instead of failing
silently in the browser later. The exact validation rules are in
[`openwiki/decisions/`](./openwiki/decisions/).

**CORS is not authentication.** Any client that is not a browser ignores it
entirely, and nothing else guards the API. A deployment reachable by anyone
other than the person running it needs a reverse proxy that authenticates, not
a shorter origin list.

### Upgrading from a version that stored documents

Before 2026-08-28 the stack ran a Redis service and kept extracted entities.
Removing that service from `docker-compose.yml` orphans the running container
rather than deleting it, so the data outlives the upgrade. Destroy it
explicitly:

```bash
docker compose down --remove-orphans -v   # from the old checkout
```

Then delete the old `STORAGE_ENCRYPTION_KEY` from every `.env`, backup and
secret store. Stored values were Fernet tokens, so a surviving key is the
difference between discarded data and readable data.

---

## 🌱 Green Impact

Med-Assist is built to run on minimal hardware. Inference is CPU-only and the
image carries nothing else: `torch` is pinned to the CPU wheel index, which
takes the installed backend environment from 4.6 GB to 1.2 GB of what would
never have been executed. Both services carry memory and CPU limits, container
logs rotate, request bodies above 50 MB are refused, and nothing is persisted
between requests — so there is no datastore to size, back up or grow.

One lever matters more than the rest: **keep `NER_INFERENCE_THREADS` in step
with `BACKEND_CPU_LIMIT`.** torch reads the host's core count rather than the
cgroup quota, so left to itself it starts a thread per host core inside a much
smaller allowance and pays the difference in contention. Measured on a 14-core
host under a 2-core quota, the same five-document batch took **11 seconds** with
the two matched and **215 seconds** without.

Note that `deploy.resources.limits` is applied by Compose V2 and silently
ignored by the legacy v1 `docker-compose` binary.

The measurements behind each bound, and why each one is set where it is, are in
[`openwiki/decisions/`](./openwiki/decisions/).

---

## 🧩 Project Structure

- [`backend/`](./backend/README.md) — FastAPI backend: extraction, NER and
  summarisation.
- [`frontend/`](./frontend/README.md) — the web interface.
- [`openwiki/decisions/`](./openwiki/decisions/) — why things are the way they
  are, one page per decision.

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
