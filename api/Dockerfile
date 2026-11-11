# Backend image for a throwaway test deployment (Render, Fly.io, Koyeb, a plain VPS…).
#
# Every container start resets its Postgres to the seed: the same known state each time.
# Writes during a session survive until the container restarts, then reset — what a test
# deployment wants. The database's URL is the host's to give, as the Render Secret File
# `SBL_DATABASE_URL` (/etc/secrets/, app/config.py) — Render's own `postgresql://…` as it
# is; app/config.py adds the async driver.

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
# Must be at least 7ba9bec: from that commit the tool reads hex colours and picks the font
# size itself, and `app/pairing/pdf.py` stopped sending either. An older jar would print
# every colour-picker colour as an error.
ARG PAIRING_LIST_REF=7ba9bec2eeb4934cacc976d59719dbc4472ce1a4
ADD https://codeload.github.com/gundramleifert/PairingList/tar.gz/${PAIRING_LIST_REF} /src.tar.gz
RUN mkdir /src \
 && tar -xzf /src.tar.gz --strip-components=1 -C /src \
 && cd /src \
 && mvn -B -q -DskipTests package

FROM python:3.12-slim

# A headless JRE for the pairing renderer above — Debian bookworm's default is 17, which
# is what the tool needs. `--no-install-recommends` keeps the fonts and X11 bits out; the
# renderer draws into a pdf and never touches a display.
# `libmagic1` tells an upload's type from its content (`app/services/uploads.py`).
RUN apt-get update \
 && apt-get install -y --no-install-recommends default-jre-headless libmagic1 \
 && rm -rf /var/lib/apt/lists/*

COPY --from=pairing \
     /src/target/pairing-list-1.0-SNAPSHOT-jar-with-dependencies.jar \
     /opt/pairing-list.jar
# A property of this image, so it belongs here rather than in render.env — and a real
# environment variable takes priority over that file anyway (app/config.py).
ENV SBL_PAIRING_JAR=/opt/pairing-list.jar

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
