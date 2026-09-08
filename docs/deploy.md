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

## Configuration — plain environment variables

Everything `sbl-api` needs, including `SBL_SMTP_PASSWORD`, is an ordinary env var —
declared in `render.yaml` with a fixed `value:` where the setting doesn't depend on the
deployment, or `sync: false` where it does (SMTP settings, since they depend on whichever
provider is in use).

| Variable | How it's set | Notes |
|---|---|---|
| `SBL_JWT_SECRET` | `render.yaml`, auto-generated | **empty closes the protected area entirely** (by design); a known/reused value would let anyone forge tokens |
| `SBL_DEV_LOGIN` | `render.yaml`, `true` | see the security note below before turning this on anywhere but a private test URL |
| `SBL_ALLOW_REGISTRATION` | `render.yaml`, `true` | lets the self-registration tab on `/account` work |
| `SBL_CORS_ORIGINS` | `render.yaml`, fixed | only matters if the site is ever called cross-origin; the `/api/*` rewrite already keeps the browser same-origin |
| `SBL_SMTP_HOST` | Dashboard (`sync: false`) | your provider's SMTP hostname, e.g. `smtp.strato.de` |
| `SBL_SMTP_PORT` | Dashboard (`sync: false`) | `587` for STARTTLS, `465` for implicit TLS/SSL — check your provider |
| `SBL_SMTP_SSL` | Dashboard (`sync: false`) | `true` for a provider that documents implicit TLS as the normal-client path (e.g. STRATO: `smtp.strato.de:465` — STRATO documents `587`/STARTTLS there as relay-only, not for a normal client like this app) |
| `SBL_SMTP_STARTTLS` | `render.yaml`, `true` | ignored if `SBL_SMTP_SSL` is `true` (the two aren't combined) |
| `SBL_SMTP_USER` | Dashboard (`sync: false`) | login name for the SMTP account (often the full email address) |
| `SBL_SMTP_PASSWORD` | Dashboard (`sync: false`) | the mailbox password / API key |
| `SBL_MAIL_FROM` | Dashboard (`sync: false`) | the `From:` address, e.g. `web@yourdomain` |

**Where the Dashboard-only (`sync: false`) values actually get entered:** a Render
Blueprint only prompts for a `sync: false` variable the *first* time a service is
provisioned — adding one to `render.yaml` later does nothing for a service that already
exists (that's exactly what cost real time to track down while getting this deployment's
SMTP working). For an existing service, add these directly on its Environment tab
(**Environment Variables**, not Secret Files) instead; a later Blueprint re-sync leaves an
existing `sync: false` value alone either way, so this is also how you change one, e.g. to
rotate the SMTP password.

**Getting real SMTP credentials for testing:** [Brevo](https://www.brevo.com) and
[Resend](https://resend.com) both have a free tier and hand you an SMTP username and
password/API key on sign-up; the concrete host and port are on your own account's SMTP
settings page in their dashboard — copy those in rather than assuming a fixed hostname,
since they can change per account/region.

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
supports both (`api/app/services/login.py`, `POST /api/auth/oidc/{provider}`), and
`GET /api/auth/providers` already reports `SBL_GOOGLE_CLIENT_ID` /
`SBL_MICROSOFT_CLIENT_ID` availability for whenever a frontend button is built against it
— but for now email is the only sign-in method the site actually offers. Once a
Google/Microsoft button exists in `web/`, add `SBL_GOOGLE_CLIENT_ID`,
`SBL_MICROSOFT_CLIENT_ID` (`sync: false` — deployment-specific, not secret) and
`SBL_MICROSOFT_TENANT` (default `common`, fixed `value:`) to `render.yaml` the same way as
the SMTP variables above.

**`SBL_DEV_LOGIN=true`** exposes `/api/dev`, which **issues real access tokens for any
seeded account without any verification** — including `admin@sbl.example.com`. That's the
whole point for a test instance (no mail server needed to try out roles), but it means
anyone who finds the URL is an admin. For a private test URL that's usually an acceptable
trade; once SMTP (and, later, an OIDC provider) is configured, it can be turned off.
