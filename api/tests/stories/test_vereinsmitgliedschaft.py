"""User Stories V-8 and V-9: Club membership — both sides must agree.

Two paths lead to membership, and neither works without the other side:

* The person applies, the club accepts.
* The club invites, the person accepts.

This differs from series and event participation: there admin can assign unilaterally
(see ``test_participation.py``).
"""

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Club, ClubMemberStatus
from tests.stories.test_login_and_roles import login_as, make_user
from tests.stories.test_registrierung import kopf, registrieren

# Two fixed clubs from the seed that others don't touch.
CLUB = "wyc"
SECOND_CLUB = "lsc"


async def club_id(slug: str) -> int:
    async with SessionLocal() as session:
        return (
            await session.execute(select(Club.id).where(Club.slug == slug))
        ).scalar_one()


async def club_leadership(client, caplog, email: str, slug: str = CLUB) -> dict[str, str]:
    """An account with ``club_manager`` role for this club."""
    from app.models.auth import Role

    await make_user(email, Role.CLUB_MANAGER, club_id=await club_id(slug))
    return kopf(await login_as(client, email, caplog))


class TestPersonApplies:
    """As a sailor I want to request membership — the club decides."""

    async def test_club_accepts_and_then_i_am_member(self, client, caplog):
        person = kopf(await registrieren(client, caplog, "vm1@example.com", "Vera Mitglied"))
        c = await club_id(CLUB)

        request = (
            await client.post("/api/club-memberships", headers=person, json={"club_id": c})
        ).json()

        leadership = await club_leadership(client, caplog, "vml1@example.com")
        accepted = await client.post(
            f"/api/club-memberships/{request['id']}/accept", headers=leadership
        )

        assert accepted.status_code == 200, accepted.text
        assert accepted.json()["status"] == ClubMemberStatus.ACTIVE
        assert accepted.json()["waiting_for"] is None

    async def test_i_cannot_accept_myself(self, client, caplog):
        """The core rule: the other side decides on the application."""
        person = kopf(await registrieren(client, caplog, "vm2@example.com", "Siggi Selbst"))
        c = await club_id(CLUB)

        request = (
            await client.post("/api/club-memberships", headers=person, json={"club_id": c})
        ).json()

        response = await client.post(
            f"/api/club-memberships/{request['id']}/accept", headers=person
        )
        assert response.status_code == 403
        assert "club" in response.json()["detail"]

    async def test_foreign_club_does_not_decide(self, client, caplog):
        person = kopf(await registrieren(client, caplog, "vm3@example.com", "Frida Fremd"))
        request = (
            await client.post(
                "/api/club-memberships",
                headers=person,
                json={"club_id": await club_id(CLUB)},
            )
        ).json()

        foreign = await club_leadership(client, caplog, "vml3@example.com", SECOND_CLUB)
        response = await client.post(
            f"/api/club-memberships/{request['id']}/accept", headers=foreign
        )
        assert response.status_code == 403

    async def test_rejection_states_reason_and_i_see_it(self, client, caplog):
        person = kopf(await registrieren(client, caplog, "vm4@example.com", "Anke Abgelehnt"))
        request = (
            await client.post(
                "/api/club-memberships",
                headers=person,
                json={"club_id": await club_id(CLUB)},
            )
        ).json()

        leadership = await club_leadership(client, caplog, "vml4@example.com")
        await client.post(
            f"/api/club-memberships/{request['id']}/reject",
            headers=leadership,
            json={"note": "Bitte erst die Mitgliedschaft im Verein klären."},
        )

        # Specifically find the membership for this club: a person can have multiple,
        # and order is not guaranteed.
        my_memberships = (await client.get("/api/club-memberships", headers=person)).json()
        entry = next(m for m in my_memberships if m["id"] == request["id"])
        assert entry["status"] == ClubMemberStatus.REJECTED
        assert "Mitgliedschaft" in entry["decision_note"]

    async def test_after_rejection_i_can_try_again(self, client, caplog):
        person = kopf(await registrieren(client, caplog, "vm5@example.com", "Nils Neuanlauf"))
        c = await club_id(CLUB)
        request = (
            await client.post("/api/club-memberships", headers=person, json={"club_id": c})
        ).json()

        leadership = await club_leadership(client, caplog, "vml5@example.com")
        await client.post(f"/api/club-memberships/{request['id']}/reject", headers=leadership)

        retry = await client.post(
            "/api/club-memberships", headers=person, json={"club_id": c}
        )
        assert retry.status_code == 201
        assert retry.json()["status"] == ClubMemberStatus.PENDING_CLUB

    async def test_i_can_withdraw_pending_application(self, client, caplog):
        person = kopf(await registrieren(client, caplog, "vm6@example.com", "Rita Rückzug"))
        request = (
            await client.post(
                "/api/club-memberships",
                headers=person,
                json={"club_id": await club_id(CLUB)},
            )
        ).json()

        assert (
            await client.delete(f"/api/club-memberships/{request['id']}", headers=person)
        ).status_code == 204
        assert (await client.get("/api/club-memberships", headers=person)).json() == []


