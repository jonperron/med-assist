# Where the weights come from. Overridable, because the default is a private
# package that only a deployment host has a token for: local builds point this
# at the tag scripts/build_model_image.sh leaves behind.
#
#   docker build --build-arg MODEL_IMAGE=med-assist-model:local -t backend ./backend
#
# An ARG before the first FROM is the one place a build argument may be used in
# a FROM line; it is outside every stage, so it is not visible inside them
# without being redeclared. Verified on Docker 29.7.2 / buildx 0.36.1.
ARG MODEL_IMAGE=ghcr.io/jonperron/med-assist-model:1.0

# Not a base image and not run: FROM scratch with the weights as its only
# layer, built by backend/Dockerfile.model. It exists so this build needs
# nothing from the host - a Git clone carries no weights, so a build that read
# them from a directory could not be reproduced anywhere that builds from a
# clone. Pulling it needs a credential; see README.md.
FROM ${MODEL_IMAGE} AS model

# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set the working directory in the container
WORKDIR /app

# The weights, from the model image rather than from the build context. This is
# the line that makes the image self-sufficient: `docker run` with no -v and no
# -e analyses documents.
#
# First, before uv and before the dependencies, because it is both the largest
# layer and the least frequently changed. Ordering matters more here than the
# usual advice suggests, and the obvious placement is wrong: put this after
# `COPY uv.lock pyproject.toml README.md` and it reads just as sensibly, but
# uv takes README.md as project metadata, so editing the backend README
# invalidates the copy and rebuilds ~850MB. Observed, not reasoned about.
# Up here, only a MODEL_IMAGE change rebuilds it - verified by editing both
# README.md and app/main.py and watching this step report CACHED.
#
# The "the weights make every build slow" problem that got them unbaked in the
# first place is therefore a cache-ordering problem, and this is the fix for it.
#
# /app/models is where NER_MODEL_NAME points. docker-compose.dev.yml can still
# mount a host directory over this path for local work on a retrained model;
# the base compose file deliberately does not, so a deployment serves the
# weights the image digest covers.
COPY --from=model /models /app/models

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy the dependencies file to the working directory
COPY uv.lock pyproject.toml README.md ./

# Install dependencies
RUN uv sync --frozen --no-dev

# Copy the content of the local src directory to the working directory
COPY ./app ./app

# The Hub stays off, in the image rather than only in docker-compose.yml.
#
# The weights being baked in again does not make these redundant. NER_MODEL_NAME
# is an environment variable, so any deployment can point it at a Hub id - and
# the obvious way to "fix" an unready container, or to try a different model
# without a rebuild, is exactly that. Without these set, transformers would
# fetch it over the network. This service analyses clinical documents on the
# promise that nothing leaves the machine, so the refusal travels with the image
# and no compose file has to remember it.
ENV HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1 \
    HF_HUB_DISABLE_TELEMETRY=1

# Where the weights are, which is now a property of the image rather than of
# whatever started it. NER_MODEL_NAME is a required setting with no default in
# app/core/config.py, so without this `docker run med-assist-backend` fails
# settings validation and reports "The NER model failed to load
# (ValidationError)" - an image carrying its own weights that cannot find them.
# Every compose file sets the same value explicitly and overrides this to
# itself; the point is the run that sets nothing.
#
# Required-with-no-default stays as it is in config.py on purpose: nothing there
# should assume a filesystem layout, and a wrong path must fail rather than
# quietly resolve. This states the layout in the one place that defines it.
ENV NER_MODEL_NAME=/app/models/

# Make port 8000 available to the world outside this container
EXPOSE 8000

# Run app.main.py when the container launches.
#
# --limit-concurrency bounds requests in flight. The 50 MB ceiling in
# LimitRequestSize bounds one request; without this, nothing bounds their sum,
# and concurrent uploads share both the tmpfs they spool into and the container
# memory limit. Four is what the 256m tmpfs in docker-compose.yml covers at the
# full ceiling; the rest of the allowance leaves room for health probes.
CMD ["uv", "run", "--no-sync", "uvicorn", "app.main:app", \
     "--host", "0.0.0.0", "--port", "8000", "--limit-concurrency", "8"]
