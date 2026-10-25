"""Story Z-8: my space — every club, series and event I am part of, and what waits for me.

"Part of" is two things: a relation I hold on it (a tuple, Story Z-2), and sailing there
(a squad puts me in a series, a crew in an event — Stories V-1, V-2), which is no tuple.
One endpoint answers both, so the overview, the club screen and the money screen stop
computing "mine" three different ways.

Every test builds its own clubs, series, events and people, so nothing here depends on
what another story did to the seed (docs/gotchas).
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

from sqlalchemy import select

from app.db import SessionLocal
from app.models import (
    Boat,
    Club,
    Event,
    EventCrew,
    Flight,
    ImportRun,
    League,
    Payment,
    PaymentRun,
    Race,
    RaceEntry,
    Sailor,
    SailorClub,
    Series,
    Team,
    TeamMembership,
)
from app.models.auth import Grant, Relation
from app.models.competition import EventStatus
from app.models.finance import PaymentStatus
from app.models.org import TeamStatus
from app.models.racing import RaceStatus
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
        # The event's own organizer hears about its setup too (Z-10) — here the claim.
        assert _needs(_context(await _mine(client, manager), "event", event))["claims"] == 1

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
        assert _needs((await _mine(client, headers))["me"]) == {"documents_expired": 1}

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


# ------------------------------------------------------------------ Story Z-10: to-dos

THIS_WEEK = date.today() + timedelta(days=3)
FAR = date.today() + timedelta(days=200)
RANKS = ["now", "soon", "info"]


def _need(entry: dict, code: str) -> dict | None:
    return next((n for n in entry["needs"] if n["code"] == code), None)


async def _club_sailor(club_id: int, birth_date: date | None) -> int:
    """A sailor who sails for this club (`SailorClub`, Story V-4), no account."""
    async with SessionLocal() as session:
        # A capitalised surname: the admin's sailor list sorts in SQL, case-sensitively,
        # and its own test reads the seed's names (test_pagination).
        sailor = Sailor(first_name=f"Kid {_tag()}", last_name="Kidd", birth_date=birth_date)
        session.add(sailor)
        await session.flush()
        session.add(SailorClub(sailor_id=sailor.id, club_id=club_id))
        await session.commit()
        return sailor.id


class TestTodos:
    """Z-10: every to-do is a row — code, count, the section that clears it, a severity —
    and appears only for those who hold that section (the model, never a summary role)."""

    async def test_every_need_names_its_section_and_severity(self, client, caplog):
        """Story Z-10: the existing codes name the section that clears them; `todos`
        repeats every need with its context, ordered by severity."""
        email = f"z10-sailor-{_tag()}@example.com"
        club = await _club()
        series = await _series()
        event = await _event(series_id=series, starts_on=THIS_WEEK)
        squad = await _team(club, series_id=series)
        crew = await _team(club, series_id=series, event_id=event)
        headers = await login(client, caplog, email)
        await _sailor(email, squad, crew, birth_date=date(1990, 1, 1))
        await upload(client, headers, valid_until=(date.today() - timedelta(days=1)).isoformat())

        body = await _mine(client, headers)
        on_series = _need(_context(body, "series", series), "waiver")
        on_event = _need(_context(body, "event", event), "waiver")
        assert on_series["section"] == "team" and on_event["section"] == "crew"
        # The matchday is in three days: the waiver is due now, on both cards.
        assert on_event["severity"] == "now" and on_event["due"] == THIS_WEEK.isoformat()
        assert on_series["severity"] == "now"
        documents = _need(body["me"], "documents_expired")
        assert (documents["section"], documents["severity"]) == ("documents", "soon")

        rows = [(t["code"], t["context"]["kind"], t["severity"]) for t in body["todos"]]
        assert ("documents_expired", "me", "soon") in rows
        assert ("waiver", "event", "now") in rows
        ranks = [RANKS.index(t["severity"]) for t in body["todos"]]
        assert ranks == sorted(ranks)
        assert _context(body, "series", series)["relations"] == ["sailor"]

    async def test_a_club_organizer_hears_about_minors_and_birth_dates(self, client, caplog):
        """Story Z-10: a minor of the club with no guardian linked, and a sailor without a
        date of birth (no waiver can be confirmed) — for the club's organizers, never for
        a member. Linking a guardian clears the first."""
        club = await _club()
        minor = await _club_sailor(club, date.today() - timedelta(days=365 * 12))
        await _club_sailor(club, None)
        await _club_sailor(club, date(1990, 1, 1))  # an adult with a date: nothing to do

        manager = await login(
            client,
            caplog,
            f"z10-clubmgr-{_tag()}@example.com",
            Grant(relation=Relation.MANAGER, club_id=club),
        )
        mine = _context(await _mine(client, manager), "club", club)
        minors = _need(mine, "minor_without_guardian")
        assert (minors["count"], minors["section"]) == (1, "minors")
        undated = _need(mine, "sailor_without_birth_date")
        assert (undated["count"], undated["section"]) == (1, "sailors")

        member = await login(
            client,
            caplog,
            f"z10-member-{_tag()}@example.com",
            Grant(relation=Relation.MEMBER, club_id=club),
        )
        assert _needs(_context(await _mine(client, member), "club", club)) == {}

        await login(
            client,
            caplog,
            f"z10-parent-{_tag()}@example.com",
            Grant(relation=Relation.GUARDIAN, sailor_id=minor),
        )
        mine = _context(await _mine(client, manager), "club", club)
        assert _need(mine, "minor_without_guardian") is None

    async def test_an_open_payment_run_waits_for_the_bank(self, client, caplog):
        """Story Z-10: a run with a payment still issued, not booked — for the club's
        treasurer and organizers, as `info`; booked, it is gone."""
        club = await _club()
        async with SessionLocal() as session:
            run = PaymentRun(
                payer_club_id=club,
                execution_date=date.today(),
                message_id=f"Z10-{_tag()}",
                debtor_name="Club",
                debtor_iban="DE89370400440532013000",
            )
            session.add(run)
            await session.flush()
            payment = Payment(payer_club_id=club, status=PaymentStatus.ISSUED, run_id=run.id)
            session.add(payment)
            await session.commit()
            payment_id = payment.id

        treasurer = await login(
            client,
            caplog,
            f"z10-treasurer-{_tag()}@example.com",
            Grant(relation=Relation.TREASURER, club_id=club),
        )
        club_card = _context(await _mine(client, treasurer), "club", club)
        open_run = _need(club_card, "payment_run_open")
        assert (open_run["count"], open_run["section"], open_run["severity"]) == (
            1,
            "payment-runs",
            "info",
        )
        member = await login(
            client,
            caplog,
            f"z10-member-{_tag()}@example.com",
            Grant(relation=Relation.MEMBER, club_id=club),
        )
        assert _needs(_context(await _mine(client, member), "club", club)) == {}

        async with SessionLocal() as session:
            (await session.get(Payment, payment_id)).status = PaymentStatus.SETTLED
            await session.commit()
        assert _needs(_context(await _mine(client, treasurer), "club", club)) == {}

    async def test_an_organizer_hears_their_event_is_not_ready_nor_published(self, client, caplog):
        """Story Z-10: a planned event's readiness reasons (VA-8) on its *Overview*, and a
        dated draft on its *Publication* — for its organizers, not for a helper. A draft
        series with dates waits on the series' *Dates*."""
        event = await _event(
            starts_on=FAR, ends_on=FAR, team_count=18, boat_count=6, flight_count=16
        )
        series = await _series(starts_on=FAR)
        manager = await login(
            client,
            caplog,
            f"z10-evmgr-{_tag()}@example.com",
            Grant(relation=Relation.MANAGER, event_id=event),
            Grant(relation=Relation.MANAGER, series_id=series),
        )
        body = await _mine(client, manager)
        mine = _context(body, "event", event)
        not_ready = _need(mine, "event_not_ready")
        # No clubs entered and no boats: two reasons, months away.
        assert (not_ready["count"], not_ready["section"], not_ready["severity"]) == (
            2,
            "overview",
            "info",
        )
        assert _need(mine, "event_unpublished")["section"] == "publication"
        assert _need(_context(body, "series", series), "event_unpublished")["section"] == "dates"

        helper = await login(
            client,
            caplog,
            f"z10-helper-{_tag()}@example.com",
            Grant(relation=Relation.HELPER, event_id=event),
        )
        assert _needs(_context(await _mine(client, helper), "event", event)) == {}

        async with SessionLocal() as session:
            (await session.get(Event, event)).published = True
            (await session.get(Series, series)).published = True
            await session.commit()
        body = await _mine(client, manager)
        assert _need(_context(body, "event", event), "event_unpublished") is None
        assert _need(_context(body, "series", series), "event_unpublished") is None

    async def test_check_in_this_week_names_the_waivers_missing(self, client, caplog):
        """Story Z-10: a race day within 7 days whose named crew has a sailor not cleared
        (VA-5) — on the event's *Check-in*, `now`, for the race committee; not a helper."""
        club = await _club()
        event = await _event(starts_on=THIS_WEEK)
        entry = await _team(club, event_id=event)
        sailor = await _club_sailor(club, date(1990, 1, 1))
        async with SessionLocal() as session:
            session.add(EventCrew(event_id=event, team_id=entry, sailor_id=sailor, role="crew"))
            await session.commit()

        officer = await login(
            client,
            caplog,
            f"z10-officer-{_tag()}@example.com",
            Grant(relation=Relation.RACE_OFFICER, event_id=event),
        )
        card = _context(await _mine(client, officer), "event", event)
        check_in = _need(card, "checkin_waivers_missing")
        assert (check_in["count"], check_in["section"], check_in["severity"]) == (
            1,
            "check-in",
            "now",
        )
        helper = await login(
            client,
            caplog,
            f"z10-helper-{_tag()}@example.com",
            Grant(relation=Relation.HELPER, event_id=event),
        )
        assert _needs(_context(await _mine(client, helper), "event", event)) == {}

    async def test_a_live_event_asks_for_missing_results(self, client, caplog):
        """Story Z-10: a finished race of a live event with an entry lacking a result — on
        *Results*, `now`, for the race committee. A race not yet sailed asks nothing."""
        club = await _club()
        event = await _event(starts_on=date.today(), status=EventStatus.LIVE)
        team = await _team(club, event_id=event)
        async with SessionLocal() as session:
            boat = Boat(event_id=event, number=1)
            flight = Flight(event_id=event, number=1)
            session.add_all([boat, flight])
            await session.flush()
            done = Race(
                flight_id=flight.id,
                number_in_flight=1,
                sequence=1,
                status=RaceStatus.FINISHED,
                finished_at=datetime.now(UTC),
            )
            waiting = Race(flight_id=flight.id, number_in_flight=2, sequence=2)
            session.add_all([done, waiting])
            await session.flush()
            session.add_all(
                [
                    RaceEntry(race_id=done.id, team_id=team, boat_id=boat.id),
                    RaceEntry(race_id=waiting.id, team_id=team, boat_id=boat.id),
                ]
            )
            await session.commit()

        officer = await login(
            client,
            caplog,
            f"z10-officer-{_tag()}@example.com",
            Grant(relation=Relation.RACE_OFFICER, event_id=event),
        )
        card = _context(await _mine(client, officer), "event", event)
        missing = _need(card, "results_missing")
        assert (missing["count"], missing["section"], missing["severity"]) == (1, "results", "now")

    async def test_an_application_waits_for_the_series_organizer(self, client, caplog):
        """Story Z-10: a club's application (V-5) waits on the series' *Registrations* for
        its manager, who decides it (A-9) — not for the applying club's own organizer."""
        club = await _club()
        series = await _series()
        async with SessionLocal() as session:
            session.add(
                Team(name="Team", club_id=club, series_id=series, status=TeamStatus.REQUESTED)
            )
            await session.commit()

        organizer = await login(
            client,
            caplog,
            f"z10-sermgr-{_tag()}@example.com",
            Grant(relation=Relation.MANAGER, series_id=series),
        )
        card = _context(await _mine(client, organizer), "series", series)
        applied = _need(card, "registrations_open")
        assert (applied["count"], applied["section"]) == (1, "registrations")

        applicant = await login(
            client,
            caplog,
            f"z10-applicant-{_tag()}@example.com",
            Grant(relation=Relation.MANAGER, club_id=club),
        )
        body = await _mine(client, applicant)
        assert _context(body, "series", series) is None
        assert "registrations_open" not in _needs(_context(body, "club", club))

    async def test_the_league_office_hears_about_clubs_and_imports(self, client, caplog):
        """Story Z-10: the site's admin gets an `office` entry — a club enrolled in no
        league's series, an import whose latest run failed. A site editor gets the office
        too, without those; `contexts` stays what is "mine" (Z-8)."""
        admin = await login(
            client, caplog, f"z10-admin-{_tag()}@example.com", Grant(relation=Relation.ADMIN)
        )

        def office_count(body: dict, code: str) -> int:
            need = _need(body["office"], code)
            return need["count"] if need else 0

        before = await _mine(client, admin)
        assert before["office"]["relations"] == ["admin"]
        clubs = office_count(before, "clubs_without_league")
        imports = office_count(before, "imports_failed")

        club = await _club()
        reference = f"z10-{_tag()}"
        async with SessionLocal() as session:
            session.add(
                ImportRun(source="m2s", reference=reference, started_at=datetime.now(UTC), ok=False)
            )
            await session.commit()
        body = await _mine(client, admin)
        assert office_count(body, "clubs_without_league") == clubs + 1
        assert office_count(body, "imports_failed") == imports + 1
        assert _need(body["office"], "clubs_without_league")["section"] == "clubs"
        assert _need(body["office"], "imports_failed")["section"] == "imports"
        assert ("imports_failed", "office") in [
            (t["code"], t["context"]["kind"]) for t in body["todos"]
        ]

        # Enrolled in a league's series, the club is shown; a later run that succeeds
        # clears the failed one.
        async with SessionLocal() as session:
            league = League(slug=f"l-{_tag()}", short_name="L", name="League")
            session.add(league)
            await session.flush()
            series = Series(slug=f"s-{_tag()}", name="S", short_name="S", league_id=league.id)
            session.add(series)
            await session.flush()
            session.add(Team(name="Team", club_id=club, series_id=series.id))
            session.add(
                ImportRun(
                    source="m2s",
                    reference=reference,
                    started_at=datetime.now(UTC) + timedelta(seconds=1),
                    ok=True,
                )
            )
            await session.commit()
        body = await _mine(client, admin)
        assert office_count(body, "clubs_without_league") == clubs
        assert office_count(body, "imports_failed") == imports

        editor = await login(
            client, caplog, f"z10-editor-{_tag()}@example.com", Grant(relation=Relation.EDITOR)
        )
        body = await _mine(client, editor)
        assert body["office"] == {"relations": ["editor"], "needs": []}
        assert body["contexts"] == []


