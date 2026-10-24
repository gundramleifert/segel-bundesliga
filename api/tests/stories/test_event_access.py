"""User Story WL-3: the race committee's tools appear on the events I run, and only there.

``GET /api/events/{id}/access`` answers, for the person asking, what they may do on *this*
event — computed with the permission model (``app/authz.py``), never from the summary
roles. The race-control page, the results tab and the live view's course controls gate on
it. Before, they asked "is this account a race officer anywhere?": an officer of one event
saw the controls on every event, and one appointed through the series never saw them.
"""

from app.db import SessionLocal
from app.models.auth import Grant, Relation
from tests.stories.test_login_and_roles import login_as, make_user
from tests.stories.test_registration import auth_headers

ACT_1 = "dsbl-1-2026-act-1"
ACT_2 = "dsbl-1-2026-act-2"
SERIES = "dsbl-1-2026"
NOTHING = {"record_results": False, "control": False, "manage": False, "announce_as": []}


async def holding(client, caplog, email: str, relation: Relation, **on: int) -> dict[str, str]:
    """A fresh account holding one tuple — ``event_id=…`` or ``series_id=…`` — signed in."""
    user_id = await make_user(email)
    async with SessionLocal() as session:
        session.add(Grant(user_id=user_id, relation=relation, **on))
        await session.commit()
    return auth_headers(await login_as(client, email, caplog))


async def access(client, event_id: int, headers: dict[str, str] | None = None) -> dict:
    response = await client.get(f"/api/events/{event_id}/access", headers=headers or {})
    assert response.status_code == 200, response.text
    return response.json()


class TestTheCommitteesToolsPerEvent:
    """WL-3: the controls follow the tuple, not the summary role."""

    async def test_an_event_race_officer_on_their_own_event_and_another(self, client, caplog, ids):
        """Results and the day's transitions on the event they were appointed to; nothing
        next door, and no setup rights anywhere — that is the organizer's."""
        mine, other = ids.event(ACT_1), ids.event(ACT_2)
        officer = await holding(
            client, caplog, "access-ro@example.org", Relation.RACE_OFFICER, event_id=mine
        )

        assert await access(client, mine, officer) == {
            "record_results": True,
            "control": True,
            "manage": False,
            "announce_as": ["race_committee"],
        }
        assert await access(client, other, officer) == NOTHING

    async def test_a_series_race_officer_covers_its_events(self, client, caplog, ids):
        """A tuple on the series rewrites down to every event in it."""
        officer = await holding(
            client,
            caplog,
            "access-series-ro@example.org",
            Relation.RACE_OFFICER,
            series_id=ids.series(SERIES),
        )
        for slug in (ACT_1, ACT_2):
            assert (await access(client, ids.event(slug), officer))["record_results"] is True

    async def test_an_event_manager_manages_and_may_close_the_day(self, client, caplog, ids):
        """The organizer manages and may start or close the day — the same people
        ``require_event_control`` lets through."""
        manager = await holding(
            client, caplog, "access-mgr@example.org", Relation.MANAGER, event_id=ids.event(ACT_1)
        )
        answer = await access(client, ids.event(ACT_1), manager)
        assert answer["manage"] is True
        assert answer["control"] is True

    async def test_a_guest_may_do_nothing(self, client, ids):
        """No token, or one that no longer works, is a guest — all false, never a 401."""
        assert await access(client, ids.event(ACT_1)) == NOTHING
        expired = {"Authorization": "Bearer not-a-token"}
        assert await access(client, ids.event(ACT_1), expired) == NOTHING

    async def test_an_unknown_event_is_not_found(self, client):
        """Like every public event endpoint: what a visitor cannot see is a 404."""
        response = await client.get("/api/events/999999/access")
        assert response.status_code == 404
