"""User stories B-7 and B-8: club page and sailor page.

Both show personal data — but only what appears on every results list anyway.
Email and birth year do not belong on a public page.
"""

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Club

# Deliberately a fixed club from the seed instead of "the first": other stories add clubs
# that would sort alphabetically before it. NRV is registered in three leagues.
CLUB = "nrv"


async def first_club() -> int:
    """The club ID — routes address via the primary key."""
    async with SessionLocal() as session:
        return (
            await session.execute(select(Club.id).where(Club.slug == CLUB))
        ).scalar_one()


class TestClubPage:
    """B-7: As a visitor, I want to see a club's page."""

    async def test_page_shows_name_emblem_and_description(self, client):
        club = (await client.get(f"/api/clubs/{await first_club()}")).json()

        assert club["name"]
        assert club["description"], "Description is missing"
        # Emblem is optional, but the field must be present.
        assert "logo_url" in club

    async def test_page_shows_teams_of_the_year(self, client):
        club = (await client.get(f"/api/clubs/{await first_club()}")).json()

        assert club["teams"], "Club should have at least one team"
        for team in club["teams"]:
            assert team["series"]["year"] == 2026
            # Series name includes the year.
            assert "2026" in team["series"]["name"]

    async def test_club_in_multiple_series_shows_all(self, client):
        """NRV is also registered in Juniors and SCL."""
        club = (await client.get(f"/api/clubs/{await first_club()}")).json()
        series = {m["series"]["slug"] for m in club["teams"]}
        assert len(series) >= 2, f"Only one series found: {series}"

    async def test_page_shows_squad(self, client):
        club = (await client.get(f"/api/clubs/{await first_club()}")).json()
        first = club["teams"][0]

        assert len(first["members"]) == 10, "Ten members per season (Story V-1)"
        # Helm first — the order a crew is announced.
        assert first["members"][0]["role"] == "helm"

    async def test_squad_reveals_no_contact_data(self, client):
        """Names are on every results list anyway — email addresses are not."""
        club = (await client.get(f"/api/clubs/{await first_club()}")).json()
        member = club["teams"][0]["members"][0]

        assert set(member) == {"id", "first_name", "last_name", "role"}

    async def test_different_year_can_be_retrieved(self, client):
        response = await client.get(
            f"/api/clubs/{await first_club()}", params={"year": 1999}
        )
        assert response.status_code == 200
        # 1999 the series didn't exist — the page is still retrievable.
        assert response.json()["teams"] == []

    async def test_unknown_club_reports_clearly(self, client):
        response = await client.get("/api/clubs/999999")
        assert response.status_code == 404
        assert "999999" in response.json()["detail"]

    async def test_invalid_id_is_rejected(self, client):
        """Routes address via primary key — a slug is not an ID there."""
        assert (await client.get("/api/clubs/nrv")).status_code == 422


class TestSailorPage:
    """B-8: As a visitor, I want to see who someone is registered with and where they sail."""

    async def _first_sailor(self, client) -> dict:
        club = (await client.get(f"/api/clubs/{await first_club()}")).json()
        return club["teams"][0]["members"][0]

    async def test_page_names_club_and_series(self, client):
        member = await self._first_sailor(client)
        sailor = (await client.get(f"/api/sailors/{member['id']}")).json()

        assert sailor["first_name"] == member["first_name"]
        assert sailor["teams"], "Person should be registered for at least one series"
        entry = sailor["teams"][0]
        assert entry["club"]["name"]
        assert "2026" in entry["series"]["name"]

    async def test_page_shows_matchdays_they_are_lined_up_for(self, client):
        member = await self._first_sailor(client)
        sailor = (await client.get(f"/api/sailors/{member['id']}")).json()

        # The helm sails all three matchdays.
        assert len(sailor["events"]) == 3
        for entry in sailor["events"]:
            assert entry["event"]["title"]
            assert entry["role"] == "helm"

    async def test_substitute_only_has_no_lineup(self, client):
        """Ten on the squad, four in the lineup — that's a difference."""
        club = (await client.get(f"/api/clubs/{await first_club()}")).json()
        substitutes = [m for m in club["teams"][0]["members"] if m["role"] == "substitute"]
        assert substitutes, "Seed should contain substitutes"

        sailor = (await client.get(f"/api/sailors/{substitutes[0]['id']}")).json()
        assert sailor["events"] == []
        assert sailor["teams"], "Registered nonetheless"

    async def test_page_reveals_no_contact_data(self, client):
        member = await self._first_sailor(client)
        sailor = (await client.get(f"/api/sailors/{member['id']}")).json()

        assert "email" not in sailor
        assert "birth_date" not in sailor

    async def test_page_is_accessible_without_login(self, client):
        member = await self._first_sailor(client)
        assert (await client.get(f"/api/sailors/{member['id']}")).status_code == 200

    async def test_unknown_person_reports_clearly(self, client):
        response = await client.get("/api/sailors/999999")
        assert response.status_code == 404
