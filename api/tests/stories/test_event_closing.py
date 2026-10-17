"""User Story VA-10: close an event, or call it off.

The counterpart to starting. ``EventStatus`` has carried ``final`` and ``cancelled`` since
the model was written, and ``app/services/standings.py`` scores ``live`` and ``final``
alike — but until now nothing set either, so every event that had ever begun stayed
``live`` forever.

Three things these tests pin down, because all three are easy to get wrong in the
convenient direction:

* **Finishing does not require a complete race list.** Requiring all races to be sailed
  would disable the button exactly on the day the wind dies, which is when it is needed.
* **Finishing freezes nothing.** A protest heard weeks later still has to land, on a
  ``final`` event as much as on a live one — that is what the race-committee screens are
  for.
* **A cancelled event costs nobody points.** It leaves the scored set entirely, so the
  "who misses an event gets participants + 1" rule must not fire for it. Being at a
  regatta that was called off must never be worse than staying home.
"""

from app.db import SessionLocal
from app.models import Event, EventStatus
from app.models.auth import Role
from tests.stories.test_create_event import (
    admin,
    event_with_participants,
    league_clubs,
)
from tests.stories.test_event_lifecycle import draw, enter_result, first_race
from tests.stories.test_login_and_roles import login_as, make_user
from tests.stories.test_registration import auth_headers


async def live_event(client, headers, title: str, date: str) -> int:
    """An event that has been drawn and started — the state closing starts from."""
    event_id = await event_with_participants(client, headers, title, date)
    await draw(client, headers, event_id)
    response = await client.post(f"/api/admin/events/{event_id}/start", headers=headers)
    assert response.status_code == 200, response.text
    return event_id


async def status_of(event_id: int) -> str:
    async with SessionLocal() as session:
        return (await session.get(Event, event_id)).status


class TestFinishingAnEvent:
    """VA-10: As an organizer I want to declare that racing is over."""

    async def test_a_live_event_can_be_finished(self, client, caplog):
        """Finishing twice is not an error, and it decides nothing about the public.

        Idempotent, exactly as starting already is — a second tap is not a mistake. Status
        and visibility stay orthogonal (VA-8).
        """
        headers = await admin(client, caplog, "vc1@example.com")
        event_id = await live_event(client, headers, "Closing Cup", "2027-06-05")

        response = await client.post(f"/api/admin/events/{event_id}/finish", headers=headers)
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "final"
        assert response.json()["published"] is True
        assert await status_of(event_id) == EventStatus.FINAL
        assert (await client.get(f"/api/events/{event_id}")).status_code == 200

        again = await client.post(f"/api/admin/events/{event_id}/finish", headers=headers)
        assert again.status_code == 200, again.text
        assert again.json()["status"] == "final"

    async def test_an_event_that_never_started_cannot_be_finished(self, client, caplog):
        """There is nothing to declare over. The refusal says which state it is in."""
        headers = await admin(client, caplog, "vc3@example.com")
        created = (
            await client.post(
                "/api/admin/events", headers=headers, json={"title": "Never Sailed Cup"}
            )
        ).json()

        response = await client.post(f"/api/admin/events/{created['id']}/finish", headers=headers)
        assert response.status_code == 409, response.text
        assert response.json()["type"] == "/errors/event-not-started"
        assert response.json()["event_status"] == "planned"
        assert await status_of(created["id"]) == EventStatus.PLANNED

    async def test_a_protest_still_lands_after_the_event_is_final(self, client, caplog):
        """Finishing does not wait for every race, and closing freezes **nothing**.

        The wind dies, three flights are lost, the day is still over: requiring a complete
        race list would disable this exactly when it is needed. The configuration was
        already frozen by the first race (VA-8); results are deliberately not, and a
        decision heard weeks later has to reach a `final` event.
        """
        headers = await admin(client, caplog, "vc5@example.com")
        event_id = await live_event(client, headers, "Protest Cup", "2027-06-26")
        race_id, boats = await first_race(event_id)
        await enter_result(client, headers, event_id, race_id, boats)

        # Every other race of the event is still `scheduled`, and that is fine.
        finished = await client.post(f"/api/admin/events/{event_id}/finish", headers=headers)
        assert finished.status_code == 200, finished.text
        assert (await client.get(f"/api/events/{event_id}")).status_code == 200

        # The protest committee reverses the first two boats, months later.
        corrected = await client.put(
            f"/api/admin/events/{event_id}/races/{race_id}/result",
            headers=headers,
            json={
                "results": [
                    {"boat_number": boat, "code": "FINISHED", "finish_position": position}
                    for position, boat in enumerate([boats[1], boats[0], *boats[2:]], start=1)
                ]
            },
        )
        assert corrected.status_code == 200, corrected.text
        assert await status_of(event_id) == EventStatus.FINAL


