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
from tests.stories.test_registrierung import auth_headers


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


class TestSeglerAnlegen:
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

    async def test_die_adresse_ist_die_verbindung_zum_konto(self, client, caplog):
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

    async def test_dieselbe_adresse_zweimal_wird_abgewiesen(self, client, caplog):
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

    async def test_die_vereinsleitung_darf_es_auch(self, client, caplog):
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

    async def test_ein_konto_ohne_rolle_legt_niemanden_an(self, client, caplog):
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

    async def test_segler_lassen_sich_ueber_den_namen_finden(self, client, caplog):
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

    async def test_ein_name_laesst_sich_berichtigen(self, client, caplog):
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


class TestKaderMelden:
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

    async def test_der_kader_haengt_an_der_serienmeldung(self, client, caplog):
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

    async def test_der_kader_ersetzt_den_bisherigen_vollstaendig(self, client, caplog):
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

    async def test_niemand_steht_zweimal_im_selben_kader(self, client, caplog):
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
        assert "twice" in response.json()["detail"]

    async def test_in_derselben_serie_nicht_fuer_zwei_vereine(self, client, caplog):
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
        assert "once per series" in second.json()["detail"]

    async def test_in_zwei_serien_fuer_zwei_vereine_ist_erlaubt(self, client, caplog):
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

    async def test_ein_fremder_verein_meldet_nicht(self, client, caplog):
        team_id, club_id = await series_registration()
        other = await as_role(
            client, caplog, "kd6@example.com", Role.CLUB_MANAGER, club_id=club_id + 1
        )
        response = await client.put(
            f"/api/admin/teams/{team_id}/members", headers=other, json={"members": []}
        )
        assert response.status_code == 403

    async def test_am_antritt_zu_einem_act_haengt_kein_kader(self, client, caplog):
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
        assert "series registration" in response.json()["detail"]

    async def test_wer_aufgestellt_ist_faellt_nicht_aus_dem_kader(self, client, caplog):
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
        assert "already selected" in response.json()["detail"]
