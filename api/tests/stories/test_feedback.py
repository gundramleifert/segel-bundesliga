"""Feedback (Stories S-9, A-15): anyone signed in tells the league office what they want
or what bothers them, from the page they are on; the site's ``feedback_receiver``s are
mailed each message and read the list, and so does the site's admin.
"""

from __future__ import annotations

import logging
from uuid import uuid4

from sqlalchemy import delete

from app.db import SessionLocal
from app.models.auth import Grant, Relation
from tests.stories.test_login_and_roles import _problem_code
from tests.stories.test_reimbursements import login, world

CONTEXT = {
    "path": "/1-liga/2026?tab=table",
    "locale": "de",
    "app_version": "0.4.0-rc.2",
    "viewport_width": 412,
    "viewport_height": 915,
}


def _tag() -> str:
    return uuid4().hex[:8]


async def send(client, headers, message: str, category: str = "bug", **extra) -> dict:
    response = await client.post(
        "/api/feedback",
        headers=headers | {"User-Agent": "Mozilla/5.0 (Test) Feedback"},
        json=CONTEXT | {"category": category, "message": message} | extra,
    )
    assert response.status_code == 201, response.text
    return response.json()


async def admin(client, caplog) -> dict[str, str]:
    return await login(
        client, caplog, f"fb-admin-{_tag()}@example.org", Grant(relation=Relation.ADMIN)
    )


async def listed(client, headers, **params) -> list[dict]:
    response = await client.get(
        "/api/admin/feedback", headers=headers, params={"limit": 100} | params
    )
    assert response.status_code == 200, response.text
    return response.json()["items"]


def _mailed(caplog) -> list[str]:
    """The addresses the feedback mails went to (the log's record of each)."""
    return [r.args[1] for r in caplog.records if r.name == "app.mail" and r.args[0] == "feedback"]


async def _no_receivers() -> None:
    async with SessionLocal() as session:
        await session.execute(delete(Grant).where(Grant.relation == Relation.FEEDBACK_RECEIVER))
        await session.commit()


class TestSendFeedback:
    """Story S-9: signed in, from any page; what I did not type is taken along."""

    async def test_a_signed_in_person_sends_and_the_context_is_kept(self, client, caplog):
        tag = _tag()
        email = f"fb-{tag}@example.org"
        me = await login(client, caplog, email)
        sent = await send(client, me, f"The table is cut off {tag}")
        assert sent["category"] == "bug"

        rows = [
            r
            for r in await listed(client, await admin(client, caplog), q=tag)
            if tag in r["message"]
        ]
        assert len(rows) == 1
        row = rows[0]
        assert row["path"] == "/1-liga/2026?tab=table"
        assert row["locale"] == "de"
        assert row["app_version"] == "0.4.0-rc.2"
        assert (row["viewport_width"], row["viewport_height"]) == (412, 915)
        # The browser is the request's, read by the server — not typed.
        assert row["user_agent"] == "Mozilla/5.0 (Test) Feedback"
        # Who: the account's name and address, never typed.
        assert row["email"] == email
        assert row["name"]
        assert row["created_at"]
        assert row["handled"] is False

    async def test_a_guest_is_refused(self, client):
        response = await client.post(
            "/api/feedback", json=CONTEXT | {"category": "bug", "message": "hello"}
        )
        assert response.status_code == 401
        assert _problem_code(response) == "not-signed-in"

    async def test_the_message_is_required_and_capped(self, client, caplog):
        me = await login(client, caplog, f"fb-empty-{_tag()}@example.org")
        blank = await client.post(
            "/api/feedback", headers=me, json=CONTEXT | {"category": "bug", "message": "   "}
        )
        assert blank.status_code == 422
        assert _problem_code(blank) == "feedback-message-empty"

        long = await client.post(
            "/api/feedback", headers=me, json=CONTEXT | {"category": "bug", "message": "x" * 5001}
        )
        assert long.status_code == 422
        assert (
            await client.post(
                "/api/feedback",
                headers=me,
                json=CONTEXT | {"category": "bug", "message": "x" * 5000},
            )
        ).status_code == 201

    async def test_the_kind_is_a_closed_set(self, client, caplog):
        me = await login(client, caplog, f"fb-kind-{_tag()}@example.org")
        for category in ("bug", "feature", "question", "other"):
            assert (await send(client, me, "x", category))["category"] == category
        wrong = await client.post(
            "/api/feedback", headers=me, json=CONTEXT | {"category": "rant", "message": "x"}
        )
        assert wrong.status_code == 422

    async def test_the_page_is_an_address_inside_the_site(self, client, caplog):
        """The admin's list links to it: an outside address would be a link off the site."""
        me = await login(client, caplog, f"fb-path-{_tag()}@example.org")
        for path in ("https://evil.example.com/", "//evil.example.com/x", "/\\evil.example.com"):
            refused = await client.post(
                "/api/feedback",
                headers=me,
                json=CONTEXT | {"category": "bug", "message": "x", "path": path},
            )
            assert refused.status_code == 422, path
        assert (await send(client, me, "x", path="/"))["category"] == "bug"

    async def test_ending_my_account_erases_what_i_sent(self, client, caplog):
        """S-9 with Z-7: a message is written by me and may say anything about me."""
        tag = _tag()
        me = await login(client, caplog, f"fb-end-{tag}@example.org")
        await send(client, me, f"Erase me {tag}")
        assert (await client.delete("/api/auth/me", headers=me)).status_code == 204
        rows = await listed(client, await admin(client, caplog), q=tag)
        assert not [r for r in rows if tag in r["message"]]


