"""Treasurer stories (F-…): who holds an event's money.

An event's costs are paid by its host club (decision of 2026-10-04), so ``treasurer`` is a
relation on the club and on the event, and the host club's treasurer is the treasurer of
every event the club hosts — the same rewrite that makes its admin the events' admin.

The rewrite itself is checked on accounts built in memory: ``User.can`` reads only the
account's tuples and the event's two foreign keys, so no row needs to exist for it. The
writing side goes through the tuple endpoints of Story Z-2, on a fresh club.
"""

from uuid import uuid4

from app.db import SessionLocal
from app.models import Club, Event, Series
from app.models.auth import Grant, Relation, Role, User
from tests.stories.test_login_and_roles import (
    _admin_headers,
    _headers,
    _problem_code,
    _write,
    make_user,
)

HOST, OTHER_CLUB, SERIES = 11, 12, 21


def _person(*grants: Grant) -> User:
    return User(email="t@example.org", display_name="t", grants=list(grants))


def _event(event_id: int = 31, *, host: int | None = HOST) -> Event:
    return Event(id=event_id, title="Act", series_id=SERIES, host_club_id=host)


class TestTreasurerRelation:
    """Story F-1: the event's treasurer is a tuple, and the host club's treasurer is it
    for every event the club hosts."""

    def test_the_host_clubs_treasurer_is_treasurer_of_its_events(self):
        treasurer = _person(Grant(relation=Relation.TREASURER, club_id=HOST))

        assert treasurer.can(Relation.TREASURER, on=Club(id=HOST))
        assert treasurer.can(Relation.TREASURER, on=_event(31))
        assert treasurer.can(Relation.TREASURER, on=_event(32))
        # Paying is all it is: no setup, no results, no people.
        assert not treasurer.can(Relation.MANAGER, on=_event())
        assert not treasurer.can(Relation.RACE_OFFICER, on=_event())
        assert not treasurer.can(Relation.ADMIN, on=_event())

    def test_another_clubs_treasurer_is_nothing_here(self):
        treasurer = _person(Grant(relation=Relation.TREASURER, club_id=OTHER_CLUB))

        assert not treasurer.can(Relation.TREASURER, on=_event())
        assert not treasurer.can(Relation.TREASURER, on=_event(host=None))

    def test_a_treasurer_of_one_event_is_not_the_clubs(self):
        treasurer = _person(Grant(relation=Relation.TREASURER, event_id=31))

        assert treasurer.can(Relation.TREASURER, on=_event(31))
        assert not treasurer.can(Relation.TREASURER, on=_event(32))
        assert not treasurer.can(Relation.TREASURER, on=Club(id=HOST))

    def test_the_admins_of_club_and_event_are_its_treasurers(self):
        club_admin = _person(Grant(relation=Relation.ADMIN, club_id=HOST))
        event_admin = _person(Grant(relation=Relation.ADMIN, event_id=31))
        site_admin = _person(Grant(relation=Relation.ADMIN))

        assert club_admin.can(Relation.TREASURER, on=Club(id=HOST))
        assert club_admin.can(Relation.TREASURER, on=_event())
        assert event_admin.can(Relation.TREASURER, on=_event(31))
        assert not event_admin.can(Relation.TREASURER, on=Club(id=HOST))
        assert site_admin.can(Relation.TREASURER, on=_event(host=None))

    def test_a_club_manager_does_not_hold_the_money(self):
        """The manager decides who sails; the money is the admin's or the treasurer's."""
        manager = _person(Grant(relation=Relation.MANAGER, club_id=HOST))

        assert not manager.can(Relation.TREASURER, on=Club(id=HOST))
        assert not manager.can(Relation.TREASURER, on=_event())

    def test_neither_series_nor_site_pays(self):
        series_manager = _person(Grant(relation=Relation.MANAGER, series_id=SERIES))

        assert not series_manager.can(Relation.TREASURER, on=_event())
        assert not series_manager.can(Relation.TREASURER, on=Series(id=SERIES))

    async def test_a_clubs_admin_names_its_treasurer(self, client, caplog, ids):
        headers = await _admin_headers(client, caplog)
        async with SessionLocal() as session:
            club = Club(slug=f"tr-{uuid4().hex[:8]}", name="Kassen-Club", short_name="KC")
            session.add(club)
            await session.commit()
            club_id = club.id
        await make_user("tr-chair@example.org", Role.CLUB_ADMIN, club_id=club_id)
        await make_user("tr-cash@example.org")
        chair = await _headers(client, caplog, "tr-chair@example.org")

        row = await _write(client, chair, "tr-cash@example.org", "treasurer", f"club:{club_id}")
        assert (row["relation"], row["object"]) == ("treasurer", f"club:{club_id}")
        me = (
            await client.get(
                "/api/auth/me", headers=await _headers(client, caplog, "tr-cash@example.org")
            )
        ).json()
        assert me["roles"] == [Role.TREASURER]

        model = (await client.get("/api/auth/model", headers=headers)).json()
        by_type = {entry["type"]: entry["relations"] for entry in model["types"]}
        assert "treasurer" in by_type["club"]
        assert "treasurer" in by_type["event"]

    async def test_a_treasurer_on_a_series_or_the_site_is_refused(self, client, caplog, ids):
        headers = await _admin_headers(client, caplog)
        await make_user("tr-nowhere@example.org")

        for obj in (f"series:{ids.series('dsbl-1-2026')}", "site"):
            response = await client.post(
                "/api/auth/tuples",
                headers=headers,
                json={"user": "tr-nowhere@example.org", "relation": "treasurer", "object": obj},
            )
            assert response.status_code == 422, response.text
            assert _problem_code(response) == "tuple-relation-invalid"
