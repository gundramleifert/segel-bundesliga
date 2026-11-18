"""Checking a team in, gated by the liability waiver (Stories VA-2, VA-5).

The owner decided on review 5.7 (2026-11-13): the waiver gates check-in. A crew may be
lined up while someone in it has not signed — a lineup is planned for weeks — but the team
checks in only once every person in its named crew is cleared. Checked in means *this*
crew was cleared, so a changed lineup undoes it.
"""

from __future__ import annotations

from datetime import date

from app.models.auth import Grant, Relation
from tests.stories.test_login_and_roles import _problem_code
from tests.stories.test_my_space import SOON, _club, _event, _person, _series, _tag, _team
from tests.stories.test_reimbursements import login

ADULT = date(1990, 5, 1)


async def _world(client, caplog):
    """A series act, one club entered with its team manager, two adult sailors in its
    squad and both named in the crew — neither has signed yet."""
    club, series = await _club(), await _series()
    event = await _event(series_id=series, starts_on=SOON)
    squad = await _team(club, series_id=series)
    entry = await _team(club, series_id=series, event_id=event)
    tag = _tag()
    manager = await login(
        client, caplog, f"ci-tm-{tag}@example.com", Grant(relation=Relation.MANAGER, club_id=club)
    )
    sailors = []
    for n in (1, 2):
        email = f"ci-sailor{n}-{tag}@example.com"
        headers = await login(client, caplog, email, Grant(relation=Relation.MEMBER, club_id=club))
        person = await _person(email, squad, birth_date=ADULT)
        sailors.append((person, headers))
    crew = await client.put(
        f"/api/admin/events/{event}/crew",
        headers=manager,
        json={"team_id": entry, "members": [{"person_id": p} for p, _ in sailors]},
    )
    assert crew.status_code == 200, crew.text
    return event, series, entry, manager, sailors


async def _sign(client, series: int, person: int, headers) -> None:
    signed = await client.post(
        f"/api/series/{series}/waiver", headers=headers, json={"person_id": person}
    )
    assert signed.status_code == 201, signed.text


async def _team_row(client, event: int, team: int, headers) -> dict:
    listed = await client.get(f"/api/admin/events/{event}/waivers", headers=headers)
    assert listed.status_code == 200, listed.text
    return next(t for t in listed.json()["teams"] if t["team_id"] == team)


class TestTheWaiverGatesCheckIn:
    """VA-2/VA-5: a team checks in once its whole crew is cleared."""

    async def test_a_crew_with_an_unsigned_sailor_does_not_check_in(self, client, caplog):
        event, series, entry, manager, sailors = await _world(client, caplog)
        (first, first_headers), (second, _) = sailors
        await _sign(client, series, first, first_headers)

        refused = await client.post(
            f"/api/admin/events/{event}/teams/{entry}/check-in", headers=manager
        )
        assert refused.status_code == 409, refused.text
        assert _problem_code(refused) == "crew-waiver-missing"
        assert refused.json()["person_ids"] == [second]

    async def test_a_cleared_crew_checks_in_and_the_list_says_so(self, client, caplog):
        event, series, entry, manager, sailors = await _world(client, caplog)
        for person, headers in sailors:
            await _sign(client, series, person, headers)
        organizer = await login(
            client,
            caplog,
            f"ci-orga-{_tag()}@example.com",
            Grant(relation=Relation.MANAGER, event_id=event),
        )
        before = await _team_row(client, event, entry, organizer)
        assert before["checked_in_at"] is None and before["not_cleared"] == []

        checked = await client.post(
            f"/api/admin/events/{event}/teams/{entry}/check-in", headers=manager
        )
        assert checked.status_code == 200, checked.text
        assert (await _team_row(client, event, entry, organizer))["checked_in_at"] is not None

        undone = await client.delete(
            f"/api/admin/events/{event}/teams/{entry}/check-in", headers=organizer
        )
        assert undone.status_code == 200, undone.text
        assert (await _team_row(client, event, entry, organizer))["checked_in_at"] is None

    async def test_a_changed_lineup_undoes_the_check_in(self, client, caplog):
        event, series, entry, manager, sailors = await _world(client, caplog)
        for person, headers in sailors:
            await _sign(client, series, person, headers)
        url = f"/api/admin/events/{event}/teams/{entry}/check-in"
        assert (await client.post(url, headers=manager)).status_code == 200
        crew = await client.get(f"/api/admin/events/{event}/crew/{entry}", headers=manager)
        assert crew.json()["checked_in_at"] is not None

        changed = await client.put(
            f"/api/admin/events/{event}/crew",
            headers=manager,
            json={"team_id": entry, "members": [{"person_id": sailors[0][0]}]},
        )
        assert changed.status_code == 200, changed.text
        # The club sees it on its own crew; the check-in list is the organizer's.
        assert changed.json()["checked_in_at"] is None
        crew = await client.get(f"/api/admin/events/{event}/crew/{entry}", headers=manager)
        assert crew.json()["checked_in_at"] is None

    async def test_no_crew_no_check_in(self, client, caplog):
        event, _, entry, manager, _ = await _world(client, caplog)
        cleared = await client.put(
            f"/api/admin/events/{event}/crew",
            headers=manager,
            json={"team_id": entry, "members": []},
        )
        assert cleared.status_code == 200, cleared.text
        refused = await client.post(
            f"/api/admin/events/{event}/teams/{entry}/check-in", headers=manager
        )
        assert refused.status_code == 409, refused.text
        assert _problem_code(refused) == "crew-missing"

    async def test_another_clubs_manager_checks_in_nobody(self, client, caplog):
        event, _, entry, _, _ = await _world(client, caplog)
        other = await login(
            client,
            caplog,
            f"ci-other-{_tag()}@example.com",
            Grant(relation=Relation.MANAGER, club_id=await _club()),
        )
        refused = await client.post(
            f"/api/admin/events/{event}/teams/{entry}/check-in", headers=other
        )
        assert refused.status_code == 403, refused.text
