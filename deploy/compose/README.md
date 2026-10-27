# The site in Docker Compose

Everything on one machine: **Postgres**, the **API**, the **SPA** behind Caddy, and
**SeaweedFS** as the S3 store for uploads.

| Service | Image | What it does |
|---|---|---|
| `db` | `postgres:17.6-alpine` | The database (volume `db-data`) |
| `db-setup` | built from `api.Dockerfile` | One-shot: `alembic upgrade head`; on an **empty** database also `app.seed_test_setup` (`api-init.sh`) |
| `api` | built from `api.Dockerfile` | uvicorn, one process; starts after `db-setup` finished |
| `web` | built from `web.Dockerfile` | The Vite build served by Caddy, which proxies `/api` to `api` |
| `storage` | `chrislusf/seaweedfs:3.97` | `weed server -s3`, the uploads' bucket (volume `storage-data`) |

**Why Caddy serves the SPA, not the API.** That is how the site already runs on Render:
a static site with an `/api/*` rewrite to the API (`render.yaml`), and the API has no
static-file route. Caddy keeps that split, and the browser stays on one origin, so there
is no CORS to configure. Server-Sent Events (live results) pass through unbuffered.

## Start

```bash
cp deploy/compose/.env.example deploy/compose/.env
# fill in POSTGRES_PASSWORD, SBL_JWT_SECRET, S3_ACCESS_KEY, S3_SECRET_KEY
docker compose -f deploy/compose/compose.yaml up --build -d --wait
```

The build context is the repo root (`.dockerignore` keeps local state out). The first build
takes a few minutes: Maven builds the pairing tool, pnpm builds the SPA. The first start
seeds the database, including 35 press pictures downloaded from SmugMug.

| URL | |
|---|---|
| http://localhost:8080 | the site (`WEB_PORT`) |
| http://localhost:8080/api/series | the API, through Caddy |
| http://localhost:8333 | the S3 endpoint (`S3_PORT`), signed with `S3_ACCESS_KEY` / `S3_SECRET_KEY` |

The API's own `/docs` and `/health` are not proxied:
`docker compose -f deploy/compose/compose.yaml exec api curl -s localhost:8000/health`.

## Uploads: local disk or S3

`SBL_STORAGE` decides where crests, photos, the media library, waiver scans, receipts and
documents are kept (`api/app/storage.py`):

- `s3` (the default here): in the bucket `SBL_S3_BUCKET` on SeaweedFS, created on the
  first use. Any S3-compatible store works — set `SBL_S3_ENDPOINT_URL` and the keys.
- `local`: in the api's `uploads` volume (`/data/uploads`).

Every file is still served by the API endpoint that checks who may see it; nothing is
public on the S3 side. **Switching does not move files** already stored — after a switch
the old ones are simply missing. To start over in the other mode, reset (below).

## Dev login — off by default

`SBL_DEV_LOGIN=true` in `.env` turns on `/api/dev`, which hands out access tokens
**without any verification**, and builds the role switcher into the SPA. The API logs a
warning at startup while it is on. Only for a stack nobody else can reach. It is a build
argument of the web image too, so change it with `up --build`.

Without it, sign in by one-time code: with no SMTP configured the code is written to the
api log (`docker compose … logs api`). `SBL_ADMIN_EMAILS=["you@example.com"]` makes an
address admin on its first sign-in. Note that the seed prints a ready admin token for
curl to the `db-setup` log — signed with your `SBL_JWT_SECRET`, valid for its lifetime.

## Reset

```bash
docker compose -f deploy/compose/compose.yaml down -v      # drop all volumes
docker compose -f deploy/compose/compose.yaml up -d --wait # migrate and seed afresh
```

Or keep the volumes and reseed the database only:
`docker compose -f deploy/compose/compose.yaml run --rm db-setup api-init --reset`.

## Postgres

This is the first setup that runs the site on Postgres; development and the test suite use
SQLite. What it took is in
`docs/gotchas/sqlite-accepts-schema-and-queries-postgres-refuses-so-the-suite-being-green-says.md`.
