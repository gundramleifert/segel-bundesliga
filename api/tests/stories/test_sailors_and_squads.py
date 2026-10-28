"""User Stories V-4 and V-1: Create sailors and register squad for a series.

Two levels that belong together: The **Person** exists independently of any competition.
The **Squad** is their registration for a series — from it, the lineup is selected
for each matchday.

The rule in focus here: Sailing for multiple clubs is allowed, but **within a series**
a person competes only once.
"""

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.db import SessionLocal
from app.models import Club, Event, Person, Series, Team, TeamMembership, TeamStatus
from app.models.auth import Role
from tests.pages import all_items
from tests.stories.test_login_and_roles import login_as, make_user
from tests.stories.test_registration import auth_headers


async def as_role(client, caplog, email: str, *roles: str, club_id: int | None = None):
    await make_user(email, *roles, club_id=club_id)
    return auth_headers(await login_as(client, email, caplog))


async def series_registration(
    series_slug: str = "junioren-2026", most_recent: bool = True
) -> tuple[int, int]:
    """A series registration: (team_id, club_id).

    Deliberately using Juniors, not the first league: scoring and lineup stories hang on that,
    and these here modify squads.
    """
    async with SessionLocal() as session:
        stmt = (
            select(Team)
            .join(Series, Team.series_id == Series.id)
            .where(Series.slug == series_slug, Team.event_id.is_(None))
            .order_by(Team.id.desc() if most_recent else Team.id)
            .limit(1)
        )
        team = (await session.execute(stmt)).scalar_one()
        return team.id, team.club_id


async def squad_of(club_slug: str, series_slug: str) -> tuple[int, list[int]]:
    """A named club's series registration with squad: (team_id, sailor IDs)."""
    async with SessionLocal() as session:
        team = (
            await session.execute(
                select(Team)
                .join(Series, Team.series_id == Series.id)
                .join(Club, Team.club_id == Club.id)
                .where(
                    Series.slug == series_slug,
                    Club.slug == club_slug,
                    Team.event_id.is_(None),
                )
            )
        ).scalar_one()
        squad = list(
            (
                await session.execute(
                    select(TeamMembership.person_id)
                    .where(TeamMembership.team_id == team.id)
                    .order_by(TeamMembership.id)
                )
            ).scalars()
        )
        return team.id, squad


async def act_id(slug: str) -> int:
    async with SessionLocal() as session:
        return (await session.execute(select(Event.id).where(Event.slug == slug))).scalar_one()


