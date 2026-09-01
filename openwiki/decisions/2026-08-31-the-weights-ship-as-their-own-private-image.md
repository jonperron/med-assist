---
type: decision
title: 2026-08-31 - The weights ship as their own private image
description: The NER weights are published as a FROM scratch image and baked into the backend image as a build stage, so a build from a Git clone is reproducible; the host mount survives as an opt-in development overlay.
tags: [deployment, docker, model, backend, privacy]
---

# 2026-08-31 - The weights ship as their own private image

Supersedes [[2026-08-31-the-model-is-mounted-not-baked-into-the-image]], which
is corrected in place rather than deleted.

## What was decided

The weights become an image of their own, and the backend image consumes it as
a build stage.

`backend/Dockerfile.model` is `FROM scratch` with one layer:

```dockerfile
FROM scratch
COPY models /models
```

`backend/Dockerfile` names it and copies from it:

```dockerfile
ARG MODEL_IMAGE=ghcr.io/jonperron/med-assist-model:1.0
FROM ${MODEL_IMAGE} AS model

FROM python:3.12-slim
WORKDIR /app
COPY --from=model /models /app/models
```

`scripts/build_model_image.sh` builds and tags it, and prints - but never runs -
the publish sequence. `docker-compose.yml` passes `MODEL_IMAGE` as a build
argument and no longer mounts anything over `/app/models`; the mount moves to
`docker-compose.dev.yml`, which is opt-in.

Four things had to be checked rather than assumed, and were:

- **`ARG` before `FROM` interpolates.** It does, on Docker 29.7.2 with buildx
  0.36.1. An `ARG` before the first `FROM` is outside every stage, which is the
  one place a build argument may appear in a `FROM` line.
- **`.dockerignore` blocks the model image, and does it loudly.** The build
  context is `./backend`, whose `.dockerignore` excludes `models/` - correct for
  the application image and wrong here. The first draft of this entry claimed
  that produced a silently empty image; the review pass challenged it, the build
  was run, and the claim was wrong. `COPY models /models` against that context
  fails outright:

  ```
  CopyIgnoredFile: Attempting to Copy file "models" that is excluded by .dockerignore (line 2)
  ERROR: failed to compute cache key: "/models": not found
  ```

  It names the file, the line and the path. The fix is still
  `backend/Dockerfile.model.dockerignore` - BuildKit prefers a
  `<dockerfile-name>.dockerignore` beside the Dockerfile over the context-wide
  one - but it is a fix for a build that refuses to run, not for a silent one.
  The size assertion in the build script is kept as a backstop rather than as
  the primary guard, because the primary guard turned out to be BuildKit.

  The earlier observation that produced the wrong claim was real but was of a
  different Dockerfile: `COPY . /models`, copying the whole context, which does
  succeed and does fill `/models` with the context's other files. That is the
  form to avoid, and it is why `Dockerfile.model` copies one named directory.
- **Layer order, not layer presence, was the real problem.** The previous entry
  unbaked the weights partly because a 420MB layer was rebuilt on every source
  edit. That is a cache-ordering fact, not a property of baking. `COPY --from=model`
  sits above uv, above the dependency install and above `COPY ./app`, so only a
  change of `MODEL_IMAGE` rebuilds it. The obvious placement is wrong in a way
  that looks right: below `COPY uv.lock pyproject.toml README.md`, editing the
  backend README invalidates it, because uv reads README.md as project metadata.
  That was measured before it was fixed.
- **`NER_MODEL_NAME` had no default.** It is `Field(...)` in
  `app/core/config.py`, so `docker run med-assist-backend` with no environment
  failed settings validation and logged "The NER model failed to load
  (ValidationError)" - an image carrying its own weights that could not find
  them. `ENV NER_MODEL_NAME=/app/models/` is added to `backend/Dockerfile`, not
  to `config.py`: the layout is a property of the image, and application code
  should still refuse to guess a path.

Verified end to end, on the real weights, with the image built from a checkout
that has no `backend/models/` directory at all - the Coolify condition:

