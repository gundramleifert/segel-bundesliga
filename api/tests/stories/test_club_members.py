"""User stories Z-5, V-8, V-9, V-10, Z-3 and A-8: who is in a club, and who organizes it.

Membership is an active ``ClubMembership`` of a person (#40, `docs/PLAN_PEOPLE.md`) — not
a tuple. The club's admin adds a person by address (`POST /api/clubs/{id}/members`), no
acceptance needed while they are in no other club; the person leaves by ending their own
(`DELETE …/members/{person_id}`). The roster (`GET /api/clubs/{id}/members`, Story V-10)
is read off the memberships, with what each member's account is to the club besides.

Every test here works on a **fresh club** it creates itself: the roster and the organizer
count are exactly the kind of number another story's writes on a seeded club would change
under a whole-suite run (docs/gotchas: a count against a seed row is green alone and red
in the suite).
"""

from uuid import uuid4

from sqlalchemy import select

from app import authz
from app.db import SessionLocal
from app.models import Club
from app.models.auth import ObjectRef, ObjectType, Relation, Role, User
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


async def _add(client, headers, email: str, club: int) -> dict:
    """The club's admin adds the person under ``email``; returns their roster entry."""
    response = await client.post(
        f"/api/clubs/{club}/members", headers=headers, json={"email": email}
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _my_tuple(client, headers, relation: str, club: int) -> dict:
    """The caller's own tuple of this relation on the club, from `/api/auth/me`."""
    me = (await client.get("/api/auth/me", headers=headers)).json()
    return next(
        t for t in me["tuples"] if t["relation"] == relation and t["object"] == f"club:{club}"
    )


class TestMembers:
    """Stories Z-5, V-8, V-9, Z-3: the club's admin adds a person by email; the member
    leaves by ending their own membership."""

    async def test_the_clubs_admin_makes_anyone_a_member_by_email(self, client, caplog):
        """Stories Z-5, V-9: the person is a member at once — no acceptance step while they
        are in no other club — and the club shows up among their clubs and in the roster."""
        club, admin = await _club_with_admin(client, caplog, "cm-admin1@example.org")
        await make_user("cm-anna@example.org")
        anna = await _headers(client, caplog, "cm-anna@example.org")

        entry = await _add(client, admin, "cm-anna@example.org", club)
        assert (entry["display_name"], entry["relations"]) == ("cm-anna", ["member"])

        assert (await _mine(client, anna))[club]["is_member"] is True
        assert [m["display_name"] for m in await _roster(client, anna, club)] == ["cm-anna"]

    async def test_membership_is_no_tuple(self, client, caplog):
        """#40: nobody writes ``member`` as a tuple any more — the model has no such
        relation to write on a club."""
        club, admin = await _club_with_admin(client, caplog, "cm-admin-t@example.org")
        await make_user("cm-tupel@example.org")
        refused = await client.post(
            "/api/auth/tuples",
            headers=admin,
            json={"user": "cm-tupel@example.org", "relation": "member", "object": f"club:{club}"},
        )
        assert refused.status_code == 422, refused.text
        assert _problem_code(refused) == "tuple-relation-invalid"

    async def test_a_person_the_club_creates_has_an_account_and_a_member_tuple(
        self, client, caplog
    ):
        """#52: every person has an account — a child the club's admin creates gets one,
        unverified, and is in the roster like everyone else, with the ``member`` tuple
        written on their account."""
        club, admin = await _club_with_admin(client, caplog, "cm-admin-k@example.org")
        email = f"kim-{uuid4().hex[:6]}@example.org"
        child = await client.post(
            "/api/admin/people",
            headers=admin,
            json={"first_name": "Kim", "last_name": "Klein", "email": email, "club_id": club},
        )
        assert child.status_code == 201, child.text
        (entry,) = await _roster(client, admin, club)
        assert entry["display_name"] == "Kim Klein" and entry["user_id"] is not None
        assert entry["person_id"] == child.json()["id"]
        async with SessionLocal() as session:
            user = (await session.execute(select(User).where(User.email == email))).scalar_one()
            assert user.email_verified is False
            assert authz.read(user, Relation.MEMBER, ObjectRef(ObjectType.CLUB, club))

    async def test_the_member_tuple_comes_and_goes_with_the_membership(self, client, caplog):
        """#52: ``member`` is written only by the membership — asking writes nothing,
        accepting writes the tuple, leaving deletes it."""
        club, admin = await _club_with_admin(
            client, caplog, f"cm-admin-{uuid4().hex[:6]}@example.org"
        )
        email = f"cm-tuple-{uuid4().hex[:6]}@example.org"
        await make_user(email)
        person = await _headers(client, caplog, email)
        here = ObjectRef(ObjectType.CLUB, club)

        async def holds() -> bool:
            async with SessionLocal() as session:
                user = (await session.execute(select(User).where(User.email == email))).scalar_one()
                return authz.read(user, Relation.MEMBER, here)

        asked = await client.post("/api/me/memberships", headers=person, json={"club_id": club})
        assert asked.status_code == 201, asked.text
        assert not await holds()
        person_id = (await client.get("/api/people/me", headers=person)).json()["id"]
        accepted = await client.post(f"/api/clubs/{club}/members/{person_id}/accept", headers=admin)
        assert accepted.status_code == 200, accepted.text
        assert await holds()
        left = await client.delete(f"/api/me/memberships/{club}", headers=person)
        assert left.status_code == 204, left.text
        assert not await holds()

    async def test_the_tuple_api_neither_lists_nor_deletes_a_membership(self, client, caplog):
        """#52: the ``member`` tuple is the membership's alone — the club's tuples list it
        not as a role, and deleting it as a tuple is refused (``tuple-is-membership``)."""
        club, admin = await _club_with_admin(
            client, caplog, f"cm-admin-{uuid4().hex[:6]}@example.org"
        )
        email = f"cm-row-{uuid4().hex[:6]}@example.org"
        await make_user(email)
        await _add(client, admin, email, club)
        office = await _admin_headers(client, caplog, "cm-office@example.org")
        listed = await client.get(
            "/api/auth/tuples", headers=office, params={"object": f"club:{club}"}
        )
        assert listed.status_code == 200, listed.text
        assert "member" not in {t["relation"] for t in listed.json()}
        async with SessionLocal() as session:
            user = (await session.execute(select(User).where(User.email == email))).scalar_one()
            (row,) = [g for g in user.grants if g.relation == Relation.MEMBER]
        refused = await client.delete(f"/api/auth/tuples/{row.id}", headers=office)
        assert refused.status_code == 409, refused.text
        assert _problem_code(refused) == "tuple-is-membership"

    async def test_a_clubs_manager_cannot_change_who_is_in(self, client, caplog):
        """Story V-8: the manager decides who *sails*, the admin who *belongs*."""
        club = await _fresh_club()
        await make_user("cm-sport@example.org", Role.TEAM_MANAGER, club_id=club)
        await make_user("cm-bert@example.org")
        sport = await _headers(client, caplog, "cm-sport@example.org")

        refused = await client.post(
            f"/api/clubs/{club}/members", headers=sport, json={"email": "cm-bert@example.org"}
        )
        assert refused.status_code == 403, refused.text
        assert _problem_code(refused) == "membership-forbidden"

    async def test_a_plain_account_cannot_make_itself_a_member(self, client, caplog):
        """Story Z-5: nobody but the club's admin adds — not even oneself (asking to join
        is step 4 of `docs/PLAN_PEOPLE.md`)."""
        club = await _fresh_club()
        await make_user("cm-self@example.org")
        me = await _headers(client, caplog, "cm-self@example.org")

        refused = await client.post(
            f"/api/clubs/{club}/members", headers=me, json={"email": "cm-self@example.org"}
        )
        assert refused.status_code == 403, refused.text
        assert _problem_code(refused) == "membership-forbidden"

    async def test_an_unknown_address_is_not_found(self, client, caplog):
        """Story V-9: someone must be on record — a person or an account."""
        club, admin = await _club_with_admin(client, caplog, "cm-admin2@example.org")
        response = await client.post(
            f"/api/clubs/{club}/members",
            headers=admin,
            json={"email": "cm-nobody-here@example.org"},
        )
        assert response.status_code == 404, response.text
        assert _problem_code(response) == "membership-address-unknown"

    async def test_someone_in_another_club_is_invited_or_added_by_the_league_office(
        self, client, caplog
    ):
        """#40, Story V-15: a second club's organizers would see and change the person, so a
        club does not simply take someone another club has — it invites them; the league
        office adds them at once."""
        first, first_admin = await _club_with_admin(client, caplog, "cm-admin-a@example.org")
        second, second_admin = await _club_with_admin(client, caplog, "cm-admin-b@example.org")
        await make_user("cm-zwei@example.org")
        await _headers(client, caplog, "cm-zwei@example.org")
        await _add(client, first_admin, "cm-zwei@example.org", first)

        invited = await _add(client, second_admin, "cm-zwei@example.org", second)
        assert invited["status"] == "invited"

        third = await _fresh_club()
        site = await _admin_headers(client, caplog, "cm-site-zwei@example.org")
        assert (await _add(client, site, "cm-zwei@example.org", third))["status"] == "active"
        zwei = await _headers(client, caplog, "cm-zwei@example.org")
        members_of = {i for i, e in (await _mine(client, zwei)).items() if e["is_member"]}
        assert members_of == {first, third}

    async def test_a_member_leaves_by_ending_their_own_membership(self, client, caplog):
        """Story Z-5: the one change a person may make on themselves."""
        club, admin = await _club_with_admin(client, caplog, "cm-admin3@example.org")
        await make_user("cm-carla@example.org")
        carla = await _headers(client, caplog, "cm-carla@example.org")
        entry = await _add(client, admin, "cm-carla@example.org", club)

        left = await client.delete(f"/api/clubs/{club}/members/{entry['person_id']}", headers=carla)
        assert left.status_code == 204, left.text

        assert await _roster(client, admin, club) == []
        assert club not in await _mine(client, carla)

    async def test_a_member_cannot_remove_another_member(self, client, caplog):
        """Story Z-5: leaving is about one's *own* membership; someone else's needs the
        admin (Story V-8)."""
        club, admin = await _club_with_admin(client, caplog, "cm-admin4@example.org")
        await make_user("cm-dora@example.org")
        await make_user("cm-emil@example.org")
        dora = await _headers(client, caplog, "cm-dora@example.org")
        await _headers(client, caplog, "cm-emil@example.org")
        await _add(client, admin, "cm-dora@example.org", club)
        emil = await _add(client, admin, "cm-emil@example.org", club)

        url = f"/api/clubs/{club}/members/{emil['person_id']}"
        refused = await client.delete(url, headers=dora)
        assert refused.status_code == 403, refused.text
        assert _problem_code(refused) == "membership-forbidden"
        names = {m["display_name"] for m in await _roster(client, admin, club)}
        assert names == {"cm-dora", "cm-emil"}

        removed = await client.delete(url, headers=admin)
        assert removed.status_code == 204, removed.text
        assert [m["display_name"] for m in await _roster(client, admin, club)] == ["cm-dora"]

    async def test_membership_implies_no_other_relation(self, client, caplog):
        """Story Z-5: a member is not an organizer, and gets no summary role from it —
        until the club's admin names them manager as well (Story A-8)."""
        club, admin = await _club_with_admin(client, caplog, "cm-admin6@example.org")
        await make_user("cm-greta@example.org")
        greta = await _headers(client, caplog, "cm-greta@example.org")
        await _add(client, admin, "cm-greta@example.org", club)

        (entry,) = await _roster(client, greta, club)
        assert entry["relations"] == ["member"]
        assert entry["organizer"] is False
        assert entry["admin"] is False
        me = (await client.get("/api/auth/me", headers=greta)).json()
        assert me["roles"] == []
        mine = (await _mine(client, greta))[club]
        assert mine["may_manage"] is False

        await _write(client, admin, "cm-greta@example.org", "manager", f"club:{club}")
        me = (await client.get("/api/auth/me", headers=greta)).json()
        assert me["roles"] == [Role.TEAM_MANAGER]
        entry = (await _mine(client, greta))[club]
        assert (entry["is_member"], entry["may_manage"]) == (True, True)


class TestMemberRoster:
    """Story V-10: a member sees who else belongs to the club — display names and what
    each is to the club, no email."""

    async def test_strangers_and_other_clubs_members_are_refused(self, client, caplog):
        """Story V-10: a stranger, or a member of a *different* club, gets 403."""
        club, admin = await _club_with_admin(client, caplog, "cm-radmin2@example.org")
        other, other_admin = await _club_with_admin(client, caplog, "cm-radmin3@example.org")
        await make_user("cm-fremd@example.org")
        await make_user("cm-nachbar@example.org")
        stranger = await _headers(client, caplog, "cm-fremd@example.org")
        neighbour = await _headers(client, caplog, "cm-nachbar@example.org")
        await _add(client, other_admin, "cm-nachbar@example.org", other)

        for headers in (stranger, neighbour):
            response = await client.get(f"/api/clubs/{club}/members", headers=headers)
            assert response.status_code == 403, response.text
            assert _problem_code(response) == "club-members-restricted-to-members"

    async def test_signed_out_gets_401(self, client):
        """Story V-10: the roster is the club's own, so there is no public form."""
        club = await _fresh_club()
        response = await client.get(f"/api/clubs/{club}/members")
        assert response.status_code == 401, response.text

    async def test_organizers_are_marked_and_a_non_member_admin_is_not_listed(self, client, caplog):
        """Story V-10: a member sees the roster with what each is to the club, no email;
        a manager who is also a member is marked `organizer`; the admin who is no member
        does not appear in the roster, and may read it all the same."""
        club, admin = await _club_with_admin(client, caplog, "cm-radmin4@example.org")
        await make_user("cm-jana@example.org")
        await make_user("cm-kai@example.org")
        await _headers(client, caplog, "cm-jana@example.org")
        await _add(client, admin, "cm-jana@example.org", club)
        await _write(client, admin, "cm-jana@example.org", "manager", f"club:{club}")
        await _add(client, admin, "cm-kai@example.org", club)
        kai = await _headers(client, caplog, "cm-kai@example.org")

        seen = await _roster(client, kai, club)
        assert [(m["display_name"], m["relations"]) for m in seen] == [
            ("cm-jana", ["manager", "member"]),
            ("cm-kai", ["member"]),
        ]
        assert all("email" not in m for m in seen)

        roster = {m["display_name"]: m for m in await _roster(client, admin, club)}
        assert set(roster) == {"cm-jana", "cm-kai"}
        assert roster["cm-jana"]["organizer"] is True
        assert roster["cm-jana"]["admin"] is False
        assert roster["cm-jana"]["relations"] == ["manager", "member"]
        assert roster["cm-kai"]["organizer"] is False

    async def test_staff_may_read_any_roster(self, client, caplog):
        """Story V-10: the site's `admin` sees every club's roster; editorial does not —
        it writes news, and a roster is no news (decided 2026-10-24)."""
        club = await _fresh_club()
        admin = await _admin_headers(client, caplog, "cm-roster-admin@example.org")
        assert await _roster(client, admin, club) == []
        await make_user("cm-redaktion@example.org", Role.EDITOR)
        editor = await _headers(client, caplog, "cm-redaktion@example.org")
        response = await client.get(f"/api/clubs/{club}/members", headers=editor)
        assert response.status_code == 403, response.text


class TestOrganizers:
    """Story A-8: the club's admin names more organizers; at least one must remain."""

    async def test_the_only_organizer_may_drop_one_of_two_relations(self, client, caplog):
        """Story A-8: who is both admin and manager, and the club's only organizer, may
        drop the manager tuple — as admin they are still a manager. The admin tuple is
        the one that has to stay."""
        club, admin = await _club_with_admin(client, caplog, "cm-oadmin-both@example.org")
        site = await _admin_headers(client, caplog, "cm-site-admin@example.org")
        await _write(client, site, "cm-oadmin-both@example.org", "manager", f"club:{club}")

        manager = await _my_tuple(client, admin, "manager", club)
        dropped = await client.delete(f"/api/auth/tuples/{manager['id']}", headers=admin)
        assert dropped.status_code == 204, dropped.text

        last = await _my_tuple(client, admin, "admin", club)
        refused = await client.delete(f"/api/auth/tuples/{last['id']}", headers=site)
        assert refused.status_code == 409
        assert _problem_code(refused) == "last-organizer"

    async def test_the_last_admin_cannot_leave_with_the_whole_account(self, client, caplog):
        """Story A-8: deleting one's own account, or the league office deactivating it, is
        the whole account going at once — no way past the last-admin rule."""
        club, admin = await _club_with_admin(client, caplog, "cm-oadmin-gone@example.org")
        refused = await client.delete("/api/auth/me", headers=admin)
        assert refused.status_code == 409, refused.text
        assert _problem_code(refused) == "last-organizer"

        site = await _admin_headers(client, caplog, "cm-site-gone@example.org")
        me = (await client.get("/api/auth/me", headers=admin)).json()
        deactivated = await client.delete(f"/api/auth/users/{me['id']}", headers=site)
        assert deactivated.status_code == 409
        assert _problem_code(deactivated) == "last-organizer"

        # With a second admin named, the first may go.
        await make_user("cm-second@example.org")
        await _write(client, admin, "cm-second@example.org", "admin", f"club:{club}")
        assert (await client.delete("/api/auth/me", headers=admin)).status_code == 204

    async def test_a_clubs_organizer_lists_no_accounts(self, client, caplog):
        """Story V-10: the account list carries every tuple — who is in which club — so it
        is the league office's alone, not every club's organizer's."""
        _, admin = await _club_with_admin(client, caplog, "cm-oadmin-list@example.org")
        assert (await client.get("/api/auth/users", headers=admin)).status_code == 403

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

    async def test_the_last_admin_cannot_go_while_only_managers_remain(self, client, caplog):
        """Story A-8: a manager beside the admin is not enough — the admin decides who is
        in the club, and a club of managers only could not add anyone any more. With a
        second admin the first may go, and a manager may go while an admin remains."""
        site = await _admin_headers(client, caplog, "cm-site-b@example.org")
        club, admin = await _club_with_admin(client, caplog, "cm-oadmin6@example.org")
        admin_row = await _my_tuple(client, admin, "admin", club)
        await make_user("cm-nora@example.org")
        manager_row = await _write(client, admin, "cm-nora@example.org", "manager", f"club:{club}")

        refused = await client.delete(f"/api/auth/tuples/{admin_row['id']}", headers=site)
        assert refused.status_code == 409, refused.text
        assert _problem_code(refused) == "last-organizer"

        gone = await client.delete(f"/api/auth/tuples/{manager_row['id']}", headers=admin)
        assert gone.status_code == 204, gone.text

        await make_user("cm-ada@example.org")
        await _write(client, admin, "cm-ada@example.org", "admin", f"club:{club}")
        handed_over = await client.delete(f"/api/auth/tuples/{admin_row['id']}", headers=site)
        assert handed_over.status_code == 204, handed_over.text

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