class TestCreatingSailors:
    """V-4: As club leadership, I want to create our sailors."""

    async def test_a_team_manager_changes_only_their_own_clubs_people(self, client, caplog):
        """Story V-4: any club's organizer finds people, but changes only those who sail for
        their club — or for no club yet. (Until 2026-10-17 any club's organizer could
        rename anyone; found by Journey J-3.)"""
        team_id, squad = await squad_of("byc", "demo-1-2026")
        byc_person = squad[0]
        async with SessionLocal() as session:
            other = (await session.execute(select(Club.id).where(Club.slug == "fsc"))).scalar_one()
            byc = (await session.execute(select(Club.id).where(Club.slug == "byc"))).scalar_one()
        foreign = await as_role(
            client, caplog, "sg-foreign@example.com", Role.TEAM_MANAGER, club_id=other
        )
        own = await as_role(client, caplog, "sg-own@example.com", Role.TEAM_MANAGER, club_id=byc)
        foreign_admin = await as_role(
            client, caplog, "sg-foreign-admin@example.com", Role.CLUB_ADMIN, club_id=other
        )

        refused = await client.patch(
            f"/api/admin/people/{byc_person}", headers=foreign, json={"first_name": "Hijacked"}
        )
        assert refused.status_code == 403, refused.text
        assert refused.json()["type"] == "/errors/person-not-yours"

        fixed = await client.patch(
            f"/api/admin/people/{byc_person}", headers=own, json={"last_name": "Corrected"}
        )
        assert fixed.status_code == 200, fixed.text

        # Someone a club creates sails for that club from the start — another club's
        # organizer cannot rename them, before any squad holds them.
        created = await client.post(
            "/api/admin/people",
            headers=foreign_admin,
            json={
                "first_name": "Neu",
                "last_name": "Ling",
                "email": "sg-newling@example.com",
                "club_id": other,
            },
        )
        assert created.status_code == 201, created.text
        assert created.json()["club_ids"] == [other]
        refused = await client.patch(
            f"/api/admin/people/{created.json()['id']}", headers=own, json={"first_name": "Neo"}
        )
        assert refused.status_code == 403, refused.text

        # Someone the league office created sails for no club yet: any club's organizer
        # may still correct the spelling.
        office = await as_role(client, caplog, "sg-own-office@example.com", Role.ADMIN)
        loose = await client.post(
            "/api/admin/people",
            headers=office,
            json={"first_name": "Los", "last_name": "Gelöst", "email": "sg-loose@example.com"},
        )
        assert loose.json()["club_ids"] == []
        renamed = await client.patch(
            f"/api/admin/people/{loose.json()['id']}", headers=own, json={"first_name": "Lose"}
        )
        assert renamed.status_code == 200, renamed.text

    async def test_an_address_once_set_is_the_league_offices_to_change(self, client, caplog):
        """Story V-4: the address links a sailor's record to an account (waivers, the
        profile). A club's organizer gives one to a person who has none; re-pointing it
        would hand the record to another account, so only the league office does that —
        however the person came into the organizer's squad."""
        _, club = await series_registration()
        manager = await as_role(
            client, caplog, "sg-mail@example.com", Role.TEAM_MANAGER, club_id=club
        )
        office = await as_role(client, caplog, "sg-mail-office@example.com", Role.ADMIN)
        club_admin = await as_role(
            client, caplog, "sg-mail-admin@example.com", Role.CLUB_ADMIN, club_id=club
        )
        created = await client.post(
            "/api/admin/people",
            headers=club_admin,
            json={
                "first_name": "Mia",
                "last_name": "Mail",
                "email": "sg-mia@example.com",
                "club_id": club,
            },
        )
        person = created.json()["id"]

        refused = await client.patch(
            f"/api/admin/people/{person}", headers=manager, json={"email": "sg-other@example.com"}
        )
        assert refused.status_code == 403
        assert refused.json()["type"] == "/errors/person-email-locked"
        unchanged = await client.patch(
            f"/api/admin/people/{person}",
            headers=manager,
            json={"first_name": "Maja", "email": "sg-mia@example.com"},
        )
        assert unchanged.status_code == 200, unchanged.text
        moved = await client.patch(
            f"/api/admin/people/{person}", headers=office, json={"email": "sg-other@example.com"}
        )
        assert moved.status_code == 200, moved.text

    async def test_email_is_required(self, client, caplog):
        """Someone created through this form must be reachable — name alone won't do."""
        header = await as_role(client, caplog, "sg1@example.com", Role.ADMIN)
        response = await client.post(
            "/api/admin/people",
            headers=header,
            json={"first_name": "Marie", "last_name": "Steuerfrau"},
        )
        assert response.status_code == 422

        with_email = await client.post(
            "/api/admin/people",
            headers=header,
            json={
                "first_name": "Marie",
                "last_name": "Steuerfrau",
                "email": "Marie.Steuerfrau@example.com",
            },
        )
        assert with_email.status_code == 201, with_email.text
        assert with_email.json()["first_name"] == "Marie"
        # The address is the link to the account, stored lowercased — otherwise two
        # spellings lead to two accounts.
        assert with_email.json()["email"] == "marie.steuerfrau@example.com"

    async def test_the_same_address_twice_is_refused(self, client, caplog):
        header = await as_role(client, caplog, "sg3@example.com", Role.ADMIN)
        data = {
            "first_name": "Doppel",
            "last_name": "Adresse",
            "email": "doppel.adresse@example.com",
        }
        assert (
            await client.post("/api/admin/people", headers=header, json=data)
        ).status_code == 201

        second = await client.post("/api/admin/people", headers=header, json=data)
        assert second.status_code == 409
        assert second.json()["type"] == "/errors/email-taken"

    async def test_an_account_without_a_role_creates_nobody(self, client, caplog):
        header = await as_role(client, caplog, "sg5@example.com")
        response = await client.post(
            "/api/admin/people",
            headers=header,
            json={
                "first_name": "Heimlich",
                "last_name": "Angelegt",
                "email": "heimlich.angelegt@example.com",
            },
        )
        assert response.status_code == 403

    async def test_sailors_can_be_found_by_name(self, client, caplog):
        header = await as_role(client, caplog, "sg6@example.com", Role.ADMIN)
        await client.post(
            "/api/admin/people",
            headers=header,
            json={
                "first_name": "Findus",
                "last_name": "Suchbar",
                "email": "findus.suchbar@example.com",
            },
        )
        matches = await all_items(
            client, "/api/admin/people", headers=header, params={"q": "suchbar"}
        )
        assert [t["last_name"] for t in matches] == ["Suchbar"]
        # Someone in no squad has an empty list of registrations, not a missing one.
        assert matches[0]["registrations"] == []


