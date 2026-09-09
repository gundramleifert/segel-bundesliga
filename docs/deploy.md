# Deploying a free test instance

Goal: both halves reachable on the public internet, at no cost, for trying things out.
**Not** production — no backup, the database resets on restart, and dev-login is on.

## What's in the box

| File | Purpose |
|---|---|
| `api/Dockerfile` | Backend image. Bakes a **seeded SQLite database** and **`render.env`** (all non-secret config) into the image — see "Configuration" below. |
| `api/render.env` | Every non-secret setting for the Render deployment, as plain `KEY=value` lines — checked into git, edited like code. |
| `render.yaml` | Render blueprint: the API (Docker) + the site (static) in one deploy. Declares no env vars for the API — see "Configuration". |

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

## Configuration — baked into the image, not the Render dashboard

Render's dashboard Environment Variables turned out unreliable for this service in
practice: `sync: false` slots that only get created on a service's *first* provisioning
(a no-op for one added to `render.yaml` afterwards), and — what finally happened here —
variables that existed in the dashboard with **no value**, silently leaving every setting
at its code default. Chasing that cost real time, so the deployment no longer depends on
it at all for anything non-secret.

**Every non-secret setting lives in `api/render.env`**, a plain `KEY=value` file checked
into git. `api/Dockerfile` copies it to `.env` at build time
(`RUN cp render.env .env`), and `api/app/config.py` already reads `.env` via
pydantic-settings (`SettingsConfigDict(env_file=".env", …)` — the same mechanism used for
local development). To change a setting: edit `render.env`, commit, push — a normal code
change, deployed by the same git push as everything else, nothing to click in a
dashboard. `render.yaml` declares **no env vars** for `sbl-api` at all.

The two real credentials are the deliberate exception — they never go into git, `.env`,
or `render.env`:

| Secret File | Notes |
|---|---|
| `SBL_JWT_SECRET` | **empty closes the protected area entirely** (by design); a known/reused value would let anyone forge tokens |
| `SBL_SMTP_PASSWORD` | the mailbox password / API key |

**Setting them:** `sbl-api` service → **Environment** tab → **Secret Files** → **Add
Secret File** → filename *exactly* the variable name → the value as the file's whole
content, nothing else (a trailing newline from pasting is fine — pydantic-settings strips
it). Mechanically, `app/config.py` sets pydantic-settings' `secrets_dir` to `/etc/secrets`
— exactly where Render mounts Secret Files — so at startup it looks there for a file
matching a setting with no env var set, and uses its content. That directory doesn't
exist on a machine without any Secret Files (e.g. your own laptop), so this is a no-op
there. Secret Files sit outside Blueprint sync entirely, so they don't share the
dashboard-env-var reliability problem above. To rotate a value, edit the Secret File in
place — nothing else changes.

If a leftover **plain environment variable** of either name exists on this service from
before this approach, delete it — an explicit env var still wins over both the Secret
File and `render.env`, so it would keep shadowing the real value.

