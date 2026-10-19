"""Stories V-13, S-8 and VA-5: a parent, linked by the club, accepts the waiver for their child.

The club's manager or admin links an adult's account to a young sailor of the club as
`guardian` — a tuple on the sailor (Story Z-2) — and from then on the parent confirms the
child's liability waiver online from their own account, method ``guardian_online``,
instead of the printed form and its scan (S-1). A sailor without a cleared waiver can
still be lined up, but the club's organizer is told (VA-5, decided 2026-10-17).

Every test builds its own club, series, matchday and sailors (``_Setting`` from the J-5
walk), so it runs beside the rest of the suite.
"""

from __future__ import annotations

from app.models.auth import Role
from tests.stories.test_journey_crew import ADULT, MINOR, _needs, _Setting, _signed_in, _tag
from tests.stories.test_login_and_roles import make_user


async def _minor_in_squad(client, caplog) -> tuple[_Setting, int, dict]:
    """A series matchday whose club has one minor in its squad and crew."""
    the = _Setting(client, caplog)
    await the.series_matchday()
    sailors = await the.sailors(MINOR)
    await the.register_squad(sailors)
    await the.name_crew(sailors)
    child_id, child = sailors[0]
    return the, child_id, child


async def _link(client, headers, sailor_id: int, email: str):
    return await client.post(
        f"/api/sailors/{sailor_id}/guardians", headers=headers, json={"email": email}
    )


class TestLinkingAGuardian:
    """V-13: only the child's club's manager or admin links a parent to them."""

    async def test_the_clubs_manager_links_and_unlinks_a_parent(self, client, caplog):
        the, child_id, _ = await _minor_in_squad(client, caplog)
        parent = f"parent-{the.tag}@example.com"
        await make_user(parent)

        linked = await _link(client, the.manager, child_id, parent)
        assert linked.status_code == 201, linked.text
        tuple_id = linked.json()["id"]

        listed = await client.get(f"/api/clubs/{the.club_id}/guardians", headers=the.manager)
        assert listed.status_code == 200, listed.text
        row = next(r for r in listed.json() if r["sailor"]["id"] == child_id)
        assert [g["email"] for g in row["guardians"]] == [parent]
        assert row["minor"] is True

        again = await _link(client, the.manager, child_id, parent)
        assert again.status_code == 409
        assert again.json()["type"] == "/errors/tuple-exists"

        removed = await client.delete(
            f"/api/sailors/{child_id}/guardians/{tuple_id}", headers=the.manager
        )
        assert removed.status_code == 204, removed.text
        listed = await client.get(f"/api/clubs/{the.club_id}/guardians", headers=the.manager)
        row = next(r for r in listed.json() if r["sailor"]["id"] == child_id)
        assert row["guardians"] == []

    async def test_the_clubs_admin_links_too(self, client, caplog):
        the, child_id, _ = await _minor_in_squad(client, caplog)
        club_admin = await _signed_in(
            client, caplog, f"cadmin-{the.tag}@example.com", Role.CLUB_ADMIN, club_id=the.club_id
        )
        await make_user(f"parent2-{the.tag}@example.com")
        linked = await _link(client, club_admin, child_id, f"parent2-{the.tag}@example.com")
        assert linked.status_code == 201, linked.text

    async def test_nobody_else_links(self, client, caplog):
        """Not another club's manager, not a club member, not the parent themselves."""
        the, child_id, child = await _minor_in_squad(client, caplog)
        parent = f"parent3-{the.tag}@example.com"
        parent_headers = await _signed_in(client, caplog, parent)

        other = _Setting(client, caplog)
        await other.club()
        for headers in (other.manager, parent_headers, child):
            refused = await _link(client, headers, child_id, parent)
            assert refused.status_code == 403, refused.text
            assert refused.json()["type"] == "/errors/guardian-link-forbidden"
        assert (
            await client.get(f"/api/clubs/{the.club_id}/guardians", headers=other.manager)
        ).status_code == 403

    async def test_the_parent_needs_an_account_and_is_not_the_child(self, client, caplog):
        the, child_id, _ = await _minor_in_squad(client, caplog)
        missing = await _link(client, the.manager, child_id, f"nobody-{_tag()}@example.com")
        assert missing.status_code == 404
        assert missing.json()["type"] == "/errors/guardian-account-missing"

        child_email = f"j5-sailor-0-{the.tag}@example.com"
        itself = await _link(client, the.manager, child_id, child_email)
        assert itself.status_code == 422
        assert itself.json()["type"] == "/errors/guardian-is-the-sailor"


