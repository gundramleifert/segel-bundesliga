"""Story V-16: a club's admin invites someone with no account by email; the link creates
their account and makes them a member — account first, then the club.

Each test works on fresh clubs and fresh addresses (docs/gotchas: counts against seed
rows). Without SBL_SMTP_HOST the link goes to the log, as a login code does; the tests
read it there.
"""

import logging
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import select, update

from app.config import settings
from app.db import SessionLocal
from app.models import AuditLog, ClubMembership, Person
from app.models.auth import Role, User
from tests.stories.test_club_members import _club_with_admin, _fresh_club, _roster
from tests.stories.test_join_with_consent import _mine, _todo
from tests.stories.test_login_and_roles import _admin_headers, _headers, _problem_code, make_user
from tests.stories.test_registration import auth_headers


def _address() -> str:
    return f"v16-{uuid4().hex[:8]}@example.org"


async def _invite(
    client, caplog, headers, club: int, email: str, first: str = "Nina", last: str = "Neu"
):
    """The club's admin invites ``email``; returns the response and the link's token."""
    with caplog.at_level(logging.WARNING, logger="app.mail"):
        response = await client.post(
            f"/api/clubs/{club}/invitations",
            headers=headers,
            json={"email": email, "first_name": first, "last_name": last},
        )
    return response, _token(caplog, response)


def _token(caplog, response) -> str | None:
    if response.status_code not in (200, 201):
        return None
    link = caplog.records[-1].args[-1]
    assert link.startswith(f"{settings.site_url}/invitation/"), link
    return link.rsplit("/", 1)[-1]


async def _people(client, headers, club: int, **filters) -> dict[int, dict]:
    response = await client.get(f"/api/clubs/{club}/people", headers=headers, params=filters)
    assert response.status_code == 200, response.text
    return {p["person_id"]: p for p in response.json()["items"]}


async def _lapse(invitation: dict) -> None:
    async with SessionLocal() as session:
        await session.execute(
            update(ClubMembership)
            .where(
                ClubMembership.club_id == invitation["club_id"],
                ClubMembership.person_id == invitation["person_id"],
            )
            .values(invitation_expires_at=datetime.now(UTC) - timedelta(minutes=1))
        )
        await session.commit()


class TestTheClubAdminInvites:
    async def test_the_person_is_pending_and_the_mail_names_club_and_inviter(self, client, caplog):
        """Story V-16, Journey step J-3.14: an address no account has → the person on
        record, *pending* (``invited``), no member; a mail naming the club and the admin,
        its link valid for 14 days."""
        club, admin = await _club_with_admin(client, caplog, _address())
        email = _address()
        with caplog.at_level(logging.WARNING, logger="app.mail"):
            response = await client.post(
                f"/api/clubs/{club}/invitations",
                headers=admin,
                json={"email": email, "first_name": "Nina", "last_name": "Neu"},
            )
        assert response.status_code == 201, response.text
        invitation = response.json()
        assert invitation["state"] == "pending"
        expires = datetime.fromisoformat(invitation["expires_at"])
        assert timedelta(days=13, hours=23) < expires - datetime.now(UTC) <= timedelta(days=14)
        assert "invitation link" in caplog.records[-1].getMessage()

        row = (await _people(client, admin, club))[invitation["person_id"]]
        assert (row["first_name"], row["status"], row["user_id"]) == ("Nina", "invited", None)
        assert row["invitation"]["state"] == "pending"
        assert invitation["person_id"] not in {m["person_id"] for m in await _roster(
            client, admin, club
        ) if m["status"] == "active"}  # fmt: skip

    async def test_only_the_club_admin_or_the_league_office(self, client, caplog):
        """Story V-16: not the team manager — the admin decides who is in the club."""
        club = await _fresh_club()
        manager_email = _address()
        await make_user(manager_email, Role.TEAM_MANAGER, club_id=club)
        manager = await _headers(client, caplog, manager_email)
        refused, _ = await _invite(client, caplog, manager, club, _address())
        assert refused.status_code == 403, refused.text
        assert _problem_code(refused) == "invitation-forbidden"

        office = await _admin_headers(client, caplog, "v16-office@example.org")
        sent, token = await _invite(client, caplog, office, club, _address())
        assert sent.status_code == 201, sent.text and token

    async def test_an_address_with_an_account_is_refused(self, client, caplog):
        """Story V-16: ``invitation-has-account`` — such a person is added by email."""
        club, admin = await _club_with_admin(client, caplog, _address())
        email = _address()
        await make_user(email)
        refused, _ = await _invite(client, caplog, admin, club, email)
        assert refused.status_code == 409, refused.text
        assert _problem_code(refused) == "invitation-has-account"

    async def test_a_person_on_record_is_invited_from_their_row(self, client, caplog):
        """Story V-16, Journey steps J-3.11 and J-3.12: the club created the person with
        an address; their row sends the invitation, and the link only adds the account —
        the membership was active already."""
        club, admin = await _club_with_admin(client, caplog, _address())
        email = _address()
        created = await client.post(
            "/api/admin/people",
            headers=admin,
            json={"first_name": "Rita", "last_name": "Reff", "email": email, "club_id": club},
        )
        assert created.status_code == 201, created.text
        person = created.json()["id"]
        with caplog.at_level(logging.WARNING, logger="app.mail"):
            sent = await client.post(f"/api/clubs/{club}/people/{person}/invitation", headers=admin)
        assert sent.status_code == 201, sent.text
        token = _token(caplog, sent)
        assert (await _people(client, admin, club))[person]["status"] == "active"

        redeemed = await client.post(
            f"/api/invitations/{token}/redeem", json={"first_name": "Rita", "last_name": "Reff"}
        )
        assert redeemed.status_code == 200, redeemed.text
        row = (await _people(client, admin, club))[person]
        assert row["status"] == "active" and row["user_id"] is not None
        assert row["invitation"] is None


