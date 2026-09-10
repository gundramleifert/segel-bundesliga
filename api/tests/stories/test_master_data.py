"""Admin user stories: create clubs and events.

Clubs are master data — they appear later in the choice of host for an event.
"""

from app.models.auth import Role
from tests.stories.test_login_and_roles import login_as, make_user


async def as_role(client, caplog, email: str, *roles: str) -> dict[str, str]:
    await make_user(email, *roles)
    token = await login_as(client, email, caplog)
    return {"Authorization": f"Bearer {token}"}


class TestClubCreation:
    """As admin or editor I want to create clubs."""

    async def test_a_club_can_be_created_with_required_info(self, client, caplog):
        headers = await as_role(client, caplog, "sd1@example.com", Role.ADMIN)
        response = await client.post(
            "/api/admin/clubs",
            headers=headers,
            json={
                "name": "Segelclub Musterhafen",
                "short_name": "SCM",
                "city": "Musterhafen",
                "logo_url": "/marke/scm.png",
            },
        )
        assert response.status_code == 201, response.text
        club = response.json()
        assert club["slug"] == "scm"
        assert club["logo_url"] == "/marke/scm.png"

        # But not public yet: series assignment decides that (Story A-3).
        clubs = (await client.get("/api/clubs")).json()
        assert not any(v["slug"] == "scm" for v in clubs)

    async def test_editors_can_also_create_clubs(self, client, caplog):
        headers = await as_role(client, caplog, "sd2@example.com", Role.EDITOR)
        response = await client.post(
            "/api/admin/clubs",
            headers=headers,
            json={"name": "Yachtclub Beispielsee", "short_name": "YCB", "city": "Beispiel"},
        )
        assert response.status_code == 201

    async def test_race_officers_cannot_create_clubs(self, client, caplog):
        headers = await as_role(client, caplog, "sd3@example.com", Role.RACE_OFFICER)
        response = await client.post(
            "/api/admin/clubs",
            headers=headers,
            json={"name": "Forbidden Club", "short_name": "VBC", "city": "Nowhere"},
        )
        assert response.status_code == 403

    async def test_unauthenticated_access_fails(self, client):
        response = await client.post(
            "/api/admin/clubs",
            json={"name": "Anonymous Club", "short_name": "ANC", "city": "Nowhere"},
        )
        assert response.status_code == 401

    async def test_abbreviation_with_umlaut_keeps_own_url(self, client, caplog):
        """'BYCÜ' and 'BYC' are different clubs — their URLs must not collide."""
        headers = await as_role(client, caplog, "sd4@example.com", Role.ADMIN)
        response = await client.post(
            "/api/admin/clubs",
            headers=headers,
            json={"name": "Musterclub Überlingen", "short_name": "MCÜ", "city": "Überlingen"},
        )
        assert response.status_code == 201
        assert response.json()["slug"] == "mcue"

    async def test_taken_url_is_detected(self, client, caplog):
        headers = await as_role(client, caplog, "sd5@example.com", Role.ADMIN)
        data = {"name": "Duplicate Club", "short_name": "DPC", "city": "Double City"}
        first = await client.post("/api/admin/clubs", headers=headers, json=data)
        assert first.status_code == 201

        second = await client.post("/api/admin/clubs", headers=headers, json=data)
        assert second.status_code == 409
        assert "taken" in second.json()["detail"]


