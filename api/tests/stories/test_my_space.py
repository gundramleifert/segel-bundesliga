"""Story Z-8: my space — every club, series and event I am part of, and what waits for me.

"Part of" is two things: a relation I hold on it (a tuple, Story Z-2), and sailing there
(a squad puts me in a series, a crew in an event — Stories V-1, V-2), which is no tuple.
One endpoint answers both, so the overview, the club screen and the money screen stop
computing "mine" three different ways.

Every test builds its own clubs, series, events and people, so nothing here depends on
what another story did to the seed (docs/gotchas).
"""

from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Club, Event, EventCrew, Sailor, Series, Team, TeamMembership
from app.models.auth import Grant, Relation
from tests.stories.test_personal_space import upload
from tests.stories.test_reimbursements import login, submitted

MINE = "/api/me/contexts"
SOON = date.today() + timedelta(days=30)


def _tag() -> str:
    return uuid4().hex[:6]


async def _club(name: str = "Club") -> int:
    tag = _tag()
    async with SessionLocal() as session:
        club = Club(slug=f"c-{tag}", name=f"{name} {tag}", short_name="C")
        session.add(club)
        await session.commit()
        return club.id


async def _series(**fields) -> int:
    tag = _tag()
    async with SessionLocal() as session:
        series = Series(slug=f"s-{tag}", name=f"Series {tag}", short_name="S", **fields)
        session.add(series)
        await session.commit()
        return series.id


async def _event(**fields) -> int:
    tag = _tag()
    async with SessionLocal() as session:
        event = Event(slug=f"e-{tag}", title=f"Event {tag}", **fields)
        session.add(event)
        await session.commit()
        return event.id


async def _team(club_id: int, *, series_id: int | None = None, event_id: int | None = None) -> int:
    async with SessionLocal() as session:
        team = Team(name="Team", club_id=club_id, series_id=series_id, event_id=event_id)
        session.add(team)
        await session.commit()
        return team.id


async def _sailor(email: str, *team_ids: int, birth_date: date | None = None) -> int:
    """A sailor record under this address, in these teams (squads or crews)."""
    async with SessionLocal() as session:
        old = (
            await session.execute(select(Sailor).where(Sailor.email == email))
        ).scalar_one_or_none()
        if old is not None:
            await session.delete(old)
            await session.commit()
        sailor = Sailor(first_name="Sai", last_name="Lor", email=email, birth_date=birth_date)
        session.add(sailor)
        await session.flush()
        session.add_all(TeamMembership(team_id=t, sailor_id=sailor.id) for t in team_ids)
        await session.commit()
        return sailor.id