class TestCancellingAnEvent:
    """VA-10: As an organizer I want to call a day off without losing what it holds."""

    async def test_cancelling_deletes_nothing(self, client, caplog):
        """A live event can be abandoned halfway, and a premature cancellation must cost no
        data — the day may yet be reinstated."""
        headers = await admin(client, caplog, "vx3@example.com")
        event_id = await live_event(client, headers, "Premature Cup", "2027-07-24")
        race_id, boats = await first_race(event_id)
        await enter_result(client, headers, event_id, race_id, boats)

        response = await client.post(f"/api/admin/events/{event_id}/cancel", headers=headers)
        assert response.status_code == 200, response.text
        assert await status_of(event_id) == EventStatus.CANCELLED

        pairing = await client.get(f"/api/events/{event_id}/pairing")
        assert pairing.status_code == 200, pairing.text
        assert pairing.json()["races"], "the pairing list survived the cancellation"

    async def test_a_cancelled_event_costs_nobody_points(self, client, caplog):
        """It leaves the scored set entirely.

        The "who misses an event gets participants + 1" rule must **not** fire for a day
        that was called off: being at a regatta that never sailed cannot be worse than
        staying home.
        """
        headers = await admin(client, caplog, "vx4@example.com")
        series = (
            await client.post(
                "/api/admin/series",
                headers=headers,
                json={"name": "Cancellation Series 2027", "year": 2027},
            )
        ).json()
        await client.put(
            f"/api/admin/series/{series['id']}/clubs",
            headers=headers,
            json={"clubs": await league_clubs(client)},
        )
        created = (
            await client.post(
                "/api/admin/events",
                headers=headers,
                json={
                    "title": "Never Sailed Act",
                    "starts_on": "2027-08-07",
                    "series": series["id"],
                    "matchday": 1,
                    "published": True,
                },
            )
        ).json()
        await client.put(
            f"/api/admin/events/{created['id']}/clubs",
            headers=headers,
            json={"clubs": await league_clubs(client)},
        )
        await client.post(f"/api/admin/events/{created['id']}/cancel", headers=headers)
        # The public table shows published series only (VA-8) — a draft answers 404.
        await client.post(f"/api/admin/series/{series['id']}/publish", headers=headers)

        table = await client.get(f"/api/series/{series['id']}/table")
        assert table.status_code == 200, table.text
        assert all(row["points"] == 0 for row in table.json()["rows"]), (
            "a cancelled act handed out points"
        )


class TestReopeningAnEvent:
    """VA-10: both closings are human judgements made in a hurry, so both undo."""

    async def test_a_finished_event_goes_back_to_live(self, client, caplog):
        headers = await admin(client, caplog, "vr1@example.com")
        event_id = await live_event(client, headers, "Reopened Cup", "2027-08-14")
        await client.post(f"/api/admin/events/{event_id}/finish", headers=headers)

        response = await client.post(f"/api/admin/events/{event_id}/reopen", headers=headers)
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "live"

    async def test_a_cancelled_event_goes_back_to_planned(self, client, caplog):
        """A planned event can be called off, and goes back to `planned` — not to `live`:
        a reinstated day is prepared again, not mid-race."""
        headers = await admin(client, caplog, "vr2@example.com")
        event_id = await event_with_participants(client, headers, "Reinstated Cup", "2027-08-21")
        cancelled = await client.post(f"/api/admin/events/{event_id}/cancel", headers=headers)
        assert cancelled.status_code == 200, cancelled.text
        assert cancelled.json()["status"] == "cancelled"

        response = await client.post(f"/api/admin/events/{event_id}/reopen", headers=headers)
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "planned"

    async def test_reopening_something_that_was_never_closed_is_refused(self, client, caplog):
        headers = await admin(client, caplog, "vr3@example.com")
        event_id = await live_event(client, headers, "Still Running Cup", "2027-08-28")

        response = await client.post(f"/api/admin/events/{event_id}/reopen", headers=headers)
        assert response.status_code == 409, response.text
        assert response.json()["type"] == "/errors/event-not-closed"
        assert response.json()["event_status"] == "live"


class TestWhoMayCloseAnEvent:
    """VA-10: the same people who may start it — and nobody else."""

    async def test_a_race_officer_may_close_the_day_they_ran(self, client, caplog):
        headers = await admin(client, caplog, "vp1@example.com")
        event_id = await live_event(client, headers, "Officer Cup", "2027-09-04")
        await make_user("officer-close@example.com", Role.RACE_OFFICER)
        officer = auth_headers(await login_as(client, "officer-close@example.com", caplog))

        response = await client.post(f"/api/admin/events/{event_id}/finish", headers=officer)
        assert response.status_code == 200, response.text

    async def test_a_team_manager_or_a_guest_may_not(self, client, caplog):
        headers = await admin(client, caplog, "vp2@example.com")
        event_id = await live_event(client, headers, "Not Yours Cup", "2027-09-11")
        await make_user("manager-close@example.com", Role.TEAM_MANAGER)
        manager = auth_headers(await login_as(client, "manager-close@example.com", caplog))

        response = await client.post(f"/api/admin/events/{event_id}/finish", headers=manager)
        assert response.status_code == 403, response.text

        guest = await client.post(f"/api/admin/events/{event_id}/finish")
        assert guest.status_code == 401, guest.text
