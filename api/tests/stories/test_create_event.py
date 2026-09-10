"""User Stories VA-6 and VA-7: create an event and immediately draw pairings.

The organizer needs **name and date**, plus the dimensions — how many teams, how many boats
with what color and name, how many flights. The pairing list follows from the dimensions,
and for typical dimensions it's ready in the catalog: no wait, no optimization, just a
starting value to shuffle.
"""

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Club
from app.models.auth import Role
from tests.stories.test_login_and_roles import login_as, make_user
from tests.stories.test_registration import auth_headers, register

BOATS = [
    {"color": "BLACK", "name": "Black Seven", "sail_number": "GER 701"},
    {"color": "GREEN", "name": "Green Henry", "sail_number": "GER 702"},
    {"color": "DARKBLUE", "name": "Blue Peter", "sail_number": "GER 703"},
    {"color": "RED", "name": "Red Baron", "sail_number": "GER 704"},
    {"color": "GRAY", "name": "Gray Mouse", "sail_number": "GER 705"},
    {"color": "ORANGE", "name": "Orange Peel", "sail_number": "GER 706"},
]


async def admin(client, caplog, email: str) -> dict[str, str]:
    await make_user(email, Role.ADMIN)
    return auth_headers(await login_as(client, email, caplog))


async def league_clubs(client) -> list[int]:
    """The 18 clubs of the running series — exactly the dimensions of the catalog entry."""
    return [club["id"] for club in (await client.get("/api/clubs")).json()][:18]


async def club_id(slug: str) -> int:
    async with SessionLocal() as session:
        return (
            await session.execute(select(Club.id).where(Club.slug == slug))
        ).scalar_one()


async def event_with_participants(client, headers, title: str, date: str) -> int:
    """Creates an event in league dimensions and registers 18 clubs as participants.

    Published right away, because these tests read the result back off the **public**
    pairing list, and that shows published events only (Story VA-8).
    """
    created = await client.post(
        "/api/admin/events",
        headers=headers,
        json={
            "title": title,
            "starts_on": date,
            "team_count": 18,
            "flight_count": 16,
            "boats": BOATS,
            "published": True,
        },
    )
    assert created.status_code == 201, created.text
    event_id = created.json()["id"]

    set_result = await client.put(
        f"/api/admin/events/{event_id}/clubs",
        headers=headers,
        json={"clubs": await league_clubs(client)},
    )
    assert set_result.status_code == 200, set_result.text
    return event_id