class TestRegisteringASquad:
    """V-1: As club leadership, I register the people who may compete for us."""

    async def _new_people(
        self, client, header, count: int, marker: str, club_id: int | None = None
    ) -> list[int]:
        ids = []
        for number in range(count):
            response = await client.post(
                "/api/admin/people",
                headers=header,
                json={
                    "first_name": f"{marker}{number}",
                    "last_name": "Squad Member",
                    "email": f"squad.{marker.lower()}{number}@example.com",
                    "club_id": club_id,
                },
            )
            assert response.status_code == 201, response.text
            ids.append(response.json()["id"])
        return ids

    async def test_a_new_squad_replaces_the_previous_one_completely(self, client, caplog):
        """The squad hangs off the series registration and is replaced as a whole. The
        club's admin creates the sailors (V-4) — they know the spelling of names, the head
        office doesn't — and the team manager registers them."""
        team_id, club_id = await series_registration()
        header = await as_role(
            client, caplog, "kd2@example.com", Role.TEAM_MANAGER, club_id=club_id
        )
        club_admin = await as_role(
            client, caplog, "kd2-admin@example.com", Role.CLUB_ADMIN, club_id=club_id
        )
        people = await self._new_people(client, club_admin, 4, "Er", club_id)
        path = f"/api/admin/teams/{team_id}/members"

        first = await client.put(
            path,
            headers=header,
            json={
                "members": [
                    {"person_id": people[0], "role": "helm"},
                    *({"person_id": s, "role": "crew"} for s in people[1:]),
                ]
            },
        )
        assert first.status_code == 200, first.text
        assert len(first.json()["members"]) == 4
        # Helm first — the order in which you name a crew.
        assert first.json()["members"][0]["role"] == "helm"

        afterwards = await client.put(
            path,
            headers=header,
            json={"members": [{"person_id": s, "role": "crew"} for s in people[:2]]},
        )
        assert {m["id"] for m in afterwards.json()["members"]} == set(people[:2])

    async def test_a_club_that_is_not_theirs_registers_nobody(self, client, caplog):
        team_id, club_id = await series_registration()
        other = await as_role(
            client, caplog, "kd6@example.com", Role.TEAM_MANAGER, club_id=club_id + 1
        )
        response = await client.put(
            f"/api/admin/teams/{team_id}/members", headers=other, json={"members": []}
        )
        assert response.status_code == 403


