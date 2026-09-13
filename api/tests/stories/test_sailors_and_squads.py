"""User Stories V-4 and V-1: Create sailors and register squad for a series.

Two levels that belong together: The **Person** exists independently of any competition.
The **Squad** is their registration for a series — from it, the lineup is selected
for each matchday.

The rule in focus here: Sailing for multiple clubs is allowed, but **within a series**
a person competes only once.
"""

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Club, Event, Series, Team, TeamMembership
from app.models.auth import Role
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
                    select(TeamMembership.sailor_id)
                    .where(TeamMembership.team_id == team.id)
                    .order_by(TeamMembership.id)
                )
            ).scalars()
        )
        return team.id, squad


async def act_id(slug: str) -> int:
    async with SessionLocal() as session:
        return (
            await session.execute(select(Event.id).where(Event.slug == slug))
        ).scalar_one()


class TestCreatingSailors:
    """V-4: As club leadership, I want to create our sailors."""

    async def test_email_is_required(self, client, caplog):
        """Someone created through this form must be reachable — name alone won't do."""
        header = await as_role(client, caplog, "sg1@example.com", Role.ADMIN)
        response = await client.post(
            "/api/admin/sailors",
            headers=header,
            json={"first_name": "Marie", "last_name": "Steuerfrau"},
        )
        assert response.status_code == 422

        with_email = await client.post(
            "/api/admin/sailors",
            headers=header,
            json={
                "first_name": "Marie",
                "last_name": "Steuerfrau",
                "email": "marie.steuerfrau@example.com",
            },
        )
        assert with_email.status_code == 201, with_email.text
        assert with_email.json()["first_name"] == "Marie"

    async def test_the_email_address_is_the_link_to_the_account(self, client, caplog):
        header = await as_role(client, caplog, "sg2@example.com", Role.ADMIN)
        response = await client.post(
            "/api/admin/sailors",
            headers=header,
            json={
                "first_name": "Jan",
                "last_name": "Vorschoter",
                "email": "Jan.Vorschoter@example.com",
            },
        )
        # Stored lowercased — otherwise two spellings lead to two accounts.
        assert response.json()["email"] == "jan.vorschoter@example.com"

    async def test_the_same_address_twice_is_refused(self, client, caplog):
        header = await as_role(client, caplog, "sg3@example.com", Role.ADMIN)
        data = {
            "first_name": "Doppel",
            "last_name": "Adresse",
            "email": "doppel.adresse@example.com",
        }
        assert (
            await client.post("/api/admin/sailors", headers=header, json=data)
        ).status_code == 201

        second = await client.post("/api/admin/sailors", headers=header, json=data)
        assert second.status_code == 409
        assert "unique" in second.json()["detail"]

    async def test_the_club_leadership_may_do_it_too(self, client, caplog):
        """They know the spelling of names, the head office doesn't."""
        _team_id, club_id = await series_registration()
        header = await as_role(
            client, caplog, "sg4@example.com", Role.CLUB_MANAGER, club_id=club_id
        )
        response = await client.post(
            "/api/admin/sailors",
            headers=header,
            json={
                "first_name": "Vereins",
                "last_name": "Melder",
                "email": "vereins.melder@example.com",
            },
        )
        assert response.status_code == 201

    async def test_an_account_without_a_role_creates_nobody(self, client, caplog):
        header = await as_role(client, caplog, "sg5@example.com")
        response = await client.post(
            "/api/admin/sailors",
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
            "/api/admin/sailors",
            headers=header,
            json={
                "first_name": "Findus",
                "last_name": "Suchbar",
                "email": "findus.suchbar@example.com",
            },
        )
        matches = (
            await client.get("/api/admin/sailors?q=suchbar", headers=header)
        ).json()
        assert [t["last_name"] for t in matches] == ["Suchbar"]

    async def test_a_name_can_be_corrected(self, client, caplog):
        header = await as_role(client, caplog, "sg7@example.com", Role.ADMIN)
        created = (
            await client.post(
                "/api/admin/sailors",
                headers=header,
                json={
                    "first_name": "Tipp",
                    "last_name": "Feler",
                    "email": "tipp.feler@example.com",
                },
            )
        ).json()

        updated = await client.patch(
            f"/api/admin/sailors/{created['id']}",
            headers=header,
            json={"last_name": "Fehler"},
        )
        assert updated.status_code == 200
        assert updated.json()["last_name"] == "Fehler"


