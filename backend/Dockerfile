# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set the working directory in the container
WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy the dependencies file to the working directory
COPY uv.lock pyproject.toml README.md ./

# Install dependencies
RUN uv sync --frozen --no-dev

# Copy the content of the local src directory to the working directory
COPY ./app ./app

# The weights are deliberately not copied. They are ~420MB, they are gitignored,
# and they change on a different schedule from the code: baked in, every source
# edit rebuilt a layer of them, and a checkout without them failed the build
# instead of starting. docker-compose.yml bind-mounts them read-only at
# /app/models, which is where NER_MODEL_NAME points. A container started without
# that mount still starts - it answers 503 on /readyz and on the analysis routes
# rather than crash-looping, and the interface says so.

# The Hub stays off, in the image rather than only in docker-compose.yml.
#
# These used to be reachable only through compose, which was survivable while
# the weights were baked in: there was always a local model to read. Now that
# the image ships without them, the obvious way to "fix" an unready container is
# to point NER_MODEL_NAME at a Hub id - and without these set, transformers
# would happily fetch it over the network. This service analyses clinical
# documents on the promise that nothing leaves the machine, so the refusal
# travels with the image and compose no longer has to remember it.
ENV HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1 \
    HF_HUB_DISABLE_TELEMETRY=1

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
