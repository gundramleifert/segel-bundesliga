# Running the site on a server

The site on one machine of our own, with Docker Compose: Postgres, the API, the SPA
behind Caddy, and SeaweedFS for the uploads. This page is the runbook: what the machine
needs, the first installation, updates, backups and what to watch.
`deploy/compose/README.md` is the reference for the stack itself (services, settings,
secrets, storage).

## Read this first — the seed still holds test accounts

**The first start also seeds the test system.** `db-setup` runs `app.seed_test_setup` on
an empty database: the real 2026 season (results, news, pictures) — and also the 44 test
accounts (`@….example.com`). A seed without them is the next step of
`docs/PLAN_SEEDING.md` (S-0); so is staging as a restored copy of prod. That ends with the seed of S-0. **Updates keep the data** (since 2026-11-19): the
migrations chain on the baseline the server was installed with — § Migrations.

## Our server

| | |
|---|---|
| Site | **https://deutsche-segelliga.de** (`www.` redirects to it) |
| Machine | `segelliga-1` at Hetzner, **`178.104.43.254`** — no DNS alias in anyone's `~/.ssh/config`, use the IP |
| Sign in | `ssh sbl@178.104.43.254` — user `sbl` (docker group), with your own key; `root` only for the host |
| Repository | `~/sbl`, a clone of `main` |
| Secrets | `deploy/compose/prod.sops.env` (`.sops.yaml`: you and the server); always `export SECRETS=$HOME/sbl/deploy/compose/prod.sops.env` before `compose.sh` |
| Settings | `~/sbl/deploy/compose/.env` — `WEB_PORT=127.0.0.1:8080`, `SBL_SITE_URL=https://deutsche-segelliga.de` |
| HTTPS | Caddy on the host, `/etc/caddy/Caddyfile` → `127.0.0.1:8080` |

**Deploying `main`** — after it is pushed and `scripts/check.sh` is green. From your machine,
in one go (the build takes a few minutes):

```bash
ssh sbl@178.104.43.254 'set -e; cd sbl
export SECRETS=$HOME/sbl/deploy/compose/prod.sops.env C=deploy/compose/compose.sh
day=$(date +%F-%H%M); mkdir -p ~/backup/$day                       # 1. backup first
$C exec -T db sh -c "pg_dump -U \$POSTGRES_USER -d \$POSTGRES_DB -Fc" > ~/backup/$day/db.dump
git pull --ff-only                                                 # 2. the code
$C up --build -d --wait                                            # 3. build; db-setup migrates
$C exec -T db sh -c "psql -U \$POSTGRES_USER -d \$POSTGRES_DB -Atc \"select version_num from alembic_version\""
$C ps'
```

Then check: `version_num` is the newest file's `revision` in `api/alembic/versions/`, every
service is healthy, `$C logs db-setup` ends without a traceback, and the change is visible
on the site. A failed migration leaves the old schema (Postgres runs it in one transaction):
fix it in a new commit and deploy again; restore the backup (§ Backups) only if data was
damaged. **Never `down -v` here** — it deletes the database and every upload.

## Migrations

`db-setup` runs `alembic upgrade head` on every `up`. The chain starts at
`7133017ca682_initial_schema.py`, the schema the server was installed with — **frozen**:
never edited, never regenerated (`tests/unit/test_migrations.py` checks its hash). A model
change ships with a new migration in the same commit:

1. Change the model.
2. In `api/`, against a database at the current head (the dev database after
   `uv run python -m app.seed_test_setup`):
   `uv run alembic revision --autogenerate -m "what changes, in a sentence"`. Read what it
   wrote: autogenerate misses renames (it drops and adds — the data is lost) and server
   defaults; a new required column needs a default or a data step for the rows already
   there. Fill `downgrade()` too.
3. `uv run pytest tests/unit/test_migrations.py` — red if models and migrations differ.
4. A migration that moves or rewrites data is tried on a copy of production first:
   restore a server backup into the dev Postgres (§ Backups, *Restoring*), `alembic
   upgrade head`, look.

## What the machine needs

| | |
|---|---|
| CPU, RAM | 2 cores, **2 GB** RAM (1 GB is the minimum). Idle the stack uses ~300 MB; a pairing-list draw or print starts a Java process, and a picture upload is resized in memory. |
| Disk | 10 GB to start: the images (~2 GB), Postgres, the uploads in SeaweedFS. |
| Software | Docker Engine with the Compose plugin (v2.20 or newer — `required: false` in `depends_on`), git, [sops](https://github.com/getsops/sops) 3.7 or newer. |
| Network | Outbound HTTPS for the build (Maven, pnpm, PyPI, GitHub) and the first seed (35 pictures from SmugMug); outbound SMTP (port 587) for mail. |

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

`db-setup` runs again on every `up`: it migrates (§ Migrations), and seeds only an empty
database. Take a backup first (§ Backups); for our own server the whole sequence is in
§ Our server.

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

The secrets need no backup — they are in git, encrypted — and neither does the **server's
private key**: it is replaceable. A new server makes its own key; put its public half in
`.sops.yaml` in place of the old one and re-key from a laptop that is a recipient
(`sops updatekeys -y deploy/compose/prod.sops.env`), so the dead machine's key is out of
the game too. What does need a backup is **your own private key** (`~/.ssh/id_ed25519`,
in a password manager): without a person's recipient key nobody can re-key. Keep the
backups off the machine (another server, a NAS, an S3 bucket of
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
  Both go to journald, because the api log holds every request's IP address and the
  privacy policy promises it is gone after **14 days**. Set that once on the host:

      sudo mkdir -p /etc/systemd/journald.conf.d
      printf '[Journal]\nMaxRetentionSec=14day\n' | sudo tee /etc/systemd/journald.conf.d/retention.conf
      sudo systemctl restart systemd-journald
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

**Mail must reach people for that.** Sign-in by one-time code needs `SBL_SMTP_*` (port 587 with STARTTLS; some hosts block 25 and 465); without it, the code only reaches the api log (`compose.sh logs api`). The sender,
`SBL_MAIL_FROM`, must be verified with the mail provider, or codes are accepted and then
silently dropped.

Test the settings without sending anything — it connects, encrypts and signs in the way a
send does — and, once that works, send yourself one login mail:

```bash
deploy/compose/compose.sh exec api python -m app.mail
deploy/compose/compose.sh exec api python -m app.mail --send you@example.com
```