class TestSquadRefusalsAreTyped:
    """V-1: every refusal carries a stable code, and the names that make it actionable.

    The squad screen has to say *which* rule was broken, in the reader's language. A 422
    whose body is an English sentence the router happened to build cannot do that: the
    frontend can only print it, and only in English. So each refusal is an RFC 9457 problem
    — `type` is the contract, and the extension members carry the names the sentence needs
    (`web/src/i18n/locales/*/errors.json`).
    """

    async def _new_people(self, client, headers, count: int, prefix: str) -> list[int]:
        ids = []
        for index in range(count):
            response = await client.post(
                "/api/admin/people",
                headers=headers,
                json={
                    "first_name": prefix,
                    "last_name": f"Typed{index}",
                    "email": f"typed-{prefix.lower()}{index}@example.com",
                },
            )
            assert response.status_code in (200, 201), response.text
            ids.append(response.json()["id"])
        return ids

    async def test_the_same_person_twice_says_who(self, client, caplog):
        admin = await as_role(client, caplog, "typed1@example.com", Role.ADMIN)
        team_id, _ = await series_registration()
        person = (await self._new_people(client, admin, 1, "Dup"))[0]

        response = await client.put(
            f"/api/admin/teams/{team_id}/members",
            headers=admin,
            json={
                "members": [
                    {"person_id": person, "role": "helm"},
                    {"person_id": person, "role": "crew"},
                ]
            },
        )
        assert response.status_code == 422, response.text
        problem = response.json()
        assert problem["type"] == "/errors/squad-duplicate-person"
        assert problem["person_ids"] == [person]

    async def test_the_database_refuses_the_same_person_twice_too(self, client, caplog):
        """V-1: the router's refusal is the polite half; the unique constraint on
        `(team_id, person_id)` holds for every other writer (an import, the seed)."""
        admin = await as_role(client, caplog, "typed-db@example.com", Role.ADMIN)
        team_id, _ = await series_registration()
        person = (await self._new_people(client, admin, 1, "DupDb"))[0]

        async with SessionLocal() as session:
            session.add_all(
                TeamMembership(team_id=team_id, person_id=person, role=role)
                for role in ("helm", "crew")
            )
            with pytest.raises(IntegrityError):
                await session.commit()

    async def test_already_sailing_for_another_club_names_both(self, client, caplog):
        admin = await as_role(client, caplog, "typed2@example.com", Role.ADMIN)
        first_team, _ = await series_registration(most_recent=True)
        second_team, _ = await series_registration(most_recent=False)
        person = (await self._new_people(client, admin, 1, "Other"))[0]
        entry = {"members": [{"person_id": person, "role": "crew"}]}

        assert (
            await client.put(f"/api/admin/teams/{first_team}/members", headers=admin, json=entry)
        ).status_code == 200

        response = await client.put(
            f"/api/admin/teams/{second_team}/members", headers=admin, json=entry
        )
        assert response.status_code == 409, response.text
        problem = response.json()
        assert problem["type"] == "/errors/squad-person-in-another-club"
        # The names, so the sentence can be built in either language rather than shipped
        # in one.
        assert problem["people"] == ["Other Typed0"]

    async def test_an_entry_in_a_series_event_says_it_carries_no_squad(self, client, caplog):
        """The squad of a series' event is the series registration's — not its entry's."""
        admin = await as_role(client, caplog, "typed3@example.com", Role.ADMIN)
        async with SessionLocal() as session:
            entry = (
                await session.execute(
                    select(Team)
                    .where(Team.event_id.is_not(None), Team.series_id.is_not(None))
                    .limit(1)
                )
            ).scalar_one()

        response = await client.put(
            f"/api/admin/teams/{entry.id}/members", headers=admin, json={"members": []}
        )
        assert response.status_code == 422, response.text
        assert response.json()["type"] == "/errors/squad-needs-series-registration"

    async def test_dropping_someone_who_is_lined_up_names_the_matchday(self, client, caplog):
        admin = await as_role(client, caplog, "typed4@example.com", Role.ADMIN)
        team_id, squad = await squad_of("byc", "demo-1-2026")
        assert len(squad) >= 4

        selected = await client.put(
            f"/api/admin/events/{await act_id('demo-1-2026-act-3')}/crew",
            headers=admin,
            json={
                "team_id": team_id,
                "members": [{"person_id": s, "role": "crew"} for s in squad[:4]],
            },
        )
        assert selected.status_code == 200, selected.text

        response = await client.put(
            f"/api/admin/teams/{team_id}/members",
            headers=admin,
            json={"members": [{"person_id": person_id, "role": "crew"} for person_id in squad[4:]]},
        )
        assert response.status_code == 409, response.text
        problem = response.json()
        assert problem["type"] == "/errors/squad-member-is-lined-up"
        # Which matchday, so the organizer knows where to go and change it first.
        assert problem["selections"]
        assert problem["selections"][0]["event"]
        assert problem["selections"][0]["sailor"]

        # The squad itself names the matchday beside each of the four — before anyone tries.
        read = (await client.get(f"/api/admin/teams/{team_id}/members", headers=admin)).json()
        act = await act_id("demo-1-2026-act-3")
        lined_up = {row["person_id"] for row in read["lineups"] if row["event_id"] == act}
        assert lined_up == set(squad[:4])

    async def test_a_rejected_registration_takes_no_squad(self, client, caplog):
        """Story V-1: a rejected registration never became a participation — a squad on it
        would hold people for a series the club is not in."""
        async with SessionLocal() as session:
            club = Club(slug="sq-rejected", name="Rejected Sailing Club", short_name="RSC")
            session.add(club)
            await session.flush()
            # A series of its own: a rejected row in a seeded series would be the "most
            # recent registration" other tests here pick.
            own = Series(slug="sq-rejected-series", name="Rejected Cup 2026", short_name="RC")
            session.add(own)
            await session.flush()
            series = own.id
            team = Team(name="RSC", club_id=club.id, series_id=series, status=TeamStatus.REJECTED)
            session.add(team)
            await session.commit()
            team_id, club_id = team.id, club.id
        manager = await as_role(
            client, caplog, "sq-rejected@example.com", Role.TEAM_MANAGER, club_id=club_id
        )
        refused = await client.put(
            f"/api/admin/teams/{team_id}/members", headers=manager, json={"members": []}
        )
        assert refused.status_code == 409
        assert refused.json()["type"] == "/errors/squad-registration-rejected"

    async def test_a_person_who_does_not_exist_is_a_typed_404(self, client, caplog):
        admin = await as_role(client, caplog, "typed5@example.com", Role.ADMIN)
        team_id, _ = await series_registration()

        response = await client.put(
            f"/api/admin/teams/{team_id}/members",
            headers=admin,
            json={"members": [{"person_id": 10_000_000, "role": "crew"}]},
        )
        assert response.status_code == 404, response.text
        problem = response.json()
        assert problem["type"] == "/errors/squad-unknown-person"
        assert problem["person_ids"] == [10_000_000]


