"""Admin user stories: create clubs and events.

Clubs are master data — they appear later in the choice of host for an event.
"""

from app.models.auth import Role
from tests.stories.test_login_and_roles import login_as, make_user


async def als(client, caplog, email: str, *rollen: str) -> dict[str, str]:
    await make_user(email, *rollen)
    token = await login_as(client, email, caplog)
    return {"Authorization": f"Bearer {token}"}


class TestClubCreation:
    """As admin or editor I want to create clubs."""

    async def test_a_club_can_be_created_with_required_info(self, client, caplog):
        headers = await als(client, caplog, "sd1@example.com", Role.ADMIN)
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
        headers = await als(client, caplog, "sd2@example.com", Role.EDITOR)
        response = await client.post(
            "/api/admin/clubs",
            headers=headers,
            json={"name": "Yachtclub Beispielsee", "short_name": "YCB", "city": "Beispiel"},
        )
        assert response.status_code == 201

    async def test_race_officers_cannot_create_clubs(self, client, caplog):
        headers = await als(client, caplog, "sd3@example.com", Role.RACE_OFFICER)
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
        headers = await als(client, caplog, "sd4@example.com", Role.ADMIN)
        response = await client.post(
            "/api/admin/clubs",
            headers=headers,
            json={"name": "Musterclub Überlingen", "short_name": "MCÜ", "city": "Überlingen"},
        )
        assert response.status_code == 201
        assert response.json()["slug"] == "mcue"

    async def test_taken_url_is_detected(self, client, caplog):
        headers = await als(client, caplog, "sd5@example.com", Role.ADMIN)
        data = {"name": "Duplicate Club", "short_name": "DPC", "city": "Double City"}
        first = await client.post("/api/admin/clubs", headers=headers, json=data)
        assert first.status_code == 201

        second = await client.post("/api/admin/clubs", headers=headers, json=data)
        assert second.status_code == 409
        assert "taken" in second.json()["detail"]