class TestAGuardianConfirms:
    """S-8: a linked parent accepts the waiver for their child, online."""

    async def test_a_parent_clears_their_minor_child_online(self, client, caplog):
        the, child_id, _ = await _minor_in_squad(client, caplog)
        parent = f"mum-{the.tag}@example.com"
        mum = await _signed_in(client, caplog, parent)
        url = f"/api/series/{the.series_id}/waiver"

        # Before the club links them, the parent is a stranger to the child.
        before = await client.post(url, headers=mum, json={"sailor_id": child_id})
        assert before.status_code == 403
        assert (await _link(client, the.manager, child_id, parent)).status_code == 201

        # The parent belongs to no club — only the child does (Story V-13).
        assert (await client.get("/api/clubs/mine", headers=mum)).json() == []

        wards = await client.get("/api/waiver/wards", headers=mum)
        assert wards.status_code == 200, wards.text
        ward = next(w for w in wards.json() if w["sailor_id"] == child_id)
        row = next(c for c in ward["competitions"] if c["scope"] == "series")
        assert row["status"] == "missing" and row["minor"] is True

        confirmed = await client.post(
            url, headers=mum, json={"sailor_id": child_id, "locale_shown": "de"}
        )
        assert confirmed.status_code == 201, confirmed.text
        body = confirmed.json()
        assert (body["method"], body["cleared"]) == ("guardian_online", True)
        assert body["guardian_name"]

        checklist = await client.get(
            f"/api/admin/events/{the.event_id}/waivers", headers=the.organizer
        )
        assert (
            next(r for r in checklist.json()["sailors"] if r["sailor_id"] == child_id)["status"]
            == "cleared"
        )
        wards = await client.get("/api/waiver/wards", headers=mum)
        ward = next(w for w in wards.json() if w["sailor_id"] == child_id)
        assert all(c["status"] == "cleared" for c in ward["competitions"])

    async def test_a_parent_who_also_runs_the_club_accepts_as_the_parent(self, client, caplog):
        """S-8: in a small club the team manager is often a sailor's parent. Linked as
        guardian, their click from "My children" is the parent's online acceptance — not
        the club's paper path, which would ask for a name and a scan."""
        the, child_id, _ = await _minor_in_squad(client, caplog)
        manager_email = f"j5-manager-{the.tag}@example.com"
        assert (await _link(client, the.manager, child_id, manager_email)).status_code == 201

        confirmed = await client.post(
            f"/api/series/{the.series_id}/waiver",
            headers=the.manager,
            json={"sailor_id": child_id, "locale_shown": "de"},
        )
        assert confirmed.status_code == 201, confirmed.text
        assert (confirmed.json()["method"], confirmed.json()["cleared"]) == (
            "guardian_online",
            True,
        )

    async def test_an_adult_ward_confirms_for_themselves(self, client, caplog):
        the = _Setting(client, caplog)
        await the.series_matchday()
        sailors = await the.sailors(ADULT)
        await the.register_squad(sailors)
        grown_id, _ = sailors[0]
        parent = f"dad-{the.tag}@example.com"
        dad = await _signed_in(client, caplog, parent)
        assert (await _link(client, the.manager, grown_id, parent)).status_code == 201

        refused = await client.post(
            f"/api/series/{the.series_id}/waiver", headers=dad, json={"sailor_id": grown_id}
        )
        assert refused.status_code == 422
        assert refused.json()["type"] == "/errors/waiver-ward-is-adult"

    async def test_my_space_tells_the_parent(self, client, caplog):
        """Z-8: the parent's *Me* card carries `ward_waiver` while a child's is missing."""
        the, child_id, _ = await _minor_in_squad(client, caplog)
        parent = f"gran-{the.tag}@example.com"
        gran = await _signed_in(client, caplog, parent)
        assert (await _link(client, the.manager, child_id, parent)).status_code == 201

        mine = (await client.get("/api/me/contexts", headers=gran)).json()
        assert {"code": "ward_waiver", "count": 1} in [
            {"code": n["code"], "count": n["count"]} for n in mine["me"]["needs"]
        ]

        await client.post(
            f"/api/series/{the.series_id}/waiver", headers=gran, json={"sailor_id": child_id}
        )
        mine = (await client.get("/api/me/contexts", headers=gran)).json()
        assert "ward_waiver" not in {n["code"] for n in mine["me"]["needs"]}


class TestTheCrewWaiverIsSaid:
    """VA-5: a sailor without a cleared waiver can be lined up — and the club is told."""

    async def test_a_crew_without_waivers_is_lined_up_and_flagged(self, client, caplog):
        the, child_id, child = await _minor_in_squad(client, caplog)
        # Lined up already (`_minor_in_squad` named the crew): no lock.
        assert "crew_waiver_missing" in await _needs(client, the.manager, "club", the.club_id)

        parent = f"aunt-{the.tag}@example.com"
        aunt = await _signed_in(client, caplog, parent)
        assert (await _link(client, the.manager, child_id, parent)).status_code == 201
        await client.post(
            f"/api/series/{the.series_id}/waiver", headers=aunt, json={"sailor_id": child_id}
        )
        assert "crew_waiver_missing" not in await _needs(client, the.manager, "club", the.club_id)
