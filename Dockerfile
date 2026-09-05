# The release image: the API and the browser interface in one container.
#
# It is not what `docker compose up` builds. Compose builds backend/Dockerfile
# and frontend/Dockerfile, one container each, because that is the shape that
# takes a memory limit, a tmpfs and a healthcheck per service. This file exists
# because a release publishes one artifact that someone runs with `docker run`,
# and splitting that across two packages made the interface's own default wrong:
# NEXT_PUBLIC_API_URL is inlined into the bundle at build time, and in one
# container the browser really does reach the API at http://localhost:8000.
#
# See openwiki/decisions/2026-09-05-the-release-image-is-one-container.md for
# what this costs.

# ---------------------------------------------------------------------------
# The interface, built exactly as frontend/Dockerfile builds it.
# ---------------------------------------------------------------------------
FROM node:24-trixie-slim AS frontend-builder

WORKDIR /build

ENV NEXT_TELEMETRY_DISABLED=1

COPY frontend/package.json frontend/package-lock.json ./

# From the lockfile, for a deterministic build.
RUN npm ci

COPY frontend/ ./

# NEXT_PUBLIC_* values are inlined into the client bundle at build time. The
# default is right for this image rather than merely conventional: both
# processes are in one container, so a browser given both published ports on
# the same host reaches the API where the bundle says it is. A deployment
# behind a proxy still has to rebuild with its own domain - see deploy/README.md.
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

RUN npm run build

# ---------------------------------------------------------------------------
# The runtime. Debian and Python, with the Node binary lifted in beside it.
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Dependencies first, and from the same three files backend/Dockerfile copies:
# pyproject.toml names README.md as the project readme, so the install fails
# without it.
COPY backend/uv.lock backend/pyproject.toml backend/README.md ./

RUN uv sync --frozen --no-dev

COPY backend/app ./app

# Just the Node binary, not the image around it: `node server.js` is the whole
# runtime the standalone build needs, and node:24-trixie-slim is the same
# Debian release as this stage, so the one shared library it links against is
# already here. Pulling the full Node image in as a second base would carry npm
# and a package manager's worth of tooling for a process that never installs
# anything.
#
# The binary is the whole dependency on linux/amd64, where it links only
# libstdc++, libgcc_s, libm, libpthread and libc - all of them already in this
# stage. It is not the whole dependency everywhere: node:24-trixie-slim also
# installs libatomic1, which the Node build needs on ARM. A `platforms:` line
# in .github/workflows/docker_build.yml is therefore not the only edit an
# arm64 image would take - this stage would need that package too, and the
# failure without it is `node` refusing to start at all.
COPY --from=node:24-trixie-slim /usr/local/bin/node /usr/local/bin/node

# `output: "standalone"` in next.config.ts emits a server plus the modules it
# actually imports. public/ and .next/static/ are not part of it and have to be
# placed by hand - Next documents this, and an image without them serves a page
# with no stylesheet and no favicon rather than an error.
COPY --from=frontend-builder /build/.next/standalone ./web/
COPY --from=frontend-builder /build/.next/static ./web/.next/static
COPY --from=frontend-builder /build/public ./web/public

COPY docker-entrypoint.sh /usr/local/bin/med-assist
# The mode travels in git, but a context unpacked from an archive can lose
# it, and the failure then is a container that exits with "permission
# denied" at every start.
RUN chmod 0755 /usr/local/bin/med-assist

# The weights are deliberately not copied, exactly as in backend/Dockerfile.
# They are ~420MB, they are gitignored, and they change on a different schedule
# from the code. docker-compose.yml bind-mounts them read-only at /app/models;
# a `docker run` has to pass `-v /path/to/weights:/app/models:ro` itself. A
# container started without them still starts - it answers 503 on /readyz and
# on the analysis routes, and the interface says so.

ENV PYTHONUNBUFFERED=1 \
    TMPDIR=/tmp \
    APP_ENV=production \
    NER_MODEL_NAME=/app/models/ \
    NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

# The Hub stays off, in the image rather than only in docker-compose.yml. The
# image ships without weights, so the obvious way to "fix" an unready container
# is to point NER_MODEL_NAME at a Hub id - and without these, transformers
# would fetch it over the network, from a service whose whole claim is that
# nothing leaves the machine.
ENV HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1 \
    HF_HUB_DISABLE_TELEMETRY=1

# One unprivileged user for both processes. Neither writes inside the image:
# the API spools uploads to TMPDIR and the interface serves what the build
# produced, so nothing here needs to be owned by it.
# Not --system: that reserves ids below 1000, and 1001 is deliberate - it is
# the id frontend/Dockerfile already gives the interface, so a bind mount
# readable by one image is readable by the other.
RUN useradd --uid 1001 --user-group --no-create-home \
        --shell /usr/sbin/nologin medassist
USER medassist

EXPOSE 8000 3000

# Ready means the weights are in memory and the interface is being served, not
# merely that the ports are open. urlopen is caught rather than left to raise:
# it answers a 503 with an exception, and an uncaught one writes a traceback
# into the container log on every check while the service is not ready.
HEALTHCHECK --interval=10s --timeout=5s --retries=5 --start-period=60s \
    CMD python -c "import urllib.request as r, sys; \
sys.exit(0 if r.urlopen('http://localhost:8000/readyz').status == 200 \
and r.urlopen('http://localhost:3000/').status == 200 else 1)" 2>/dev/null || exit 1

ENTRYPOINT ["/usr/local/bin/med-assist"]