class TestCreateEvent:
    """As an organizer, I want to create an event with its dimensions."""

    async def test_name_and_date_sufficient(self, client, caplog):
        headers = await admin(client, caplog, "va1@example.com")
        response = await client.post(
            "/api/admin/events",
            headers=headers,
            json={"title": "Simple Cup", "starts_on": "2026-10-03"},
        )
        assert response.status_code == 201, response.text
        assert response.json()["title"] == "Simple Cup"

    async def test_boats_get_color_and_name(self, client, caplog):
        """On the water, people refer to color and name."""
        headers = await admin(client, caplog, "va2@example.com")
        event_id = await event_with_participants(
            client, headers, "Boat Cup", "2026-10-10"
        )

        pairing = (await client.get(f"/api/events/{event_id}/pairing")).json()
        assert [boat["color"] for boat in pairing["boats"]] == [b["color"] for b in BOATS]
        assert [boat["name"] for boat in pairing["boats"]] == [b["name"] for b in BOATS]

    async def test_without_boat_specs_league_colors_apply(self, client, caplog):
        headers = await admin(client, caplog, "va3@example.com")
        created = (
            await client.post(
                "/api/admin/events",
                headers=headers,
                json={
                    "title": "Colorless Cup",
                    "starts_on": "2026-10-17",
                    "boat_count": 6,
                    "published": True,
                },
            )
        ).json()

        pairing = (await client.get(f"/api/events/{created['id']}/pairing")).json()
        assert [boat["color"] for boat in pairing["boats"]] == [
            "BLACK", "GREEN", "DARKBLUE", "RED", "GRAY", "ORANGE"
        ]

    async def test_boat_count_derives_from_specified_boats(self, client, caplog):
        headers = await admin(client, caplog, "va4@example.com")
        created = (
            await client.post(
                "/api/admin/events",
                headers=headers,
                json={
                    "title": "Four-Boat Cup",
                    "starts_on": "2026-10-24",
                    "boats": BOATS[:4],
                },
            )
        ).json()
        assert created["boat_count"] == 4

    async def test_club_leadership_can_host_for_own_club(
        self, client, caplog
    ):
        """The host should be able to record the date without waiting for someone."""
        club = await club_id("kyc")
        await make_user("va5@example.com", Role.CLUB_MANAGER, club_id=club)
        headers = auth_headers(await login_as(client, "va5@example.com", caplog))

        response = await client.post(
            "/api/admin/events",
            headers=headers,
            json={
                "title": "Kiel Club Cup",
                "starts_on": "2026-11-07",
                "host_club_id": club,
            },
        )
        assert response.status_code == 201, response.text

    async def test_cannot_host_for_foreign_club(self, client, caplog):
        await make_user("va6@example.com", Role.CLUB_MANAGER, club_id=await club_id("kyc"))
        headers = auth_headers(await login_as(client, "va6@example.com", caplog))

        response = await client.post(
            "/api/admin/events",
            headers=headers,
            json={
                "title": "Foreign Cup",
                "starts_on": "2026-11-14",
                "host_club_id": await club_id("nrv"),
            },
        )
        assert response.status_code == 403
        assert "own club" in response.json()["detail"]

    async def test_account_without_role_cannot_create_event(self, client, caplog):
        headers = auth_headers(await register(client, caplog, "va7@example.com", "Otto Nobody"))
        response = await client.post(
            "/api/admin/events",
            headers=headers,
            json={"title": "Secret Cup", "starts_on": "2026-11-21"},
        )
        assert response.status_code == 403


