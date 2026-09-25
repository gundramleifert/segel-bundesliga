"""User stories Z-5, V-8, V-9, V-10, Z-3 and A-8: who is in a club, and who organizes it.

Membership is the relation tuple ``user:member:club`` (Story Z-5), written by the club's
admin through the tuple endpoints of Story Z-2 — no request, no invitation, no acceptance.
A member leaves by deleting their own tuple. The roster (`GET /api/clubs/{id}/members`,
Story V-10) is read off the same tuples.

Every test here works on a **fresh club** it creates itself: the roster and the organizer
count are exactly the kind of number another story's writes on a seeded club would change
under a whole-suite run (docs/gotchas: a count against a seed row is green alone and red
in the suite).
"""

from uuid import uuid4

from app.db import SessionLocal
from app.models import Club
from app.models.auth import Role
from tests.stories.test_login_and_roles import (
    _admin_headers,
    _headers,
    _problem_code,
    _write,
    make_user,
)

MINE = "/api/clubs/mine"


async def _fresh_club() -> int:
    """A club nobody belongs to and nobody organizes yet."""
    async with SessionLocal() as session:
        club = Club(
            slug=f"cm-{uuid4().hex[:8]}",
            name="Segelclub Frisch",
            short_name="SCF",
            city="Irgendwo",
        )
        session.add(club)
        await session.commit()
        return club.id


async def _club_with_admin(client, caplog, email: str) -> tuple[int, dict[str, str]]:
    """A fresh club whose one organizer is ``email``, as its ``admin``; returns the club
    and that admin's headers."""
    club = await _fresh_club()
    await make_user(email, Role.CLUB_ADMIN, club_id=club)
    return club, await _headers(client, caplog, email)


