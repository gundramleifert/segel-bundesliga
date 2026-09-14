# Backend image for a throwaway test deployment (Render, Fly.io, Koyeb, a plain VPS…).
#
# It bakes a freshly seeded SQLite database into the image: every container start begins
# from the same known state, and there is no external database to run. Writes during a
# session survive until the container restarts, then reset. That is exactly what a test
# deployment wants — see docs/deploy.md.

# ----------------------------------------------------------------- the pairing tool
# The printable pairing list is rendered by the Java tool (Story B-3, app/pairing/pdf.py),
# which lives in its own repository. Built here from a pinned commit rather than carrying
# a 13 MB binary in git or depending on a release that repository does not publish — the
# build is reproducible, and bumping the tool is a one-line change with a diff to read.
#
# This stage costs a few minutes on a cold build (Maven fetching iText) and is skipped
# entirely once cached. Without it the API still runs: it answers the pairing download
# with 503 and the site leaves the button out (`renderer_available`).
FROM maven:3.9-eclipse-temurin-17 AS pairing
ARG PAIRING_LIST_REF=838d20824cd51b665b20a92e3ca6caca5c5d4b6a
ADD https://codeload.github.com/gundramleifert/PairingList/tar.gz/${PAIRING_LIST_REF} /src.tar.gz
RUN mkdir /src \
 && tar -xzf /src.tar.gz --strip-components=1 -C /src \
 && cd /src \
 && mvn -B -q -DskipTests package

FROM python:3.12-slim

# A headless JRE for the pairing renderer above — Debian bookworm's default is 17, which
# is what the tool needs. `--no-install-recommends` keeps the fonts and X11 bits out; the
# renderer draws into a pdf and never touches a display.
RUN apt-get update \
 && apt-get install -y --no-install-recommends default-jre-headless \
 && rm -rf /var/lib/apt/lists/*

COPY --from=pairing \
     /src/target/pairing-list-1.0-SNAPSHOT-jar-with-dependencies.jar \
     /opt/pairing-list.jar
# A property of this image, so it belongs here rather than in render.env — and a real
# environment variable takes priority over that file anyway (app/config.py).
ENV SBL_PAIRING_JAR=/opt/pairing-list.jar

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
