"""User Stories A-3, A-4, and B-6: Series assignment, series naming, guest access.

At the core: a **series** is a set of events scored together — "DSBL 2026". The assignment
of a club to a series is modeled as a `Team` row. Because the year is in the series, an
assignment to "DSBL 2026" does not apply to "DSBL 2027".
"""

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Series
from app.models.auth import Role
from tests.stories.test_login_and_roles import login_as, make_user


async def as_role(client, caplog, email: str, *roles: str) -> dict[str, str]:
    await make_user(email, *roles)
    token = await login_as(client, email, caplog)
    return {"Authorization": f"Bearer {token}"}


async def new_club(client, headers, name: str, abbrev: str | None = None) -> dict:
    response = await client.post(
        "/api/admin/clubs",
        headers=headers,
        json={"name": name, **({"short_name": abbrev} if abbrev else {})},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def create_series(slug: str, name: str, year: int) -> int:
    """Create a series if missing — for year transition tests."""
    async with SessionLocal() as session:
        existing = (
            await session.execute(select(Series).where(Series.slug == slug))
        ).scalar_one_or_none()
        if existing is not None:
            return existing.id
        # Published: these stand for the next year's real competition, and the public
        # views under test show published series only (Story VA-8).
        series = Series(
            slug=slug, name=name, short_name=name, year=year, scoring={}, published=True
        )
        session.add(series)
        await session.commit()
        return series.id


class TestClubCreationAndAssignment:
    """A-3: A club appears publicly only when assigned to a series."""

    async def test_name_alone_suffices_for_creation(self, client, caplog):
        headers = await as_role(client, caplog, "lz1@example.com", Role.EDITOR)
        club = await new_club(client, headers, "Segelverein Namenlos")

        assert club["slug"] == "segelverein-namenlos"
        # Without its own abbreviation, the name is used initially — better than guessing.
        assert club["short_name"] == "Segelverein Namenlos"
        assert club["city"] is None

    async def test_unassigned_club_does_not_appear_on_homepage(self, client, caplog):
        headers = await as_role(client, caplog, "lz2@example.com", Role.EDITOR)
        club = await new_club(client, headers, "Unsichtbarer Segelclub", "USC")

        public = (await client.get("/api/clubs")).json()
        assert club["slug"] not in {v["slug"] for v in public}

    async def test_admin_also_sees_unassigned_clubs(self, client, caplog):
        headers = await as_role(client, caplog, "lz3@example.com", Role.EDITOR)
        club = await new_club(client, headers, "Noch Ungeordnet", "NUG")

        all_clubs = (await client.get("/api/admin/clubs", headers=headers)).json()
        entry = next(v for v in all_clubs if v["slug"] == club["slug"])
        assert entry["assignments"] == []
        assert entry["visible"] is False

    async def test_after_assignment_club_appears(self, client, caplog, ids):
        headers = await as_role(client, caplog, "lz4@example.com", Role.EDITOR)
        club = await new_club(client, headers, "Sichtbarer Segelclub", "SSC")

        response = await client.put(
            f"/api/admin/clubs/{club['id']}/series",
            headers=headers,
            json={"series": [ids.series("dsbl-2-2026")]},
        )
        assert response.status_code == 200, response.text
        assert response.json()["visible"] is True

        public = (await client.get("/api/clubs")).json()
        assert club["slug"] in {v["slug"] for v in public}

    async def test_club_can_enter_multiple_series(self, client, caplog, ids):
        headers = await as_role(client, caplog, "lz5@example.com", Role.EDITOR)
        club = await new_club(client, headers, "Vielseitiger Segelclub", "VSC")

        desired = ["dsbl-2-2026", "junioren-2026", "scl-2026"]
        response = await client.put(
            f"/api/admin/clubs/{club['id']}/series",
            headers=headers,
            json={"series": [ids.series(slug) for slug in desired]},
        )
        series_slugs = {z["series"]["slug"] for z in response.json()["assignments"]}
        assert series_slugs == set(desired)

        # It appears in each of these series, but not in the first.
        for slug in ("junioren-2026", "scl-2026"):
            filtered = (
                await client.get("/api/clubs", params={"series": ids.series(slug)})
            ).json()
            assert club["slug"] in {v["slug"] for v in filtered}

        first = (
            await client.get("/api/clubs", params={"series": ids.series("dsbl-1-2026")})
        ).json()
        assert club["slug"] not in {v["slug"] for v in first}

    async def test_assignment_can_be_revoked(self, client, caplog, ids):
        headers = await as_role(client, caplog, "lz6@example.com", Role.EDITOR)
        club = await new_club(client, headers, "Wechselhafter Segelclub", "WSC")
        path = f"/api/admin/clubs/{club['id']}/series"

        await client.put(path, headers=headers, json={"series": [ids.series("junioren-2026")]})
        empty = await client.put(path, headers=headers, json={"series": []})

        assert empty.json()["assignments"] == []
        assert empty.json()["visible"] is False

    async def test_unknown_series_is_rejected(self, client, caplog):
        headers = await as_role(client, caplog, "lz7@example.com", Role.EDITOR)
        club = await new_club(client, headers, "Fehlerhafter Segelclub", "FSC2")

        response = await client.put(
            f"/api/admin/clubs/{club['id']}/series",
            headers=headers,
            json={"series": [999999]},
        )
        assert response.status_code == 404

    async def test_race_officers_cannot_assign(self, client, caplog, ids):
        headers = await as_role(client, caplog, "lz8@example.com", Role.EDITOR)
        club = await new_club(client, headers, "Geschuetzter Segelclub", "GSC")

        race_officer = await as_role(client, caplog, "lz9@example.com", Role.RACE_OFFICER)
        response = await client.put(
            f"/api/admin/clubs/{club['id']}/series",
            headers=race_officer,
            json={"series": [ids.series("junioren-2026")]},
        )
        assert response.status_code == 403


class TestYearTransition:
    """A-3: "DSBL 2026" is not "DSBL 2027" — a new assignment is needed."""

    async def test_2026_assignment_does_not_apply_to_2027(self, client, caplog, ids):
        next_series = await create_series("dsbl-1-2027", "1. Segel-Bundesliga 2027", 2027)
        headers = await as_role(client, caplog, "sw1@example.com", Role.ADMIN)
        club = await new_club(client, headers, "Jahreswechsel Segelclub", "JWC")

        await client.put(
            f"/api/admin/clubs/{club['id']}/series",
            headers=headers,
            json={"series": [ids.series("dsbl-2-2026")]},
        )

        in_2026 = (await client.get("/api/clubs", params={"year": 2026})).json()
        in_2027 = (await client.get("/api/clubs", params={"series": next_series})).json()

        assert club["slug"] in {v["slug"] for v in in_2026}
        assert club["slug"] not in {v["slug"] for v in in_2027}

    async def test_new_assignment_includes_club_in_2027(self, client, caplog, ids):
        next_series = await create_series("dsbl-1-2027", "1. Segel-Bundesliga 2027", 2027)
        headers = await as_role(client, caplog, "sw2@example.com", Role.ADMIN)
        club = await new_club(client, headers, "Treuer Segelclub", "TSC")

        await client.put(
            f"/api/admin/clubs/{club['id']}/series",
            headers=headers,
            json={"series": [ids.series("dsbl-2-2026"), next_series]},
        )

        for year, filter_ in ((2026, {"year": 2026}), (2027, {"series": next_series})):
            clubs_list = (await client.get("/api/clubs", params=filter_)).json()
            assert club["slug"] in {v["slug"] for v in clubs_list}, f"missing in {year}"

    async def test_assignments_for_both_years_coexist(self, client, caplog, ids):
        next_series = await create_series("dsbl-1-2027", "1. Segel-Bundesliga 2027", 2027)
        headers = await as_role(client, caplog, "sw3@example.com", Role.ADMIN)
        club = await new_club(client, headers, "Aufsteiger Segelclub", "ASC")

        response = await client.put(
            f"/api/admin/clubs/{club['id']}/series",
            headers=headers,
            json={"series": [ids.series("dsbl-2-2026"), next_series]},
        )

        # A promotion: 2026 second league, 2027 first. Both remain visible.
        series_slugs = {z["series"]["slug"] for z in response.json()["assignments"]}
        assert {"dsbl-2-2026", "dsbl-1-2027"} <= series_slugs

    async def test_future_year_does_not_move_public_page(self, client, caplog):
        """"DSBL 2099" is created for assignment.

        It must not move the public page to a year where no one has registered yet —
        otherwise the website would be empty after creation.
        """
        await create_series("dsbl-2099", "Segel-Bundesliga 2099", 2099)

        clubs_list = (await client.get("/api/clubs")).json()
        assert clubs_list, "Current year must not jump into the future"

        series_list = (await client.get("/api/series")).json()
        assert all(s["year"] != 2099 for s in series_list)


class TestSeriesNaming:
    """A-4: Series name includes the year — there is only one name."""

    async def test_series_list_includes_year(self, client):
        series_list = (await client.get("/api/series", params={"year": 2026})).json()
        first = next(s for s in series_list if s["slug"] == "dsbl-1-2026")

        assert first["name"] == "1. Segel-Bundesliga 2026"
        assert first["short_name"] == "1. Liga 2026"
        assert first["year"] == 2026

    async def test_multiple_series_coexist(self, client):
        series_slugs = {s["slug"] for s in (await client.get("/api/series")).json()}
        assert {"dsbl-1-2026", "dsbl-2-2026", "junioren-2026", "scl-2026"} <= series_slugs

    async def test_series_table_includes_year(self, client, ids):
        table = (
            await client.get(f"/api/series/{ids.series('dsbl-1-2026')}/table")
        ).json()
        assert table["series"]["name"] == "1. Segel-Bundesliga 2026"

    async def test_event_shows_its_series(self, client, ids):
        detail = (
            await client.get(f"/api/events/{ids.event('dsbl-1-2026-act-1')}")
        ).json()
        assert detail["event"]["series"]["name"] == "1. Segel-Bundesliga 2026"

    async def test_assignment_shows_series_name(self, client, caplog, ids):
        headers = await as_role(client, caplog, "ln1@example.com", Role.EDITOR)
        club = await new_club(client, headers, "Benennungs Segelclub", "BSC2")
        response = await client.put(
            f"/api/admin/clubs/{club['id']}/series",
            headers=headers,
            json={"series": [ids.series("junioren-2026")]},
        )
        assignment = response.json()["assignments"][0]
        assert assignment["series"]["name"] == "Junioren-Segelliga 2026"


class TestGuestAccess:
    """B-6: The public page also serves visitors without an account."""

    async def test_public_pages_do_not_require_login(self, client, ids):
        event = ids.event("dsbl-1-2026-act-1")
        paths = [
            "/api/clubs",
            "/api/series",
            "/api/events",
            f"/api/events/{event}",
            f"/api/events/{event}/pairing",
            f"/api/series/{ids.series('dsbl-1-2026')}/table",
        ]
        for path in paths:
            assert (await client.get(path)).status_code == 200, path

    async def test_expired_token_does_not_break_page(self, client):
        """Someone returning with an old session is a guest — not locked out."""
        response = await client.get(
            "/api/clubs", headers={"Authorization": "Bearer completely-invalid"}
        )
        assert response.status_code == 200

    async def test_protected_areas_remain_closed(self, client):
        for path in ("/api/admin/clubs", "/api/auth/me"):
            assert (await client.get(path)).status_code == 401, path
