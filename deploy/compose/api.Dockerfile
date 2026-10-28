# Backend image for the Compose stack (deploy/compose/compose.yaml). Build context: repo root.
#
# The database is Postgres, the data lives in volumes and S3, and every setting comes from
# the environment — the image itself carries no state and no configuration.

# ----------------------------------------------------------------- the pairing tool
# The printable pairing list (Story B-3, app/pairing/pdf.py) is rendered by the Java tool,
# which lives in its own repository: built here from a pinned commit rather than carrying a
# 13 MB binary in git. Must be at least 7ba9bec: from that commit the tool reads hex colours
# and picks the font size itself, which app/pairing/pdf.py relies on.
FROM maven:3.9.11-eclipse-temurin-17 AS pairing
ARG PAIRING_LIST_REF=7ba9bec2eeb4934cacc976d59719dbc4472ce1a4
ADD https://codeload.github.com/gundramleifert/PairingList/tar.gz/${PAIRING_LIST_REF} /src.tar.gz
RUN mkdir /src \
 && tar -xzf /src.tar.gz --strip-components=1 -C /src \
 && cd /src \
 && mvn -B -q -DskipTests package

# ----------------------------------------------------------------- the API
# bookworm pinned: its default JRE is 17, the version the pairing tool is built for.
FROM python:3.12.11-slim-bookworm

# libmagic1: an upload's type is its content (app/services/uploads.py).
# curl: the container's healthcheck.
RUN apt-get update \
 && apt-get install -y --no-install-recommends default-jre-headless libmagic1 curl \
 && rm -rf /var/lib/apt/lists/*

COPY --from=pairing \
     /src/target/pairing-list-1.0-SNAPSHOT-jar-with-dependencies.jar \
     /opt/pairing-list.jar
ENV SBL_PAIRING_JAR=/opt/pairing-list.jar

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