class TestPairingFromCatalog:
    """As an organizer, I want pairings immediately, not after ten minutes."""

    async def test_catalog_lists_ready_dimensions(self, client, caplog):
        headers = await admin(client, caplog, "pk1@example.com")
        entries = (
            await client.get("/api/admin/pairing/catalog", headers=headers)
        ).json()
        assert any(
            (e["teams"], e["boats"], e["flights"]) == (18, 6, 16) for e in entries
        )

    async def test_catalog_produces_complete_pairing_list(
        self, client, caplog
    ):
        headers = await admin(client, caplog, "pk2@example.com")
        event_id = await event_with_participants(
            client, headers, "Catalog Cup", "2026-11-28"
        )

        response = await client.post(
            f"/api/admin/events/{event_id}/pairing/from-catalog",
            headers=headers,
            json={"seed": 42},
        )
        assert response.status_code == 200, response.text
        assert response.json()["races"] == 48

        pairing = (await client.get(f"/api/events/{event_id}/pairing")).json()
        assert len(pairing["races"]) == 48
        for race in pairing["races"]:
            assert sorted(int(n) for n in race["teams_by_boat"]) == [1, 2, 3, 4, 5, 6]

    async def test_quality_of_stored_list_is_preserved(self, client, caplog):
        """Only who sits where is shuffled — not the structure."""
        headers = await admin(client, caplog, "pk3@example.com")
        event_id = await event_with_participants(
            client, headers, "Quality Cup", "2026-12-05"
        )

        report = (
            await client.post(
                f"/api/admin/events/{event_id}/pairing/from-catalog",
                headers=headers,
                json={"seed": 7},
            )
        ).json()["quality"]
        assert report["boat_changes"] == 0
        assert report["repeated_groups"] == 0

    async def test_same_seed_produces_same_draw(self, client, caplog):
        """In case of dispute, a draw must be reproducible."""
        headers = await admin(client, caplog, "pk4@example.com")
        event_id = await event_with_participants(
            client, headers, "Repeat Cup", "2026-12-12"
        )

        async def draw(seed: int) -> list:
            await client.post(
                f"/api/admin/events/{event_id}/pairing/from-catalog",
                headers=headers,
                json={"seed": seed},
            )
            pairing = (await client.get(f"/api/events/{event_id}/pairing")).json()
            return [
                {boat: team["id"] for boat, team in race["teams_by_boat"].items()}
                for race in pairing["races"]
            ]

        first = await draw(99)
        assert await draw(99) == first
        assert await draw(100) != first

    async def test_event_boats_survive_redraw(
        self, client, caplog
    ):
        """The same boats are at the dock, regardless of how often redrawing happens."""
        headers = await admin(client, caplog, "pk5@example.com")
        event_id = await event_with_participants(
            client, headers, "Dock Cup", "2026-12-19"
        )

        for seed in (1, 2):
            await client.post(
                f"/api/admin/events/{event_id}/pairing/from-catalog",
                headers=headers,
                json={"seed": seed},
            )

        pairing = (await client.get(f"/api/events/{event_id}/pairing")).json()
        assert [boat["name"] for boat in pairing["boats"]] == [b["name"] for b in BOATS]

    async def test_dimension_without_entry_reports_clearly(self, client, caplog):
        headers = await admin(client, caplog, "pk6@example.com")
        created = (
            await client.post(
                "/api/admin/events",
                headers=headers,
                json={
                    "title": "Odd Cup",
                    "starts_on": "2026-12-26",
                    "team_count": 18,
                    "boat_count": 5,
                    "flight_count": 11,
                },
            )
        ).json()
        await client.put(
            f"/api/admin/events/{created['id']}/clubs",
            headers=headers,
            json={"clubs": await league_clubs(client)},
        )

        response = await client.post(
            f"/api/admin/events/{created['id']}/pairing/from-catalog",
            headers=headers,
            json={"seed": 1},
        )
        assert response.status_code == 404
        body = response.json()
        assert body["type"] == "/errors/pairing-catalog-missing"
        assert (body["teams"], body["boats"], body["flights"]) == (18, 5, 11)
        # The sizes that *are* stored travel with the error, so "then what can I pick?" is
        # answered without a second request.
        assert "18/6/16" in body["available"]

    async def test_a_draw_before_the_clubs_are_added_says_so(self, client, caplog):
        """Clubs are added after an event is created, so a draw attempted too early must name
        that as the reason. It used to fail as a bare 404 "not found": the catalog was asked
        for a nought-team entry, and the message mentioned neither the teams nor the fix."""
        headers = await admin(client, caplog, "pk7@example.com")
        created = (
            await client.post(
                "/api/admin/events",
                headers=headers,
                json={
                    "title": "Too Early Cup",
                    "starts_on": "2027-01-09",
                    "team_count": 18,
                    "boat_count": 6,
                    "flight_count": 16,
                },
            )
        ).json()

        response = await client.post(
            f"/api/admin/events/{created['id']}/pairing/from-catalog",
            headers=headers,
            json={"seed": 1},
        )
        assert response.status_code == 409
        body = response.json()
        assert body["type"] == "/errors/pairing-team-count-mismatch"
        assert body["registered"] == 0
        assert body["configured"] == 18

        # And once the clubs are there, the same call succeeds unchanged.
        await client.put(
            f"/api/admin/events/{created['id']}/clubs",
            headers=headers,
            json={"clubs": await league_clubs(client)},
        )
        drawn = await client.post(
            f"/api/admin/events/{created['id']}/pairing/from-catalog",
            headers=headers,
            json={"seed": 1},
        )
        assert drawn.status_code == 200, drawn.text
        assert drawn.json()["races"] == 48