class TestSpieltagAnlegen:
    """Als Veranstalter will ich einen Spieltag mit Name, Datum und Ausrichter anlegen."""

    async def _ausrichter(self, client) -> dict:
        return (await client.get("/api/clubs")).json()[0]

    async def test_name_datum_und_ausrichter_genuegen(self, client, caplog, ids):
        kopf = await als(client, caplog, "ev1@example.com", Role.ADMIN)
        verein = await self._ausrichter(client)

        antwort = await client.post(
            "/api/admin/events",
            headers=kopf,
            json={
                "title": "Herbst-Spieltag Musterhafen",
                "starts_on": "2026-09-18",
                "series": ids.series("dsbl-1-2026"),
                "host_club_id": verein["id"],
            },
        )
        assert antwort.status_code == 201, antwort.text
        event = antwort.json()

        assert event["title"] == "Herbst-Spieltag Musterhafen"
        assert event["host_club"]["id"] == verein["id"]
        # Ohne Enddatum gilt der Spieltag als eintägig.
        assert event["ends_on"] == event["starts_on"] == "2026-09-18"
        # Das Revier steht beim Anlegen noch nicht fest.
        assert event["venue"] is None
        assert event["status"] == "planned"

    async def test_die_spieltagsnummer_wird_fortgezaehlt(self, client, caplog, ids):
        """Zwei Anlagen hintereinander: die zweite trägt die nächste Nummer.

        Früher wurde die höchste Nummer aus `/api/events` gelesen. Das geht nicht mehr:
        die öffentliche Liste zeigt nur veröffentlichte Veranstaltungen (Story VA-8), ein
        Entwurf zählt aber sehr wohl mit, wenn weitergezählt wird. Der Vergleich zweier
        aufeinanderfolgender Anlagen prüft dasselbe und hängt an keiner Sichtbarkeit.
        """
        kopf = await als(client, caplog, "ev2@example.com", Role.ADMIN)

        async def anlegen(titel: str, tag: str) -> int:
            antwort = await client.post(
                "/api/admin/events",
                headers=kopf,
                json={
                    "title": titel,
                    "starts_on": tag,
                    "series": ids.series("dsbl-1-2026"),
                },
            )
            assert antwort.status_code == 201, antwort.text
            return antwort.json()["matchday"]

        erster = await anlegen("Nächster Spieltag", "2026-10-02")
        assert await anlegen("Übernächster Spieltag", "2026-10-09") == erster + 1

    async def test_ohne_eigenes_logo_gilt_das_wappen_des_ausrichters(self, client, caplog, ids):
        kopf = await als(client, caplog, "ev3@example.com", Role.ADMIN)
        verein = await self._ausrichter(client)
        await client.patch(
            f"/api/admin/clubs/{verein['id']}",
            headers=kopf,
            json={"logo_url": "/marke/ausrichter.png"},
        )

        antwort = await client.post(
            "/api/admin/events",
            headers=kopf,
            json={
                "title": "Spieltag mit Vereinswappen",
                "starts_on": "2026-10-16",
                "series": ids.series("dsbl-1-2026"),
                "host_club_id": verein["id"],
            },
        )
        assert antwort.json()["logo_url"] == "/marke/ausrichter.png"

    async def test_ein_eigenes_logo_hat_vorrang(self, client, caplog, ids):
        kopf = await als(client, caplog, "ev4@example.com", Role.ADMIN)
        verein = await self._ausrichter(client)

        antwort = await client.post(
            "/api/admin/events",
            headers=kopf,
            json={
                "title": "Spieltag mit eigenem Logo",
                "starts_on": "2026-10-30",
                "series": ids.series("dsbl-1-2026"),
                "host_club_id": verein["id"],
                "logo_url": "/marke/spieltag.png",
            },
        )
        assert antwort.json()["logo_url"] == "/marke/spieltag.png"

    async def test_redaktion_und_wettfahrtleitung_duerfen_ebenfalls(self, client, caplog, ids):
        for nummer, rolle in enumerate([Role.EDITOR, Role.RACE_OFFICER], start=5):
            kopf = await als(client, caplog, f"ev{nummer}@example.com", rolle)
            antwort = await client.post(
                "/api/admin/events",
                headers=kopf,
                json={
                    "title": f"Spieltag von {rolle}",
                    "starts_on": "2026-11-13",
                    "series": ids.series("dsbl-1-2026"),
                },
            )
            assert antwort.status_code == 201, f"{rolle}: {antwort.text}"

    async def test_ein_vereinskonto_darf_keine_spieltage_anlegen(self, client, caplog, ids):
        kopf = await als(client, caplog, "ev7@example.com", Role.CLUB_MANAGER)
        antwort = await client.post(
            "/api/admin/events",
            headers=kopf,
            json={
                "title": "Unerlaubt",
                "starts_on": "2026-11-20",
                "series": ids.series("dsbl-1-2026"),
            },
        )
        assert antwort.status_code == 403

    async def test_ein_unbekannter_ausrichter_wird_abgewiesen(self, client, caplog, ids):
        kopf = await als(client, caplog, "ev8@example.com", Role.ADMIN)
        antwort = await client.post(
            "/api/admin/events",
            headers=kopf,
            json={
                "title": "Spieltag ohne Verein",
                "starts_on": "2026-11-27",
                "series": ids.series("dsbl-1-2026"),
                "host_club_id": 999999,
            },
        )
        assert antwort.status_code == 404
        assert "not known" in antwort.json()["detail"]

    async def test_ein_ende_vor_dem_beginn_wird_abgewiesen(self, client, caplog, ids):
        kopf = await als(client, caplog, "ev9@example.com", Role.ADMIN)
        antwort = await client.post(
            "/api/admin/events",
            headers=kopf,
            json={
                "title": "Rückwärts",
                "starts_on": "2026-12-04",
                "ends_on": "2026-12-01",
                "series": ids.series("dsbl-1-2026"),
            },
        )
        assert antwort.status_code == 422

    async def test_ein_angelegter_spieltag_laesst_sich_nachbessern(self, client, caplog):
        kopf = await als(client, caplog, "ev10@example.com", Role.ADMIN)
        angelegt = (
            await client.post(
                "/api/admin/events",
                headers=kopf,
                json={"title": "Vorläufig", "starts_on": "2026-12-11", "league": "dsbl-1-2026",
                      "season": 2026},
            )
        ).json()

        geaendert = await client.patch(
            f"/api/admin/events/{angelegt['id']}",
            headers=kopf,
            json={"title": "Endgültiger Name", "status": "live"},
        )
        assert geaendert.status_code == 200
        assert geaendert.json()["title"] == "Endgültiger Name"
        assert geaendert.json()["status"] == "live"