class TestOneInvitationAtATime:
    async def test_another_club_is_refused_without_naming_the_club(self, client, caplog):
        """Story V-16, Journey step J-3.15: ``invitation-pending`` (409), naming no club."""
        first, first_admin = await _club_with_admin(client, caplog, _address())
        second, second_admin = await _club_with_admin(client, caplog, _address())
        email = _address()
        sent, _ = await _invite(client, caplog, first_admin, first, email)
        assert sent.status_code == 201, sent.text
        refused, _ = await _invite(client, caplog, second_admin, second, email)
        assert refused.status_code == 409, refused.text
        assert _problem_code(refused) == "invitation-pending"
        assert "Segelclub" not in refused.text and "club_id" not in refused.json()

    async def test_resending_makes_a_new_link_and_kills_the_old(self, client, caplog):
        """Story V-16, Journey step J-3.16: the inviting club's admin resends; 14 days
        again."""
        club, admin = await _club_with_admin(client, caplog, _address())
        sent, old = await _invite(client, caplog, admin, club, _address())
        await _lapse(sent.json())
        person = sent.json()["person_id"]
        with caplog.at_level(logging.WARNING, logger="app.mail"):
            resent = await client.post(
                f"/api/clubs/{club}/people/{person}/invitation/resend", headers=admin
            )
        assert resent.status_code == 200, resent.text
        assert resent.json()["state"] == "pending"
        new = _token(caplog, resent)
        assert new != old
        assert (await client.get(f"/api/invitations/{old}")).status_code == 404
        assert (await client.get(f"/api/invitations/{new}")).status_code == 200

    async def test_another_clubs_admin_cannot_resend_or_withdraw(self, client, caplog):
        """Story V-16: only the inviting club's admin (or the site's)."""
        club, admin = await _club_with_admin(client, caplog, _address())
        other, other_admin = await _club_with_admin(client, caplog, _address())
        sent, _ = await _invite(client, caplog, admin, club, _address())
        person = sent.json()["person_id"]
        resend = await client.post(
            f"/api/clubs/{club}/people/{person}/invitation/resend", headers=other_admin
        )
        assert resend.status_code == 403, resend.text
        withdraw = await client.delete(
            f"/api/clubs/{other}/people/{person}/invitation", headers=other_admin
        )
        assert withdraw.status_code == 404, withdraw.text

    async def test_withdrawing_removes_the_pending_row_and_the_record_made_for_it(
        self, client, caplog
    ):
        """Story V-16: the invitation, the pending row and the person created only for it
        are gone; the address is free again."""
        club, admin = await _club_with_admin(client, caplog, _address())
        email = _address()
        sent, token = await _invite(client, caplog, admin, club, email)
        body = sent.json()
        withdrawn = await client.delete(
            f"/api/clubs/{club}/people/{body['person_id']}/invitation", headers=admin
        )
        assert withdrawn.status_code == 204, withdrawn.text
        assert body["person_id"] not in await _people(client, admin, club)
        async with SessionLocal() as session:
            assert await session.get(Person, body["person_id"]) is None
        assert (await client.get(f"/api/invitations/{token}")).status_code == 404

    async def test_ending_the_row_any_way_ends_the_link(self, client, caplog):
        """Story V-16: the invitation is the membership row's — removed through *People*
        like any pending row, its link is dead and cannot bring the person back."""
        club, admin = await _club_with_admin(client, caplog, _address())
        sent, token = await _invite(client, caplog, admin, club, _address())
        person = sent.json()["person_id"]
        removed = await client.delete(f"/api/clubs/{club}/members/{person}", headers=admin)
        assert removed.status_code == 204, removed.text
        assert (await client.get(f"/api/invitations/{token}")).status_code == 404
        redeemed = await client.post(
            f"/api/invitations/{token}/redeem", json={"first_name": "A", "last_name": "B"}
        )
        assert redeemed.status_code == 404, redeemed.text

    async def test_an_expired_invitation_blocks_nobody_and_is_a_to_do(self, client, caplog):
        """Story V-16: after 14 days the row shows *expired*, the club's admin has the
        to-do ``invitation_expired`` landing on *People*, and another club may invite."""
        club, admin = await _club_with_admin(client, caplog, _address())
        other, other_admin = await _club_with_admin(client, caplog, _address())
        email = _address()
        sent, token = await _invite(client, caplog, admin, club, email)
        assert await _todo(client, admin, "club", "invitation_expired", club) == 0
        await _lapse(sent.json())

        lapsed = await client.get(f"/api/invitations/{token}")
        assert lapsed.status_code == 410, lapsed.text
        assert _problem_code(lapsed) == "invitation-expired"
        assert lapsed.json()["club"] == "Segelclub Frisch"
        expired = await _people(client, admin, club, invitation="expired")
        assert expired[sent.json()["person_id"]]["invitation"]["state"] == "expired"
        assert await _todo(client, admin, "club", "invitation_expired", club) == 1

        again, _ = await _invite(client, caplog, other_admin, other, email)
        assert again.status_code == 201, again.text


