"""Journey J-5 (``docs/journeys/crew-cleared.md``): a club's crew is cleared for a matchday.

Each test below is one **walk** of the journey — the main path with one set of branches —
and every ``step("J-5.k", …)`` is a row of the journey's table, in the table's order:

- **adult crew, series matchday**: squad for the series, crew from it, each sailor
  confirms the waiver online, the check-in list is all green;
- **minor crew with a guardian**: the squad starts below the series' minimum, one sailor
  has no date of birth on file, the guardian's paper form is downloaded and its scan
  uploaded — once by the sailor, once by the club manager;
- **stand-alone event**: an event in no series carries its own squad on the club's entry,
  and its own waiver.

Stories V-1, V-12, V-2, Z-8, S-2, S-1 and VA-5 — each is tested on its own elsewhere; what
these walks add is the **order**: that the squad feeds the crew, the crew is what my space
asks the waiver of, and the waivers are what the organizer's check-in list reads. Through
the HTTP API only, on a club, series and event each walk creates for itself, so they run
beside the rest of the suite.
"""

from __future__ import annotations

import io
from datetime import date, timedelta
from uuid import uuid4

import pytest

from app.models.auth import Role
from tests.journeys import step
from tests.stories.test_create_event import admin
from tests.stories.test_login_and_roles import login_as, make_user
from tests.stories.test_registration import auth_headers

MINE = "/api/me/contexts"
MATCHDAY = date.today() + timedelta(days=30)
ADULT = "1990-04-01"
MINOR = "2012-05-01"  # under 18 on any 2026 reference date


def _tag() -> str:
    return uuid4().hex[:8]


def _png() -> bytes:
    """A real, tiny PNG — the scan is checked by content, so it has to be an image."""
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (4, 4), "white").save(buffer, format="PNG")
    return buffer.getvalue()


async def _signed_in(client, caplog, email: str, *roles: str, club_id: int | None = None):
    await make_user(email, *roles, club_id=club_id)
    return auth_headers(await login_as(client, email, caplog))


async def _needs(client, headers, kind: str, object_id: int) -> set[str]:
    """What my space says needs me on this club, series or event (Story Z-8)."""
    response = await client.get(MINE, headers=headers)
    assert response.status_code == 200, response.text
    context = next(
        (c for c in response.json()["contexts"] if c["kind"] == kind and c["id"] == object_id),
        None,
    )
    assert context is not None, f"{kind} {object_id} is not in my space"
    return {need["code"] for need in context["needs"]}


