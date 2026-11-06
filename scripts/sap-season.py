#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx"]
# ///
"""A 2027 season on the local SAP Sailing, in three stages — watched live on our site.

Against the running site (`tilt up`, its backend pointed at `deploy/sap-local/`) and the
local SAP, never SAP's hosted server:

  seed   Stage 1 — a fresh installation: the site's database seeded again
         (`app.seed_test_setup --reset`; the 1. Liga 2027's clubs follow from the 2026
         tables) and the local SAP emptied (`deploy/sap-local/clean.sh`, the six boats
         stay). Both together: SAP keeps race logs by leaderboard name (docs/gotchas).

  send   Stage 2 — from the site to SAP, as an organizer does it ("Send to SAP Sailing",
         Story VA-15): one act (``--event``) or every act of a series (``--series``).
         An act without dates gets practice dates (one weekend a month from the first —
         only the first and last were announced), one without a draw gets one from the
         catalog; then it is marked scored on SAP and sent.

  sail   Stage 3 — one act sailed at SAP: published and started here, then race by race
         its finishing order posted to SAP the way the race committee's Race Manager app
         does (random, seeded, now and then a DSQ), ``--every`` seconds apart. The site
         takes each result from SAP by itself while the act is live (Story WL-5, every
         ``SBL_SAP_POLL_SECONDS``), so the act's page follows live:
         http://localhost:5173/1-liga/2027/act-1/results

  all    the three in a row: seed, send the series, sail act 1.

    scripts/sap-season.py seed
    scripts/sap-season.py send --series dsbl-1-2027
    scripts/sap-season.py send --event dsbl-1-2027-friedrichshafen
    scripts/sap-season.py sail --event dsbl-1-2027-friedrichshafen --every 5
    scripts/sap-season.py sail --event dsbl-1-2027-friedrichshafen --every 0 --races 6
    scripts/sap-season.py all
"""

from __future__ import annotations

import argparse
import random
import subprocess
import sys
import time
import uuid
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import quote

import httpx

ROOT = Path(__file__).resolve().parents[1]
SITE = "http://localhost:8000"
WEB = "http://localhost:5173"
SAP = "http://127.0.0.1:8888/sailingserver"
SAP_AUTH = ("admin", "admin")  # the local server's published default
ADMIN = "admin@sbl.example.com"
SERIES = "dsbl-1-2027"


# ---------------------------------------------------------------- the site


def site_client(email: str = ADMIN) -> httpx.Client:
    """The site as one of its test accounts (`/api/dev/login`, `SBL_DEV_LOGIN`)."""
    for _ in range(60):  # the backend may still be starting after a reseed
        try:
            login = httpx.post(f"{SITE}/api/dev/login", json={"email": email}, timeout=30)
            break
        except httpx.TransportError:
            time.sleep(1)
    else:
        sys.exit(f"The site does not answer at {SITE} — is `tilt up` running?")
    if login.status_code != 200:
        sys.exit(f"Signing in as {email} failed ({login.status_code}): {login.text}")
    token = login.json()["access_token"]
    return httpx.Client(base_url=SITE, headers={"Authorization": f"Bearer {token}"}, timeout=120)


def ok(response: httpx.Response, what: str) -> dict:
    if response.status_code >= 400:
        sys.exit(f"{what}: {response.status_code} {response.text}")
    return response.json() if response.content else {}


def items(site: httpx.Client, path: str, **params) -> list[dict]:
    listed = ok(site.get(path, params={"size": 100, **params}), path)
    return listed.get("items", listed)


def series_of(site: httpx.Client, slug: str) -> dict:
    series = next((s for s in items(site, "/api/admin/series") if s["slug"] == slug), None)
    if series is None:
        sys.exit(f"No series {slug} — run stage 1 first: scripts/sap-season.py seed")
    return series


def acts_of(site: httpx.Client, series: dict) -> list[dict]:
    return sorted(items(site, "/api/admin/events", series_id=series["id"]), key=lambda e: e["matchday"])


def event_of(site: httpx.Client, slug: str) -> dict:
    event = next((e for e in items(site, "/api/admin/events") if e["slug"] == slug), None)
    if event is None:
        sys.exit(f"No event {slug}")
    return event


# ---------------------------------------------------------------- stage 1


