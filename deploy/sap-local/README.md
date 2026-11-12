# SAP Sailing Analytics, locally, for tests

SAP hosts SAP Sailing Analytics for us, and it is the live scoring for the 2027 season
(agreed 2026-11-01). Until we have access to theirs, this folder runs the same server on
one machine, so the integration can be built and tried against it. Everything needed is
in this folder: SAP's published Docker image, no clone of their repository, no build.

## What you need

- Docker with Compose, and about **8 GB RAM** free while it runs (SAP's own sizing for a
  league like ours).
- To be a sops recipient (`.sops.yaml`) for the map in the race viewer — the Google Maps key
  is in `deploy/compose/secrets.sops.env`. Without it everything runs except the map.

## Start

From the repository root:

```bash
sops exec-env deploy/compose/secrets.sops.env 'docker compose -f deploy/sap-local/compose.yaml up -d'
```

Without sops, `docker compose -f deploy/sap-local/compose.yaml up -d` starts it without a map.
The first start downloads ~3.5 GB of images; the server is up about half a minute after
the containers start:

```bash
curl -s http://127.0.0.1:8888/gwt/status        # JSON with the build version once it is up
```

| What | Where |
|---|---|
| Admin console | http://127.0.0.1:8888/gwt/AdminConsole.html — user `admin`, password `admin` |
| Start page | http://127.0.0.1:8888/index.html |
| API | http://127.0.0.1:8888/sailingserver/api/v1/regattas — the same API `app/imports/sap.py` reads on `www.sapsailing.com` |

Everything listens on `127.0.0.1` only: the admin password is the published default.

## Let our site embed it

```bash
deploy/sap-local/configure.sh
```

Lets the dev site (`localhost:5173`) and the e2e stacks (`5173+n`) show SAP's race viewer
and leaderboard in a frame — SAP sends `frame-ancestors` with only the origins listed.
That list is the one setting SAP's REST API does not offer (only the admin console's
*Local Server Management › CORS and CSP "frame-ancestors"*), so the script writes the
MongoDB document behind it and restarts the server. Everything else — events, regattas,
competitors, the boats per race — goes through the REST API, which takes `admin:admin`
as basic auth here. SAP's hosted server is configured by SAP: they add our domains.

## Stop and reset

```bash
docker compose -f deploy/sap-local/compose.yaml down       # stop; regattas stay
docker compose -f deploy/sap-local/compose.yaml down -v    # stop and forget everything
```

Empty it without forgetting the six boats and the settings — every test run and every
send leaves events behind:

```bash
deploy/sap-local/clean.sh
```

## A whole season on it

`scripts/sap-season.py` plays the 1. Liga 2027 on this SAP, through the site as an
organizer and a race committee would — `tilt up` must run, its backend talks to this SAP:

```bash
scripts/sap-season.py seed                                   # 1: reseed the site, empty SAP
scripts/sap-season.py send --series dsbl-1-2027              # 2: every act to SAP …
scripts/sap-season.py send --event dsbl-1-2027-friedrichshafen   # … or one
scripts/sap-season.py sail --event dsbl-1-2027-friedrichshafen   # 3: sail it at SAP, live
scripts/sap-season.py all                                    # the three in a row
```

Stage 2 gives an act without announced dates practice dates (only in the local database)
and a draw from the catalog, marks it scored on SAP and sends it. Stage 3 publishes and
starts the act, then posts one race every `--every` seconds (default 10) to SAP the way
the Race Manager app does — a random order, now and then a DSQ; the site takes each one by
itself while the act is live (`SBL_SAP_POLL_SECONDS`, 5 under Tilt), so
http://localhost:5173/1-liga/2027/act-1/results fills race by race.

## Send an event to it (DSL→SAP, Story VA-15)

```bash
deploy/sap-local/boats.sh          # once: the league's six J/70s, ids in boats.json
cd api && uv run python -m app.imports sap-send demo-2-2026-act-3 \
    --base-url http://127.0.0.1:8888/sailingserver/api --boats ../deploy/sap-local/boats.json
```

Creates the event, a flight per race column (`F1`…) with its races as fleets
(`Race 1`…), the teams under their club codes, and our pairing list race by race. Sending
again keeps the teams and replaces the draw; an event whose first race was sailed is
refused. An act of a series lands in the season's leaderboard group (named as the series,
made by the first send). The six boats come first: the league's boats sail every event,
so they are made once per server — here by `boats.sh` (`POST /v1/boats`), on SAP's
server in its admin console. The account is
`SBL_SAP_USER` / `SBL_SAP_PASSWORD` (here `admin`/`admin`, the default).

Enter results for it in the admin console, then read them back with the import below
(`--regatta` with the leaderboard name the send printed).

## Testing our import against it

1. In the admin console, create a regatta and its leaderboard, add the competitors and
   enter a few race results. Name it as the league names its matchdays —
   `2. Segel-Bundesliga 2027 - Warnemünde (1)` — because the importer recognises a
   matchday by that name (`app/imports/sap.py`, `_NAME`).
2. Check the importer sees it, without writing anything:

   ```bash
   cd api && uv run python -m app.imports sap --base-url http://127.0.0.1:8888/sailingserver/api --list
   ```

3. Import it into the development database (as a draft unless `--publish`):

   ```bash
   uv run python -m app.imports sap --base-url http://127.0.0.1:8888/sailingserver/api --regatta "2. Segel-Bundesliga 2027 - Warnemünde (1)"
   ```

The backend's test suite never calls this server — external systems are tested against
recorded answers in `api/tests/fixtures/` (CLAUDE.md). A response worth keeping as such a
fixture is fetched from here and saved there.

## How it is set up

`compose.yaml` is SAP's own `docker/docker-compose-25.yml` (github.com/SAP/sailing-analytics),
changed in three places: the ports are bound to localhost, Mongo keeps its data in a
volume, and Mongo is pulled from ECR because the company's Docker Hub proxy answers 403
for its layers.

## The Google Maps key

Only the race viewer's map needs it. It lives in the Google Cloud project
**segel-bundesliga-513420**:
https://console.cloud.google.com/apis/dashboard?project=segel-bundesliga-513420

- **Only the Maps JavaScript API** is needed — the viewer loads that one script
  (`GoogleMapsLoader.java` in SAP's source); restrict the key to it and to the websites
  `http://127.0.0.1:8888/*` and `http://localhost:8888/*`.
- Cost: 10,000 map loads a month are free. Google has no spending cap — a budget only
  alerts — so cap the daily quota under *APIs & Services › Maps JavaScript API › Quotas*
  (300 a day stays inside the free amount); above it the map stops, nothing is billed.
- The key is `GOOGLE_MAPS_KEY` in `deploy/compose/secrets.sops.env`, encrypted like every
  secret here, and reaches the container as environment only — the start command above.
  Never in plaintext in the repository or a chat. On the public site SAP hosts the viewer,
  with their key.
