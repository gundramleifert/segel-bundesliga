"""User Stories V-5 and A-9: Request, accept, and reject participations.

Two paths lead to the same row: the admin sets directly, or the club applies
and gets accepted. An application doesn't count anywhere until it's accepted.
"""

from sqlalchemy import select

from app.db import SessionLocal
from app.models import AuditLog
from app.models.auth import Role, User
from tests.stories.test_login_and_roles import login_as, make_user


async def as_role(client, caplog, email: str, *roles: str) -> dict[str, str]:
    await make_user(email, *roles)
    return {"Authorization": f"Bearer {await login_as(client, email, caplog)}"}


async def club_leadership(client, caplog, email: str, club_id: int) -> dict[str, str]:
    await make_user(email, Role.CLUB_MANAGER, club_id=club_id)
    return {"Authorization": f"Bearer {await login_as(client, email, caplog)}"}


async def new_club(client, headers, name: str) -> dict:
    response = await client.post("/api/admin/clubs", headers=headers, json={"name": name})
    assert response.status_code == 201, response.text
    return response.json()


class TestAntragStellen:
    """V-5: As a club officer, I register my club."""

    async def test_ein_verein_meldet_sich_selbst_an(self, client, caplog, ids):
        admin = await as_role(client, caplog, "tn1a@example.com", Role.ADMIN)
        club = await new_club(client, admin, "Bewerber Segelclub")
        headers = await club_leadership(client, caplog, "tn1@example.com", club["id"])

        response = await client.post(
            "/api/applications",
            headers=headers,
            json={"club_id": club["id"], "series_id": ids.series("dsbl-2-2026")},
        )
        assert response.status_code == 201, response.text
        assert response.json()["status"] == "requested"

    async def test_ein_antrag_macht_den_verein_noch_nicht_sichtbar(self, client, caplog, ids):
        admin = await as_role(client, caplog, "tn2a@example.com", Role.ADMIN)
        club = await new_club(client, admin, "Wartender Segelclub")
        headers = await club_leadership(client, caplog, "tn2@example.com", club["id"])

        await client.post(
            "/api/applications",
            headers=headers,
            json={"club_id": club["id"], "series_id": ids.series("dsbl-2-2026")},
        )

        public = (await client.get("/api/clubs")).json()
        assert club["slug"] not in {v["slug"] for v in public}

    async def test_der_verein_sieht_den_stand_seines_antrags(self, client, caplog, ids):
        admin = await as_role(client, caplog, "tn3a@example.com", Role.ADMIN)
        club = await new_club(client, admin, "Neugieriger Segelclub")
        headers = await club_leadership(client, caplog, "tn3@example.com", club["id"])

        await client.post(
            "/api/applications",
            headers=headers,
            json={"club_id": club["id"], "series_id": ids.series("junioren-2026")},
        )

        own = (await client.get("/api/applications", headers=headers)).json()
        assert len(own) == 1
        assert own[0]["status"] == "requested"
        assert own[0]["series"]["slug"] == "junioren-2026"

    async def test_ein_fremder_verein_laesst_sich_nicht_anmelden(self, client, caplog, ids):
        admin = await as_role(client, caplog, "tn4a@example.com", Role.ADMIN)
        own = await new_club(client, admin, "Eigener Segelclub")
        other = await new_club(client, admin, "Fremder Segelclub")
        headers = await club_leadership(client, caplog, "tn4@example.com", own["id"])

        response = await client.post(
            "/api/applications",
            headers=headers,
            json={"club_id": other["id"], "series_id": ids.series("dsbl-2-2026")},
        )
        assert response.status_code == 403

    async def test_ein_zweiter_antrag_wird_abgewiesen(self, client, caplog, ids):
        admin = await as_role(client, caplog, "tn5a@example.com", Role.ADMIN)
        club = await new_club(client, admin, "Hartnaeckiger Segelclub")
        headers = await club_leadership(client, caplog, "tn5@example.com", club["id"])
        data = {"club_id": club["id"], "series_id": ids.series("dsbl-2-2026")}

        assert (
            await client.post("/api/applications", headers=headers, json=data)
        ).status_code == 201
        second = await client.post("/api/applications", headers=headers, json=data)
        assert second.status_code == 409

    async def test_ein_antrag_laesst_sich_zurueckziehen(self, client, caplog, ids):
        admin = await as_role(client, caplog, "tn6a@example.com", Role.ADMIN)
        club = await new_club(client, admin, "Unentschlossener Segelclub")
        headers = await club_leadership(client, caplog, "tn6@example.com", club["id"])

        application = (
            await client.post(
                "/api/applications",
                headers=headers,
                json={"club_id": club["id"], "series_id": ids.series("dsbl-2-2026")},
            )
        ).json()

        result = await client.delete(f"/api/applications/{application['team_id']}", headers=headers)
        assert result.status_code == 204
        assert (await client.get("/api/applications", headers=headers)).json() == []

    async def test_ohne_rolle_geht_gar_nichts(self, client, caplog, ids):
        admin = await as_role(client, caplog, "tn7a@example.com", Role.ADMIN)
        club = await new_club(client, admin, "Rollenloser Segelclub")
        headers = await as_role(client, caplog, "tn7@example.com")

        response = await client.post(
            "/api/applications",
            headers=headers,
            json={"club_id": club["id"], "series_id": ids.series("dsbl-2-2026")},
        )
        assert response.status_code == 403