**Getting real SMTP credentials for testing:** [Brevo](https://www.brevo.com) and
[Resend](https://resend.com) both have a free tier and hand you an SMTP username and
password/API key on sign-up; the concrete host and port are on your own account's SMTP
settings page in their dashboard — copy those into `render.env` rather than assuming a
fixed hostname, since they can change per account/region.

---

## When the platform blocks outbound SMTP entirely (Render did)

Confirmed with a dev-only network probe (since removed, see below): on this Render plan,
**both** port 465 and 587 to a real SMTP server time out — an egress firewall, not a
wrong setting anywhere. No SMTP port/TLS combination gets past that; the only way through
is a provider's **HTTPS API** instead of raw SMTP, since HTTPS clearly isn't blocked (the
platform itself depends on it).

`api/app/mail.py` supports this as an **opt-in, dev/test-only alternate transport**:
Brevo's HTTP API (`POST https://api.brevo.com/v3/smtp/email`). It activates automatically
whenever `SBL_BREVO_API_KEY` is set — checked *before* SMTP in `send_login_code` — with
the SMTP path otherwise untouched and still the intended one for a host that can actually
reach an SMTP server (e.g. a plain VPS instead of Render).

**Setting it up:**
1. Sign up at [brevo.com](https://www.brevo.com) (free tier).
2. Create an API key: Settings → SMTP & API → API Keys.
3. Verify the `SBL_MAIL_FROM` address as a sender in Brevo (usually just a confirmation
   link sent to that inbox — full domain authentication via DNS records improves
   deliverability but isn't required to start).
4. Add `SBL_BREVO_API_KEY` as a **Secret File** the same way as `SBL_JWT_SECRET` /
   `SBL_SMTP_PASSWORD` (it's a real credential, not something for `render.env`).

Verified end to end with a real Brevo account and API key: a login email sent through the
live Render deployment arrived in the inbox. The three dev-only diagnostic routes used to
establish this (`/api/dev/smtp-config`, `/api/dev/test-email`, `/api/dev/network-probe`)
have since been removed from `app/routers/dev.py` — they did their job. If a future
deployment needs the same kind of investigation, `git log` has the implementation to
resurrect.

**Checking whether a code was actually sent:** `app.mail` logs every attempt — an `INFO`
line naming the recipient and host (or "via Brevo") on success, an `ERROR` line with the
underlying error on failure (wrong credentials, wrong port/encryption, connection
refused, Brevo's error body, …). On Render, that's the `sbl-api` service's **Logs** tab;
locally it's just stdout. A 202 from `/api/auth/email/request` or `/api/auth/register`
only means the request was accepted — it deliberately never reveals whether the address
has an account or whether the mail server accepted the message (see the code comment in
`app.services.login.request_email_code` for why), so the logs are the actual source of
truth for "did it send."

**Google and Microsoft sign-in are not wired up in the UI yet** — the backend already
supports both (`api/app/services/login.py`, `POST /api/auth/oidc/{provider}`), and
`GET /api/auth/providers` already reports `SBL_GOOGLE_CLIENT_ID` /
`SBL_MICROSOFT_CLIENT_ID` availability for whenever a frontend button is built against it
— but for now email is the only sign-in method the site actually offers. Once a
Google/Microsoft button exists in `web/`, add `SBL_GOOGLE_CLIENT_ID`,
`SBL_MICROSOFT_CLIENT_ID` (public identifiers, not secret) and `SBL_MICROSOFT_TENANT`
(default `common`) to `render.env` the same way as the SMTP settings above.

**`SBL_DEV_LOGIN=true`** (in `render.env`) exposes `/api/dev`, which **issues real access
tokens for any seeded account without any verification** — including
`admin@sbl.example.com`. That's the whole point for a test instance (no mail server
needed to try out roles), but it means anyone who finds the URL is an admin. For a
private test URL that's usually an acceptable trade; once SMTP (and, later, an OIDC
provider) is confirmed working, it can be turned off by editing `render.env`.

**Getting the first real admin without `SBL_DEV_LOGIN`:** once dev-login is off, nothing
in the interface can grant the very first `admin` role — every role-granting endpoint
requires being `admin` already. `SBL_ADMIN_EMAILS` solves exactly that bootstrap problem:
any address listed there (case-insensitive) is granted `admin` automatically the moment
it successfully signs in, through any provider (`app.services.login._resolve_user`) —
checked on every sign-in, so adding an address later still takes effect on that person's
next login. Add it to `render.env` as a JSON array, the same way as `SBL_CORS_ORIGINS`:
`SBL_ADMIN_EMAILS=["you@example.com"]`. From there, that account can grant `admin`,
`editor`, `race_officer`, and `club_manager` to anyone else via the accounts admin UI
(Story Z-2) — the whitelist only needs to cover whoever bootstraps the first admin.
