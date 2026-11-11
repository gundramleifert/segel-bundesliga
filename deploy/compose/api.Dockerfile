# Backend image for the Compose stack (deploy/compose/compose.yaml). Build context: repo root.
#
# The database is Postgres, the data lives in volumes and S3, and every setting comes from
# the environment — the image itself carries no state and no configuration.

FROM python:3.12.11-slim-bookworm

# libmagic1: an upload's type is its content (app/services/uploads.py).
# curl: the container's healthcheck.
# No Java: the printed pairing list is drawn in Python (app/pairing/pdf.py).
RUN apt-get update \
 && apt-get install -y --no-install-recommends libmagic1 curl \
 && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.11.11 /uv /uvx /bin/

WORKDIR /app
ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1

COPY api/pyproject.toml api/uv.lock ./
# The cache mount keeps downloaded wheels across builds, so a lock change fetches only what changed.
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev

COPY api/alembic.ini ./
COPY api/alembic ./alembic
COPY api/app ./app
COPY deploy/compose/api-init.sh /usr/local/bin/api-init
RUN chmod +x /usr/local/bin/api-init

# No uploads directory: in this stack every file is in S3 (compose.yaml, SBL_STORAGE).
ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=5 \
  CMD curl -fsS http://127.0.0.1:8000/health || exit 1

# One process: the live hub and the job runner are in-process (app/live.py, app/jobs.py).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