class TestCreatingAMatchday:
    """As an organizer I want to create a matchday with a name, a date and a host club."""

    async def _host_club(self, client) -> dict:
        return (await client.get("/api/clubs")).json()[0]

    async def test_name_date_and_host_club_are_enough(self, client, caplog, ids):
        headers = await as_role(client, caplog, "ev1@example.com", Role.ADMIN)
        club = await self._host_club(client)

        response = await client.post(
            "/api/admin/events",
            headers=headers,
            json={
                "title": "Autumn Matchday Sampleport",
                "starts_on": "2026-09-18",
                "series": ids.series("dsbl-1-2026"),
                "host_club_id": club["id"],
            },
        )
        assert response.status_code == 201, response.text
        event = response.json()

        assert event["title"] == "Autumn Matchday Sampleport"
        assert event["host_club"]["id"] == club["id"]
        # With no end date the matchday counts as a single day.
        assert event["ends_on"] == event["starts_on"] == "2026-09-18"
        # The venue is often not settled yet when the event is created.
        assert event["venue"] is None
        assert event["status"] == "planned"

    async def test_the_act_number_counts_on(self, client, caplog, ids):
        """Two creations in a row: the second carries the next number.

        This used to read the highest number off `/api/events`, which no longer works: the
        public list shows published events only (Story VA-8), while a draft very much does
        count when the numbering continues. Comparing two consecutive creations checks the
        same thing and depends on no visibility at all.
        """
        headers = await as_role(client, caplog, "ev2@example.com", Role.ADMIN)

        async def create(title: str, tag: str) -> int:
            response = await client.post(
                "/api/admin/events",
                headers=headers,
                json={
                    "title": title,
                    "starts_on": tag,
                    "series": ids.series("dsbl-1-2026"),
                },
            )
            assert response.status_code == 201, response.text
            return response.json()["matchday"]

        first = await create("Next Matchday", "2026-10-02")
        assert await create("The Matchday After", "2026-10-09") == first + 1

    async def test_without_its_own_logo_the_host_clubs_crest_applies(self, client, caplog, ids):
        headers = await as_role(client, caplog, "ev3@example.com", Role.ADMIN)
        club = await self._host_club(client)
        await client.patch(
            f"/api/admin/clubs/{club['id']}",
            headers=headers,
            json={"logo_url": "/marke/host_club.png"},
        )

        response = await client.post(
            "/api/admin/events",
            headers=headers,
            json={
                "title": "Spieltag mit Vereinswappen",
                "starts_on": "2026-10-16",
                "series": ids.series("dsbl-1-2026"),
                "host_club_id": club["id"],
            },
        )
        assert response.json()["logo_url"] == "/marke/host_club.png"

    async def test_ein_eigenes_logo_hat_vorrang(self, client, caplog, ids):
        headers = await as_role(client, caplog, "ev4@example.com", Role.ADMIN)
        club = await self._host_club(client)

        response = await client.post(
            "/api/admin/events",
            headers=headers,
            json={
                "title": "Spieltag mit eigenem Logo",
                "starts_on": "2026-10-30",
                "series": ids.series("dsbl-1-2026"),
                "host_club_id": club["id"],
                "logo_url": "/marke/spieltag.png",
            },
        )
        assert response.json()["logo_url"] == "/marke/spieltag.png"

    async def test_editorial_and_the_race_committee_may_too(self, client, caplog, ids):
        for nummer, rolle in enumerate([Role.EDITOR, Role.RACE_OFFICER], start=5):
            headers = await as_role(client, caplog, f"ev{nummer}@example.com", rolle)
            response = await client.post(
                "/api/admin/events",
                headers=headers,
                json={
                    "title": f"Spieltag von {rolle}",
                    "starts_on": "2026-11-13",
                    "series": ids.series("dsbl-1-2026"),
                },
            )
            assert response.status_code == 201, f"{rolle}: {response.text}"

    async def test_a_club_account_cannot_create_matchdays(self, client, caplog, ids):
        headers = await as_role(client, caplog, "ev7@example.com", Role.CLUB_MANAGER)
        response = await client.post(
            "/api/admin/events",
            headers=headers,
            json={
                "title": "Unerlaubt",
                "starts_on": "2026-11-20",
                "series": ids.series("dsbl-1-2026"),
            },
        )
        assert response.status_code == 403

    async def test_an_unknown_host_club_is_refused(self, client, caplog, ids):
        headers = await as_role(client, caplog, "ev8@example.com", Role.ADMIN)
        response = await client.post(
            "/api/admin/events",
            headers=headers,
            json={
                "title": "Spieltag ohne Verein",
                "starts_on": "2026-11-27",
                "series": ids.series("dsbl-1-2026"),
                "host_club_id": 999999,
            },
        )
        assert response.status_code == 404
        assert "not known" in response.json()["detail"]

    async def test_an_end_before_the_start_is_refused(self, client, caplog, ids):
        headers = await as_role(client, caplog, "ev9@example.com", Role.ADMIN)
        response = await client.post(
            "/api/admin/events",
            headers=headers,
            json={
                "title": "Backwards",
                "starts_on": "2026-12-04",
                "ends_on": "2026-12-01",
                "series": ids.series("dsbl-1-2026"),
            },
        )
        assert response.status_code == 422

    async def test_a_saved_matchday_can_be_corrected_afterwards(self, client, caplog):
        headers = await as_role(client, caplog, "ev10@example.com", Role.ADMIN)
        created = (
            await client.post(
                "/api/admin/events",
                headers=headers,
                json={"title": "Provisional", "starts_on": "2026-12-11", "league": "dsbl-1-2026",
                      "season": 2026},
            )
        ).json()

        changed = await client.patch(
            f"/api/admin/events/{created['id']}",
            headers=headers,
            json={"title": "Final Name", "status": "live"},
        )
        assert changed.status_code == 200
        assert changed.json()["title"] == "Final Name"
        assert changed.json()["status"] == "live"


