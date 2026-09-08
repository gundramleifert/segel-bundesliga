# Backend image for a throwaway test deployment (Render, Fly.io, Koyeb, a plain VPS…).
#
# It bakes a freshly seeded SQLite database into the image: every container start begins
# from the same known state, and there is no external database to run. Writes during a
# session survive until the container restarts, then reset. That is exactly what a test
# deployment wants — see docs/deploy.md.

FROM python:3.12-slim

# uv, for installing the locked dependencies.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app
ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1

# Dependencies first, so a code change doesn't re-install them.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY . .
ENV PATH="/app/.venv/bin:$PATH"

# Non-secret deployment config, baked in rather than left to the host's env vars — see
# render.env for why. Real secrets are never here; they come from Render Secret Files
# at runtime (/etc/secrets/<name>, see app/config.py's _SECRETS_DIR), which still take
# priority over this file if a host ever sets the same var as an actual env var.
RUN cp render.env .env

# Seed the database at build time. The secret here is only used by the seed script to
# mint the sample tokens it prints; it is NOT the runtime signing secret (set that as a
# real environment variable — SBL_JWT_SECRET — on the host).
ARG SEED_JWT_SECRET=build-time-seed-only
RUN SBL_JWT_SECRET="$SEED_JWT_SECRET" \
    SBL_DATABASE_URL="sqlite+aiosqlite:////app/sbl.db" \
    python -m app.seed_test_setup --reset

ENV SBL_DATABASE_URL="sqlite+aiosqlite:////app/sbl.db"
EXPOSE 8000

# Hosts inject $PORT; default to 8000 when run directly.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
