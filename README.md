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

- **Nothing stored, at all**
  `POST /api/analyze` reads a document, extracts its entities and answers in a single request. Nothing reaches storage, so there is no file id to come back for and nothing to delete. `POST /api/analyze/stream` streams the same work document by document so a caller can show progress; it holds nothing between events either. These two are the whole API: there is no datastore behind the service and no endpoint that writes one.

- **Nothing to expire, nothing to erase**
  Retention is bounded by the request rather than by a timer. A submitted document lives in memory for as long as it takes to answer, and the only trace it leaves is the multipart spool the HTTP server writes for parts above 1 MB — which `docker-compose.yml` puts on a `tmpfs`.

- **No language model, no egress**
  Summaries are assembled from NER output by fixed rules, not generated. Document text is never sent anywhere, and `POST /api/analyze` does not even echo it back to the caller — nor, since 2026-08-28, the character positions of the spans within it.

- **The browser enforces it too**
  The interface serves a Content-Security-Policy whose `connect-src` names two origins: the page itself and the backend given by `NEXT_PUBLIC_API_URL`. Script on that page cannot open a connection anywhere else — no fetch, no websocket, no beacon, no remote image. Fonts are self-hosted, images are local, and no referrer is sent anywhere. It is not a complete barrier: no CSP any browser ships can refuse a deliberate navigation, so script running in the page could still leave with data in a URL. What the policy removes is every silent channel, and it enforces "only the configured API origin" — whether that origin is on this machine is the operator's call. [`frontend/README.md`](./frontend/README.md) has the details and the deployment consequence.

  This is a local-processing guarantee, not a compliance claim. The extracted entities are health data and remain personal data under GDPR, the API is still unauthenticated, and clinical text is adversarial: read a summary before you rely on it. [`backend/README.md`](./backend/README.md) states the scope and the known gaps.

---

## 🚀 Running Locally

```bash
cp .env.example .env
scripts/build_model_image.sh              # -> med-assist-model:local
# then edit the MODEL_IMAGE line in .env to read:
#   MODEL_IMAGE=med-assist-model:local
docker compose up --build
```

