# Deploying a free test instance

Goal: both halves reachable on the public internet, at no cost, for trying things out.
**Not** production — no backup, the database resets on restart, and dev-login is on.

## What's in the box

| File | Purpose |
|---|---|
| `api/Dockerfile` | Backend image. Bakes a **seeded SQLite database** into the image, so there is no external DB and every restart returns to a known state. |
| `render.yaml` | Render blueprint: the API (Docker) + the site (static) in one deploy. |

The frontend calls the API at a **relative** `/api/...` path. Every option below keeps the
browser same-origin (a proxy / rewrite), so there is no CORS setup and no build-time API
URL to bake in.

---

## Option A — Render (simplest, one blueprint)

1. Push the repo to GitHub.
2. [dashboard.render.com](https://dashboard.render.com) → **New → Blueprint** → select the repo.
3. Confirm. Render reads `render.yaml` and creates:
   - `sbl-api` — Docker web service, free plan
   - `sbl-web` — static site, free
4. First build takes a few minutes (the image seeds the DB). Then the site is at
   `https://sbl-web.onrender.com`.

If a service name is already taken, Render adds a suffix (`sbl-api-xyz`). Then edit the
`destination:` of the `/api/*` rewrite in `render.yaml` to the real API URL and push again.

**Trade-offs**

- Free web services **sleep after 15 minutes idle**; the next request wakes them (~1 min).
- The SQLite database is inside the image → a redeploy or a wake-from-sleep **resets it to
  the seeded data**. Good for testing, useless as storage.
- No Java in the image → pairing lists come from the **catalog** only
  (`api/app/pairing/schedules/`); on-demand generation via the JAR is unavailable.

---

## Option B — Fly.io (API) + Cloudflare Pages (site)

Use this if the 15-minute sleep is annoying — Fly keeps a machine warm longer and its
free allowance covers one small always-on VM.

**API on Fly:**

```bash
cd api
fly launch --no-deploy          # generates fly.toml; pick a name, e.g. sbl-api
fly secrets set SBL_JWT_SECRET="$(openssl rand -hex 32)" SBL_DEV_LOGIN=true
fly deploy                       # uses api/Dockerfile
```

In the generated `fly.toml` set `internal_port = 8080` (Fly's default) or add
`ENV PORT=8080`; the Dockerfile already honours `$PORT`.

**Site on Cloudflare Pages:**

1. [dash.cloudflare.com](https://dash.cloudflare.com) → Workers & Pages → **Create → Pages**
   → connect the repo.
2. Build settings: root directory `web`, build command `pnpm install --prod=false && pnpm build`,
   output directory `dist`.
3. Add `web/public/_redirects` so the SPA and the API proxy work:

   ```
   /api/*  https://sbl-api.fly.dev/api/:splat  200
   /*      /index.html                          200
   ```

   (The `200` makes Cloudflare **proxy** rather than redirect — the browser stays on the
   Pages domain.)

---

## Security note — `SBL_DEV_LOGIN`

`SBL_DEV_LOGIN=true` exposes `/api/dev`, which **issues real access tokens for any seeded
account without any verification** — including `admin@sbl.example.com`. That is the whole
point for a test instance (no mail server needed), but it means anyone who finds the URL
is an admin.

For a test instance that's usually an acceptable trade for a link you don't publish. To
close it instead, set `SBL_DEV_LOGIN=false` and configure SMTP (`SBL_SMTP_*`,
`SBL_MAIL_FROM`) — Brevo and Resend both have a free tier — so the email one-time-code
login works.

Leave `SBL_JWT_SECRET` to `generateValue` / a random string. An **empty** secret closes
the protected area entirely (by design); a **known** secret would let anyone forge tokens.

---

## Turning on real sign-in (SMTP)

The UI's sign-in flow is a one-time code sent by email (`POST /api/auth/email/request` /
`/email/verify`) — this is the only sign-in method the frontend offers today. Without SMTP
configured, `api/app/mail.py` falls back to **logging** the code instead of sending it,
which is only useful with `SBL_DEV_LOGIN=true` and shell access to read the log. To make
sign-in actually usable for real users, `render.yaml` declares these variables on
`sbl-api` (see the "SMTP" block there):

| Variable | Default | Notes |
|---|---|---|
| `SBL_SMTP_HOST` | *(none, `sync: false`)* | your provider's SMTP hostname |
| `SBL_SMTP_PORT` | `587` | STARTTLS submission port — check your provider if it differs |
| `SBL_SMTP_USER` | *(none, `sync: false`)* | login name for the SMTP account |
| `SBL_SMTP_PASSWORD` | *(none, `sync: false`)* | login password / API key |
| `SBL_SMTP_STARTTLS` | `true` | STARTTLS on the plaintext connection (ignored if `SBL_SMTP_SSL` is `true`) |
| `SBL_SMTP_SSL` | `false` | implicit TLS/SSL from the first byte instead — set `true` **and** `SBL_SMTP_PORT=465` for a provider that documents that as the normal-client path (e.g. STRATO: `smtp.strato.de:465`, username = the full email address, `587`/STARTTLS documented there as relay-only) |
| `SBL_MAIL_FROM` | *(none, `sync: false`)* | the `From:` address, e.g. `noreply@yourdomain` |

**Where to enter the `sync: false` values:** these are deliberately left out of
`render.yaml` (see the "Security note" above the sign-in section, and the comment next to
each `sync: false` line) — a Render Blueprint prompts for each `sync: false` variable
once, during the **initial** Blueprint creation flow in the Dashboard. If you deploy first
and configure SMTP afterwards, or need to change a value later, go to the `sbl-api`
service in the Render Dashboard → **Environment** tab → add/edit the variable there
directly; a later re-sync of the Blueprint from `render.yaml` does not touch variables
already marked `sync: false`, so this is also how you rotate a password. The value never
gets written back into `render.yaml` or committed to the repo either way.

**Getting real SMTP credentials for testing:** this doc already points at
[Brevo](https://www.brevo.com) and [Resend](https://resend.com) as free-tier options for
closing `SBL_DEV_LOGIN`. Both give you an SMTP username and password/API key on sign-up;
the concrete host and port are on your own account's SMTP settings page in their
dashboard (Brevo's transactional-email SMTP page, Resend's SMTP integration page) — copy
those values into `SBL_SMTP_HOST`/`SBL_SMTP_PORT` rather than assuming a fixed hostname,
since these can change per account/region.

**Checking whether a code was actually sent:** `app.mail` logs every attempt — an `INFO`
line naming the recipient and host on success, an `ERROR` line with the underlying SMTP
error on failure (wrong credentials, wrong port/encryption, connection refused, …). On
Render, that's the `sbl-api` service's **Logs** tab; locally it's just stdout. A 202
response from `/api/auth/email/request` or `/api/auth/register` only means the request was
accepted — it deliberately never reveals whether the address has an account or whether the
mail server accepted the message (see the code comment in
`app.services.login.request_email_code` for why) — the log line is the actual source of
truth for "did it send."

**Google and Microsoft sign-in are not wired up in the UI yet** — the backend already
supports both (`api/app/services/login.py`, `POST /api/auth/oidc/{provider}`) and
`GET /api/auth/providers` already reports `SBL_GOOGLE_CLIENT_ID` /
`SBL_MICROSOFT_CLIENT_ID` availability for whenever a frontend button is built against it,
but for now email is the only sign-in method the site actually offers, so `render.yaml`
does not declare those two variables. Once a Google/Microsoft sign-in button exists in
`web/`, add `SBL_GOOGLE_CLIENT_ID`, `SBL_MICROSOFT_CLIENT_ID` (both `sync: false` —
deployment-specific, not secret) and `SBL_MICROSOFT_TENANT` (default `common`) to
`sbl-api` in `render.yaml` the same way as the SMTP variables above.

Once SMTP is configured (and, later, an OIDC provider if one gets added), `SBL_DEV_LOGIN`
can be turned off.