class TestRedeeming:
    async def test_the_link_creates_a_verified_account_and_a_member(
        self, client, caplog, monkeypatch
    ):
        """Story V-16, Journey step J-3.13: the name as the club entered it, corrected by
        the person;
        an account with the address verified, linked to the club's person, the membership
        active, signed in — with registration closed and self-signup off."""
        monkeypatch.setattr(settings, "allow_registration", False)
        monkeypatch.setattr(settings, "allow_self_signup", False)
        club, admin = await _club_with_admin(client, caplog, _address())
        email = _address()
        sent, token = await _invite(client, caplog, admin, club, email, "Nina", "Nue")
        person = sent.json()["person_id"]

        shown = await client.get(f"/api/invitations/{token}")
        assert shown.status_code == 200, shown.text
        assert shown.json() == {
            "club_id": club,
            "club_name": "Segelclub Frisch",
            "first_name": "Nina",
            "last_name": "Nue",
            "email": email,
        }
        redeemed = await client.post(
            f"/api/invitations/{token}/redeem", json={"first_name": "Nina", "last_name": "Neu"}
        )
        assert redeemed.status_code == 200, redeemed.text
        headers = auth_headers(redeemed.json()["access_token"])
        me = (await client.get("/api/auth/me", headers=headers)).json()
        assert (me["email"], me["email_verified"]) == (email, True)
        mine = (await client.get("/api/people/me", headers=headers)).json()
        assert (mine["id"], mine["last_name"]) == (person, "Neu")
        assert (await _mine(client, headers)) == {club: "active"}

        used = await client.get(f"/api/invitations/{token}")
        assert used.status_code == 410, used.text
        assert _problem_code(used) == "invitation-used"
        again = await client.post(
            f"/api/invitations/{token}/redeem", json={"first_name": "N", "last_name": "N"}
        )
        assert again.status_code == 410, again.text

    async def test_registering_meanwhile_leaves_the_invitation_in_my_clubs(self, client, caplog):
        """Story V-16: the person registers on their own while invited — their verified
        account is linked to the same person, the invitation waits in *Me › My clubs*,
        and the link says to sign in."""
        club, admin = await _club_with_admin(client, caplog, _address())
        email = _address()
        sent, token = await _invite(client, caplog, admin, club, email)
        with caplog.at_level(logging.WARNING, logger="app.mail"):
            registered = await client.post(
                "/api/auth/register", json={"email": email, "display_name": "Nina Neu"}
            )
        assert registered.status_code == 202, registered.text
        code = caplog.records[-1].args[-1]
        verified = await client.post("/api/auth/email/verify", json={"email": email, "code": code})
        assert verified.status_code == 200, verified.text
        headers = auth_headers(verified.json()["access_token"])
        assert (await client.get("/api/people/me", headers=headers)).json()["id"] == sent.json()[
            "person_id"
        ]
        assert (await _mine(client, headers)) == {club: "invited"}

        link = await client.get(f"/api/invitations/{token}")
        assert link.status_code == 409, link.text
        assert _problem_code(link) == "invitation-has-account"

    async def test_a_registered_but_unconfirmed_account_is_confirmed_by_the_link(
        self, client, caplog
    ):
        """Story V-16: the link reaching the address proves it, as a code would — the
        account registered meanwhile and never confirmed is the one signed in."""
        club, admin = await _club_with_admin(client, caplog, _address())
        email = _address()
        _, token = await _invite(client, caplog, admin, club, email)
        await client.post("/api/auth/register", json={"email": email, "display_name": "N N"})
        redeemed = await client.post(
            f"/api/invitations/{token}/redeem", json={"first_name": "Nina", "last_name": "Neu"}
        )
        assert redeemed.status_code == 200, redeemed.text
        async with SessionLocal() as session:
            users = (await session.execute(select(User).where(User.email == email))).scalars()
            assert [u.email_verified for u in users] == [True]