class TestFreieVeranstaltung:
    """A-2: Ein Event kann zu einer Liga gehören — muss aber nicht.

    Ein Pokal, ein Trainingswochenende oder eine Einladungsregatta steht für sich: sie
    erscheint im Kalender, fließt aber in keine Ligatabelle ein.
    """

    async def test_eine_veranstaltung_ohne_serie_laesst_sich_anlegen(self, client, caplog):
        kopf = await als(client, caplog, "fr1@example.com", Role.ADMIN)
        antwort = await client.post(
            "/api/admin/events",
            headers=kopf,
            json={"title": "Herbstpokal Musterhafen", "starts_on": "2026-10-24"},
        )
        assert antwort.status_code == 201, antwort.text
        event = antwort.json()

        assert event["series"] is None
        assert event["matchday"] is None
        # Die Adresse entsteht aus Titel und Jahr, nicht aus Serie und Act-Nummer.
        assert event["slug"] == "herbstpokal-musterhafen-2026"

    async def test_sie_erscheint_im_terminkalender(self, client, caplog):
        kopf = await als(client, caplog, "fr2@example.com", Role.ADMIN)
        angelegt = (
            await client.post(
                "/api/admin/events",
                headers=kopf,
                # Veröffentlicht — im Terminkalender steht, was öffentlich ist (VA-8).
                json={
                    "title": "Trainingswochenende Nord",
                    "starts_on": "2026-11-07",
                    "published": True,
                },
            )
        ).json()

        termine = (await client.get("/api/events")).json()
        assert angelegt["slug"] in {e["slug"] for e in termine}

    async def test_sie_zaehlt_in_keine_ligatabelle(self, client, caplog, ids):
        kopf = await als(client, caplog, "fr3@example.com", Role.ADMIN)
        await client.post(
            "/api/admin/events",
            headers=kopf,
            json={"title": "Einladungsregatta Süd", "starts_on": "2026-11-21"},
        )

        tabelle = (await client.get(f"/api/series/{ids.series('dsbl-1-2026')}/table")).json()
        spieltage = {e["title"] for e in tabelle["events"]}
        assert "Einladungsregatta Süd" not in spieltage

    async def test_ihre_detailseite_bleibt_abrufbar(self, client, caplog):
        """Ohne Liga gibt es keine Mannschaften — die Tageswertung bleibt eben leer."""
        kopf = await als(client, caplog, "fr4@example.com", Role.ADMIN)
        angelegt = (
            await client.post(
                "/api/admin/events",
                headers=kopf,
                json={
                    "title": "Clubregatta Beispielsee",
                    "starts_on": "2026-12-05",
                    "published": True,
                },
            )
        ).json()

        antwort = await client.get(f"/api/events/{angelegt['id']}")
        assert antwort.status_code == 200
        detail = antwort.json()
        assert detail["standings"] == []
        assert detail["races_total"] == 0

    async def test_eine_unbekannte_serie_wird_abgewiesen(self, client, caplog):
        kopf = await als(client, caplog, "fr5@example.com", Role.ADMIN)
        antwort = await client.post(
            "/api/admin/events",
            headers=kopf,
            json={"title": "Falsche Serie", "starts_on": "2026-12-12", "series": 999999},
        )
        assert antwort.status_code == 404
        assert "not set up" in antwort.json()["detail"]