class TestStandaloneEvent:
    """A-2: an event may belong to a series — but need not.

    A cup, a training weekend or an invitational regatta stands on its own: it appears in
    the calendar and counts in no series table.
    """

    async def test_an_event_without_a_series_can_be_created(self, client, caplog):
        headers = await as_role(client, caplog, "fr1@example.com", Role.ADMIN)
        response = await client.post(
            "/api/admin/events",
            headers=headers,
            json={"title": "Autumn Cup Sampleport", "starts_on": "2026-10-24"},
        )
        assert response.status_code == 201, response.text
        event = response.json()

        assert event["series"] is None
        assert event["matchday"] is None
        # The URL comes from title and year, not from the series and an act number.
        assert event["slug"] == "autumn-cup-sampleport-2026"

    async def test_it_appears_in_the_calendar(self, client, caplog):
        headers = await as_role(client, caplog, "fr2@example.com", Role.ADMIN)
        created = (
            await client.post(
                "/api/admin/events",
                headers=headers,
                # Published — the calendar shows what is public (Story VA-8).
                json={
                    "title": "Training Weekend North",
                    "starts_on": "2026-11-07",
                    "published": True,
                },
            )
        ).json()

        calendar = (await client.get("/api/events")).json()
        assert created["slug"] in {e["slug"] for e in calendar}

    async def test_it_counts_in_no_series_table(self, client, caplog, ids):
        headers = await as_role(client, caplog, "fr3@example.com", Role.ADMIN)
        await client.post(
            "/api/admin/events",
            headers=headers,
            json={"title": "Invitational Regatta South", "starts_on": "2026-11-21"},
        )

        table = (await client.get(f"/api/series/{ids.series('dsbl-1-2026')}/table")).json()
        matchdays = {e["title"] for e in table["events"]}
        assert "Invitational Regatta South" not in matchdays

    async def test_their_detail_page_stays_reachable(self, client, caplog):
        """With no series there are no teams, so the results table is simply empty."""
        headers = await as_role(client, caplog, "fr4@example.com", Role.ADMIN)
        created = (
            await client.post(
                "/api/admin/events",
                headers=headers,
                json={
                    "title": "Clubregatta Beispielsee",
                    "starts_on": "2026-12-05",
                    "published": True,
                },
            )
        ).json()

        response = await client.get(f"/api/events/{created['id']}")
        assert response.status_code == 200
        detail = response.json()
        assert detail["standings"] == []
        assert detail["races_total"] == 0

    async def test_an_unknown_series_is_refused(self, client, caplog):
        headers = await as_role(client, caplog, "fr5@example.com", Role.ADMIN)
        response = await client.post(
            "/api/admin/events",
            headers=headers,
            json={"title": "Falsche Serie", "starts_on": "2026-12-12", "series": 999999},
        )
        assert response.status_code == 404
        assert "not set up" in response.json()["detail"]
