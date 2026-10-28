# Running the site on a server

The site on one machine of our own, with Docker Compose: Postgres, the API, the SPA
behind Caddy, and SeaweedFS for the uploads. This page is the runbook: what the machine
needs, the first installation, updates, backups and what to watch.
`deploy/compose/README.md` is the reference for the stack itself (services, settings,
secrets, storage).

## Read this first — it is not ready for real data yet

Two things make this a **demonstration or pre-production** install today, not one that
keeps a club's real data:

- **The first start also seeds the test system.** `db-setup` runs `app.seed_test_setup` on
  an empty database: the real 2026 season (results, news, pictures) — and also the 44 test
  accounts (`@….example.com`) and the demo series of invented data. The demo series stay
  unpublished here (`SEED_PUBLISH_DEMO=false`), but the accounts exist. A seed without
  them is the next step of `docs/PLAN_SEEDING.md` (S-0); so is staging as a restored
  copy of prod.
- **An update can lose the data.** As long as nothing is in production there is **one**
  Alembic migration, regenerated whenever the models change (CLAUDE.md, "Migrations").
  An existing database cannot be upgraded across such a change: `alembic upgrade head`
  finds nothing to do and the code meets a schema it does not expect. Such an update is a
  reset.

Both end the day the project starts a migration chain and a production seed. Until then,
anything entered on the server is test data.

## What the machine needs

