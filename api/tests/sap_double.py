"""The local SAP Sailing as the double of SAP's hosted server (`deploy/sap-local/`).

The real software, on this machine: what the site sends lands in a real SAP, and the race
committee's results are entered the way SAP's own race committee app enters them — a
``RaceLogFinishPositioningConfirmedEvent`` posted to ``/sailingserver/rc/racelog``, which
SAP turns into its leaderboard (tried 2026-11-01). There is no simulation of SAP: a test
that needs it is skipped when no local SAP answers.

What SAP's REST API does not show — the draw of a race nobody tracks — is read from its
own store, the ``RACE_LOGS`` collection of the local MongoDB (docs/gotchas).
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx

ROOT = os.environ.get("SBL_SAP_DOUBLE", "http://127.0.0.1:8888")
API = f"{ROOT}/sailingserver/api"
AUTH = ("admin", "admin")  # the local server's published default (deploy/sap-local)
BOATS_FILE = Path(__file__).parents[2] / "deploy/sap-local/boats.json"
MONGO = os.environ.get("SBL_SAP_MONGO", "sap-sailing-mongo-1")  # its container


def available() -> bool:
    try:
        return httpx.get(f"{ROOT}/gwt/status", timeout=3).status_code == 200
    except httpx.HTTPError:
        return False


def leaderboards() -> list[str]:
    response = httpx.get(f"{API}/v1/leaderboards", auth=AUTH, timeout=60)
    return response.raise_for_status().json()


def _java_uuid(encoded: str) -> str:
    """A UUID as SAP's MongoDB driver stores it — Java's legacy binary, each half reversed."""
    raw = base64.b64decode(encoded)
    return str(uuid.UUID(bytes=raw[:8][::-1] + raw[8:][::-1]))


def boats() -> dict[str, str]:
    """Our boat colour → the local SAP's boat id (`deploy/sap-local/boats.sh`)."""
    return {colour: b["id"] for colour, b in json.loads(BOATS_FILE.read_text()).items()}