class TestRegisteringASquad:
    """V-1: As club leadership, I register the people who may compete for us."""

    async def _new_sailors(self, client, header, count: int, marker: str) -> list[int]:
        ids = []
        for number in range(count):
            response = await client.post(
                "/api/admin/sailors",
                headers=header,
                json={
                    "first_name": f"{marker}{number}",
                    "last_name": "Squad Member",
                    "email": f"squad.{marker.lower()}{number}@example.com",
                },
            )
            assert response.status_code == 201, response.text
            ids.append(response.json()["id"])
        return ids

    async def test_the_squad_hangs_off_the_series_registration(self, client, caplog):
        team_id, club_id = await series_registration()
        header = await as_role(
            client, caplog, "kd1@example.com", Role.CLUB_MANAGER, club_id=club_id
        )
        sailors = await self._new_sailors(client, header, 3, "Ka")

        response = await client.put(
            f"/api/admin/teams/{team_id}/members",
            headers=header,
            json={
                "members": [
                    {"sailor_id": sailors[0], "role": "helm"},
                    *({"sailor_id": s, "role": "crew"} for s in sailors[1:]),
                ]
            },
        )
        assert response.status_code == 200, response.text
        assert len(response.json()["members"]) == 3
        # Helm first — the order in which you name a crew.
        assert response.json()["members"][0]["role"] == "helm"

    async def test_a_new_squad_replaces_the_previous_one_completely(self, client, caplog):
        team_id, club_id = await series_registration()
        header = await as_role(
            client, caplog, "kd2@example.com", Role.CLUB_MANAGER, club_id=club_id
        )
        sailors = await self._new_sailors(client, header, 4, "Er")
        path = f"/api/admin/teams/{team_id}/members"

        await client.put(
            path,
            headers=header,
            json={"members": [{"sailor_id": s, "role": "crew"} for s in sailors[:4]]},
        )
        afterwards = await client.put(
            path,
            headers=header,
            json={"members": [{"sailor_id": s, "role": "crew"} for s in sailors[:2]]},
        )
        assert {m["id"] for m in afterwards.json()["members"]} == set(sailors[:2])

    async def test_nobody_appears_twice_in_the_same_squad(self, client, caplog):
        team_id, club_id = await series_registration()
        header = await as_role(
            client, caplog, "kd3@example.com", Role.CLUB_MANAGER, club_id=club_id
        )
        sailors = await self._new_sailors(client, header, 1, "Dp")

        response = await client.put(
            f"/api/admin/teams/{team_id}/members",
            headers=header,
            json={
                "members": [
                    {"sailor_id": sailors[0], "role": "helm"},
                    {"sailor_id": sailors[0], "role": "crew"},
                ]
            },
        )
        assert response.status_code == 422
        assert response.json()["type"] == "/errors/squad-duplicate-sailor"

    async def test_not_for_two_clubs_in_the_same_series(self, client, caplog):
        """Otherwise the person would be competing against themselves."""
        admin = await as_role(client, caplog, "kd4a@example.com", Role.ADMIN)
        first_team, _ = await series_registration(most_recent=True)
        second_team, _ = await series_registration(most_recent=False)
        assert first_team != second_team

        sailors = await self._new_sailors(client, admin, 1, "Zw")
        entry = {"members": [{"sailor_id": sailors[0], "role": "crew"}]}

        assert (
            await client.put(
                f"/api/admin/teams/{first_team}/members", headers=admin, json=entry
            )
        ).status_code == 200

        second = await client.put(
            f"/api/admin/teams/{second_team}/members", headers=admin, json=entry
        )
        assert second.status_code == 409
        assert second.json()["type"] == "/errors/squad-sailor-in-another-club"

    async def test_two_clubs_in_two_different_series_is_allowed(self, client, caplog):
        admin = await as_role(client, caplog, "kd5@example.com", Role.ADMIN)
        juniors, _ = await series_registration("junioren-2026")
        scl, _ = await series_registration("scl-2026")

        sailors = await self._new_sailors(client, admin, 1, "Ms")
        entry = {"members": [{"sailor_id": sailors[0], "role": "crew"}]}

        for team_id in (juniors, scl):
            response = await client.put(
                f"/api/admin/teams/{team_id}/members", headers=admin, json=entry
            )
            assert response.status_code == 200, response.text

    async def test_a_club_that_is_not_theirs_registers_nobody(self, client, caplog):
        team_id, club_id = await series_registration()
        other = await as_role(
            client, caplog, "kd6@example.com", Role.CLUB_MANAGER, club_id=club_id + 1
        )
        response = await client.put(
            f"/api/admin/teams/{team_id}/members", headers=other, json={"members": []}
        )
        assert response.status_code == 403

    async def test_entering_an_act_carries_no_squad_of_its_own(self, client, caplog):
        """Registered for the series, selected for individual matchdays."""
        admin = await as_role(client, caplog, "kd7@example.com", Role.ADMIN)
        async with SessionLocal() as session:
            entry = (
                await session.execute(
                    select(Team).where(Team.event_id.is_not(None)).limit(1)
                )
            ).scalar_one()

        response = await client.put(
            f"/api/admin/teams/{entry.id}/members",
            headers=admin,
            json={"members": []},
        )
        assert response.status_code == 422
        assert response.json()["type"] == "/errors/squad-needs-series-registration"

    async def test_someone_in_a_lineup_cannot_drop_out_of_the_squad(self, client, caplog):
        """Otherwise a lineup would exist that has no registration anymore."""
        admin = await as_role(client, caplog, "kd8@example.com", Role.ADMIN)

        # A fixed seed club with full squad. Deliberately not "the last team of the series":
        # other stories add teams whose squad is empty.
        team_id, squad = await squad_of("byc", "dsbl-1-2026")
        assert len(squad) >= 4, "The seed should create a full squad"

        selected = await client.put(
            f"/api/admin/events/{await act_id('dsbl-1-2026-act-3')}/crew",
            headers=admin,
            json={
                "team_id": team_id,
                "members": [{"sailor_id": s, "role": "crew"} for s in squad[:4]],
            },
        )
        assert selected.status_code == 200, selected.text

        # Empty the squad — that would strip their registration from those selected.
        response = await client.put(
            f"/api/admin/teams/{team_id}/members",
            headers=admin,
            json={"members": []},
        )
        assert response.status_code == 409
        assert response.json()["type"] == "/errors/squad-member-is-lined-up"