async def _roster(client, headers, club: int) -> list[dict]:
    response = await client.get(f"/api/clubs/{club}/members", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


async def _mine(client, headers) -> dict[int, dict]:
    """`/api/clubs/mine`, keyed by club id."""
    response = await client.get(MINE, headers=headers)
    assert response.status_code == 200, response.text
    return {entry["club"]["id"]: entry for entry in response.json()}


async def _my_tuple(client, headers, relation: str, club: int) -> dict:
    """The caller's own tuple of this relation on the club, from `/api/auth/me` — where a
    member finds the id they need to leave."""
    me = (await client.get("/api/auth/me", headers=headers)).json()
    return next(
        t for t in me["tuples"] if t["relation"] == relation and t["object"] == f"club:{club}"
    )


class TestMembers:
    """Stories Z-5, V-8, V-9, Z-3: the club's admin writes `member` for an account by
    email; the member leaves by deleting their own tuple."""

    async def test_the_clubs_admin_makes_anyone_a_member_by_email(self, client, caplog):
        """Stories Z-5, V-9: the person is a member at once — no acceptance step — and
        the club shows up among their clubs and in the roster."""
        club, admin = await _club_with_admin(client, caplog, "cm-admin1@example.org")
        await make_user("cm-anna@example.org")
        anna = await _headers(client, caplog, "cm-anna@example.org")

        row = await _write(client, admin, "cm-anna@example.org", "member", f"club:{club}")
        assert (row["relation"], row["object"]) == ("member", f"club:{club}")

        assert (await _mine(client, anna))[club]["is_member"] is True
        assert [m["display_name"] for m in await _roster(client, anna, club)] == ["cm-anna"]

    async def test_a_clubs_manager_cannot_change_who_is_in(self, client, caplog):
        """Story V-8: the manager decides who *sails*, the admin who *belongs*."""
        club = await _fresh_club()
        await make_user("cm-sport@example.org", Role.CLUB_MANAGER, club_id=club)
        await make_user("cm-bert@example.org")
        sport = await _headers(client, caplog, "cm-sport@example.org")

        refused = await client.post(
            "/api/auth/tuples",
            headers=sport,
            json={"user": "cm-bert@example.org", "relation": "member", "object": f"club:{club}"},
        )
        assert refused.status_code == 403, refused.text
        assert _problem_code(refused) == "tuple-forbidden"

    async def test_a_plain_account_cannot_make_itself_a_member(self, client, caplog):
        """Story Z-5: nobody but the club's admin writes the tuple — not even for oneself."""
        club = await _fresh_club()
        await make_user("cm-self@example.org")
        me = await _headers(client, caplog, "cm-self@example.org")

        refused = await client.post(
            "/api/auth/tuples",
            headers=me,
            json={"user": "cm-self@example.org", "relation": "member", "object": f"club:{club}"},
        )
        assert refused.status_code == 403, refused.text
        assert _problem_code(refused) == "tuple-forbidden"

    async def test_an_unknown_address_is_not_found(self, client, caplog):
        """Story V-9: an account must exist; the panel says so and the person registers."""
        club, admin = await _club_with_admin(client, caplog, "cm-admin2@example.org")

        response = await client.post(
            "/api/auth/tuples",
            headers=admin,
            json={
                "user": "cm-nobody-here@example.org",
                "relation": "member",
                "object": f"club:{club}",
            },
        )
        assert response.status_code == 404, response.text

    async def test_a_member_leaves_by_deleting_their_own_tuple(self, client, caplog):
        """Story Z-5: the one write a person may make on themselves."""
        club, admin = await _club_with_admin(client, caplog, "cm-admin3@example.org")
        await make_user("cm-carla@example.org")
        carla = await _headers(client, caplog, "cm-carla@example.org")
        await _write(client, admin, "cm-carla@example.org", "member", f"club:{club}")
        row = await _my_tuple(client, carla, "member", club)

        left = await client.delete(f"/api/auth/tuples/{row['id']}", headers=carla)
        assert left.status_code == 204, left.text

        assert await _roster(client, admin, club) == []
        assert club not in await _mine(client, carla)

    async def test_a_member_cannot_remove_another_member(self, client, caplog):
        """Story Z-5: leaving is about one's *own* tuple; someone else's needs the admin."""
        club, admin = await _club_with_admin(client, caplog, "cm-admin4@example.org")
        await make_user("cm-dora@example.org")
        await make_user("cm-emil@example.org")
        dora = await _headers(client, caplog, "cm-dora@example.org")
        await _write(client, admin, "cm-dora@example.org", "member", f"club:{club}")
        emil_row = await _write(client, admin, "cm-emil@example.org", "member", f"club:{club}")

        refused = await client.delete(f"/api/auth/tuples/{emil_row['id']}", headers=dora)
        assert refused.status_code == 403, refused.text
        assert _problem_code(refused) == "tuple-forbidden"
        names = {m["display_name"] for m in await _roster(client, admin, club)}
        assert names == {"cm-dora", "cm-emil"}

    async def test_the_clubs_admin_removes_a_member(self, client, caplog):
        """Stories Z-5, V-8: removing is deleting the tuple."""
        club, admin = await _club_with_admin(client, caplog, "cm-admin5@example.org")
        await make_user("cm-fritz@example.org")
        row = await _write(client, admin, "cm-fritz@example.org", "member", f"club:{club}")

        removed = await client.delete(f"/api/auth/tuples/{row['id']}", headers=admin)
        assert removed.status_code == 204, removed.text
        assert await _roster(client, admin, club) == []

    async def test_membership_implies_no_other_relation(self, client, caplog):
        """Story Z-5: a member is not an organizer, and gets no summary role from it."""
        club, admin = await _club_with_admin(client, caplog, "cm-admin6@example.org")
        await make_user("cm-greta@example.org")
        greta = await _headers(client, caplog, "cm-greta@example.org")
        await _write(client, admin, "cm-greta@example.org", "member", f"club:{club}")

        (entry,) = await _roster(client, greta, club)
        assert entry["relations"] == ["member"]
        assert entry["organizer"] is False
        assert entry["admin"] is False
        me = (await client.get("/api/auth/me", headers=greta)).json()
        assert me["roles"] == []
        mine = (await _mine(client, greta))[club]
        assert mine["may_manage"] is False


class TestMemberRoster:
    """Story V-10: a member sees who else belongs to the club — display names and what
    each is to the club, no email."""

    async def test_a_member_sees_the_roster_with_relations(self, client, caplog):
        club, admin = await _club_with_admin(client, caplog, "cm-radmin1@example.org")
        await make_user("cm-hanna@example.org")
        await make_user("cm-ingo@example.org")
        hanna = await _headers(client, caplog, "cm-hanna@example.org")
        await _write(client, admin, "cm-hanna@example.org", "member", f"club:{club}")
        await _write(client, admin, "cm-ingo@example.org", "member", f"club:{club}")
        await _write(client, admin, "cm-ingo@example.org", "race_officer", f"club:{club}")

        roster = await _roster(client, hanna, club)
        assert [(m["display_name"], m["relations"]) for m in roster] == [
            ("cm-hanna", ["member"]),
            ("cm-ingo", ["race_officer", "member"]),
        ]
        assert all("email" not in m for m in roster)

    async def test_strangers_and_other_clubs_members_are_refused(self, client, caplog):
        """Story V-10: a stranger, or a member of a *different* club, gets 403."""
        club, admin = await _club_with_admin(client, caplog, "cm-radmin2@example.org")
        other, other_admin = await _club_with_admin(client, caplog, "cm-radmin3@example.org")
        await make_user("cm-fremd@example.org")
        await make_user("cm-nachbar@example.org")
        stranger = await _headers(client, caplog, "cm-fremd@example.org")
        neighbour = await _headers(client, caplog, "cm-nachbar@example.org")
        await _write(client, other_admin, "cm-nachbar@example.org", "member", f"club:{other}")

        for headers in (stranger, neighbour):
            response = await client.get(f"/api/clubs/{club}/members", headers=headers)
            assert response.status_code == 403, response.text
            assert _problem_code(response) == "club-members-restricted-to-members"

    async def test_signed_out_gets_401(self, client):
        """Story V-10: the roster is about accounts, so there is no public form."""
        club = await _fresh_club()
        response = await client.get(f"/api/clubs/{club}/members")
        assert response.status_code == 401, response.text

    async def test_organizers_are_marked_and_a_non_member_admin_is_not_listed(self, client, caplog):
        """Story V-10: a manager who is also a member is marked `organizer`; the admin who
        is no member does not appear in the roster, and may read it all the same."""
        club, admin = await _club_with_admin(client, caplog, "cm-radmin4@example.org")
        await make_user("cm-jana@example.org")
        await make_user("cm-kai@example.org")
        await _write(client, admin, "cm-jana@example.org", "member", f"club:{club}")
        await _write(client, admin, "cm-jana@example.org", "manager", f"club:{club}")
        await _write(client, admin, "cm-kai@example.org", "member", f"club:{club}")

        roster = {m["display_name"]: m for m in await _roster(client, admin, club)}
        assert set(roster) == {"cm-jana", "cm-kai"}
        assert roster["cm-jana"]["organizer"] is True
        assert roster["cm-jana"]["admin"] is False
        assert roster["cm-jana"]["relations"] == ["manager", "member"]
        assert roster["cm-kai"]["organizer"] is False

    async def test_staff_may_read_any_roster(self, client, caplog):
        """Story V-10: `admin`/`editor` staff see every club's roster."""
        club = await _fresh_club()
        await make_user("cm-redaktion@example.org", Role.EDITOR)
        editor = await _headers(client, caplog, "cm-redaktion@example.org")
        assert await _roster(client, editor, club) == []


class TestOrganizers:
    """Story A-8: the club's admin names more organizers; at least one must remain."""

    async def test_the_clubs_admin_names_a_member_manager(self, client, caplog):
        club, admin = await _club_with_admin(client, caplog, "cm-oadmin1@example.org")
        await make_user("cm-lena@example.org")
        lena = await _headers(client, caplog, "cm-lena@example.org")
        await _write(client, admin, "cm-lena@example.org", "member", f"club:{club}")

        await _write(client, admin, "cm-lena@example.org", "manager", f"club:{club}")

        me = (await client.get("/api/auth/me", headers=lena)).json()
        assert me["roles"] == [Role.CLUB_MANAGER]
        entry = (await _mine(client, lena))[club]
        assert (entry["is_member"], entry["may_manage"]) == (True, True)

    async def test_the_only_organizer_may_drop_one_of_two_relations(self, client, caplog):
        """Story A-8: who is both admin and manager, and the club's only organizer, may
        delete one of the two — they remain an organizer. Only the last relation of the
        last person is refused."""
        club, admin = await _club_with_admin(client, caplog, "cm-oadmin-both@example.org")
        site = await _admin_headers(client, caplog, "cm-site-admin@example.org")
        await _write(client, site, "cm-oadmin-both@example.org", "manager", f"club:{club}")

        mine = await _my_tuple(client, admin, "admin", club)
        dropped = await client.delete(f"/api/auth/tuples/{mine['id']}", headers=admin)
        assert dropped.status_code == 204, dropped.text

        last = await _my_tuple(client, admin, "manager", club)
        refused = await client.delete(f"/api/auth/tuples/{last['id']}", headers=site)
        assert refused.status_code == 409
        assert _problem_code(refused) == "last-organizer"

    async def test_an_organizer_need_not_be_a_member(self, client, caplog):
        """Story A-8: `manager` for a non-member is allowed — organizers often never sail."""
        club, admin = await _club_with_admin(client, caplog, "cm-oadmin2@example.org")
        await make_user("cm-max@example.org")
        maxi = await _headers(client, caplog, "cm-max@example.org")

        await _write(client, admin, "cm-max@example.org", "manager", f"club:{club}")

        entry = (await _mine(client, maxi))[club]
        assert (entry["is_member"], entry["may_manage"]) == (False, True)
        # Not a member, so not in the roster — and allowed to read it as an organizer.
        assert await _roster(client, maxi, club) == []

    async def test_the_last_organizer_cannot_be_removed(self, client, caplog):
        """Story A-8: at least one organizer — admin or manager — must remain."""
        site = await _admin_headers(client, caplog, "cm-site@example.org")
        club, admin = await _club_with_admin(client, caplog, "cm-oadmin3@example.org")
        admin_row = await _my_tuple(client, admin, "admin", club)

        refused = await client.delete(f"/api/auth/tuples/{admin_row['id']}", headers=site)
        assert refused.status_code == 409, refused.text
        assert _problem_code(refused) == "last-organizer"

        # With a manager beside them the admin may go — then the manager is the last one.
        await make_user("cm-nora@example.org")
        manager_row = await _write(client, admin, "cm-nora@example.org", "manager", f"club:{club}")
        gone = await client.delete(f"/api/auth/tuples/{admin_row['id']}", headers=site)
        assert gone.status_code == 204, gone.text

        refused = await client.delete(f"/api/auth/tuples/{manager_row['id']}", headers=site)
        assert refused.status_code == 409, refused.text
        assert _problem_code(refused) == "last-organizer"

    async def test_a_person_can_organize_two_clubs(self, client, caplog):
        """Story A-8: a second club no longer fails because of the first; removing one
        leaves the other alone."""
        first, first_admin = await _club_with_admin(client, caplog, "cm-oadmin4@example.org")
        second, second_admin = await _club_with_admin(client, caplog, "cm-oadmin5@example.org")
        await make_user("cm-otto@example.org")
        otto = await _headers(client, caplog, "cm-otto@example.org")

        await _write(client, first_admin, "cm-otto@example.org", "manager", f"club:{first}")
        row = await _write(client, second_admin, "cm-otto@example.org", "manager", f"club:{second}")

        managed = {i for i, e in (await _mine(client, otto)).items() if e["may_manage"]}
        assert managed == {first, second}

        removed = await client.delete(f"/api/auth/tuples/{row['id']}", headers=second_admin)
        assert removed.status_code == 204, removed.text
        managed = {i for i, e in (await _mine(client, otto)).items() if e["may_manage"]}
        assert managed == {first}