class TestEveryInvitationIsLogged:
    async def test_sent_resent_withdrawn_and_redeemed(self, client, caplog):
        """Story V-16: every invitation sent, resent, withdrawn and redeemed is audited."""
        club, admin = await _club_with_admin(client, caplog, _address())
        sent, _ = await _invite(client, caplog, admin, club, _address())
        first = sent.json()
        await _lapse(first)
        row = f"/api/clubs/{club}/people/{first['person_id']}/invitation"
        await client.post(f"{row}/resend", headers=admin)
        await client.delete(row, headers=admin)

        async def actions(person: int) -> list[str]:
            async with SessionLocal() as session:
                return [
                    row.action
                    for row in (
                        await session.execute(
                            select(AuditLog)
                            .where(AuditLog.entity_type == "person", AuditLog.entity_id == person)
                            .order_by(AuditLog.id)
                        )
                    ).scalars()
                ]

        assert await actions(first["person_id"]) == [
            "invitation_sent",
            "invitation_resent",
            "invitation_withdrawn",
        ]
        # Asked before the next person exists: SQLite hands the deleted record's id on.
        sent, token = await _invite(client, caplog, admin, club, _address())
        second = sent.json()
        await client.post(
            f"/api/invitations/{token}/redeem", json={"first_name": "A", "last_name": "B"}
        )

        assert (await actions(second["person_id"]))[-2:] == [
            "invitation_sent",
            "invitation_redeemed",
        ]