def seed() -> None:
    """A fresh installation, and an empty SAP to go with it."""
    print("Stage 1: seeding the site …")
    subprocess.run(
        ["uv", "run", "python", "-m", "app.seed_test_setup", "--reset"],
        cwd=ROOT / "api",
        check=True,
        stdout=subprocess.DEVNULL,
    )
    print("Stage 1: emptying the local SAP …")
    subprocess.run([ROOT / "deploy/sap-local/clean.sh"], check=True, stdout=subprocess.DEVNULL)
    print("Stage 1 done: the 1. Liga 2027 is seeded, SAP is empty.")


# ---------------------------------------------------------------- stage 2


def send(site: httpx.Client, act: dict, practice_day: date | None) -> None:
    """Dates if it has none, a draw if it has none, scored on SAP — then sent there."""
    event_id, title = act["id"], act["title"]
    if not act.get("starts_on"):
        if practice_day is None:
            sys.exit(f"{title} has no dates — send its whole series, or give it dates first")
        ok(
            site.patch(
                f"/api/admin/events/{event_id}",
                json={"starts_on": practice_day.isoformat(), "ends_on": (practice_day + timedelta(days=2)).isoformat()},
            ),
            f"{title}: dates",
        )
        print(f"  practice dates from {practice_day}")
    if not ok(site.get(f"/api/admin/events/{event_id}/races"), f"{title}: races")["races"]:
        ok(site.post(f"/api/admin/events/{event_id}/pairing/from-catalog", json={"seed": act["matchday"]}), f"{title}: draw")
        print("  pairing list drawn from the catalog")
    ok(site.patch(f"/api/admin/events/{event_id}", json={"results_source": "sap"}), f"{title}: scored on SAP")
    sent = ok(site.post(f"/api/events/{event_id}/sap/send"), f"{title}: send to SAP")
    print(f"  sent: {sent['leaderboard']} — {sent['teams_created']} teams new, {sent['teams_kept']} kept, {sent['races']} races")


def send_series(site: httpx.Client, slug: str) -> None:
    season = acts_of(site, series_of(site, slug))
    first = date.fromisoformat(next(a["starts_on"] for a in season if a.get("starts_on")))
    for n, act in enumerate(season):
        print(f"Stage 2: act {act['matchday']}, {act['title']}")
        send(site, act, first + timedelta(weeks=4 * n))


# ---------------------------------------------------------------- stage 3


def race_manager_finish(order: list[tuple[dict, int | None, str]]) -> dict:
    """A confirmed finishing order as SAP's Race Manager app sends it to the race log —
    the way results reach SAP (the race committee works in that app)."""
    now = int(time.time() * 1000)
    return {
        "@class": "RaceLogFinishPositioningConfirmedEvent",
        "id": str(uuid.uuid4()),
        "createdAt": now,
        "timestamp": now,
        "passId": 0,
        "competitors": [],
        "authorName": "Race committee",
        "authorPriority": 1,
        "positionedCompetitors": [
            {
                "competitorId": c["id"],
                "competitorName": c["name"],
                "competitorShortName": c["shortName"],
                "competitorBoatName": None,
                "competitorBoatSailId": None,
                "maxPointsReason": reason,
                "score": None,
                "comment": None,
                "mergeState": "OK",
                "rank": place,
                "finishingTimePointAsMillis": None,
            }
            for c, place, reason in order
        ],
    }


def finishing_order(teams: list[dict], rng: random.Random) -> list[tuple[dict, int | None, str]]:
    """The race as sailed: a random order, and about one race in twelve a disqualification
    — the boat leaves the order, the others close up."""
    shuffled = teams[:]
    rng.shuffle(shuffled)
    disqualified = shuffled.pop(rng.randrange(len(shuffled))) if rng.random() < 1 / 12 else None
    order = [(c, place, "NONE") for place, c in enumerate(shuffled, 1)]
    return order + ([(disqualified, None, "DSQ")] if disqualified else [])


