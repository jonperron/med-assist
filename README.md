# 🩺 Med-Assist

[![Build Status](https://img.shields.io/github/actions/workflow/status/jonperron/med-assist/backend-ci.yml?branch=main)](https://github.com/jonperron/med-assist/actions)

Med-Assist turns one or several medical documents about the same patient into
a short clinical summary — pathologies, symptoms, examinations, treatments,
localisations. No language model is involved: a medical NER model tags spans
in the text, and fixed rules assemble the summary from those spans, so it
can't say anything the documents didn't.

> **⚠️ Under active development.** Not for clinical decision-making — it does
> not replace professional medical judgment.

---

## 🔐 Privacy

- **Local-first, no egress.** Runs on your own infrastructure. No external
  APIs, no cloud calls, no language model. The interface's
  Content-Security-Policy backs this at the browser: `connect-src` names only
  the page itself and the configured API origin, closing every silent
  channel out of it.
- **Nothing is stored.** `POST /api/analyze` and `POST /api/analyze/stream`
  are the whole API — read, extract, answer, forget. No datastore, no file
  id, nothing to delete. Document text is never echoed back to the caller.
- **No accounts, no login.** Anyone who can reach the API can use it. This is
  meant to run on your own machine — see [Configuration](#configuration)
  before exposing it to anyone else, and don't point clinicians at a public
  instance with real documents.

This is a local-processing guarantee, not a compliance claim: extracted
entities are still health data (personal data under GDPR), and clinical text
is adversarial input — read a summary before relying on it.

---

## 🚀 Running it

```bash
cp .env.example .env      # no secrets to fill in; defaults run as-is
docker compose up --build
```

- Interface: [localhost:3000](http://localhost:3000)
- API: [localhost:8000](http://localhost:8000)

### The model

Weights aren't in the repo or the image — mount them read-only from
`MODEL_DIR` (default `./backend/models`): `config.json`,
`model.safetensors`, `tokenizer.json`, `tokenizer_config.json`. Swap models
with `docker compose restart backend`, no rebuild needed.

Missing weights don't crash the stack: the backend answers `503` on
`/readyz` and both analysis routes, and the UI shows a service-unavailable
message. If you see it, check `MODEL_DIR`, then `docker compose logs backend`.

### The published image

Every release publishes one image, `ghcr.io/jonperron/med-assist:<version>`,
holding the API and the interface in a single container. It is the artifact for
running a tagged version without a checkout; `docker compose up` above still
builds the two services separately, and that is what a working copy uses.

```bash
docker run \
  -p 127.0.0.1:8000:8000 -p 127.0.0.1:3000:3000 \
  --tmpfs /tmp:size=256m,mode=1777,noexec,nosuid,nodev \
  --cap-drop ALL --security-opt no-new-privileges \
  -v "$PWD/backend/models:/app/models:ro" \
  ghcr.io/jonperron/med-assist:<version>
```

The weights are not in it, for the same reason they are not in the compose
build, and the `--tmpfs` is not decoration: without it uploaded documents are
spooled to the container's writable layer rather than to memory. It carries
none of the compose stack's other per-service bounds either - the memory and
CPU limits, the restart policy, the log rotation - and `deploy/README.md` says
which flags put them back.

The interface in it is built to look for the API at `http://localhost:8000`, and
that address is resolved by the browser rather than by the container — so the
published image serves a browser on the machine running Docker, and nothing
else. Reaching it from another machine is a rebuild with your own
`NEXT_PUBLIC_API_URL`, not a published port; the next section has both variables
and [`deploy/README.md`](./deploy/README.md) has the rest.

## Configuration

| Variable | What it does |
| --- | --- |
| `NEXT_PUBLIC_API_URL` | Where the browser looks for the API. Baked in at build time — changing it needs a frontend rebuild. |
| `CORS_ALLOWED_ORIGINS` | Comma-separated origins (`scheme://host[:port]`, no trailing slash — a trailing slash or an implied port like `:443`/`:80` is normalized rather than refused). Enforced server-side, not just sent to browsers: a `Sec-Fetch-Site` of `same-origin`/`none` is accepted before the list is even consulted; otherwise a request whose `Origin` is outside the list gets a fixed `403` before its body is read, and a request with neither header is let through. Unset or empty keeps the default (`http://localhost:3000`) rather than denying everything. `*` and anything that isn't a valid origin are refused at startup, by position, never quoted. |
| `UNSECURED_DEPLOYMENT` | Set `true` on any non-local deployment — puts a banner on every screen saying this installation is open, anyone can reach it, and documents sent through it may be read by a third party. Read at request time; just restart. |
| `NER_MODEL_NAME` | Path to the local model directory. Required. |
| `APP_ENV` | `production` (default) or `development` — the latter enables mock endpoints, never mounted otherwise. |
| `MAX_BATCH_FILES` | Max documents per request (default `20`), bounding how many can queue behind a model that admits one document at a time. Each file is separately capped at 10 MB — a ceiling that bounds bytes, not inference time, so twenty small text files are the expensive case and a small deployment should lower this. |
| `NER_INFERENCE_THREADS`, `NER_MAX_CONCURRENT_INFERENCES` | Threads per inference (default `0`, one per host core) and documents inside the model at once (default `1`). See Footprint below for why the first one matters. |

Update `NEXT_PUBLIC_API_URL` and `CORS_ALLOWED_ORIGINS` together — mismatched,
the API works but the browser silently drops every response.

**CORS is not authentication, and neither is the banner.** Nothing in the app
authenticates callers, and non-browser clients ignore CORS entirely. Put an
authenticating reverse proxy in front before exposing this to anyone but
yourself — see [`deploy/README.md`](./deploy/README.md).

### Upgrading a shared-credential deployment (2026-08-31 to 2026-09-05)

`API_ACCESS_TOKEN` is no longer read. Remove it from every `.env` and secret
store. If a proxy rule injected `Authorization: Bearer` for it, that rule now
enforces nothing — replace it with real authentication on the proxy.
Details: [`deploy/README.md`](./deploy/README.md).

### Upgrading a document-storing deployment (pre-2026-08-28)

That version ran Redis and kept extracted entities. Removing the service from
`docker-compose.yml` orphans the container instead of deleting it, so old
data survives the upgrade unless you remove it explicitly:

```bash
docker compose down --remove-orphans -v   # from the old checkout
```

Then delete the old `STORAGE_ENCRYPTION_KEY` from every `.env`, backup and
secret store. Stored values were Fernet tokens, so a surviving key is the
difference between discarded data and readable data.

---

## 🌱 Footprint

CPU-only inference, CPU-only `torch` wheel (1.2 GB vs. 4.6 GB), memory/CPU
limits on both containers, rotated logs, 50 MB request cap, nothing
persisted. One thing to get right yourself: **set `NER_INFERENCE_THREADS` to
match `BACKEND_CPU_LIMIT`** — torch defaults to one thread per host core
regardless of your cgroup quota, and the mismatch is expensive (11s vs. 215s
for the same batch, measured on a 14-core host under a 2-core limit).

`deploy.resources.limits` requires Compose V2 — the legacy v1
`docker-compose` binary silently ignores it.

Rationale and measurements: [`openwiki/decisions/`](./openwiki/decisions/).

---

## 🤝 Contributing

Access control is the open gap and a good place to start: no accounts, no
sessions, no rate limiting, no audit trail. If you want to add any of these,
open an issue first — it's a decision that needs a page in
[`openwiki/decisions/`](./openwiki/decisions/) before it needs code. See
[`deploy/README.md`](./deploy/README.md) for the current shape.

---

## 📜 License

Apache 2.0.

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