class TestReadFeedback:
    """Story A-15: the site's admin reads it, newest first, filtered on the server, and
    marks it handled."""

    async def test_only_the_site_admin_reads(self, client, caplog):
        club = (await world()).club
        for who, grants in {
            "nobody": (),
            "editor": (Grant(relation=Relation.EDITOR),),
            "club-admin": (Grant(relation=Relation.ADMIN, club_id=club),),
        }.items():
            headers = await login(client, caplog, f"fb-{who}-{_tag()}@example.org", *grants)
            response = await client.get("/api/admin/feedback", headers=headers)
            assert response.status_code == 403, who
        assert (await client.get("/api/admin/feedback")).status_code == 401

    async def test_newest_first_and_filtered_by_kind_and_handled(self, client, caplog):
        tag = _tag()
        me = await login(client, caplog, f"fb-order-{tag}@example.org")
        first = await send(client, me, f"first {tag}", "feature")
        second = await send(client, me, f"second {tag}", "question")
        office = await admin(client, caplog)

        mine = [r["id"] for r in await listed(client, office, q=tag) if tag in r["message"]]
        assert mine == [second["id"], first["id"]]

        questions = await listed(client, office, category="question", q=tag)
        assert {r["category"] for r in questions} == {"question"}
        assert second["id"] in [r["id"] for r in questions]
        assert first["id"] not in [r["id"] for r in questions]

        marked = await client.patch(
            f"/api/admin/feedback/{first['id']}", headers=office, json={"handled": True}
        )
        assert marked.status_code == 200, marked.text
        assert marked.json()["handled"] is True
        open_ids = [r["id"] for r in await listed(client, office, handled=False, q=tag)]
        assert first["id"] not in open_ids and second["id"] in open_ids
        assert first["id"] in [r["id"] for r in await listed(client, office, handled=True, q=tag)]

        reopened = await client.patch(
            f"/api/admin/feedback/{first['id']}", headers=office, json={"handled": False}
        )
        assert reopened.json()["handled"] is False

    async def test_marking_is_the_admins_alone(self, client, caplog):
        me = await login(client, caplog, f"fb-mark-{_tag()}@example.org")
        sent = await send(client, me, "mine")
        response = await client.patch(
            f"/api/admin/feedback/{sent['id']}", headers=me, json={"handled": True}
        )
        assert response.status_code == 403
        missing = await client.patch(
            "/api/admin/feedback/987654321",
            headers=await admin(client, caplog),
            json={"handled": True},
        )
        assert missing.status_code == 404


class TestFeedbackReceivers:
    """Story A-15: the site's ``feedback_receiver`` — granted in *Access* like every site
    role — is mailed each new message and reads the list; nobody else is mailed."""

    async def test_only_receivers_are_mailed_and_none_means_no_mail(self, client, caplog):
        tag = _tag()
        await _no_receivers()
        office = await admin(client, caplog)
        me = await login(client, caplog, f"fb-sender-{tag}@example.org")

        caplog.clear()
        with caplog.at_level(logging.WARNING, logger="app.mail"):
            await send(client, me, f"nobody hears {tag}")
        assert _mailed(caplog) == []
        # Stored all the same.
        assert [r for r in await listed(client, office, q=tag) if tag in r["message"]]

        receiver_email = f"fb-receiver-{tag}@example.org"
        receiver = await login(client, caplog, receiver_email)
        granted = await client.post(
            "/api/auth/tuples",
            headers=office,
            json={"user": receiver_email, "relation": "feedback_receiver", "object": "site"},
        )
        assert granted.status_code == 201, granted.text

        caplog.clear()
        with caplog.at_level(logging.WARNING, logger="app.mail"):
            await send(client, me, f"someone hears {tag}")
        # The admin reads the list, but holds no tuple of its own: not mailed.
        assert _mailed(caplog) == [receiver_email]

        # The receiver reads and marks; a tuple on nothing else.
        rows = [r for r in await listed(client, receiver, q=tag) if tag in r["message"]]
        assert len(rows) == 2
        marked = await client.patch(
            f"/api/admin/feedback/{rows[0]['id']}", headers=receiver, json={"handled": True}
        )
        assert marked.status_code == 200, marked.text
        await _no_receivers()

    async def test_the_mail_carries_what_was_sent(self, client, caplog, monkeypatch):
        tag = _tag()
        await _no_receivers()
        receiver_email = f"fb-rcv-{tag}@example.org"
        await login(client, caplog, receiver_email, Grant(relation=Relation.FEEDBACK_RECEIVER))
        sender_email = f"fb-who-{tag}@example.org"
        me = await login(client, caplog, sender_email)

        sent: list[tuple[str, object]] = []

        async def deliver(email, mail, *, what, secret):
            sent.append((email, mail))

        monkeypatch.setattr("app.mail._deliver", deliver)
        await send(client, me, f"The table is cut off {tag}", "feature")
        assert [email for email, _ in sent] == [receiver_email]
        mail = sent[0][1]
        # German unless the reader's language is known (`MAIL_LOCALE`).
        assert "Wunsch" in mail.subject
        for part in (
            f"The table is cut off {tag}",
            "/1-liga/2026?tab=table",
            sender_email,
            "0.4.0-rc.2",
            "412×915",
            "Mozilla/5.0 (Test) Feedback",
        ):
            assert part in mail.body, part
        await _no_receivers()
