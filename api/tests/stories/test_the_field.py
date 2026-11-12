"""Who sails an event, and when that may change (Stories VA-8, VA-10, A-9; review 3.2–3.5).

One question decides it — has racing started here? — and it has one answer,
``event_readiness.racing_started``: a race left ``scheduled``, a result recorded, or a
start ever signalled. Never the status, which a cancellation and a reopening move about,
and never the draw's empty rows. Before it, any change to the field clears the draw; after
it, the change is refused.
"""

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Event, Team, TeamStatus
from app.services.event_state import has_pairing_list
from tests.pages import all_items
from tests.stories.test_create_event import (
    BOATS,
    admin,
    event_with_participants,
    league_clubs,
)
from tests.stories.test_event_closing import live_event
from tests.stories.test_event_lifecycle import draw, enter_result, first_race
from tests.stories.test_login_and_roles import _problem_code


async def clubs(client) -> tuple[list[int], int]:
    """The 18 clubs of a league field, and one more."""
    every = [club["id"] for club in await all_items(client, "/api/clubs")]
    return every[:18], every[18]


async def series_with_act(client, headers, name: str, date: str) -> tuple[int, int]:
    """A series of the 18 clubs and its first act, entered by the series (adopted)."""
    field, _ = await clubs(client)
    series = (
        await client.post("/api/admin/series", headers=headers, json={"name": name, "year": 2027})
    ).json()
    saved = await client.put(
        f"/api/admin/series/{series['id']}/clubs", headers=headers, json={"clubs": field}
    )
    assert saved.status_code == 200, saved.text
    act = await client.post(
        "/api/admin/events",
        headers=headers,
        json={
            "title": f"{name} act 1",
            "starts_on": date,
            "series": series["id"],
            "matchday": 1,
            "team_count": 18,
            "flight_count": 16,
            "boats": BOATS,
            "published": True,
        },
    )
    assert act.status_code == 201, act.text
    return series["id"], act.json()["id"]


async def entered(event_id: int) -> set[int]:
    async with SessionLocal() as session:
        event = await session.get(Event, event_id)
        assert event is not None
        return set(
            (await session.execute(select(Team.club_id).where(Team.event_id == event_id))).scalars()
        )


async def drawn(event_id: int) -> bool:
    async with SessionLocal() as session:
        return await has_pairing_list(session, event_id)


class TestRacingStartedHasOneAnswer:
    """Review 3.2: the path that went wrong — a sailed act called off and reinstated was
    `planned` again, took in a new club and lost its results from the table."""

    async def test_a_sailed_act_called_off_and_reinstated_is_live_again(self, client, caplog):
        """VA-10: reopening goes back to where the event honestly was."""
        headers = await admin(client, caplog, "field1@example.com")
        event_id = await live_event(client, headers, "Reinstated Sailed Cup", "2027-09-04")
        race_id, boats = await first_race(event_id)
        await enter_result(client, headers, event_id, race_id, boats)

        await client.post(f"/api/admin/events/{event_id}/cancel", headers=headers)
        reopened = await client.post(f"/api/admin/events/{event_id}/reopen", headers=headers)

        assert reopened.json()["status"] == "live"

    async def test_a_new_series_club_never_lands_in_a_sailed_act(self, client, caplog):
        headers = await admin(client, caplog, "field2@example.com")
        series, act = await series_with_act(client, headers, "Field Series A", "2027-09-11")
        await draw(client, headers, act)
        assert (await client.post(f"/api/admin/events/{act}/start", headers=headers)).is_success
        race_id, boats = await first_race(act)
        await enter_result(client, headers, act, race_id, boats)
        await client.post(f"/api/admin/events/{act}/cancel", headers=headers)
        await client.post(f"/api/admin/events/{act}/reopen", headers=headers)

        field, extra = await clubs(client)
        saved = await client.put(
            f"/api/admin/series/{series}/clubs", headers=headers, json={"clubs": [*field, extra]}
        )

        assert saved.status_code == 200, saved.text
        assert extra not in await entered(act)