| | |
|---|---|
| CPU, RAM | 2 cores, **2 GB** RAM (1 GB is the minimum). Idle the stack uses ~300 MB; a pairing-list draw or print starts a Java process, and a picture upload is resized in memory. |
| Disk | 10 GB to start: the images (~2 GB), Postgres, the uploads in SeaweedFS. |
| Software | Docker Engine with the Compose plugin (v2.20 or newer — `required: false` in `depends_on`), git, [sops](https://github.com/getsops/sops) 3.7 or newer. |
| Network | Outbound HTTPS for the build (Maven, pnpm, PyPI, GitHub) and the first seed (35 pictures from SmugMug); outbound SMTP or HTTPS to Brevo for mail. |

## First installation

**1. A key for the server.** sops decrypts with an SSH key and needs the private key as
a file. Give the server its own key, so it reads only the secrets meant for it:

```bash
# on the server, as the user that will run the stack
ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519 -N "" -C "sbl-server"
cat ~/.ssh/id_ed25519.pub
```

**2. Its own secrets file** (on your machine, as a recipient). Each installation has its
own `*.sops.env` beside `secrets.sops.env`; give it a rule in `.sops.yaml` naming you
and the server, so neither your laptop's file nor the server's opens the other:

```yaml
# .sops.yaml
keys:
  - &gundram "ssh-ed25519 AAAA… Gundram Leifert"
  - &server  "ssh-ed25519 AAAA… sbl-server"
creation_rules:
  - path_regex: deploy/compose/prod\.sops\.env$
    age: [*gundram, *server]
  - path_regex: deploy/compose/[^/]*\.sops\.env$   # stays last: the first match wins
    age: [*gundram]
```

```bash
sops deploy/compose/prod.sops.env   # opens an empty file in $EDITOR, encrypts it on save
```

with real values — generate each with
`python3 -c "import secrets; print(secrets.token_urlsafe(48))"`:

```dotenv
POSTGRES_PASSWORD=…
SBL_JWT_SECRET=…
S3_ACCESS_KEY=…
S3_SECRET_KEY=…
SBL_SMTP_PASSWORD=
SBL_BREVO_API_KEY=
```

Commit `.sops.yaml` and `prod.sops.env`; `scripts/check-sops.py` (in `scripts/check.sh`)
fails if the file is not encrypted or not encrypted for the rule's keys.

**3. The code and the settings** on the server:

```bash
git clone https://github.com/gundramleifert/segel-bundesliga.git && cd segel-bundesliga
cp deploy/compose/.env.example deploy/compose/.env
```

In `deploy/compose/.env`, at least:

| Setting | Value on a server |
|---|---|
| `SBL_DEV_LOGIN` | `false` — `true` hands out admin tokens without any check |
| `SBL_CORS_ORIGINS` | `["https://<your domain>"]` |
| `SBL_ADMIN_EMAILS` | `["you@…"]` — the first admin, made on their first sign-in (below, "The first admin") |
| `SBL_SMTP_HOST`, `_PORT`, `_USER`, `SBL_MAIL_FROM` | your mail server; without one, sign-in codes only reach the api log |
| `SBL_ALLOW_REGISTRATION` | `false` until people may register themselves |
| `WEB_PORT` | the port the TLS proxy (below) talks to, e.g. `8080` |

**4. Start it:**

```bash
SECRETS=deploy/compose/prod.sops.env deploy/compose/compose.sh up --build -d --wait
```

The first build takes a few minutes (the pairing tool, the SPA); `db-setup` then migrates
and seeds. `compose.sh ps` shows every service healthy and `db-setup` exited 0. Put
`export SECRETS=$PWD/deploy/compose/prod.sops.env` in the user's shell profile so no
later command forgets it — without it `compose.sh` uses `secrets.sops.env`, the
placeholders.

**5. HTTPS in front.** The stack answers plain HTTP on `WEB_PORT`; TLS is the job of a
proxy on the host — a Caddy, nginx or Traefik already there, or the hoster's load
balancer. With a Caddy on the host, the whole configuration is:

```caddyfile
liga.example.org {
	reverse_proxy 127.0.0.1:8080
}
```

The live results are Server-Sent Events: a proxy that buffers responses (nginx by
default) needs `proxy_buffering off` for `/api/live`. Caddy passes them through.

**6. Close the ports.** `compose.yaml` publishes `WEB_PORT` and `S3_PORT` on every
interface. Let only 22, 80 and 443 in through the firewall — the S3 endpoint is signed,
but nobody outside needs it, and the plain-HTTP port must only be reached through the
proxy.

**7. Check it:** the site opens on the domain; sign in with the address in
`SBL_ADMIN_EMAILS` (the code arrives by mail); `compose.sh logs db-setup` holds a ready
admin token from the seed — signed with the real JWT secret, so treat that log as a
secret and clear it with `compose.sh rm -f db-setup` once you are in.

## Updates

```bash
git pull
deploy/compose/compose.sh up --build -d --wait
```

`db-setup` runs again on every `up`: it migrates, and seeds only an empty database. Read
"it is not ready for real data" above first — while the migration is regenerated, a pull
that changed the models needs a reset (`compose.sh down -v`, then `up`), and a backup
before it is all that keeps anything.

## Backups

Two things hold data, and both are copied while the stack runs:

```bash
C=deploy/compose/compose.sh
day=$(date +%F); mkdir -p ~/backup/$day

# the database — one compressed custom-format file
$C exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > ~/backup/$day/db.dump

# every upload, under its key — the same folder layout as a local uploads directory
$C run --rm --no-deps --user "$(id -u):$(id -g)" -v ~/backup/$day/uploads:/copy \
  api python -m app.storage_copy export /copy
```

The secrets need no backup — they are in git, encrypted — but the **server's private key**
does, or nobody can decrypt `prod.sops.env` after the machine is gone except the other
recipients. Keep the backups off the machine (another server, a NAS, an S3 bucket of
another provider); a nightly cron line around the two commands is enough.

**Restoring** — the API stopped, so nothing holds the tables open:

```bash
$C stop api
$C exec -T db sh -c 'pg_restore --clean --if-exists -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < ~/backup/<day>/db.dump
$C run --rm --no-deps -v ~/backup/<day>/uploads:/copy:ro api python -m app.storage_copy import /copy
$C up -d --wait
```

Restore both from the same night: the database names the files, the files are what it
names.

## Watching it

- **Health:** `compose.sh ps` — every service has a healthcheck; `restart:
  unless-stopped` brings a crashed one back, and the stack comes back after a reboot as
  long as Docker starts at boot.
- **Logs:** `compose.sh logs -f api` (every request, every mail attempt — "did the code
  go out" is answered here, never by the API's 202), `compose.sh logs web` (Caddy).
- **Resources:** `docker stats`. No service has a memory limit; on a 2 GB machine that
  is fine, on a shared one set `mem_limit` in `compose.yaml`.

## Moving the uploads to another S3

Interchangeable by configuration — `deploy/compose/README.md`, "Uploads": `export` with
the old settings, change `SBL_S3_*` (and `COMPOSE_PROFILES` when SeaweedFS is no longer
needed), `import`, `up -d`.

## The first admin

With dev login off, nothing in the interface can grant the very first `admin` — every
role-granting endpoint needs an admin already. `SBL_ADMIN_EMAILS` solves that bootstrap:
an address listed there (case-insensitive, a JSON list) becomes `admin` the moment it
signs in through any method (`app.services.login._resolve_user`), checked on every
sign-in, so an address added later takes effect on that person's next login. From there,
that account grants roles to everyone else (Story Z-2).

**Mail must reach people for that.** Sign-in by one-time code needs `SBL_SMTP_*`, or
`SBL_BREVO_API_KEY` where the host blocks outbound SMTP (HTTPS to Brevo instead); without
either, the code only reaches the api log (`compose.sh logs api`). The sender,
`SBL_MAIL_FROM`, must be verified with the mail provider, or codes are accepted and then
silently dropped.
