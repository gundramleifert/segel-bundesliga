"""Stories V-8 and V-10: *Club › People* — one list of the club's people (#45).

Everyone with a membership of the club, searched, filtered and sorted on the server
(Story A-13): the organizers see the whole list with addresses and dates of birth, the
invitations and requests too; a plain member sees the roster — active members, names,
accounts and roles — and filters by nothing that would reveal a date of birth.

Each test works on a fresh club (docs/gotchas: counts against seed rows).
"""

from uuid import uuid4

from tests.stories.test_club_members import _add, _club_with_admin, _fresh_club
from tests.stories.test_login_and_roles import _headers, _problem_code, _write, make_user


def _tag() -> str:
    return uuid4().hex[:6]


async def _people(client, headers, club: int, **params) -> list[dict]:
    response = await client.get(f"/api/clubs/{club}/people", headers=headers, params=params)
    assert response.status_code == 200, response.text
    return response.json()["items"]


async def _person(client, headers, club: int, first: str, last: str, birth: str | None) -> int:
    body = {
        "first_name": first,
        "last_name": last,
        "email": f"{first.lower()}-{_tag()}@example.org",
    }
    if birth:
        body["birth_date"] = birth
    response = await client.post(
        "/api/admin/people", headers=headers, json=body | {"club_id": club}
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def _club_of_four(client, caplog):
    """A club with its admin (no member), a member with an account who is its manager, an
    adult and a child created by the club — no accounts — the child without a date."""
    club, admin = await _club_with_admin(client, caplog, f"cp-admin-{_tag()}@example.org")
    member_email = f"cp-mia-{_tag()}@example.org"
    await make_user(member_email)
    member = await _headers(client, caplog, member_email)
    await _add(client, admin, member_email, club)
    await _write(client, admin, member_email, "manager", f"club:{club}")
    adult = await _person(client, admin, club, "Arne", "Alt", "1980-05-01")
    child = await _person(client, admin, club, "Kai", "Kind", None)
    return club, admin, member, member_email, adult, child


class TestClubPeople:
    """Story V-8: the organizers' list, narrowed on the server."""

    async def test_the_organizers_see_everyone_and_narrow_the_list(self, client, caplog):
        club, admin, _, member_email, adult, child = await _club_of_four(client, caplog)

        everyone = await _people(client, admin, club, sort="last_name")
        # Case does not order: the admin's name is the lowercase part of an address.
        names = [p["last_name"] for p in everyone]
        assert names == sorted(names, key=str.lower)
        arne, kai = (next(p for p in everyone if p["person_id"] == i) for i in (adult, child))
        mia = next(p for p in everyone if p["email"] == member_email)
        assert (mia["roles"], mia["status"]) == (["manager"], "active")
        # The account's address — what a role is written to from the row's menu.
        assert mia["account_email"] == member_email
        # The club's admin is no member, and listed all the same: organizers often never sail.
        (board,) = [p for p in everyone if p["roles"] == ["admin"]]
        assert board["status"] is None
        assert arne["birth_date"] == "1980-05-01" and arne["minor"] is False
        assert kai["birth_date"] is None and kai["minor"] is None

        assert [p["person_id"] for p in await _people(client, admin, club, q="kind")] == [child]
        assert [p["email"] for p in await _people(client, admin, club, role="manager")] == [
            member_email
        ]
        assert {p["person_id"] for p in await _people(client, admin, club, account="false")} == {
            adult,
            child,
        }
        # An account's person has no date until it is given.
        undated = {p["person_id"] for p in await _people(client, admin, club, no_birth_date="true")}
        assert undated == {child, mia["person_id"], board["person_id"]}
        assert [p["person_id"] for p in await _people(client, admin, club, minor="false")] == [
            adult
        ]
        assert await _people(client, admin, club, in_squad="true") == []
        by_age = await _people(client, admin, club, sort="-birth_date", no_birth_date="false")
        assert [p["person_id"] for p in by_age] == [adult]

    async def test_waiting_rows_are_the_organizers_and_filtered_by_status(self, client, caplog):
        """Stories V-8, V-15: a request waits in the list, filtered by status."""
        club, admin, *_ = await _club_of_four(client, caplog)
        email = f"cp-ask-{_tag()}@example.org"
        await make_user(email)
        asker = await _headers(client, caplog, email)
        assert (
            await client.post("/api/me/memberships", headers=asker, json={"club_id": club})
        ).status_code == 201

        waiting = await _people(client, admin, club, status="requested")
        assert [p["status"] for p in waiting] == ["requested"]

    async def test_an_unknown_sort_is_refused(self, client, caplog):
        club, admin = await _club_with_admin(client, caplog, f"cp-sort-{_tag()}@example.org")
        response = await client.get(
            f"/api/clubs/{club}/people", headers=admin, params={"sort": "email"}
        )
        assert response.status_code == 422, response.text
        assert _problem_code(response) == "unknown-sort-column"


class TestTheRoster:
    """Story V-10: a plain member reads the roster — names, accounts and roles."""

    async def test_a_member_sees_names_and_roles_and_no_dates(self, client, caplog):
        club, admin, _, _, adult, child = await _club_of_four(client, caplog)
        plain = f"cp-plain-{_tag()}@example.org"
        await make_user(plain)
        member = await _headers(client, caplog, plain)
        await _add(client, admin, plain, club)

        seen = await _people(client, member, club)
        assert {p["person_id"] for p in seen} >= {adult, child}
        assert all(
            p["email"] is None and p["account_email"] is None and p["birth_date"] is None
            for p in seen
        )
        for forbidden in ({"minor": "true"}, {"no_birth_date": "true"}, {"status": "requested"}):
            response = await client.get(
                f"/api/clubs/{club}/people", headers=member, params=forbidden
            )
            assert response.status_code == 403, response.text
            assert _problem_code(response) == "club-people-filter-forbidden"

    async def test_a_stranger_is_refused(self, client, caplog):
        club = await _fresh_club()
        email = f"cp-fremd-{_tag()}@example.org"
        await make_user(email)
        stranger = await _headers(client, caplog, email)
        response = await client.get(f"/api/clubs/{club}/people", headers=stranger)
        assert response.status_code == 403, response.text
        assert _problem_code(response) == "club-members-restricted-to-members"