- `docker run -p 8020:8000 med-assist-backend` with **no volume and no
  environment** answers `{"status":"ready"}` on `/readyz`, logs the weight load,
  and returns a summary for a synthetic French clinical document.
- With `MODEL_DIR` mounted read-only over `/app/models`: ready.
- With an *empty* directory mounted there: 503, and the log says
  "The NER model failed to load (ValueError)".

### The registry must be private

The model is `Dr-BERT/DrBERT-7GB` fine-tuned for token classification on the
DEFT 2021 corpus of French clinical cases. The corpus is not distributable. That
is certain, it is sufficient on its own, and it is the argument to lead with.

The second argument is weaker than the first draft of this entry stated, and the
security pass was right to push back. Training-data extraction is demonstrated
for generative language models; for a fine-tuned encoder token classifier the
path is materially harder and, as far as anyone here knows, not established. So
the honest form is: the possibility that these weights carry memorised spans of
the clinical text they were trained on cannot be ruled out. That is enough to
act on, and it does not need to be overstated to carry the decision.

Publishing these weights is therefore a data-protection problem rather than a
licensing one, and unlike a licensing mistake it cannot be undone: whoever
pulled the package keeps it.

This has a sharp edge specific to GHCR, and the first draft of this entry got
the mechanism wrong in the safe direction and the remedy wrong in the dangerous
one. It said a new package simply inherits the repository's visibility, and had
the operator create the package by pushing the model image to a throwaway tag -
which is the disclosure, since that push is what creates the package.

What is actually true: a GHCR package *linked* to a repository takes that
repository's visibility, and linking happens automatically when CI pushes with
`GITHUB_TOKEN` or when the image carries an `org.opencontainers.image.source`
label. A manually pushed, unlinked user-scoped package is created private. But
"probably private" is not a basis for publishing clinical-derived weights, so
the sequence does not rely on it: `scripts/build_model_image.sh` has the
operator create the package by pushing a **weightless placeholder**, confirm
`visibility` reads `private`, and only then push the model image. At no point is
the model image the artifact that creates the package. `Dockerfile.model`
carries a comment forbidding a source label, for the same reason.

**The backend image inherits all of this.** `COPY --from=model /models` puts the
same bytes in it, so it is exactly as sensitive as the model image and equally
not publishable. That sentence was missing from the first draft, and its absence
mattered: `.github/workflows/docker_build.yml` pushes
`ghcr.io/${{ github.repository }}` from CI on every release, which is the linked
case, from a public repository. It fails today only because it builds a context
with no Dockerfile in it - a bug that looks like it wants fixing, whose obvious
fix is the incident. A warning comment now sits on that step, and pointing it at
a backend image needs its own decision entry.

`scripts/build_model_image.sh` has **no push flag**, deliberately. It builds,
verifies and prints the commands. Adding a flag that pushes is a decision entry
of its own, because the whole safety of this arrangement rests on the push being
a thing a person does on purpose.

## The alternative that was rejected

**Committing the weights to the repository**, with Git LFS or without. It would
make the clone self-sufficient with no registry, no credential and no publish
step, and it is what the previous entry's failure most directly argues for.

Rejected on the same privacy grounds as the registry: this repository is public,
so committing the weights publishes them, and Git makes that worse than a
registry does. A package can at least be deleted; a commit in a public
repository is in every fork and every clone, and rewriting the history does not
recall them. LFS moves the bytes without changing who can fetch them.

**Keeping the mount and fixing the deployment instead** - shipping the weights
to the Coolify host out of band and pointing `MODEL_DIR` at them - was also
rejected. It works, and it keeps the image small, but it makes the deployment a
host with state that has to be restored by hand, and it leaves the digest gap
the previous entry accepted. It also does not scale past one host.

**A named volume populated by an init container** was rejected for the reason
the previous entry gave: the weights end up in two places and "which model is
this serving" becomes a question about volume contents.

## What it costs