class _Setting:
    """What exists before the first step: a club with its manager, a published competition
    the club is entered in, an event organizer, and the club's sailors with their accounts."""

    def __init__(self, client, caplog):
        self.client, self.caplog = client, caplog
        self.tag = _tag()

    async def club(self) -> None:
        self.admin = await admin(self.client, self.caplog, f"j5-office-{self.tag}@example.com")
        created = await self.client.post(
            "/api/admin/clubs",
            headers=self.admin,
            json={"name": f"Crew Club {self.tag}", "short_name": f"CC{self.tag}", "city": "Kiel"},
        )
        assert created.status_code in (200, 201), created.text
        self.club_id = created.json()["id"]
        self.manager = await _signed_in(
            self.client,
            self.caplog,
            f"j5-manager-{self.tag}@example.com",
            Role.CLUB_MANAGER,
            club_id=self.club_id,
        )

    async def series_matchday(self) -> None:
        """A published series the club is registered in, and one matchday of it."""
        await self.club()
        series = await self.client.post(
            "/api/admin/series",
            headers=self.admin,
            json={
                "name": f"Crew Series {self.tag} 2026",
                "year": 2026,
                "clubs": [self.club_id],
                "squad_min": 4,
                "squad_max": 10,
                "published": True,
            },
        )
        assert series.status_code == 201, series.text
        self.series_id = series.json()["id"]
        event = await self.client.post(
            "/api/admin/events",
            headers=self.admin,
            json={
                "title": f"Crew Matchday {self.tag}",
                "starts_on": MATCHDAY.isoformat(),
                "series": self.series_id,
                "matchday": 1,
                "published": True,
            },
        )
        assert event.status_code == 201, event.text
        self.event_id = event.json()["id"]
        await self._organizer()
        await self._teams()

    async def stand_alone_event(self) -> None:
        """An event in no series, with the club entered by its organizer."""
        await self.club()
        event = await self.client.post(
            "/api/admin/events",
            headers=self.admin,
            json={
                "title": f"Crew Cup {self.tag}",
                "starts_on": MATCHDAY.isoformat(),
                "squad_min": 4,
                "squad_max": 6,
                "published": True,
            },
        )
        assert event.status_code == 201, event.text
        self.event_id = event.json()["id"]
        self.series_id = None
        entered = await self.client.put(
            f"/api/admin/events/{self.event_id}/clubs",
            headers=self.admin,
            json={"clubs": [self.club_id]},
        )
        assert entered.status_code == 200, entered.text
        await self._organizer()
        await self._teams()

    async def _organizer(self) -> None:
        """The event organizer: `manager` on this one event, written as a tuple."""
        email = f"j5-organizer-{self.tag}@example.com"
        await make_user(email)
        granted = await self.client.post(
            "/api/auth/tuples",
            headers=self.admin,
            json={"user": email, "relation": "manager", "object": f"event:{self.event_id}"},
        )
        assert granted.status_code == 201, granted.text
        self.organizer = auth_headers(await login_as(self.client, email, self.caplog))

    async def _teams(self) -> None:
        """The club's entry to the event, and the team its squad hangs off — the club
        screen's own answer (`/api/clubs/mine`, Story V-12)."""
        mine = await self.client.get("/api/clubs/mine", headers=self.manager)
        assert mine.status_code == 200, mine.text
        club = next(c for c in mine.json() if c["club"]["id"] == self.club_id)
        entry = next(e for e in club["events"] if e["event_id"] == self.event_id)
        self.entry_team, self.squad_team = entry["team_id"], entry["squad_team_id"]

    async def sailors(self, *births: str | None) -> list[tuple[int, dict[str, str]]]:
        """The club's sailors (Story V-4, by the club manager), each with an account."""
        out = []
        for n, birth in enumerate(births):
            email = f"j5-sailor-{n}-{self.tag}@example.com"
            body: dict[str, object] = {
                "first_name": f"Sailor{n}",
                "last_name": self.tag,
                "email": email,
            }
            if birth is not None:
                body["birth_date"] = birth
            created = await self.client.post("/api/admin/sailors", headers=self.manager, json=body)
            assert created.status_code == 201, created.text
            out.append((created.json()["id"], await _signed_in(self.client, self.caplog, email)))
        return out

    async def register_squad(self, sailors: list[tuple[int, dict]]) -> dict:
        roles = ["helm"] + ["crew"] * (len(sailors) - 1)
        response = await self.client.put(
            f"/api/admin/teams/{self.squad_team}/members",
            headers=self.manager,
            json={
                "members": [
                    {"sailor_id": s, "role": r} for (s, _), r in zip(sailors, roles, strict=True)
                ]
            },
        )
        assert response.status_code == 200, response.text
        return response.json()

    async def name_crew(self, sailors: list[tuple[int, dict]]) -> None:
        roles = ["helm"] + ["crew"] * (len(sailors) - 1)
        response = await self.client.put(
            f"/api/admin/events/{self.event_id}/crew",
            headers=self.manager,
            json={
                "team_id": self.entry_team,
                "members": [
                    {"sailor_id": s, "role": r} for (s, _), r in zip(sailors, roles, strict=True)
                ],
            },
        )
        assert response.status_code == 200, response.text
        assert {m["id"] for m in response.json()["members"]} == {s for s, _ in sailors}

    @property
    def scope(self) -> tuple[str, int]:
        """Where the waiver is signed: the series, or the event when it stands alone."""
        return ("series", self.series_id) if self.series_id else ("event", self.event_id)

    @property
    def waiver_url(self) -> str:
        kind, object_id = self.scope
        return f"/api/{kind}/{object_id}/waiver"

    async def my_waiver(self, headers) -> dict:
        response = await self.client.get("/api/waiver/me", headers=headers)
        assert response.status_code == 200, response.text
        kind, object_id = self.scope
        return next(
            r
            for r in response.json()["competitions"]
            if r["scope"] == kind and r["scope_id"] == object_id
        )

    async def check_in(self) -> dict:
        response = await self.client.get(
            f"/api/admin/events/{self.event_id}/waivers", headers=self.organizer
        )
        assert response.status_code == 200, response.text
        return response.json()