class TestASailorSailsForTheirClub:
    """V-4, V-1: a club's organizer puts in a squad the club's own members — never someone
    another club has, nor someone in no club: who is in the club is its admin's to decide,
    the team manager's only who sails (decided 2026-10-28). Before 2026-10-25 any club
    could put anyone in its squad and so sign their waivers and link their parents."""

    async def _two_clubs(self, tag: str) -> tuple[int, int, int, int]:
        """Two fresh clubs, each registered for a series of its own: (team A, club A,
        team B, club B) — two series, because a person sails once per series."""
        async with SessionLocal() as session:
            ids = []
            for side in ("a", "b"):
                club = Club(slug=f"{tag}-{side}", name=f"{tag} {side}", short_name=f"{tag}{side}")
                series = Series(slug=f"{tag}-{side}-series", name=f"{tag} {side}", short_name="X")
                session.add_all([club, series])
                await session.flush()
                team = Team(name=club.short_name, club_id=club.id, series_id=series.id)
                session.add(team)
                await session.flush()
                ids += [team.id, club.id]
            await session.commit()
        return ids[0], ids[1], ids[2], ids[3]

    async def test_a_squad_takes_nobody_another_club_has(self, client, caplog):
        team_a, club_a, team_b, club_b = await self._two_clubs("sfc1")
        a = await as_role(client, caplog, "sfc1-a@example.com", Role.TEAM_MANAGER, club_id=club_a)
        b = await as_role(client, caplog, "sfc1-b@example.com", Role.TEAM_MANAGER, club_id=club_b)
        admin_a = await as_role(
            client, caplog, "sfc1-admin-a@example.com", Role.CLUB_ADMIN, club_id=club_a
        )
        created = await client.post(
            "/api/admin/people",
            headers=admin_a,
            json={
                "first_name": "Anna",
                "last_name": "Eigen",
                "email": "sfc1-anna@example.com",
                "club_id": club_a,
            },
        )
        person = created.json()["id"]

        taken = await client.put(
            f"/api/admin/teams/{team_b}/members",
            headers=b,
            json={"members": [{"person_id": person, "role": "helm"}]},
        )
        assert taken.status_code == 403, taken.text
        assert taken.json()["type"] == "/errors/squad-person-of-another-club"
        assert taken.json()["people"] == ["Anna Eigen"]

        own = await client.put(
            f"/api/admin/teams/{team_a}/members",
            headers=a,
            json={"members": [{"person_id": person, "role": "helm"}]},
        )
        assert own.status_code == 200, own.text

    async def test_only_the_league_office_adds_a_second_club(self, client, caplog):
        team_a, club_a, team_b, club_b = await self._two_clubs("sfc2")
        office = await as_role(client, caplog, "sfc2-office@example.com", Role.ADMIN)
        b = await as_role(client, caplog, "sfc2-b@example.com", Role.TEAM_MANAGER, club_id=club_b)
        admin_a = await as_role(
            client, caplog, "sfc2-admin-a@example.com", Role.CLUB_ADMIN, club_id=club_a
        )
        admin_b = await as_role(
            client, caplog, "sfc2-admin-b@example.com", Role.CLUB_ADMIN, club_id=club_b
        )
        created = await client.post(
            "/api/admin/people",
            headers=admin_a,
            json={
                "first_name": "Ben",
                "last_name": "Beide",
                "email": "sfc2-ben@example.com",
                "club_id": club_a,
            },
        )
        person = created.json()["id"]

        # No club hands a person to another — not even the one they sail for.
        handed = await client.put(f"/api/admin/people/{person}/clubs/{club_b}", headers=admin_a)
        assert handed.status_code in (404, 405), handed.text

        joined = await client.put(
            f"/api/admin/teams/{team_b}/members",
            headers=office,
            json={"members": [{"person_id": person, "role": "crew"}]},
        )
        assert joined.status_code == 200, joined.text
        found = await client.get("/api/admin/people", headers=office, params={"q": "Beide"})
        assert found.json()["items"][0]["club_ids"] == sorted([club_a, club_b])

        # Each club's admin lets go of its own connection only — never its team manager.
        cut = await client.delete(f"/api/admin/people/{person}/clubs/{club_a}", headers=admin_b)
        assert cut.status_code == 403, cut.text
        by_manager = await client.delete(f"/api/admin/people/{person}/clubs/{club_b}", headers=b)
        assert by_manager.status_code == 403, by_manager.text
        left = await client.delete(f"/api/admin/people/{person}/clubs/{club_b}", headers=admin_b)
        assert left.status_code == 200, left.text
        assert left.json()["club_ids"] == [club_a]

    async def test_someone_in_no_club_joins_through_the_club_admin_not_the_squad(
        self, client, caplog
    ):
        """The league office creates people without a club (an import does too). A team
        manager cannot take them into the club through a squad (`squad-person-not-a-member`,
        decided 2026-10-28) — the club's admin adds them, then they sail."""
        team_a, club_a, team_b, club_b = await self._two_clubs("sfc3")
        office = await as_role(client, caplog, "sfc3-office@example.com", Role.ADMIN)
        a = await as_role(client, caplog, "sfc3-a@example.com", Role.TEAM_MANAGER, club_id=club_a)
        b = await as_role(client, caplog, "sfc3-b@example.com", Role.TEAM_MANAGER, club_id=club_b)
        admin_a = await as_role(
            client, caplog, "sfc3-admin-a@example.com", Role.CLUB_ADMIN, club_id=club_a
        )
        created = await client.post(
            "/api/admin/people",
            headers=office,
            json={"first_name": "Cleo", "last_name": "Frei", "email": "sfc3-cleo@example.com"},
        )
        person = created.json()["id"]
        assert created.json()["club_ids"] == []

        refused = await client.put(
            f"/api/admin/teams/{team_a}/members",
            headers=a,
            json={"members": [{"person_id": person, "role": "crew"}]},
        )
        assert refused.status_code == 403, refused.text
        assert refused.json()["type"] == "/errors/squad-person-not-a-member"
        assert refused.json()["people"] == ["Cleo Frei"]

        added = await client.post(
            f"/api/clubs/{club_a}/members", headers=admin_a, json={"email": "sfc3-cleo@example.com"}
        )
        assert added.status_code == 201, added.text
        first = await client.put(
            f"/api/admin/teams/{team_a}/members",
            headers=a,
            json={"members": [{"person_id": person, "role": "crew"}]},
        )
        assert first.status_code == 200, first.text
        second = await client.put(
            f"/api/admin/teams/{team_b}/members",
            headers=b,
            json={"members": [{"person_id": person, "role": "crew"}]},
        )
        assert second.status_code == 403, second.text

    async def test_only_the_club_admin_creates_people_for_their_own_club(self, client, caplog):
        """A new person is a member at once, so creating one is the club's admin's — the
        team manager decides who sails, not who is in the club (decided 2026-10-28).

        Journey step J-3.11."""
        _, club_a, _, club_b = await self._two_clubs("sfc4")
        manager = await as_role(
            client, caplog, "sfc4-m@example.com", Role.TEAM_MANAGER, club_id=club_a
        )
        a = await as_role(client, caplog, "sfc4-a@example.com", Role.CLUB_ADMIN, club_id=club_a)
        person = {"first_name": "Dora", "last_name": "Dort", "email": "sfc4-dora@example.com"}
        by_manager = await client.post(
            "/api/admin/people", headers=manager, json={**person, "club_id": club_a}
        )
        assert by_manager.status_code == 403, by_manager.text
        assert by_manager.json()["type"] == "/errors/person-club-not-yours"
        without = await client.post("/api/admin/people", headers=a, json=person)
        assert without.status_code == 422, without.text
        assert without.json()["type"] == "/errors/person-needs-club"
        elsewhere = await client.post(
            "/api/admin/people", headers=a, json={**person, "club_id": club_b}
        )
        assert elsewhere.status_code == 403, elsewhere.text
        assert elsewhere.json()["type"] == "/errors/person-club-not-yours"
        own = await client.post("/api/admin/people", headers=a, json={**person, "club_id": club_a})
        assert own.status_code == 201, own.text
        assert own.json()["club_ids"] == [club_a]


