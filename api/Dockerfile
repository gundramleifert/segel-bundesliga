# Backend image for a throwaway test deployment (Render, Fly.io, Koyeb, a plain VPS…).
#
# Every container start resets its Postgres to the seed: the same known state each time.
# Writes during a session survive until the container restarts, then reset — what a test
# deployment wants. The database's URL is the host's to give, as the Render Secret File
# `SBL_DATABASE_URL` (/etc/secrets/, app/config.py) — Render's own `postgresql://…` as it
# is; app/config.py adds the async driver.

FROM python:3.12-slim

# `libmagic1` tells an upload's type from its content (`app/services/uploads.py`).
RUN apt-get update \
 && apt-get install -y --no-install-recommends libmagic1 \
 && rm -rf /var/lib/apt/lists/*

# uv, for installing the locked dependencies.
COPY --from=ghcr.io/astral-sh/uv:0.9.7 /uv /uvx /bin/

WORKDIR /app
ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1

# Dependencies first, so a code change doesn't re-install them. The lock names public
# PyPI (`[[tool.uv.index]]` in pyproject.toml); a company mirror in it would be
# unreachable from here and fail every build (docs/gotchas).
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY . .
ENV PATH="/app/.venv/bin:$PATH"

# Non-secret deployment config, baked in rather than left to the host's env vars — see
# render.env for why. Real secrets are never here; they come from Render Secret Files
# at runtime (/etc/secrets/<name>, see app/config.py's _SECRETS_DIR), which still take
# priority over this file if a host ever sets the same var as an actual env var.
RUN cp render.env .env

EXPOSE 8000

# On start: reset the database to the seed — the 2026 season as sailed, and the press
# pictures, downloaded from SmugMug (app/seed_media.py; one that cannot be fetched is left
# out) — then `publish_preview` publishes the 1. Liga 2027, the preview of branch
# `vorschau`. Hosts inject $PORT; default to 8000 when run directly.
CMD ["sh", "-c", "python -m app.seed_test_setup --reset \
  && python -c 'import asyncio; from app.seed import publish_preview; asyncio.run(publish_preview())' \
  && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