class TestACrewIsClearedForAMatchday:
    """Journey J-5: a club's crew is cleared for a matchday."""

    async def test_adult_crew_for_a_series_matchday(self, client, caplog):
        """Journey J-5 — the series squad, a crew from it, every adult confirms online."""
        the = _Setting(client, caplog)
        await the.series_matchday()
        squad = await the.sailors(ADULT, ADULT, ADULT, ADULT, ADULT)

        step("J-5.1", "club manager registers the squad for the series")
        saved = await the.register_squad(squad)
        assert len(saved["members"]) == 5
        assert (saved["squad_min"], saved["squad_max"]) == (4, 10)
        assert "squad_below_min" not in await _needs(client, the.manager, "club", the.club_id)

        step("J-5.5", "club manager names the crew for the matchday from the squad")
        crew = squad[:4]
        await the.name_crew(crew)

        step("J-5.6", "each sailor's my space says the series' waiver is missing")
        for _, headers in squad:
            assert "waiver" in await _needs(client, headers, "series", the.series_id)
            assert (await the.my_waiver(headers))["status"] == "missing"

        step("J-5.8", "each adult reads the waiver and confirms it online")
        for sailor_id, headers in squad:
            confirmed = await client.post(
                the.waiver_url, headers=headers, json={"sailor_id": sailor_id, "locale_shown": "de"}
            )
            assert confirmed.status_code == 201, confirmed.text
            assert confirmed.json()["method"] == "online" and confirmed.json()["cleared"] is True
            assert "waiver" not in await _needs(client, headers, "series", the.series_id)

        step("J-5.14", "the event organizer's check-in list shows everyone cleared")
        listing = await the.check_in()
        assert {row["sailor_id"] for row in listing["sailors"]} == {s for s, _ in squad}
        assert listing["outstanding"] == 0
        assert {row["status"] for row in listing["sailors"]} == {"cleared"}

    async def test_minor_crew_with_a_guardian(self, client, caplog):
        """Journey J-5 — a squad short of the minimum at first, a missing date of birth,
        and the guardian's signature on paper, uploaded by the sailor and by the club."""
        the = _Setting(client, caplog)
        await the.series_matchday()
        squad = await the.sailors(MINOR, MINOR, None, MINOR)

        step("J-5.1", "club manager registers the first three sailors for the series")
        saved = await the.register_squad(squad[:3])
        assert len(saved["members"]) == 3

        step("J-5.2", "the squad is below the series' minimum: said, and saved anyway")
        assert (saved["squad_min"], len(saved["members"])) == (4, 3)
        assert "squad_below_min" in await _needs(client, the.manager, "club", the.club_id)

        step("J-5.3", "club manager completes the squad later")
        assert len((await the.register_squad(squad))["members"]) == 4
        assert "squad_below_min" not in await _needs(client, the.manager, "club", the.club_id)

        step("J-5.5", "club manager names the crew for the matchday from the squad")
        await the.name_crew(squad)

        step("J-5.6", "each sailor's my space says the series' waiver is missing")
        for _, headers in squad:
            assert "waiver" in await _needs(client, headers, "series", the.series_id)
        undated_id, undated = squad[2]
        # Without a date of birth the page says so first (`birth_date_known`), and no
        # path is offered: age decides which one, and it cannot be judged.
        mine = (await client.get("/api/waiver/me", headers=undated)).json()
        assert mine["birth_date_known"] is False
        assert (await the.my_waiver(undated))["minor"] is None
        refused = await client.post(the.waiver_url, headers=undated, json={"sailor_id": undated_id})
        assert refused.status_code == 422
        assert refused.json()["type"] == "/errors/waiver-birth-date-required"

        step("J-5.7", "the sailor without a date of birth enters it")
        patched = await client.patch("/api/sailors/me", headers=undated, json={"birth_date": MINOR})
        assert patched.status_code == 200, patched.text
        row = await the.my_waiver(undated)
        assert (row["status"], row["minor"]) == ("missing", True)

        step("J-5.9", "each minor downloads the guardian form — an own click is not enough")
        for sailor_id, headers in squad:
            refused = await client.post(
                the.waiver_url, headers=headers, json={"sailor_id": sailor_id, "method": "online"}
            )
            assert refused.status_code == 422
            assert refused.json()["type"] == "/errors/guardian-confirmation-needed"
            form = await client.get(
                "/api/waiver/form",
                headers=headers,
                params={
                    "scope": "series",
                    "scope_id": the.series_id,
                    "sailor_id": sailor_id,
                    "locale": "de",
                },
            )
            assert form.status_code == 200, form.text
            assert form.headers["content-type"] == "application/pdf"
            assert form.content.startswith(b"%PDF")

        # J-5.10 / J-5.11 happen on paper, between the sailor and their guardian.

        def scan(sailor_id: int) -> dict:
            return dict(
                files={"file": ("signed.png", _png(), "image/png")},
                data={"sailor_id": str(sailor_id), "guardian_name": f"Parent of {sailor_id}"},
            )

        step("J-5.12", "three sailors upload the signed scan themselves")
        for sailor_id, headers in squad[:3]:
            uploaded = await client.post(
                f"{the.waiver_url}/scan", headers=headers, **scan(sailor_id)
            )
            assert uploaded.status_code == 201, uploaded.text
            assert uploaded.json()["method"] == "guardian" and uploaded.json()["cleared"] is True

        step("J-5.13", "the club manager uploads the last one, collected at the club")
        last_id, last = squad[3]
        uploaded = await client.post(f"{the.waiver_url}/scan", headers=the.manager, **scan(last_id))
        assert uploaded.status_code == 201, uploaded.text
        assert (await the.my_waiver(last))["status"] == "cleared"

        step("J-5.14", "the event organizer's check-in list shows everyone cleared, scans on file")
        listing = await the.check_in()
        assert listing["outstanding"] == 0
        assert all(
            row["status"] == "cleared" and row["minor"] and row["scan_available"]
            for row in listing["sailors"]
        )

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "A stand-alone event's squad cannot be saved: PUT /api/admin/teams/{entry}/members "
            "refuses an event entry (squad-needs-series-registration), although V-12 and "
            "participation.squad_team hang the squad off it. Not on the journey's Tests: line "
            "until it passes — then add it there, and J-5.4 is covered."
        ),
    )
    async def test_stand_alone_event(self, client, caplog):
        """Journey J-5 — an event in no series: its squad on the club's entry, its own
        waiver. The walk the journey drew and the code does not allow yet."""
        the = _Setting(client, caplog)
        await the.stand_alone_event()
        squad = await the.sailors(ADULT, ADULT, ADULT, ADULT)
        assert the.squad_team == the.entry_team  # the entry carries the squad

        step("J-5.4", "club manager registers the squad on the event entry")
        saved = await the.register_squad(squad)
        assert saved["series_id"] is None
        assert (saved["squad_min"], saved["squad_max"]) == (4, 6)  # the event's own limits

        step("J-5.5", "club manager names the crew from that squad")
        await the.name_crew(squad)

        step("J-5.6", "each sailor's my space asks the event's waiver, not a series'")
        for _, headers in squad:
            assert "waiver" in await _needs(client, headers, "event", the.event_id)

        step("J-5.8", "each adult confirms the event's waiver online")
        for sailor_id, headers in squad:
            confirmed = await client.post(
                the.waiver_url, headers=headers, json={"sailor_id": sailor_id}
            )
            assert confirmed.status_code == 201, confirmed.text
            assert confirmed.json()["scope"] == "event"

        step("J-5.14", "the event organizer's check-in list shows everyone cleared")
        listing = await the.check_in()
        assert listing["outstanding"] == 0 and len(listing["sailors"]) == 4