async def _mine(client, headers) -> dict:
    response = await client.get(MINE, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def _context(body: dict, kind: str, object_id: int) -> dict | None:
    return next((c for c in body["contexts"] if c["kind"] == kind and c["id"] == object_id), None)


def _needs(entry: dict) -> dict[str, int]:
    return {need["code"]: need["count"] for need in entry["needs"]}


class TestMySpace:
    """Z-8: one answer to "which clubs, series and events are mine"."""

    async def test_a_guest_is_not_answered(self, client):
        """About one person, so there is no public form of it."""
        assert (await client.get(MINE)).status_code == 401

    async def test_every_relation_i_hold_is_a_context_and_a_chip(self, client, caplog):
        """A treasurer, a jury member and a helper each find their thing — the three
        people the old screens had no door for."""
        club, series, event = await _club(), await _series(), await _event(starts_on=SOON)
        headers = await login(
            client,
            caplog,
            f"z8-many-{_tag()}@example.com",
            Grant(relation=Relation.MEMBER, club_id=club),
            Grant(relation=Relation.TREASURER, club_id=club),
            Grant(relation=Relation.JURY, series_id=series),
            Grant(relation=Relation.HELPER, event_id=event),
        )
        body = await _mine(client, headers)

        assert _context(body, "club", club)["relations"] == ["member", "treasurer"]
        assert _context(body, "series", series)["relations"] == ["jury"]
        helped = _context(body, "event", event)
        assert helped["relations"] == ["helper"]
        assert helped["starts_on"] == SOON.isoformat()

    async def test_an_editor_of_a_regatta_finds_it_too(self, client, caplog):
        """Story R-1 (2026-10-24) put `editor` on series and events; my space answered
        such a person with a 500, because its order of relations did not know the name."""
        series = await _series()
        headers = await login(
            client,
            caplog,
            f"z8-editor-{_tag()}@example.com",
            Grant(relation=Relation.EDITOR, series_id=series),
        )
        assert _context(await _mine(client, headers), "series", series)["relations"] == ["editor"]

    async def test_a_site_relation_is_not_mine(self, client, caplog):
        """The league office's reach is `/admin`'s business — an editor does not get
        every club of the country on their own page. No context is a normal answer — the
        page says how to join a club — and the *Me* card is always there."""
        headers = await login(
            client, caplog, f"z8-editor-{_tag()}@example.com", Grant(relation=Relation.EDITOR)
        )
        body = await _mine(client, headers)
        assert body["contexts"] == []
        assert body["me"]["needs"] == []
        assert body["me"]["name"]

    async def test_sailing_puts_me_in_a_series_and_an_event(self, client, caplog):
        """No tuple anywhere — the squad and the crew are what make me part of it. An
        unsigned waiver of a series needs me on the series and on each of its events I
        sail in — the matchday is where I meet it (Story S-1, decided 2026-10-17) — and
        one signature clears them all."""
        email = f"z8-sailor-{_tag()}@example.com"
        club = await _club()
        series = await _series()
        event = await _event(series_id=series, starts_on=SOON)
        squad = await _team(club, series_id=series)
        crew = await _team(club, series_id=series, event_id=event)
        headers = await login(client, caplog, email)
        await _sailor(email, squad, crew, birth_date=date(1990, 1, 1))

        body = await _mine(client, headers)
        sailed = _context(body, "series", series)
        assert sailed["relations"] == ["sailor"]
        assert [t["club_id"] for t in sailed["teams"]] == [club]
        assert _needs(sailed) == {"waiver": 1}
        sailing = _context(body, "event", event)
        assert sailing["relations"] == ["sailor"]
        assert _needs(sailing) == {"waiver": 1}

        sailor_id = (await client.get("/api/waiver/me", headers=headers)).json()["sailor_id"]
        signed = await client.post(
            f"/api/series/{series}/waiver", headers=headers, json={"sailor_id": sailor_id}
        )
        assert signed.status_code == 201, signed.text
        body = await _mine(client, headers)
        assert _needs(_context(body, "series", series)) == {}
        assert _needs(_context(body, "event", event)) == {}
        # Sailing for a club is not membership of it: the club is no context of mine.
        assert _context(body, "club", club) is None

    async def test_a_named_crew_puts_me_in_the_matchday(self, client, caplog):
        """A series matchday's crew is its `EventCrew` — the entry holds no members (Story
        V-2) — so being named is what makes the event mine. Its series' unsigned waiver
        asks there too, and still counts once in the total (the badge, Story Z-8)."""
        email = f"z8-crew-{_tag()}@example.com"
        club = await _club()
        series = await _series()
        event = await _event(series_id=series, starts_on=SOON)
        squad = await _team(club, series_id=series)
        entry = await _team(club, series_id=series, event_id=event)
        headers = await login(client, caplog, email)
        sailor_id = await _sailor(email, squad, birth_date=date(1990, 1, 1))
        async with SessionLocal() as session:
            session.add(EventCrew(event_id=event, team_id=entry, sailor_id=sailor_id, role="crew"))
            await session.commit()

        body = await _mine(client, headers)
        crewed = _context(body, "event", event)
        assert crewed is not None and crewed["relations"] == ["sailor"]
        assert [t["club_id"] for t in crewed["teams"]] == [club]
        assert _needs(crewed) == {"waiver": 1}
        assert _needs(_context(body, "series", series)) == {"waiver": 1}
        assert body["total"] == 1

    async def test_claims_to_decide_need_the_one_who_decides(self, client, caplog):
        """On the event when I hold the event, on the paying club when I hold the club —
        and never on the claimant's own card."""
        club = await _club("Host")
        event = await _event(host_club_id=club, starts_on=SOON)
        helper = await login(
            client,
            caplog,
            f"z8-helper-{_tag()}@example.com",
            Grant(relation=Relation.HELPER, event_id=event),
        )
        await submitted(client, helper, event=event)

        treasurer = await login(
            client,
            caplog,
            f"z8-treasurer-{_tag()}@example.com",
            Grant(relation=Relation.TREASURER, club_id=club),
        )
        assert _needs(_context(await _mine(client, treasurer), "club", club)) == {"claims": 1}

        manager = await login(
            client,
            caplog,
            f"z8-evmanager-{_tag()}@example.com",
            Grant(relation=Relation.MANAGER, event_id=event),
        )
        assert _needs(_context(await _mine(client, manager), "event", event)) == {"claims": 1}

        assert _needs(_context(await _mine(client, helper), "event", event)) == {}

    async def test_a_club_organizer_hears_about_squads_and_crews(self, client, caplog):
        """A squad below the series' minimum, an upcoming entry with nobody named — the two
        things only the club's organizer can fix, on the club's card."""
        club = await _club()
        series = await _series(squad_min=4)
        await _team(club, series_id=series)  # registered, nobody in the squad yet
        event = await _event(series_id=series, starts_on=SOON)
        await _team(club, series_id=series, event_id=event)  # entered, no crew named

        manager = await login(
            client,
            caplog,
            f"z8-clubmgr-{_tag()}@example.com",
            Grant(relation=Relation.MANAGER, club_id=club),
        )
        assert _needs(_context(await _mine(client, manager), "club", club)) == {
            "squad_below_min": 1,
            "crew_missing": 1,
        }

        member = await login(
            client,
            caplog,
            f"z8-member-{_tag()}@example.com",
            Grant(relation=Relation.MEMBER, club_id=club),
        )
        assert _needs(_context(await _mine(client, member), "club", club)) == {}

    async def test_an_expired_document_needs_me(self, client, caplog):
        headers = await login(client, caplog, f"z8-docs-{_tag()}@example.com")
        await upload(client, headers, valid_until=(date.today() - timedelta(days=1)).isoformat())
        await upload(client, headers, valid_until=SOON.isoformat())
        assert (await _mine(client, headers))["me"]["needs"] == [
            {"code": "documents_expired", "count": 1}
        ]

    async def test_a_past_event_is_still_mine(self, client, caplog):
        """The page folds the past away; the answer keeps it, with its dates."""
        event = await _event(starts_on=date(2020, 5, 1), ends_on=date(2020, 5, 2))
        headers = await login(
            client,
            caplog,
            f"z8-past-{_tag()}@example.com",
            Grant(relation=Relation.JURY, event_id=event),
        )
        past = _context(await _mine(client, headers), "event", event)
        assert past["ends_on"] == "2020-05-02"