class TestEntscheidung:
    """A-9: As an admin, I accept or reject applications."""

    async def _antrag(self, client, caplog, name: str, email: str, ids, serie="dsbl-2-2026"):
        admin = await as_role(client, caplog, f"{email}-adm@example.com", Role.ADMIN)
        club = await new_club(client, admin, name)
        headers = await club_leadership(client, caplog, f"{email}@example.com", club["id"])
        application = (
            await client.post(
                "/api/applications",
                headers=headers,
                json={"club_id": club["id"], "series_id": ids.series(serie)},
            )
        ).json()
        return admin, club, application

    async def test_annehmen_macht_den_verein_zum_teilnehmer(self, client, caplog, ids):
        admin, club, application = await self._antrag(
            client, caplog, "Angenommener Segelclub", "tn8", ids
        )

        response = await client.post(
            f"/api/admin/applications/{application['team_id']}/accept", headers=admin
        )
        assert response.status_code == 200
        assert response.json()["status"] == "accepted"

        public = (await client.get("/api/clubs")).json()
        assert club["slug"] in {v["slug"] for v in public}

    async def test_ablehnen_nennt_den_grund(self, client, caplog, ids):
        admin, club, application = await self._antrag(
            client, caplog, "Abgelehnter Segelclub", "tn9", ids
        )

        response = await client.post(
            f"/api/admin/applications/{application['team_id']}/reject",
            headers=admin,
            json={"note": "Das Feld ist voll."},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "rejected"
        assert response.json()["decision_note"] == "Das Feld ist voll."

        public = (await client.get("/api/clubs")).json()
        assert club["slug"] not in {v["slug"] for v in public}

    async def test_der_verein_erfaehrt_die_ablehnung(self, client, caplog, ids):
        admin, club, application = await self._antrag(
            client, caplog, "Erfahrender Segelclub", "tn10", ids
        )
        await client.post(
            f"/api/admin/applications/{application['team_id']}/reject",
            headers=admin,
            json={"note": "Zu spät gemeldet."},
        )

        headers = {"Authorization": f"Bearer {await login_as(client, 'tn10@example.com', caplog)}"}
        own = (await client.get("/api/applications", headers=headers)).json()
        assert own[0]["status"] == "rejected"
        assert own[0]["decision_note"] == "Zu spät gemeldet."

    async def test_nach_einer_ablehnung_ist_ein_neuer_anlauf_moeglich(self, client, caplog, ids):
        admin, club, application = await self._antrag(
            client, caplog, "Zweiter Anlauf Segelclub", "tn11", ids
        )
        await client.post(
            f"/api/admin/applications/{application['team_id']}/reject", headers=admin
        )

        headers = {"Authorization": f"Bearer {await login_as(client, 'tn11@example.com', caplog)}"}
        retry = await client.post(
            "/api/applications",
            headers=headers,
            json={"club_id": club["id"], "series_id": ids.series("dsbl-2-2026")},
        )
        assert retry.status_code == 201
        assert retry.json()["status"] == "requested"

    async def test_die_verwaltung_sieht_die_offenen_antraege(self, client, caplog, ids):
        admin, _club, _application = await self._antrag(
            client, caplog, "Offener Segelclub", "tn12", ids
        )

        pending = (await client.get("/api/admin/applications", headers=admin)).json()
        assert any(a["club"]["name"] == "Offener Segelclub" for a in pending)
        assert all(a["status"] == "requested" for a in pending)

    async def test_jede_entscheidung_wird_protokolliert(self, client, caplog, ids):
        admin, _club, application = await self._antrag(
            client, caplog, "Protokollierter Segelclub", "tn13", ids
        )
        await client.post(
            f"/api/admin/applications/{application['team_id']}/accept", headers=admin
        )

        async with SessionLocal() as session:
            entry = (
                await session.execute(
                    select(AuditLog).where(
                        AuditLog.entity_type == "team",
                        AuditLog.entity_id == application["team_id"],
                    )
                )
            ).scalars().first()
        assert entry is not None
        assert entry.payload["to"] == "accepted"
        assert entry.actor == "tn13-adm@example.com"

    async def test_eine_teilnahme_mit_ergebnissen_laesst_sich_nicht_widerrufen(
        self, client, caplog, ids
    ):
        """A team that has raced has results attached."""
        admin = await as_role(client, caplog, "tn14@example.com", Role.ADMIN)
        raced = (
            await client.get(
                "/api/admin/applications",
                headers=admin,
                params={"status_filter": "accepted", "series_id": ids.series("dsbl-1-2026")},
            )
        ).json()
        assert raced, "The first series should have accepted participations"

        response = await client.post(
            f"/api/admin/applications/{raced[0]['team_id']}/reject", headers=admin
        )
        assert response.status_code == 409
        assert "race results" in response.json()["detail"]

    async def test_ein_vereinskonto_darf_nicht_entscheiden(self, client, caplog, ids):
        _admin, club, application = await self._antrag(
            client, caplog, "Selbstentscheider Segelclub", "tn15", ids
        )
        headers = {"Authorization": f"Bearer {await login_as(client, 'tn15@example.com', caplog)}"}

        response = await client.post(
            f"/api/admin/applications/{application['team_id']}/accept", headers=headers
        )
        assert response.status_code == 403


class TestTeilnahmeAnEinerVeranstaltung:
    """V-6: As a club officer, I register my club for an event.

    The pairing list is attached to the event, as is participation. For an act of a series:
    whoever participates must also be registered for the series.
    """

    async def test_ein_verein_meldet_sich_fuer_eine_einzelveranstaltung_an(
        self, client, caplog, ids
    ):
        admin = await as_role(client, caplog, "tv1a@example.com", Role.ADMIN)
        club = await new_club(client, admin, "Pokal Segelclub")
        event = (
            await client.post(
                "/api/admin/events",
                headers=admin,
                json={"title": "Offener Herbstpokal", "starts_on": "2026-09-26"},
            )
        ).json()

        headers = await club_leadership(client, caplog, "tv1b@example.com", club["id"])
        response = await client.post(
            "/api/applications",
            headers=headers,
            json={"club_id": club["id"], "event_id": event["id"]},
        )
        assert response.status_code == 201, response.text
        assert response.json()["status"] == "requested"
        assert response.json()["event"]["title"] == "Offener Herbstpokal"

    async def test_ein_beantragter_verein_wird_nicht_ausgelost(self, client, caplog, ids):
        """Until acceptance, an application doesn't count anywhere — not even in the draw."""
        from app.db import SessionLocal
        from app.models import Event
        from app.services import event_entries

        admin = await as_role(client, caplog, "tv2a@example.com", Role.ADMIN)
        club = await new_club(client, admin, "Abwartender Segelclub")
        event_data = (
            await client.post(
                "/api/admin/events",
                headers=admin,
                json={"title": "Wartepokal", "starts_on": "2026-09-27"},
            )
        ).json()

        headers = await club_leadership(client, caplog, "tv2b@example.com", club["id"])
        await client.post(
            "/api/applications",
            headers=headers,
            json={"club_id": club["id"], "event_id": event_data["id"]},
        )

        async with SessionLocal() as session:
            event = await session.get(Event, event_data["id"])
            assert event is not None
            assert await event_entries(session, event.id) == []

    async def test_wer_nicht_fuer_die_serie_gemeldet_ist_tritt_bei_ihrem_act_nicht_an(
        self, client, caplog, ids
    ):
        """Otherwise a club would appear in the daily standings but not in any series table."""
        admin = await as_role(client, caplog, "tv3a@example.com", Role.ADMIN)
        club = await new_club(client, admin, "Serienloser Segelclub")

        headers = await club_leadership(client, caplog, "tv3b@example.com", club["id"])
        response = await client.post(
            "/api/applications",
            headers=headers,
            json={"club_id": club["id"], "event_id": ids.event("dsbl-1-2026-act-3")},
        )
        assert response.status_code == 422
        assert "isn't registered for this event's series" in response.json()["detail"]

    async def test_die_verwaltung_setzt_ohne_rueckfrage_zu(self, client, caplog, ids):
        """The other direction needs no consent: the admin assigns.

        Unlike club membership, where both sides must agree.
        """
        admin = await as_role(client, caplog, "tv4a@example.com", Role.ADMIN)
        club = await new_club(client, admin, "Gesetzter Segelclub")
        event = (
            await client.post(
                "/api/admin/events",
                headers=admin,
                json={"title": "Setzpokal", "starts_on": "2026-09-28"},
            )
        ).json()

        result = await client.put(
            f"/api/admin/events/{event['id']}/clubs",
            headers=admin,
            json={"clubs": [club["id"]]},
        )
        assert result.status_code == 200, result.text
        assert [z["status"] for z in result.json()] == ["accepted"]

    async def test_eine_zusage_von_oben_hebt_den_offenen_antrag_auf(
        self, client, caplog, ids
    ):
        admin = await as_role(client, caplog, "tv5a@example.com", Role.ADMIN)
        club = await new_club(client, admin, "Doppelweg Segelclub")
        event = (
            await client.post(
                "/api/admin/events",
                headers=admin,
                json={"title": "Doppelwegpokal", "starts_on": "2026-09-29"},
            )
        ).json()

        headers = await club_leadership(client, caplog, "tv5b@example.com", club["id"])
        await client.post(
            "/api/applications",
            headers=headers,
            json={"club_id": club["id"], "event_id": event["id"]},
        )

        result = await client.put(
            f"/api/admin/events/{event['id']}/clubs",
            headers=admin,
            json={"clubs": [club["id"]]},
        )
        assert [z["status"] for z in result.json()] == ["accepted"]

    async def test_die_acts_einer_serie_uebernehmen_ihre_vereine(self, client, caplog, ids):
        """Normally, the same clubs participate in all acts."""
        admin = await as_role(client, caplog, "tv6a@example.com", Role.ADMIN)
        created = (
            await client.post(
                "/api/admin/events",
                headers=admin,
                json={
                    "title": "4. Spieltag",
                    "starts_on": "2026-09-30",
                    "series": ids.series("dsbl-1-2026"),
                },
            )
        ).json()

        participants = (
            await client.get(
                f"/api/admin/events/{created['id']}/clubs", headers=admin
            )
        ).json()
        # Intentionally checked against the series and not a fixed number: other stories
        # register clubs afterwards. The claim is that the act takes exactly its series' clubs.
        series = (await client.get("/api/admin/series", headers=admin)).json()
        s = next(s for s in series if s["id"] == ids.series("dsbl-1-2026"))

        assert {z["club"]["id"] for z in participants} == {c["id"] for c in s["clubs"]}
        assert all(z["status"] == "accepted" for z in participants)

    async def test_entweder_serie_oder_veranstaltung_aber_nicht_beides(
        self, client, caplog, ids
    ):
        admin = await as_role(client, caplog, "tv7a@example.com", Role.ADMIN)
        club = await new_club(client, admin, "Zwiespaeltiger Segelclub")
        headers = await club_leadership(client, caplog, "tv7b@example.com", club["id"])

        response = await client.post(
            "/api/applications",
            headers=headers,
            json={
                "club_id": club["id"],
                "series_id": ids.series("dsbl-1-2026"),
                "event_id": ids.event("dsbl-1-2026-act-3"),
            },
        )
        assert response.status_code == 422


class TestNurDieVereinsleitungMeldet:
    """V-6: Only the club organizer registers participants for series and events."""

    async def test_ein_gewoehnliches_mitglied_meldet_niemanden(self, client, caplog, ids):
        admin = await as_role(client, caplog, "nv1a@example.com", Role.ADMIN)
        club = await new_club(client, admin, "Mitglieder Segelclub")

        headers = await club_leadership(client, caplog, "nv1b@example.com", club["id"])
        # Remove the role again: registration only works with club_manager.
        async with SessionLocal() as session:
            from sqlalchemy import delete

            from app.models.auth import UserRole

            user = (
                await session.execute(
                    select(User).where(User.email == "nv1b@example.com")
                )
            ).scalar_one()
            await session.execute(delete(UserRole).where(UserRole.user_id == user.id))
            await session.commit()

        response = await client.post(
            "/api/applications",
            headers=headers,
            json={"club_id": club["id"], "series_id": ids.series("dsbl-1-2026")},
        )
        assert response.status_code == 403
        assert "club officers" in response.json()["detail"]

    async def test_die_wettfahrtleitung_meldet_auch_niemanden(self, client, caplog, ids):
        """They run the races — the club registers itself."""
        admin = await as_role(client, caplog, "nv2a@example.com", Role.ADMIN)
        club = await new_club(client, admin, "Wettfahrt Segelclub")

        race_officer = await as_role(client, caplog, "nv2b@example.com", Role.RACE_OFFICER)
        response = await client.post(
            "/api/applications",
            headers=race_officer,
            json={"club_id": club["id"], "series_id": ids.series("dsbl-1-2026")},
        )
        assert response.status_code == 403