class TestFindingTheRightPerson:
    """V-1: a candidate list has to identify people, not just name them.

    A person belongs to as many clubs as they sail for — one `TeamMembership` row per
    series registration — and in this data eighteen people share a surname. So a row
    reading "Nanisberg · 3 registrations" answers neither of the two questions a club
    manager actually has: is this the right one, and can I add them at all.
    """

    async def test_a_sailor_carries_the_clubs_and_series_they_sail_for(self, client, caplog):
        admin = await as_role(client, caplog, "who1@example.com", Role.ADMIN)
        team_id, club_id = await series_registration()

        created = await client.post(
            "/api/admin/people",
            headers=admin,
            json={
                "first_name": "Identifiable",
                "last_name": "Person",
                "email": "who-identifiable@example.com",
            },
        )
        assert created.status_code in (200, 201), created.text
        person_id = created.json()["id"]

        assert (
            await client.put(
                f"/api/admin/teams/{team_id}/members",
                headers=admin,
                json={"members": [{"person_id": person_id, "role": "helm"}]},
            )
        ).status_code == 200

        found = await client.get("/api/admin/people", headers=admin, params={"q": "Identifiable"})
        assert found.status_code == 200, found.text
        person = next(p for p in found.json()["items"] if p["id"] == person_id)

        assert len(person["registrations"]) == 1
        registration = person["registrations"][0]
        assert registration["club"]["id"] == club_id
        # Club *and* series: the club alone does not say which competition, and a person
        # can be in the same club for two of them.
        assert registration["series"]["id"]
        assert registration["role"] == "helm"

    async def test_the_same_person_in_two_clubs_shows_both(self, client, caplog):
        """The case the bare count could not express. Two clubs, two different series —
        allowed, and the reason the list has to name them."""
        admin = await as_role(client, caplog, "who2@example.com", Role.ADMIN)
        juniors, juniors_club = await series_registration("junioren-2026")
        scl, scl_club = await series_registration("scl-2026")

        created = await client.post(
            "/api/admin/people",
            headers=admin,
            json={
                "first_name": "Two",
                "last_name": "Clubs",
                "email": "who-twoclubs@example.com",
            },
        )
        person_id = created.json()["id"]

        for team_id in (juniors, scl):
            response = await client.put(
                f"/api/admin/teams/{team_id}/members",
                headers=admin,
                json={"members": [{"person_id": person_id, "role": "crew"}]},
            )
            assert response.status_code == 200, response.text

        person = next(
            p
            for p in await all_items(
                client, "/api/admin/people", headers=admin, params={"q": "Clubs"}
            )
            if p["id"] == person_id
        )
        assert {r["club"]["id"] for r in person["registrations"]} == {
            juniors_club,
            scl_club,
        }
        assert len({r["series"]["id"] for r in person["registrations"]}) == 2