class LocalSap:
    """The local SAP, seen as the race committee and the jury at the regatta."""

    def __init__(self, leaderboard: str) -> None:
        self.leaderboard = leaderboard
        self._http = httpx.Client(auth=AUTH, timeout=60)

    def close(self) -> None:
        self._http.close()

    def _board(self) -> dict[str, Any]:
        response = self._http.get(f"{API}/v2/leaderboards/{quote(self.leaderboard, safe='')}")
        return response.raise_for_status().json()

    def competitors(self) -> dict[str, str]:
        """SAP's competitor id by its short name — the club code the site sent. Who sails
        which boat in a race SAP's leaderboard cannot say while nobody tracks it: it
        names each team's own boat, so the seating comes from our draw."""
        return {c["shortName"]: c["id"] for c in self._board()["competitors"]}

    def names(self) -> dict[str, str]:
        """Each competitor's name at SAP by its short name — what SAP's pages show."""
        return {c["shortName"]: c["name"] for c in self._board()["competitors"]}

    def competitor_ids(self) -> set[str]:
        """Every competitor SAP has in the leaderboard — two may share a short name."""
        return {c["id"] for c in self._board()["competitors"]}

    def draw(self, column: str, fleet: str) -> dict[str, str]:
        """Competitor id → boat id, as SAP's race log registers the race's teams — the
        draw the site sent."""
        query = {
            "RACE_LOG_IDENTIFIER": {"a": self.leaderboard, "b": column, "c": fleet},
            "RACE_LOG_EVENT.RACE_LOG_EVENT_CLASS": "RaceLogRegisterCompetitorEvent",
        }
        script = (
            f"db.RACE_LOGS.find({json.dumps(query)}).sort({{_id: 1}}).forEach(d => print("
            "d.RACE_LOG_EVENT.RACE_LOG_COMPETITOR_ID.toString('base64'),"
            "d.RACE_LOG_EVENT.RACE_LOG_BOAT_ID.toString('base64')))"
        )
        out = subprocess.run(
            ["docker", "exec", MONGO, "mongosh", "test", "--quiet", "--eval", script],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        return dict(
            (_java_uuid(competitor), _java_uuid(boat))
            for competitor, boat in (line.split() for line in out.splitlines() if line.strip())
        )

    def delete(self) -> None:
        """Deletes the event at SAP with its regatta, leaderboard and group — as someone
        at SAP might, or `deploy/sap-local/clean.sh` does."""
        # A draft act is a non-public event at SAP, which the list leaves out unless asked.
        response = self._http.get(f"{API}/v1/events", params={"showNonPublic": "true"})
        events = response.raise_for_status().json()
        for event in events:
            if event["name"] == self.leaderboard:
                self._http.delete(
                    f"{API}/v1/events/{event['id']}",
                    params={
                        "withLeaderboardGroups": "true",
                        "withLeaderboards": "true",
                        "withRegattas": "true",
                    },
                ).raise_for_status()

    def discard(self, thresholds: list[int]) -> None:
        """Gives SAP's ``Flights`` series discards — from ``thresholds[i]`` races on, one
        more race discarded — so SAP's net points are no longer ours."""
        flights = next(s for s in self.regatta()["series"] if s["name"] == "Flights")
        response = self._http.post(
            f"{API}/v1/regattas/updateOrCreateSeries",
            json={
                "regattaName": self.leaderboard,
                "seriesName": "Flights",
                "seriesNameNew": "Flights",
                "isMedal": False,
                "isFleetsCanRunInParallel": False,
                "startsWithZeroScore": False,
                "firstColumnIsNonDiscardableCarryForward": False,
                "hasSplitFleetContiguousScoring": False,
                "hasCrossFleetMergedRanking": True,
                "oneAlwaysStaysOne": False,
                "resultDiscardingThresholds": thresholds,
                # Every fleet again with its colour: SAP reads one for each.
                "fleets": [
                    {
                        "fleetName": f["name"],
                        "orderNo": 0,
                        "htmlColor": "#{r:02X}{g:02X}{b:02X}".format(**f["color"]),
                    }
                    for f in flights["fleets"]
                ],
            },
        )
        response.raise_for_status()

    def scored(self, column: str, fleet: str) -> int:
        """How many of the race's teams SAP's leaderboard has a score for."""
        return sum(
            1
            for competitor in self._board()["competitors"]
            if (
                cell := (competitor.get("columns") or competitor.get("raceScores") or {}).get(
                    column
                )
            )
            and cell.get("fleet") == fleet
            and cell.get("totalPoints") is not None
        )

    def regatta(self) -> dict[str, Any]:
        response = self._http.get(f"{API}/v1/regattas/{quote(self.leaderboard, safe='')}")
        return response.raise_for_status().json()

    def enter(self, column: str, fleet: str, results: list[tuple[str, int | None, str]]) -> None:
        """The race committee confirms a race's finish: (competitor, place, reason) —
        ``NONE`` for a finish, ``DSQ`` and the like for a scored penalty. Posted as SAP's
        Race Manager app does it, a ``RaceLogFinishPositioningConfirmedEvent`` to the race
        log servlet: the race committee enters results in that app (decided 2026-11-03),
        and SAP offers no REST endpoint for it."""
        names = {c["id"]: c for c in self._board()["competitors"]}
        now = int(time.time() * 1000)
        event = {
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
                    "competitorId": cid,
                    "competitorName": names[cid]["name"],
                    "competitorShortName": names[cid]["shortName"],
                    "competitorBoatName": None,
                    "competitorBoatSailId": None,
                    "maxPointsReason": reason,
                    "score": None,
                    "comment": None,
                    "mergeState": "OK",
                    "rank": place,
                    "finishingTimePointAsMillis": None,
                }
                for cid, place, reason in results
            ],
        }
        response = self._http.post(
            f"{ROOT}/sailingserver/rc/racelog",
            params={
                "leaderboard": self.leaderboard,
                "race_column": column,
                "fleet": fleet,
                "clientuuid": str(uuid.uuid4()),
            },
            json=event,
        )
        response.raise_for_status()

        self._wait_scored(column, fleet, len(results))

    def _wait_scored(self, column: str, fleet: str, count: int) -> None:
        # SAP scores the race log asynchronously; the race committee's app sees it a moment
        # later too.
        for _ in range(50):
            if self.scored(column, fleet) == count:
                return
            time.sleep(0.1)
        raise AssertionError(f"SAP did not score {column}/{fleet}")