class TestClubInvites:
    """As club leadership I want to admit someone — the person decides."""

    async def test_invitation_waits_for_person(self, client, caplog):
        await registrieren(client, caplog, "ve1@example.com", "Emil Eingeladen")
        leadership = await club_leadership(client, caplog, "vel1@example.com")

        response = await client.post(
            f"/api/admin/clubs/{await club_id(CLUB)}/members",
            headers=leadership,
            json={"email": "ve1@example.com"},
        )
        assert response.status_code == 201, response.text
        assert response.json()["status"] == ClubMemberStatus.PENDING_USER
        assert response.json()["waiting_for"] == "user"

    async def test_club_cannot_accept_on_behalf_of_person(self, client, caplog):
        """Otherwise a club could attach members who don't know about it."""
        await registrieren(client, caplog, "ve2@example.com", "Uta Ungefragt")
        leadership = await club_leadership(client, caplog, "vel2@example.com")
        invitation = (
            await client.post(
                f"/api/admin/clubs/{await club_id(CLUB)}/members",
                headers=leadership,
                json={"email": "ve2@example.com"},
            )
        ).json()

        response = await client.post(
            f"/api/club-memberships/{invitation['id']}/accept", headers=leadership
        )
        assert response.status_code == 403
        assert "invited person" in response.json()["detail"]

    async def test_if_person_accepts_they_become_member(self, client, caplog):
        person = kopf(await registrieren(client, caplog, "ve3@example.com", "Jan Ja"))
        leadership = await club_leadership(client, caplog, "vel3@example.com")
        invitation = (
            await client.post(
                f"/api/admin/clubs/{await club_id(CLUB)}/members",
                headers=leadership,
                json={"email": "ve3@example.com"},
            )
        ).json()

        accepted = await client.post(
            f"/api/club-memberships/{invitation['id']}/accept", headers=person
        )
        assert accepted.status_code == 200
        assert accepted.json()["status"] == ClubMemberStatus.ACTIVE

        me = (await client.get("/api/auth/me", headers=person)).json()
        assert me["club_id"] == await club_id(CLUB)

    async def test_person_can_reject(self, client, caplog):
        person = kopf(await registrieren(client, caplog, "ve4@example.com", "Nina Nein"))
        leadership = await club_leadership(client, caplog, "vel4@example.com")
        invitation = (
            await client.post(
                f"/api/admin/clubs/{await club_id(CLUB)}/members",
                headers=leadership,
                json={"email": "ve4@example.com"},
            )
        ).json()

        rejected = await client.post(
            f"/api/club-memberships/{invitation['id']}/reject",
            headers=person,
            json={"note": "Ich segle woanders."},
        )
        assert rejected.status_code == 200
        assert rejected.json()["status"] == ClubMemberStatus.REJECTED

    async def test_person_without_account_cannot_be_admitted(self, client, caplog):
        leadership = await club_leadership(client, caplog, "vel5@example.com")
        response = await client.post(
            f"/api/admin/clubs/{await club_id(CLUB)}/members",
            headers=leadership,
            json={"email": "gibtesnicht@example.com"},
        )
        assert response.status_code == 404
        assert "register" in response.json()["detail"]

    async def test_regular_account_cannot_admit_members(self, client, caplog):
        person = kopf(await registrieren(client, caplog, "ve6@example.com", "Otto Ohnerecht"))
        response = await client.post(
            f"/api/admin/clubs/{await club_id(CLUB)}/members",
            headers=person,
            json={"email": "ve6@example.com"},
        )
        assert response.status_code == 403