def sail(site: httpx.Client, slug: str, every: float, races: int | None, seed_value: int) -> None:
    """The act published and started here, then sailed at SAP race by race."""
    act = event_of(site, slug)
    event_id = act["id"]
    detail = ok(site.get(f"/api/admin/events/{event_id}"), "event")
    leaderboard = detail.get("sap_leaderboard")
    if not leaderboard:
        sys.exit(f"{slug} is not on SAP yet — stage 2 first: scripts/sap-season.py send --event {slug}")
    series = detail.get("series")
    if series and not series.get("published"):
        ok(site.post(f"/api/admin/series/{series['id']}/publish"), "publish the series")
        print(f"  published {series['name']}")
    if not detail["published"]:
        ok(site.post(f"/api/admin/events/{event_id}/publish"), "publish the act")
        print(f"  published {detail['title']}")
    if detail["status"] == "planned":
        ok(site.post(f"/api/admin/events/{event_id}/start"), "start")
        print("  started — the site now asks SAP for its results while it is live")

    board = httpx.get(f"{SAP}/api/v2/leaderboards/{quote(leaderboard, safe='')}", auth=SAP_AUTH, timeout=60)
    by_code = {c["shortName"]: c for c in board.raise_for_status().json()["competitors"]}
    schedule = ok(site.get(f"/api/admin/events/{event_id}/races"), "races")["races"]
    schedule = schedule[:races] if races else schedule
    page = act_page(detail)
    print(f"Stage 3: sailing {len(schedule)} races at SAP, one every {every:g} s — watch {page}")
    rng = random.Random(seed_value)
    with httpx.Client(auth=SAP_AUTH, timeout=60) as sap:
        for race in schedule:
            teams = [by_code[e["team"]["club"]["short_name"]] for e in race["entries"]]
            order = finishing_order(teams, rng)
            response = sap.post(
                f"{SAP}/rc/racelog",
                params={
                    "leaderboard": leaderboard,
                    "race_column": f"F{race['flight']}",
                    "fleet": f"Race {race['race_in_flight']}",
                    "clientuuid": str(uuid.uuid4()),
                },
                json=race_manager_finish(order),
            )
            if response.status_code != 200:
                sys.exit(f"SAP refused F{race['flight']}/Race {race['race_in_flight']}: {response.text}")
            winner = order[0][0]["shortName"]
            penalty = next((c["shortName"] for c, _, reason in order if reason != "NONE"), None)
            print(f"  F{race['flight']} race {race['race_in_flight']}: {winner} wins" + (f", {penalty} DSQ" if penalty else ""))
            if every:
                time.sleep(every)
    if not every:
        # Not waiting for the server's next ask: taken now.
        taken = ok(site.post(f"/api/events/{event_id}/sap/results"), "results from SAP")
        print(f"  {taken['results']} results taken back")
    print(f"Done — {page}")


def act_page(event: dict) -> str:
    series = event.get("series") or {}
    league = {1: "1-liga", 2: "2-liga"}.get(series.get("level"))
    if league and series.get("year") and event.get("matchday"):
        return f"{WEB}/{league}/{series['year']}/act-{event['matchday']}/results"
    return f"{WEB}/events/{event['id']}"


# ---------------------------------------------------------------- command line


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--as", dest="email", default=ADMIN, help="the site account (default: the league office)")
    stages = parser.add_subparsers(dest="stage", required=True)
    stages.add_parser("seed", help="stage 1: reseed the site, empty the local SAP")
    to_sap = stages.add_parser("send", help="stage 2: send a series or one act to SAP")
    which = to_sap.add_mutually_exclusive_group(required=True)
    which.add_argument("--series", help="every act of this series, e.g. dsbl-1-2027")
    which.add_argument("--event", help="one act, e.g. dsbl-1-2027-friedrichshafen")
    sailing = stages.add_parser("sail", help="stage 3: sail one act at SAP, live on the site")
    sailing.add_argument("--event", default=f"{SERIES}-friedrichshafen", help="the act (default: act 1)")
    sailing.add_argument("--every", type=float, default=10, help="seconds between races (0: all at once)")
    sailing.add_argument("--races", type=int, help="only the first N races")
    sailing.add_argument("--seed", type=int, default=2027, help="the random finishing orders' seed")
    everything = stages.add_parser("all", help="stage 1, the 1. Liga 2027 sent, act 1 sailed")
    everything.add_argument("--every", type=float, default=10, help="seconds between races")
    everything.add_argument("--races", type=int, help="only the first N races")
    args = parser.parse_args()

    if args.stage in ("seed", "all"):
        seed()
    if args.stage == "seed":
        return
    site = site_client(args.email)
    if args.stage == "send":
        if args.series:
            send_series(site, args.series)
        else:
            print(f"Stage 2: {args.event}")
            send(site, event_of(site, args.event), None)
    elif args.stage == "sail":
        sail(site, args.event, args.every, args.races, args.seed)
    else:
        send_series(site, SERIES)
        sail(site, f"{SERIES}-friedrichshafen", args.every, args.races, 2027)


if __name__ == "__main__":
    main()
