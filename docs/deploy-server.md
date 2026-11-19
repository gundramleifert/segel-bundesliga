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
`docs/PLAN_SEEDING.md` (S-0), and it ends there. **Updates keep the data** (since 2026-11-19): the
migrations chain on the baseline the server was installed with — § Migrations.

## Our server

One machine runs **production and staging** side by side, each a Compose stack of its own
(project name, containers, volumes, images, secrets), behind the host's Caddy.

| | Production | Staging |
|---|---|---|
| Site | **https://deutsche-segelliga.de** (`www.` redirects) | **https://staging.deutsche-segelliga.de** |
| Clone | `~/sbl` | `~/sbl-staging` |
| Secrets | `deploy/compose/prod.sops.env` | `deploy/compose/staging.sops.env` |
| `.env` | `WEB_PORT=127.0.0.1:8080`, `S3_PORT=127.0.0.1:8333` | `COMPOSE_PROJECT_NAME=segelliga-staging`, `WEB_PORT=127.0.0.1:8081`, `S3_PORT=127.0.0.1:8334`, `SBL_ENVIRONMENT=staging`, **no `SBL_SMTP_HOST`** |
| Data | its own, kept across every update | **a copy of production's**, taken anew on every deploy |

- **Machine:** `segelliga-1` at Hetzner, **`178.104.43.254`** (no alias in `~/.ssh/config`,
  use the IP). `ssh sbl@178.104.43.254` for everything here — user `sbl`, docker group,
  your own key; `root@` only for the host (Caddy, packages).
- **HTTPS:** Caddy on the host (systemd), `/etc/caddy/Caddyfile`: each domain →
  `reverse_proxy` to its stack's `WEB_PORT`. It stays on the host and not in a stack
  because two stacks share ports 80 and 443.
- **Staging is red.** `SBL_ENVIRONMENT=staging` in its `.env` paints every page's top bar
  red and names it there. The web container's Caddy hands the value to the SPA as
  `/environment.js` when it starts — not built in, since production runs staging's images.
- **Staging sends no mail.** Its database holds production's real people; without
  `SBL_SMTP_HOST` a sign-in code goes to its api log only
  (`compose.sh logs api | grep -i code`). Sign in there with a password, or read the code
  from the log. No dev login either — `compose.yaml` fixes it off.

### Deploying — a release candidate on staging, then the release

Every change reaches production as a **release**: a tag `vX.Y.Z` on `main`, preceded by a
**release candidate** `vX.Y.Z-rc.N` on the same commit that staging has run. Both are
**annotated** tags (who, when, a message), so `git describe` names them; production only
ever takes a release, never an rc. The footer of every page shows what runs: *Version
0.1.0* in production, *Version 0.1.0-rc.7 · 1b2d26a* on staging — `deploy.sh` writes `SBL_VERSION` and `SBL_COMMIT` to the stack's `.env`
when it starts it, and the web container hands them out with `SBL_ENVIRONMENT`.
`scripts/deploy.py` (a uv script with a Typer CLI) does it from your machine; the server
side, `deploy/compose/deploy.sh`, **refuses** production for anything staging has not
passed on a copy of the real data — so a migration has always run once on that data
before it touches production.

```bash
scripts/deploy.py status            # what prod and staging run: tag, image, migration
scripts/deploy.py staging 1.2.0     # check.sh, tag v1.2.0-rc.N on main, run it on staging
#   try it on https://staging.deutsche-segelliga.de; broken → fix on main, the same command again (rc.N+1)
scripts/deploy.py prod              # tag v1.2.0 on the commit staging passed, deploy it
scripts/deploy.py logs staging api  # the last lines of a service's log
```

`staging` wants `main` checked out and pushed (a tag names what origin has), runs
`scripts/check.sh` unless `--no-check`, picks the next `rc.N`, and pushes the tag. On the
server it runs `deploy.sh` **as that tag has it** (`git show <tag>:…` into a temporary
file — never the copy in a clone it is about to check out). `deploy.sh staging` takes
production's database (`pg_dump`) and uploads, empties staging, restores them, builds the
rc **on the server** — the images carry their commit as the label
`org.opencontainers.image.revision` — starts it (`db-setup` migrates) and records in
`~/staging-passed` the rc, its commit and the Alembic revision it reached.

`prod` reads `~/staging-passed`, asks, tags the release on that commit and runs `deploy.sh
prod`: it refuses unless the release is that commit and staging still runs it at that
revision, from images built from it; then it backs production up into
`~/backup/<date-time>/` (database and uploads), checks the commit out, **re-tags staging's
images as production's** — nothing is built again, production runs the very images
staging ran — starts them and checks production reached the same revision.

Without the tool, the same by hand: `git tag v1.2.0-rc.1 && git push origin v1.2.0-rc.1`,
then on the server `bash <(git -C ~/sbl-staging show v1.2.0-rc.1:deploy/compose/deploy.sh)
staging v1.2.0-rc.1` after a `git -C ~/sbl-staging fetch --tags`; likewise `prod v1.2.0`.

**Versions:** `X` for a change people must learn anew, `Y` for a new feature or a
migration, `Z` for a fix. A staging run takes ~5 minutes (the build), a production run ~1.

**When it fails:** a failed migration leaves the old schema (Postgres runs it in one
transaction) — fix it on `main`, a new rc. Restore a backup (§ Backups) only if data was
damaged. **Never `down -v` on this machine** — it deletes a stack's database and uploads.

### Setting up staging (done once, 2026-11-19)

```bash
ssh sbl@178.104.43.254
git clone -q https://github.com/gundramleifert/segel-bundesliga.git ~/sbl-staging
cd ~/sbl-staging/deploy/compose && cp ~/sbl/deploy/compose/.env .env
# in .env: COMPOSE_PROJECT_NAME=segelliga-staging, WEB_PORT=127.0.0.1:8081,
# S3_PORT=127.0.0.1:8334, SBL_SITE_URL and SBL_CORS_ORIGINS to the staging domain,
# SBL_SMTP_HOST= (empty), SBL_ENVIRONMENT=staging
```

The DNS record `staging.deutsche-segelliga.de A 178.104.43.254`, and as `root` a block in
`/etc/caddy/Caddyfile` — `staging.deutsche-segelliga.de { reverse_proxy 127.0.0.1:8081 }` —
then `systemctl reload caddy`.

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
4. It runs on a copy of production on staging before production (§ Deploying), always.

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
database. Take a backup first (§ Backups); our own server deploys only through `deploy.sh`
(§ Our server).

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