class TestBothDirectionsMeet:
    """When both sides want the same thing, the matter is decided."""

    async def test_application_and_invitation_together_create_membership(
        self, client, caplog
    ):
        person = kopf(await registrieren(client, caplog, "bt1@example.com", "Tim Treffen"))
        c = await club_id(CLUB)
        await client.post("/api/club-memberships", headers=person, json={"club_id": c})

        leadership = await club_leadership(client, caplog, "btl1@example.com")
        response = await client.post(
            f"/api/admin/clubs/{c}/members",
            headers=leadership,
            json={"email": "bt1@example.com"},
        )
        assert response.status_code == 201
        assert response.json()["status"] == ClubMemberStatus.ACTIVE

    async def test_person_can_be_member_of_multiple_clubs(self, client, caplog):
        """The 'once only' limit applies per competition, not for membership."""
        person = kopf(await registrieren(client, caplog, "bt2@example.com", "Doro Doppelt"))

        clubs_list = (
            (CLUB, "btl2a@example.com"),
            (SECOND_CLUB, "btl2b@example.com"),
        )
        for slug, leadership_email in clubs_list:
            c = await club_id(slug)
            request = (
                await client.post(
                    "/api/club-memberships", headers=person, json={"club_id": c}
                )
            ).json()
            leadership = await club_leadership(client, caplog, leadership_email, slug)
            accepted = await client.post(
                f"/api/club-memberships/{request['id']}/accept", headers=leadership
            )
            assert accepted.status_code == 200

        my_memberships = (await client.get("/api/club-memberships", headers=person)).json()
        active = [m for m in my_memberships if m["status"] == ClubMemberStatus.ACTIVE]
        assert len(active) == 2

    async def test_club_sees_its_pending_requests(self, client, caplog):
        person = kopf(await registrieren(client, caplog, "bt3@example.com", "Lisa Liste"))
        c = await club_id(SECOND_CLUB)
        await client.post("/api/club-memberships", headers=person, json={"club_id": c})

        leadership = await club_leadership(client, caplog, "btl3@example.com", SECOND_CLUB)
        members_response = await client.get(
            f"/api/admin/clubs/{c}/members", headers=leadership
        )
        members_list = members_response.json()
        assert any(
            entry["email"] == "bt3@example.com"
            and entry["status"] == ClubMemberStatus.PENDING_CLUB
            for entry in members_list
        )


