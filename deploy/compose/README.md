# The site in Docker Compose

Everything on one machine: **Postgres**, the **API**, the **SPA** behind Caddy, and
**SeaweedFS** as the S3 store for uploads.

This is the reference for the stack. Putting it on a server — the first installation,
HTTPS, updates, backups — is `docs/deploy-server.md`.

| Service | Image | What it does |
|---|---|---|
| `db` | `postgres:17.6-alpine` | The database (volume `db-data`) |
| `db-setup` | built from `api.Dockerfile` | One-shot: `app.seed_test_setup --if-empty` — migrates, and seeds only an **empty** database (`api-init.sh`) |
| `api` | built from `api.Dockerfile` | uvicorn, one process; starts after `db-setup` finished |
| `web` | built from `web.Dockerfile` | The Vite build served by Caddy, which proxies `/api` to `api` |
| `storage` | `chrislusf/seaweedfs:3.97` | `weed server -s3`, the uploads' bucket (volume `storage-data`); only in the profile `seaweedfs` — leave it out for an outside S3 provider |

**Why Caddy serves the SPA, not the API.** The API has no static-file route; Caddy serves
the built SPA and proxies `/api`, and the browser stays on one origin, so there
is no CORS to configure. Server-Sent Events (live results) pass through unbuffered.

## Start

```bash
cp deploy/compose/.env.example deploy/compose/.env   # the settings; no secrets in it
deploy/compose/compose.sh up --build -d --wait      # docker compose, secrets from sops
```

`compose.sh` is `docker compose -f deploy/compose/compose.yaml` with the secrets
decrypted from `secrets.sops.env` — every compose command works through it
(`compose.sh logs -f api`, `compose.sh down`). See "Secrets" below.

The build context is the repo root (`.dockerignore` keeps local state out). The first build
takes a few minutes: Maven builds the pairing tool, pnpm builds the SPA. The first start
seeds the database, including 35 press pictures downloaded from SmugMug.

| URL | |
|---|---|
| http://localhost:8080 | the site (`WEB_PORT`) |
| http://localhost:8080/api/series | the API, through Caddy |
| http://localhost:8333 | the S3 endpoint (`S3_PORT`), signed with `S3_ACCESS_KEY` / `S3_SECRET_KEY` |

The API's own `/docs` and `/health` are not proxied:
`deploy/compose/compose.sh exec api curl -s localhost:8000/health`.

## Secrets — sops, encrypted in the repository

The secrets are in `deploy/compose/secrets.sops.env`, a dotenv file encrypted with
[sops](https://github.com/getsops/sops) and committed: the database password, the JWT
secret, the S3 key pair, and the optional SMTP password and Brevo key. Who may decrypt it
is `.sops.yaml` at the repo root — **SSH public keys** (`ssh-ed25519` or `ssh-rsa`), so a
recipient needs no extra key: sops decrypts with `~/.ssh/id_ed25519` (or the file named
in `SOPS_AGE_SSH_PRIVATE_KEY_FILE`). A key behind an ssh-agent or on a hardware token
does not work.

```bash
sops deploy/compose/secrets.sops.env          # edit: decrypts into $EDITOR, encrypts on save
sops decrypt deploy/compose/secrets.sops.env  # read
```

`compose.sh` runs `sops exec-env`: the values go to `docker compose` as environment
variables, which win over `.env`, and are never written to disk decrypted. Another
installation gets its own file — `prod.sops.env` beside it, matched by the same rule —
used with `SECRETS=deploy/compose/prod.sops.env deploy/compose/compose.sh up -d`.
Without sops (not a recipient, or no sops installed), put the secrets in `.env` and call
`docker compose -f deploy/compose/compose.yaml` directly.

**The file holds placeholders** (`placeholder-…`) until the real values are set: replace
the four required ones before anyone else can reach the stack. The two optional ones stay
empty unless used — a Brevo key, once set, sends every mail through Brevo.

**Changing a secret of a running stack.** Postgres takes `POSTGRES_PASSWORD` only when
it creates its volume: on an existing one change it with `ALTER USER sbl PASSWORD '…'`
first, or start over with `compose.sh down -v`. A new JWT secret signs everyone out; new S3
keys need SeaweedFS restarted (`compose.sh up -d`) or the provider's keys changed.

**A new recipient** — a teammate, or the server that runs the stack (its host key
`/etc/ssh/ssh_host_ed25519_key.pub`, or a deploy key of its own): add the public key to
`.sops.yaml`, then re-key the file, or they get "no key could decrypt":
`sops updatekeys -y deploy/compose/secrets.sops.env`. `scripts/check-sops.py` (part of
`scripts/check.sh`) fails while a file is not encrypted or its recipients differ from
its rule.

## Uploads: always S3, any provider

Crests, photos, the media library, waiver scans, receipts and documents are kept in one
S3 bucket (`api/app/storage.py`); no container keeps files of its own, so the API can be
rebuilt or moved without losing any. Every file is still served by the API endpoint that
checks who may see it — nothing is public on the S3 side, and the bucket needs no policy.

**Which S3** is configuration, not code:

- **SeaweedFS in this stack** (the default): `COMPOSE_PROFILES=seaweedfs` starts the
  `storage` service, `SBL_S3_ENDPOINT_URL=http://storage:8333`.
- **An outside provider** (AWS, Hetzner Object Storage, Cloudflare R2, MinIO, …): remove
  `seaweedfs` from `COMPOSE_PROFILES` — `storage` is then not started and nothing waits
  for it — and set `SBL_S3_ENDPOINT_URL` (empty for AWS), `SBL_S3_REGION`,
  `SBL_S3_BUCKET`, the key pair in `S3_ACCESS_KEY` / `S3_SECRET_KEY`, and
  `SBL_S3_ADDRESSING_STYLE=virtual` where the provider wants it (AWS). The bucket is
  created on the first use if the key may create one; otherwise create it beforehand.
  `SBL_S3_PREFIX` lets several installations share one bucket.

**Moving the files** — from a site that kept them on disk, or from one provider to
another — is a copy under the same keys, `python -m app.storage_copy`, run in the api
image against a directory on the host:

```bash
C=deploy/compose/compose.sh
# every file of the configured store into ./uploads-copy
$C run --rm --no-deps -v "$PWD/uploads-copy:/copy" api python -m app.storage_copy export /copy
# ... switch the S3 settings in .env to the new provider, then:
$C run --rm --no-deps -v "$PWD/uploads-copy:/copy" api python -m app.storage_copy import /copy
```

An old uploads directory (`SBL_UPLOADS_DIR` of a site on `SBL_STORAGE=local`) is already
such a directory: `import` it as it is. The same `export` is a backup of every upload.
(`--no-deps` with SeaweedFS still needs `storage` running: `$C up -d storage` first.)

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
deploy/compose/compose.sh down -v      # drop all volumes
deploy/compose/compose.sh up -d --wait # migrate and seed afresh
```

Or keep the volumes and reseed the database only:
`deploy/compose/compose.sh run --rm db-setup api-init --reset`.

## Postgres

This is the first setup that runs the site on Postgres; development and the test suite use
SQLite. What it took is in
`docs/gotchas/sqlite-accepts-schema-and-queries-postgres-refuses-so-the-suite-being-green-says.md`.