class TestSquadLimits:
    """Story V-1: the squad's size is set per series — or per event when it stands alone.
    The maximum is enforced on save; the minimum is guidance the screen shows."""

    async def _series_with_one_club(self, client, admin, name: str, **limits) -> tuple[int, int]:
        """A fresh series with one club → (series_id, team_id). Fresh, because the seeded
        series are what every other squad story registers into."""
        async with SessionLocal() as session:
            club_id = (
                await session.execute(select(Club.id).where(Club.slug == "fsc"))
            ).scalar_one()
        created = await client.post(
            "/api/admin/series",
            headers=admin,
            json={"name": name, "year": 2027, "clubs": [club_id], **limits},
        )
        assert created.status_code == 201, created.text
        series_id = created.json()["id"]
        async with SessionLocal() as session:
            team_id = (
                await session.execute(
                    select(Team.id).where(Team.series_id == series_id, Team.club_id == club_id)
                )
            ).scalar_one()
        return series_id, team_id

    async def test_the_squad_carries_the_limits_of_its_series(self, client, caplog):
        admin = await as_role(client, caplog, "lim-admin@example.com", Role.ADMIN)
        series_id, team_id = await self._series_with_one_club(client, admin, "Limits League 2027")

        squad = (await client.get(f"/api/admin/teams/{team_id}/members", headers=admin)).json()
        assert (squad["squad_min"], squad["squad_max"]) == (4, 10)  # the defaults

        changed = await client.patch(
            f"/api/admin/series/{series_id}",
            headers=admin,
            json={"squad_min": 3, "squad_max": 6},
        )
        assert changed.status_code == 200, changed.text
        assert (changed.json()["squad_min"], changed.json()["squad_max"]) == (3, 6)
        squad = (await client.get(f"/api/admin/teams/{team_id}/members", headers=admin)).json()
        assert (squad["squad_min"], squad["squad_max"]) == (3, 6)

    async def test_the_maximum_is_enforced_and_the_minimum_is_not(self, client, caplog):
        admin = await as_role(client, caplog, "lim-admin2@example.com", Role.ADMIN)
        _, team_id = await self._series_with_one_club(
            client, admin, "Small League 2027", squad_min=2, squad_max=3
        )
        people = await TestRegisteringASquad._new_people(self, client, admin, 4, "Li")
        path = f"/api/admin/teams/{team_id}/members"

        too_many = await client.put(
            path,
            headers=admin,
            json={"members": [{"person_id": s, "role": "crew"} for s in people]},
        )
        assert too_many.status_code == 422, too_many.text
        problem = too_many.json()
        assert problem["type"] == "/errors/squad-too-large"
        assert problem["squad_max"] == 3
        assert problem["registered"] == 4

        # Below the minimum saves: a squad is built up over weeks.
        one = await client.put(
            path, headers=admin, json={"members": [{"person_id": people[0], "role": "helm"}]}
        )
        assert one.status_code == 200, one.text
        assert len(one.json()["members"]) == 1

    async def test_a_minimum_above_the_maximum_is_refused(self, client, caplog):
        admin = await as_role(client, caplog, "lim-admin3@example.com", Role.ADMIN)
        series_id, _ = await self._series_with_one_club(client, admin, "Odd League 2027")
        response = await client.patch(
            f"/api/admin/series/{series_id}", headers=admin, json={"squad_min": 8, "squad_max": 5}
        )
        assert response.status_code == 422, response.text
        assert response.json()["type"] == "/errors/squad-limits-invalid"

        created = await client.post(
            "/api/admin/series",
            headers=admin,
            json={"name": "Odder League 2027", "year": 2027, "squad_min": 8, "squad_max": 5},
        )
        assert created.status_code == 422
        assert created.json()["type"] == "/errors/squad-limits-invalid"

    async def test_a_stand_alone_event_has_its_own_limits(self, client, caplog):
        admin = await as_role(client, caplog, "lim-admin4@example.com", Role.ADMIN)
        async with SessionLocal() as session:
            club_id = (
                await session.execute(select(Club.id).where(Club.slug == "fsc"))
            ).scalar_one()
        created = await client.post(
            "/api/admin/events",
            headers=admin,
            json={"title": "FSC Cup", "starts_on": "2027-05-01", "squad_min": 2, "squad_max": 5},
        )
        assert created.status_code == 201, created.text
        event_id = created.json()["id"]
        assert (created.json()["squad_min"], created.json()["squad_max"]) == (2, 5)
        entered = await client.put(
            f"/api/admin/events/{event_id}/clubs", headers=admin, json={"clubs": [club_id]}
        )
        assert entered.status_code == 200, entered.text
        team_id = next(e["team_id"] for e in entered.json() if e["club"]["id"] == club_id)

        squad = (await client.get(f"/api/admin/teams/{team_id}/members", headers=admin)).json()
        assert (squad["squad_min"], squad["squad_max"]) == (2, 5)

        # The entry *is* the squad's team: it is saved there, within the event's limits.
        async with SessionLocal() as session:
            people = list(
                (await session.execute(select(Person.id).order_by(Person.id).limit(6))).scalars()
            )
        saved = await client.put(
            f"/api/admin/teams/{team_id}/members",
            headers=admin,
            json={"members": [{"person_id": sid, "role": "crew"} for sid in people[:3]]},
        )
        assert saved.status_code == 200, saved.text
        assert {m["id"] for m in saved.json()["members"]} == set(people[:3])
        too_many = await client.put(
            f"/api/admin/teams/{team_id}/members",
            headers=admin,
            json={"members": [{"person_id": sid, "role": "crew"} for sid in people]},
        )
        assert too_many.status_code == 422
        assert too_many.json()["type"] == "/errors/squad-too-large"

        widened = await client.patch(
            f"/api/admin/events/{event_id}", headers=admin, json={"squad_max": 6}
        )
        assert widened.status_code == 200, widened.text
        squad = (await client.get(f"/api/admin/teams/{team_id}/members", headers=admin)).json()
        assert squad["squad_max"] == 6