class TestOrganizerRole:
    """Story A-8: an organizer appoints further organizers — and at least one stays.

    Actor throughout is an admin: the admin passes the club-leadership check, and using
    one fixed acting account keeps the seed's one-manager-per-club invariant intact so
    the "last organizer" count stays predictable.
    """

    async def _admin(self, client, caplog):
        from app.models.auth import Role

        await make_user("org-admin@example.com", Role.ADMIN)
        return kopf(await login_as(client, "org-admin@example.com", caplog))

    async def _active_member(self, client, caplog, admin, email: str, slug: str) -> tuple[int, int]:
        """Register a person and have the admin accept them into the club."""
        person = kopf(await registrieren(client, caplog, email, "New Member"))
        c = await club_id(slug)
        request = (
            await client.post("/api/club-memberships", headers=person, json={"club_id": c})
        ).json()
        accepted = await client.post(
            f"/api/club-memberships/{request['id']}/accept", headers=admin
        )
        assert accepted.status_code == 200, accepted.text
        return request["user_id"], c

    async def test_an_organizer_can_appoint_another(self, client, caplog):
        admin = await self._admin(client, caplog)
        member_id, c = await self._active_member(client, caplog, admin, "orgm1@example.com", "kyc")

        response = await client.post(
            f"/api/admin/clubs/{c}/members/{member_id}/organizer", headers=admin
        )
        assert response.status_code == 200, response.text
        assert response.json()["organizer"] is True

    async def test_a_non_organizer_cannot_appoint(self, client, caplog):
        admin = await self._admin(client, caplog)
        member_id, c = await self._active_member(client, caplog, admin, "orgm2@example.com", "fsc")
        outsider = kopf(await registrieren(client, caplog, "outsider2@example.com", "Nobody"))

        response = await client.post(
            f"/api/admin/clubs/{c}/members/{member_id}/organizer", headers=outsider
        )
        assert response.status_code == 403

    async def test_only_active_members_can_become_organizers(self, client, caplog):
        admin = await self._admin(client, caplog)
        c = await club_id("vsaw")
        stranger = kopf(await registrieren(client, caplog, "stranger3@example.com", "Stranger"))
        await client.post("/api/club-memberships", headers=stranger, json={"club_id": c})
        stranger_id = (
            await client.get("/api/club-memberships", headers=stranger)
        ).json()[0]["user_id"]

        response = await client.post(
            f"/api/admin/clubs/{c}/members/{stranger_id}/organizer", headers=admin
        )
        assert response.status_code == 404
        assert "active member" in response.json()["detail"]

    async def test_a_second_organizer_can_step_down(self, client, caplog):
        admin = await self._admin(client, caplog)
        p1, c = await self._active_member(client, caplog, admin, "orgm5a@example.com", "myc")
        p2, _ = await self._active_member(client, caplog, admin, "orgm5b@example.com", "myc")
        for pid in (p1, p2):
            await client.post(
                f"/api/admin/clubs/{c}/members/{pid}/organizer", headers=admin
            )
        # Two organizers now — revoking one leaves one, which is allowed.
        response = await client.delete(
            f"/api/admin/clubs/{c}/members/{p2}/organizer", headers=admin
        )
        assert response.status_code == 200
        assert response.json()["organizer"] is False

    async def test_the_last_organizer_cannot_be_demoted(self, client, caplog):
        admin = await self._admin(client, caplog)
        p1, c = await self._active_member(client, caplog, admin, "org4p1@example.com", "dtyc")

        # p1 is now the only organizer of dtyc — they cannot be the one to step down.
        await client.post(f"/api/admin/clubs/{c}/members/{p1}/organizer", headers=admin)
        response = await client.delete(
            f"/api/admin/clubs/{c}/members/{p1}/organizer", headers=admin
        )
        assert response.status_code == 409
        assert "at least one" in response.json()["detail"].lower()

    async def test_cannot_organize_two_clubs(self, client, caplog):
        admin = await self._admin(client, caplog)
        # This person already organizes "svk" (seeded as its manager's peer via role).
        organizes_svk = await club_leadership(client, caplog, "org6b@example.com", "svk")
        assert organizes_svk  # created with club_id=svk + club_manager
        member_id, c = await self._active_member(client, caplog, admin, "org6b@example.com", "cyc")

        response = await client.post(
            f"/api/admin/clubs/{c}/members/{member_id}/organizer", headers=admin
        )
        assert response.status_code == 409
        assert "different club" in response.json()["detail"]