class TestSquadRefusalsAreTyped:
    """V-1: every refusal carries a stable code, and the names that make it actionable.

    The squad screen has to say *which* rule was broken, in the reader's language. A 422
    whose body is an English sentence the router happened to build cannot do that: the
    frontend can only print it, and only in English. So each refusal is an RFC 9457 problem
    — `type` is the contract, and the extension members carry the names the sentence needs
    (`web/src/i18n/locales/*/errors.json`).
    """

    async def _new_sailors(self, client, headers, count: int, prefix: str) -> list[int]:
        ids = []
        for index in range(count):
            response = await client.post(
                "/api/admin/sailors",
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
        sailor = (await self._new_sailors(client, admin, 1, "Dup"))[0]

        response = await client.put(
            f"/api/admin/teams/{team_id}/members",
            headers=admin,
            json={
                "members": [
                    {"sailor_id": sailor, "role": "helm"},
                    {"sailor_id": sailor, "role": "crew"},
                ]
            },
        )
        assert response.status_code == 422, response.text
        problem = response.json()
        assert problem["type"] == "/errors/squad-duplicate-sailor"
        assert problem["sailor_ids"] == [sailor]

    async def test_already_sailing_for_another_club_names_both(self, client, caplog):
        admin = await as_role(client, caplog, "typed2@example.com", Role.ADMIN)
        first_team, _ = await series_registration(most_recent=True)
        second_team, _ = await series_registration(most_recent=False)
        sailor = (await self._new_sailors(client, admin, 1, "Other"))[0]
        entry = {"members": [{"sailor_id": sailor, "role": "crew"}]}

        assert (
            await client.put(
                f"/api/admin/teams/{first_team}/members", headers=admin, json=entry
            )
        ).status_code == 200

        response = await client.put(
            f"/api/admin/teams/{second_team}/members", headers=admin, json=entry
        )
        assert response.status_code == 409, response.text
        problem = response.json()
        assert problem["type"] == "/errors/squad-sailor-in-another-club"
        # The names, so the sentence can be built in either language rather than shipped
        # in one.
        assert problem["sailors"] == ["Other Typed0"]

    async def test_an_event_entry_says_it_carries_no_squad(self, client, caplog):
        admin = await as_role(client, caplog, "typed3@example.com", Role.ADMIN)
        async with SessionLocal() as session:
            entry = (
                await session.execute(
                    select(Team).where(Team.event_id.is_not(None)).limit(1)
                )
            ).scalar_one()

        response = await client.put(
            f"/api/admin/teams/{entry.id}/members", headers=admin, json={"members": []}
        )
        assert response.status_code == 422, response.text
        assert response.json()["type"] == "/errors/squad-needs-series-registration"

    async def test_dropping_someone_who_is_lined_up_names_the_matchday(
        self, client, caplog
    ):
        admin = await as_role(client, caplog, "typed4@example.com", Role.ADMIN)
        team_id, squad = await squad_of("byc", "dsbl-1-2026")
        assert len(squad) >= 4

        selected = await client.put(
            f"/api/admin/events/{await act_id('dsbl-1-2026-act-3')}/crew",
            headers=admin,
            json={
                "team_id": team_id,
                "members": [{"sailor_id": s, "role": "crew"} for s in squad[:4]],
            },
        )
        assert selected.status_code == 200, selected.text

        response = await client.put(
            f"/api/admin/teams/{team_id}/members",
            headers=admin,
            json={
                "members": [
                    {"sailor_id": sailor_id, "role": "crew"} for sailor_id in squad[4:]
                ]
            },
        )
        assert response.status_code == 409, response.text
        problem = response.json()
        assert problem["type"] == "/errors/squad-member-is-lined-up"
        # Which matchday, so the organizer knows where to go and change it first.
        assert problem["selections"]
        assert problem["selections"][0]["event"]
        assert problem["selections"][0]["sailor"]

    async def test_a_person_who_does_not_exist_is_a_typed_404(self, client, caplog):
        admin = await as_role(client, caplog, "typed5@example.com", Role.ADMIN)
        team_id, _ = await series_registration()

        response = await client.put(
            f"/api/admin/teams/{team_id}/members",
            headers=admin,
            json={"members": [{"sailor_id": 10_000_000, "role": "crew"}]},
        )
        assert response.status_code == 404, response.text
        problem = response.json()
        assert problem["type"] == "/errors/squad-unknown-sailor"
        assert problem["sailor_ids"] == [10_000_000]


class TestFindingTheRightPerson:
    """V-1: a candidate list has to identify people, not just name them.

    A person belongs to as many clubs as they sail for — one `TeamMembership` row per
    series registration — and in this data eighteen people share a surname. So a row
    reading "Nanisberg · 3 registrations" answers neither of the two questions a club
    manager actually has: is this the right one, and can I add them at all.
    """

    async def test_a_sailor_carries_the_clubs_and_series_they_sail_for(
        self, client, caplog
    ):
        admin = await as_role(client, caplog, "who1@example.com", Role.ADMIN)
        team_id, club_id = await series_registration()

        created = await client.post(
            "/api/admin/sailors",
            headers=admin,
            json={
                "first_name": "Identifiable",
                "last_name": "Person",
                "email": "who-identifiable@example.com",
            },
        )
        assert created.status_code in (200, 201), created.text
        sailor_id = created.json()["id"]

        assert (
            await client.put(
                f"/api/admin/teams/{team_id}/members",
                headers=admin,
                json={"members": [{"sailor_id": sailor_id, "role": "helm"}]},
            )
        ).status_code == 200

        found = await client.get(
            "/api/admin/sailors", headers=admin, params={"q": "Identifiable"}
        )
        assert found.status_code == 200, found.text
        person = next(p for p in found.json() if p["id"] == sailor_id)

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
            "/api/admin/sailors",
            headers=admin,
            json={
                "first_name": "Two",
                "last_name": "Clubs",
                "email": "who-twoclubs@example.com",
            },
        )
        sailor_id = created.json()["id"]

        for team_id in (juniors, scl):
            response = await client.put(
                f"/api/admin/teams/{team_id}/members",
                headers=admin,
                json={"members": [{"sailor_id": sailor_id, "role": "crew"}]},
            )
            assert response.status_code == 200, response.text

        person = next(
            p
            for p in (
                await client.get(
                    "/api/admin/sailors", headers=admin, params={"q": "Clubs"}
                )
            ).json()
            if p["id"] == sailor_id
        )
        assert {r["club"]["id"] for r in person["registrations"]} == {
            juniors_club,
            scl_club,
        }
        assert len({r["series"]["id"] for r in person["registrations"]}) == 2

    async def test_someone_in_no_squad_has_an_empty_list(self, client, caplog):
        admin = await as_role(client, caplog, "who3@example.com", Role.ADMIN)
        created = await client.post(
            "/api/admin/sailors",
            headers=admin,
            json={
                "first_name": "Unregistered",
                "last_name": "Person",
                "email": "who-none@example.com",
            },
        )
        person = next(
            p
            for p in (
                await client.get(
                    "/api/admin/sailors", headers=admin, params={"q": "Unregistered"}
                )
            ).json()
            if p["id"] == created.json()["id"]
        )
        assert person["registrations"] == []

    async def test_an_event_entry_is_not_a_registration(self, client, caplog):
        """Only series registrations count here. A `Team` with an `event_id` is an entry
        in one event and carries no squad, so it would name a club the person is not
        registered with (Story V-1)."""
        admin = await as_role(client, caplog, "who4@example.com", Role.ADMIN)
        team_id, _ = await series_registration()
        created = await client.post(
            "/api/admin/sailors",
            headers=admin,
            json={
                "first_name": "Seriesonly",
                "last_name": "Person",
                "email": "who-seriesonly@example.com",
            },
        )
        sailor_id = created.json()["id"]
        await client.put(
            f"/api/admin/teams/{team_id}/members",
            headers=admin,
            json={"members": [{"sailor_id": sailor_id, "role": "crew"}]},
        )

        person = next(
            p
            for p in (
                await client.get(
                    "/api/admin/sailors", headers=admin, params={"q": "Seriesonly"}
                )
            ).json()
            if p["id"] == sailor_id
        )
        async with SessionLocal() as session:
            registered_teams = {
                team.id
                for team in (
                    await session.execute(
                        select(Team).where(Team.id.in_([r["team_id"] for r in person["registrations"]]))
                    )
                ).scalars()
            }
            for team in (
                await session.execute(select(Team).where(Team.id.in_(registered_teams)))
            ).scalars():
                assert team.event_id is None
