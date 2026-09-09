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

- Interface: [localhost:3050](http://localhost:3050)
- API: [localhost:8050](http://localhost:8050)

### The model

Weights aren't in the repo or the image — mount them read-only from
`MODEL_DIR` (default `./backend/models`): `config.json`,
`model.safetensors`, `tokenizer.json`, `tokenizer_config.json`. Swap models
with `docker compose restart app`, no rebuild needed.

## Configuration

| Variable | What it does |
| --- | --- |
| `NEXT_PUBLIC_API_URL` | Where the browser looks for the API. Baked in at build time — changing it needs a frontend rebuild. |
| `CORS_ALLOWED_ORIGINS` | Comma-separated origins (`scheme://host[:port]`, no trailing slash — a trailing slash or an implied port like `:443`/`:80` is normalized rather than refused). Enforced server-side, not just sent to browsers: a `Sec-Fetch-Site` of `same-origin`/`none` is accepted before the list is even consulted; otherwise a request whose `Origin` is outside the list gets a fixed `403` before its body is read, and a request with neither header is let through. `docker-compose.yml` passes it explicitly, defaulting to `http://localhost:3050` to match the interface's compose-published port above; run the backend without Compose and leave it unset or empty and it falls back in code to `http://localhost:3000` rather than denying everything. `*` and anything that isn't a valid origin are refused at startup, by position, never quoted. |
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