class TestAChangedFieldClearsTheDraw:
    """Review 3.4: any change to who sails, before racing starts, clears the draw — it was
    drawn for other clubs; after racing started, the change is refused."""

    async def test_setting_the_clubs_clears_the_draw(self, client, caplog):
        headers = await admin(client, caplog, "field3@example.com")
        event_id = await event_with_participants(client, headers, "Redrawn Cup", "2027-09-18")
        await draw(client, headers, event_id)
        field, extra = await clubs(client)

        same = await client.put(
            f"/api/admin/events/{event_id}/clubs", headers=headers, json={"clubs": field}
        )
        assert same.status_code == 200 and await drawn(event_id), "nothing changed, draw kept"

        changed = await client.put(
            f"/api/admin/events/{event_id}/clubs",
            headers=headers,
            json={"clubs": [*field[:17], extra]},
        )
        assert changed.status_code == 200, changed.text
        assert not await drawn(event_id)

    async def test_a_drawn_club_can_be_taken_out_before_racing(self, client, caplog):
        """The draw's empty rows are not results: taking a club out is a change of field,
        not "participation-has-results"."""
        headers = await admin(client, caplog, "field4@example.com")
        event_id = await event_with_participants(client, headers, "Shrunk Cup", "2027-09-25")
        await draw(client, headers, event_id)

        response = await client.put(
            f"/api/admin/events/{event_id}/clubs",
            headers=headers,
            json={"clubs": (await league_clubs(client))[:17]},
        )

        assert response.status_code == 200, response.text
        assert not await drawn(event_id)

    async def test_a_series_club_joining_later_clears_its_acts_draws(self, client, caplog):
        headers = await admin(client, caplog, "field5@example.com")
        series, act = await series_with_act(client, headers, "Field Series B", "2027-10-02")
        await draw(client, headers, act)
        field, extra = await clubs(client)

        await client.put(
            f"/api/admin/series/{series}/clubs",
            headers=headers,
            json={"clubs": [*field[:17], extra]},
        )

        assert extra in await entered(act) and field[17] not in await entered(act)
        assert not await drawn(act)

    async def test_once_racing_started_the_field_stays(self, client, caplog):
        headers = await admin(client, caplog, "field6@example.com")
        event_id = await live_event(client, headers, "Frozen Field Cup", "2027-10-09")
        race_id, boats = await first_race(event_id)
        await enter_result(client, headers, event_id, race_id, boats)
        field, extra = await clubs(client)

        response = await client.put(
            f"/api/admin/events/{event_id}/clubs",
            headers=headers,
            json={"clubs": [*field[:17], extra]},
        )

        assert _problem_code(response) == "event-configuration-frozen"
        assert await drawn(event_id)


class TestListingAClubAcceptsIt:
    """Review 3.5: an organizer listing a club decides its request — on the event's
    screen as on the series'."""

    async def test_a_requested_entry_listed_by_the_organizer_is_accepted(self, client, caplog):
        headers = await admin(client, caplog, "field7@example.com")
        event_id = await event_with_participants(client, headers, "Accepted Cup", "2027-10-16")
        async with SessionLocal() as session:
            team = (
                await session.execute(select(Team).where(Team.event_id == event_id).limit(1))
            ).scalar_one()
            team.status = TeamStatus.REQUESTED
            await session.commit()
            team_id = team.id

        await client.put(
            f"/api/admin/events/{event_id}/clubs",
            headers=headers,
            json={"clubs": await league_clubs(client)},
        )

        async with SessionLocal() as session:
            assert (await session.get(Team, team_id)).status == TeamStatus.ACCEPTED

    async def test_a_requested_registration_listed_for_the_series_is_accepted(self, client, caplog):
        headers = await admin(client, caplog, "field8@example.com")
        series, _ = await series_with_act(client, headers, "Field Series C", "2027-10-23")
        async with SessionLocal() as session:
            team = (
                await session.execute(
                    select(Team).where(Team.series_id == series, Team.event_id.is_(None)).limit(1)
                )
            ).scalar_one()
            team.status = TeamStatus.REQUESTED
            await session.commit()
            team_id = team.id
        field, _ = await clubs(client)

        await client.put(
            f"/api/admin/series/{series}/clubs", headers=headers, json={"clubs": field}
        )

        async with SessionLocal() as session:
            assert (await session.get(Team, team_id)).status == TeamStatus.ACCEPTED