The interface is served at [http://localhost:3000](http://localhost:3000) and the API at [http://localhost:8000](http://localhost:8000).

Edit the line rather than appending one: `.env.example` already sets
`MODEL_IMAGE`, and a file with the key twice works only because the parser
takes the last assignment.

**This needs the weights on disk.** `scripts/build_model_image.sh` reads
`backend/models/`, which is gitignored, so a fresh clone does not have them and
the script refuses. Without either the weights or a credential for the private
model package, the backend image cannot be built at all — this is a change from
the previous arrangement, where the stack built and started permanently
unready. The frontend builds and runs on its own; the training project that
produces the weights lives in a separate private repository, for the reasons in
[`backend/README.md`](./backend/README.md).

### The model

The weights are not in this repository — they are ~420MB and gitignored — so
they reach the backend image through an image of their own. `MODEL_IMAGE` names
it, `backend/Dockerfile` consumes it as a build stage, and the result is an
image that carries its own model: `docker run med-assist-backend` with no
volume and no environment reaches `{"status": "ready"}` and analyses documents.

> **The registry holding that image must be private — and so must any backend
> image built from it.** The model is DrBERT fine-tuned on the DEFT 2021 corpus
> of French clinical cases. The corpus is not distributable, which settles it on
> its own; on top of that, the possibility that fine-tuned weights carry
> memorised spans of the clinical text they were trained on cannot be ruled out.
> A public package here is a data-protection incident rather than a licensing
> footnote, and it cannot be taken back from whoever has already pulled it.
>
> The backend image copies `/models` out of the model image, so it contains the
> same bytes and is equally not publishable. `ghcr.io/jonperron/med-assist` is a
> package attached to a public repository; nothing may push a weight-carrying
> backend image to it. See `.github/workflows/docker_build.yml`.
>
> On GHCR, a package linked to a repository takes that repository's visibility,
> and a package is linked automatically when CI pushes it with `GITHUB_TOKEN` or
> when the image carries an `org.opencontainers.image.source` label. A manually
> pushed, unlinked user-scoped package is created private — but "probably
> private" is not a basis for publishing these weights, so
> `scripts/build_model_image.sh` prints a sequence that creates the package with
> a weightless placeholder, has you confirm it is private, and only then pushes.
> It has no push flag.

Locally you need no registry at all. `scripts/build_model_image.sh` reads
`backend/models/` — or `MODEL_DIR`, wherever the weights actually are — and
leaves `med-assist-model:local` on the machine; point `MODEL_IMAGE` at it. The
script refuses a directory that is not a model directory, refuses one holding
anything it does not recognise — a training run's checkpoints and prediction
dumps must not reach a published image — and refuses to leave behind an image
too small to contain weights. That last one is a backstop: an excluded
`models/` makes the build fail outright with `"/models": not found`, naming the
`.dockerignore` line, rather than quietly producing an empty image.

A build with neither a local tag nor a credential for the private package fails
on the pull, before anything starts. That is the intended failure: it is a
build error naming a missing image, not a container that answers `503` for ever
with nothing to say why.

#### Working on a retrained model

The mount is still there, as an opt-in overlay, so a retrained directory is a
restart rather than a rebuild and a re-publish:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up
```

`MODEL_DIR` says which directory. The overlay requires it rather than defaulting
it — a default is how you mount an empty directory over good weights by
forgetting a variable — and it is mounted read-only over `/app/models`,
shadowing the baked-in weights. To stop typing the
two `-f` flags, put `COMPOSE_FILE=docker-compose.yml:docker-compose.dev.yml` in
`.env` — Compose reads it from there. `.env` is gitignored, which is the point
of the split: the opt-in cannot follow the repository onto a deployment host in
a clone.

Use it and the weights being served are no longer the ones the image digest
covers, and nothing on screen distinguishes them — so a stale directory looks
exactly like a good model. Do not use this overlay on a deployment.

If `MODEL_DIR` is wrong, nothing crashes: Docker creates a missing bind source
as an empty directory rather than refusing, and an empty directory shadows the
baked-in weights just as well as a full one. The backend comes up, and
`GET /readyz` and both analysis routes answer `503`. The interface says so at
the top of the screen and holds the analyse button shut, so it looks like a
service that is not available yet rather than like documents that were
rejected. It rechecks every few seconds and re-enables itself — there is
nothing to reload. If that warning is on screen, check first whether the dev
overlay is in play at all; dropping it gets the baked-in model back. Then check
`MODEL_DIR`, then `docker compose logs backend`.

A second, differently worded notice appears when the interface cannot reach the
backend at all rather than being told it is not ready. That one leaves the
button enabled: a deployment that does not route `/readyz` — it sits at the
root, while analysis sits under `/api` — would otherwise have a working
analysis path disabled by a probe that is the only broken part.

### Deploying where the build starts from a Git clone

Coolify, and every other platform that deploys by cloning the repository and
running a build on the host, sees exactly what a `git clone` contains. That is
what the model image is for. `backend/models/` is gitignored, so a clone has no
weights; the arrangement this replaced bind-mounted `./backend/models` and
Docker created the missing path as an empty directory rather than refusing, so
the deployment came up, failed the load, and answered `503` on `/readyz` for
ever with nothing in the build log to explain it.

Before the first deploy, once per model version:

1. Build the model image and publish it to a **private** registry —
   `scripts/build_model_image.sh <version>` prints the sequence, including
   setting the package visibility before the first push. Read the warning above
   first; it is not a formality.
2. Give the deployment host a read-only credential for that package. On Coolify
   that is a registry credential on the server, so the build can pull it.
3. Set `MODEL_IMAGE` to the published reference in the deployment's environment.

Then deploy the base `docker-compose.yml` and nothing else — no `MODEL_DIR`, no
`docker-compose.dev.yml`, no volume. The build pulls the weights, bakes them in,
and the running service needs no host state at all. A missing or unreadable
`MODEL_IMAGE` fails the build with a pull error naming the image, which is a
failure someone can act on.

Retraining means a **new version tag**, never a moved one, and a rebuild. The
backend image's digest covers its weights only if the tag it was built against
does not change underneath it.

### Serving it from somewhere other than localhost

Two variables describe the same connection and have to move together:

- `NEXT_PUBLIC_API_URL` is where the browser looks for the API. It is baked into the frontend bundle at build time, so changing it means rebuilding the frontend image.
- `CORS_ALLOWED_ORIGINS` is which pages the API will answer. Comma-separated, each entry `scheme://host[:port]` with no trailing slash — `https://med-assist.example.org,https://med-assist.example.org:8443`.

Change one without the other and the API is reachable but every answer is dropped by the browser, which shows up as a network error rather than as a refusal. Unset, `CORS_ALLOWED_ORIGINS` stays on the local frontend origin; it is never widened to `*`, because this API answers with credentials and a browser rejects a credentialed response allowed to everyone. A value that is not an origin — a path, a wildcard, a space, a port that is not a number, an international domain that is not in its punycode form — stops the backend at startup instead of failing silently in the browser later; under Compose that shows up as a container restarting rather than as an unhealthy one, so read its log. Two spellings with one obvious reading are rewritten instead of refused: a single trailing slash is dropped, and so is a port the scheme already implies (`https://host:443` is sent by the browser as `https://host`).

CORS is a browser-side control and nothing else. It does not authenticate anyone: any client that is not a browser can call the API whatever this variable says, and there is no authentication in front of it. A deployment reachable by anyone other than the person running it needs a reverse proxy that authenticates, not a shorter origin list.

### Upgrading from the version that mounted the model

If you have an existing checkout and an existing `.env`, two things change and
neither announces itself.

Your `.env` predates `MODEL_IMAGE`, so `docker-compose.yml` falls back to the
private package and the build stops on a pull error naming an image you have
never heard of. Run `scripts/build_model_image.sh` and add the resulting
`MODEL_IMAGE=med-assist-model:local` to `.env`.

And the first run after this change must be `docker compose up --build`.
Without `--build`, Compose reuses the backend image you built before, which has
no weights in it and no mount to supply them — a service that starts, fails the
load and answers `503`, which is precisely the failure this change removes.

`MODEL_DIR` is now inert unless you opt into `docker-compose.dev.yml`. It has
also lost its default: the overlay requires it, so that forgetting it fails the
command instead of mounting an empty directory over the baked-in weights.

### Upgrading from a version that stored documents

Before 2026-08-28 the stack ran a Redis service and kept extracted entities — and,
where `STORE_DOCUMENT_TEXT` was set, document text. That service is gone from
`docker-compose.yml`, which orphans an existing container rather than deleting it:
the data outlives the upgrade, and the endpoint that could erase a record no longer
exists. Destroy it explicitly.

```bash
docker compose down --remove-orphans -v   # from the old checkout
```

Then delete the old `STORAGE_ENCRYPTION_KEY` from every `.env`, backup and secret
store. Stored values were Fernet tokens, so a surviving key is the difference
between discarded data and readable data.

---

## 🌱 Green Impact

Med-Assist is built to run on minimal hardware, with a small footprint. It’s optimized to reduce energy usage and maximize sustainability—making it ideal for edge devices or local hospital servers.

Concretely, inference is CPU-only and the image carries nothing else:

- `torch` is pinned to the PyTorch CPU wheel index. The default PyPI package resolves to the CUDA build on Linux and drags the `nvidia-*` wheel set with it: pinning to the CPU build takes the installed backend environment from 4.6 GB to 1.2 GB, all of it GPU runtime that would never have been executed.
- The NER pipeline is built with `device="cpu"`, and `NER_INFERENCE_THREADS` caps what one inference spends.
- One document is inside the model at a time by default (`NER_MAX_CONCURRENT_INFERENCES`), so the model's peak memory follows the largest document rather than the number of concurrent uploads.
- Documents longer than the model's 512-token window are read through a sliding window rather than truncated, so the end of a long discharge summary is analysed like the beginning.
- The model is read once at startup, off the request path. `GET /readyz` answers `503` until it is in memory, and so do the routes that need it, so nothing reports healthy before it can actually analyse a document.
- The weights are carried in the image, from a model image of their own. The backend image measures 2.47 GB against the 1.62 GB it measured while they were mounted from the host — a gap wider than the ~420 MB the files occupy on disk, so take the image figures from `docker image inspect` rather than deriving them from the weights. That is the price of an image that runs anywhere without host state, and it is paid once per model version rather than per build: the `COPY --from=model` sits above the dependency and source layers, so only a change of `MODEL_IMAGE` rebuilds it, and nothing re-uploads it to the daemon because it never enters the build context.

And what the stack may take from the host is capped rather than recommended:

- Both services carry memory and CPU limits (`BACKEND_MEMORY_LIMIT`, `BACKEND_CPU_LIMIT`, and the frontend pair). Measured under the defaults: the backend is ready 12 seconds after start, idles at 470 MiB, and peaks at 504 MiB across a batch of five long documents. The 2 GB default is headroom for a large PDF rather than a tight fit; it starts and analyses at 512 MB with nothing to spare.
- `NER_INFERENCE_THREADS` defaults to the CPU limit rather than to torch's own default, because torch reads the host's core count and not the cgroup quota. This is the single largest lever here: on a 14-core host under a 2-core quota, the same five-document batch took **11 seconds** with the two matched and **215 seconds** with torch left to start a thread per host core. Raise `BACKEND_CPU_LIMIT` to make analysis faster; leave the two in step whichever way you move them.
- Container logs rotate at three 10 MB files per service. Compose's default driver never rotates, which is the one thing here that would otherwise grow until the disk filled.
- A request body over 50 MB is refused. Where a length is declared, it is refused before a byte is read; where one is not, the count runs on the receive channel and the body is cut off at the ceiling. Either way it cannot be written in full and refused afterwards.
- Uploads above 1 MB are spooled to a RAM-backed `/tmp`, sized at 256 MB to cover four concurrent max-size requests, with uvicorn's `--limit-concurrency` bounding how many can be in flight. Spooled parts never reach the container's writable layer. They are pages in host RAM, so a host under memory pressure can page them to swap — the guarantee is about the container's disk, not about physics.

Nothing is persisted between requests, so there is no datastore to size, back up or grow.

Note that `deploy.resources.limits` is applied by Compose V2 and silently ignored by the legacy v1 `docker-compose` binary; check `docker compose version` before relying on the limits.

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