class TestReachedContexts:
    """Z-10: a context reached through another — a series manager's event, anything the
    league office opens — opens with the relations the model gives there."""

    async def test_a_series_manager_opens_an_event_of_their_series(self, client, caplog):
        """Not in the list (the plan: inherited objects are reached inside), but answered
        on its own, as its manager — so the event's set-up is theirs to open."""
        series = await _series()
        event = await _event(series_id=series, starts_on=SOON)
        headers = await login(
            client,
            caplog,
            f"z10-reach-{_tag()}@example.com",
            Grant(relation=Relation.MANAGER, series_id=series),
        )
        assert _context(await _mine(client, headers), "event", event) is None
        response = await client.get(f"{MINE}/event/{event}", headers=headers)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["name"].startswith("Event ")
        assert body["series_id"] == series
        assert "manager" in body["relations"]
        assert "sailor" not in body["relations"]

    async def test_a_context_of_mine_comes_back_as_listed(self, client, caplog):
        club = await _club()
        headers = await login(
            client,
            caplog,
            f"z10-listed-{_tag()}@example.com",
            Grant(relation=Relation.MEMBER, club_id=club),
        )
        body = (await client.get(f"{MINE}/club/{club}", headers=headers)).json()
        assert body == _context(await _mine(client, headers), "club", club)

    async def test_the_site_admin_opens_any_club(self, client, caplog):
        club = await _club()
        headers = await login(
            client, caplog, f"z10-office-{_tag()}@example.com", Grant(relation=Relation.ADMIN)
        )
        body = (await client.get(f"{MINE}/club/{club}", headers=headers)).json()
        assert "admin" in body["relations"]

    async def test_nothing_held_is_not_found(self, client, caplog):
        """Not mine to see, as in the list — and an id that does not exist says the same."""
        club = await _club()
        headers = await login(client, caplog, f"z10-none-{_tag()}@example.com")
        response = await client.get(f"{MINE}/club/{club}", headers=headers)
        assert response.status_code == 404
        assert response.json()["type"].endswith("/context-not-found")
        assert (await client.get(f"{MINE}/club/999999", headers=headers)).status_code == 404
