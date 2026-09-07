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