- **The backend image is 2.47 GB rather than 1.62 GB.** Measured. That 850 MB is
  pulled by every deployment and stored per model version. It is paid once per
  model version rather than per build - the layer is above the source layers and
  never enters the build context - but it is a real cost of an image that runs
  with no host state.
- **There is a publish step before the first deploy, and it is dangerous.** An
  operator has to build the model image, create the package private *before*
  pushing, push it, and grant the deployment a read token. Getting the order
  wrong publishes clinical-derived weights to a public package. A script that
  prints instructions is weaker than a script that does it, and this is a
  deliberate trade: automating the push would remove the ordering mistake and
  add the risk of an accidental one.
- **Local development now needs a build step it did not need.** `docker compose
  up --build` on a fresh checkout no longer works on its own: without a
  credential for the private package the pull fails. The fix is one command
  (`scripts/build_model_image.sh`) and one line in `.env`, and the failure is a
  loud build error rather than a silent 503 - but it is a step in the getting
  started path that was not there yesterday.
- **Two ways to get weights, and the overlay wins silently.** With
  `docker-compose.dev.yml` in play, a bind mount shadows the baked-in weights,
  including when the directory it names does not exist - Docker creates a
  missing bind source empty, and an empty directory shadows them just as well as
  a full one. So the fixed deployment failure is still reachable locally, by a
  developer who has opted in. It is now opt-in, named `dev`, and documented as
  not for deployment; it is not prevented.
- **The digest gap is closed by default and not by construction.** The backend
  image digest covers its weights again, which is what the previous entry
  accepted losing. But nothing verifies at load time which weights are present,
  so the overlay reopens the gap while it is in use, and nothing in the response
  or the interface says which model answered. The expected-digest manifest that
  entry called for is still the real fix and still unwritten.
- **`MODEL_IMAGE` defaults to a tag this repository cannot prove is private.**
  The default in `backend/Dockerfile` and `docker-compose.yml` names
  `ghcr.io/jonperron/med-assist-model:1.0`. Nothing in the build checks that
  package's visibility, and nothing could - it is a property of a remote
  registry at pull time. The protection is documentation and the absence of a
  push flag.
- **Retraining is now a publish rather than a restart.** The mount made a new
  model a `docker compose restart backend`. In the default path it is: build a
  model image, tag it a new version, push it, change `MODEL_IMAGE`, rebuild the
  backend. That is the point - the model is versioned with the image again - but
  it is slower, and the dev overlay exists because the fast path is genuinely
  useful while a model is being iterated on.
- **`ENV NER_MODEL_NAME` turns one loud failure into a quiet wrong answer.**
  Before, a run that mounted weights at a non-default path and forgot to set the
  variable failed settings validation immediately. Now it starts, serves the
  weights baked into the image, reports ready, and returns clinically plausible
  output from a model the operator did not intend to be testing - and by design
  nothing in the response or the interface names a model, so nothing can say so.
  The mitigation the superseded entry already proposed applies here too and is
  still unwritten: log the resolved model path and a digest from the lifespan
  handler, to the operator-facing container log only.
- **The build script's allowlist can reject a legitimate model file.** It stages
  a named set of files rather than the directory, because `MODEL_DIR` is
  documented as pointing anywhere and a training run's output directory holds
  checkpoints and prediction dumps - and a prediction dump over this corpus is
  clinical text, which would otherwise ship inside a published image that no
  check would question, since both the file check and the size check only ever
  ask whether there is enough and never whether there is too much. The cost is
  that a model needing a file nobody anticipated stops the build until someone
  adds the name. That is the intended direction of failure, but it is friction,
  and it will look like a bug to whoever hits it first.
- **A moved tag silently breaks the guarantee.** `MODEL_IMAGE` is resolved at
  build time, and re-tagging `1.0` at a different set of weights would make two
  backend images with different content claim the same provenance. Nothing
  enforces immutable tags. The scripts and READMEs say "a new version tag, never
  a moved one"; that is all.
