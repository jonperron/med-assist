# ---------------------------------------------------------------------------
# Interface build
# ---------------------------------------------------------------------------
FROM node:24-trixie-slim AS frontend-builder

WORKDIR /build

ENV NEXT_TELEMETRY_DISABLED=1

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./

ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

RUN npm run build

# ---------------------------------------------------------------------------
# Runtime.
# ---------------------------------------------------------------------------
FROM python:3.12-slim-trixie AS runtime

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY backend/uv.lock backend/pyproject.toml ./

RUN uv sync --frozen --no-dev

COPY backend/app ./app

COPY --from=frontend-builder /usr/local/bin/node /usr/local/bin/node
RUN /usr/local/bin/node --version

COPY --from=frontend-builder /build/.next/standalone ./web/
COPY --from=frontend-builder /build/.next/static ./web/.next/static
COPY --from=frontend-builder /build/public ./web/public

COPY docker-entrypoint.sh /usr/local/bin/med-assist
RUN chmod 0755 /usr/local/bin/med-assist

ENV PYTHONUNBUFFERED=1 \
    TMPDIR=/tmp \
    APP_ENV=production \
    NER_MODEL_NAME=/app/models/ \
    NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

ENV HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1 \
    HF_HUB_DISABLE_TELEMETRY=1

RUN useradd --uid 1001 --user-group --no-create-home \
        --shell /usr/sbin/nologin medassist
USER medassist

EXPOSE 8000 3000

HEALTHCHECK --interval=10s --timeout=5s --retries=5 --start-period=60s \
    CMD python -c "import urllib.request as r, sys; \
sys.exit(0 if r.urlopen('http://localhost:8000/readyz').status == 200 \
and r.urlopen('http://localhost:3000/').status == 200 else 1)" 2>/dev/null || exit 1

ENTRYPOINT ["/usr/local/bin/med-assist"]
