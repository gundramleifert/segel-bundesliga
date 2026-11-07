"""Stories JU-1 to JU-5: the jury organizer keeps the league's pool of judges, asks them
for events, and whom they approve is the event's jury.

Each test signs in fresh addresses (docs/gotchas: counts against seed rows); the events
are the seed's 1. Liga 2027 drafts, still planned, and a 2026 act that is over. Without
SBL_SMTP_HOST a mail goes to the log; the tests read who got one there.
"""

import logging
from uuid import uuid4

from app.models.auth import Grant, Relation
from tests.accounts import account
from tests.stories.test_join_with_consent import _todo
from tests.stories.test_login_and_roles import _headers, _problem_code

KIEL = "dsbl-1-2027-kiel-strande"
HAMBURG = "dsbl-1-2027-hamburg-alster"
OVER = "dsbl-1-2026-act-2"


def _address(what: str) -> str:
    return f"ju-{what}-{uuid4().hex[:8]}@example.org"


async def _organizer(client, caplog) -> dict[str, str]:
    email = _address("orga")
    await account(email, Grant(relation=Relation.JURY_ORGANIZER))
    return await _headers(client, caplog, email)


async def _judge(client, caplog, organizer, name: str = "Judge") -> tuple[int, str, dict[str, str]]:
    """A fresh account the organizer puts in the pool: its id, address and headers."""
    email = _address("judge")
    user_id = await account(email, display_name=f"{name} {uuid4().hex[:6]}")
    response = await client.post("/api/jury/judges", headers=organizer, json={"user_id": user_id})
    assert response.status_code == 201, response.text
    return user_id, email, await _headers(client, caplog, email)


async def _pool(client, organizer, **params) -> dict[int, dict]:
    response = await client.get(
        "/api/jury/judges", headers=organizer, params={"limit": 100, **params}
    )
    assert response.status_code == 200, response.text
    return {j["user_id"]: j for j in response.json()["items"]}


async def _mine(client, headers) -> dict:
    response = await client.get("/api/me/jury", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def _mailed(caplog) -> list[str]:
    """The addresses the jury's mails went to (the log's record of each)."""
    return [r.args[1] for r in caplog.records if r.name == "app.mail" and "jury" in str(r.args[0])]


class TestThePool:
    async def test_the_jury_organizer_says_who_is_a_judge(self, client, caplog):
        """JU-1: the organizer finds an account, puts it in the pool and takes it out —
        a `judge` tuple on the site, which grants nothing on any event."""
        organizer = await _organizer(client, caplog)
        email = _address("cand")
        user_id = await account(email, display_name=f"Kandidat {uuid4().hex[:6]}")

        found = await client.get("/api/jury/candidates", headers=organizer, params={"q": email})
        assert [c["user_id"] for c in found.json()["items"]] == [user_id]

        assert (
            await client.post("/api/jury/judges", headers=organizer, json={"user_id": user_id})
        ).status_code == 201
        assert user_id in await _pool(client, organizer, q=email)
        again = await client.post("/api/jury/judges", headers=organizer, json={"user_id": user_id})
        assert again.status_code == 409
        # In the pool, no longer a candidate.
        found = await client.get("/api/jury/candidates", headers=organizer, params={"q": email})
        assert found.json()["items"] == []

        judge = await _headers(client, caplog, email)
        assert (await _mine(client, judge))["judge"] is True
        # A judge has no league office.
        contexts = (await client.get("/api/me/contexts", headers=judge)).json()
        assert contexts["office"] is None
        # *Me › Jury* is theirs: `judge` is a relation of the *Me* card.
        assert contexts["me"]["relations"] == ["judge"]

        assert (
            await client.delete(f"/api/jury/judges/{user_id}", headers=organizer)
        ).status_code == 204
        assert user_id not in await _pool(client, organizer, q=email)
        assert (await _mine(client, judge))["judge"] is False

    async def test_the_organizer_has_the_jury_section_of_the_office(self, client, caplog):
        """JU-1: `jury_organizer` opens the league office, its relation named there."""
        organizer = await _organizer(client, caplog)
        office = (await client.get("/api/me/contexts", headers=organizer)).json()["office"]
        assert office["relations"] == ["jury_organizer"]

    async def test_nobody_else_keeps_the_pool(self, client, caplog, ids):
        """JU-1: an event's jury, or a judge, is no jury organizer."""
        email = _address("eventjury")
        await account(email, Grant(relation=Relation.JURY, event_id=ids.event(KIEL)))
        jury = await _headers(client, caplog, email)
        organizer = await _organizer(client, caplog)
        _, _, judge = await _judge(client, caplog, organizer)
        for headers in (jury, judge):
            assert (await client.get("/api/jury/judges", headers=headers)).status_code == 403
            response = await client.post(
                "/api/jury/invitations",
                headers=headers,
                json={"event_ids": [ids.event(KIEL)], "user_ids": []},
            )
            assert response.status_code == 403

    async def test_leaving_the_pool_withdraws_open_requests_but_not_a_jury(
        self, client, caplog, ids
    ):
        """JU-1: an open request goes with the judge; an approved event stays theirs."""
        organizer = await _organizer(client, caplog)
        user_id, _, judge = await _judge(client, caplog, organizer)
        kiel, hamburg = ids.event(KIEL), ids.event(HAMBURG)
        await client.post(
            "/api/jury/invitations",
            headers=organizer,
            json={"event_ids": [kiel, hamburg], "user_ids": [user_id]},
        )
        assert (
            await client.put(f"/api/jury/events/{kiel}/judges/{user_id}", headers=organizer)
        ).status_code == 200

        assert (
            await client.delete(f"/api/jury/judges/{user_id}", headers=organizer)
        ).status_code == 204
        requests = {r["event"]["id"]: r["state"] for r in (await _mine(client, judge))["requests"]}
        assert requests == {kiel: "approved"}


class TestLicences:
    async def test_a_judge_says_which_licences_they_hold(self, client, caplog):
        """JU-2: the judge's own word — saved by them, shown and filtered by in the pool."""
        organizer = await _organizer(client, caplog)
        user_id, email, judge = await _judge(client, caplog, organizer)
        assert (await _mine(client, judge))["licences"] == []

        response = await client.put(
            "/api/me/jury/licences", headers=judge, json={"licences": ["umpire", "national_judge"]}
        )
        assert response.status_code == 200, response.text
        assert sorted((await _mine(client, judge))["licences"]) == ["national_judge", "umpire"]

        pool = await _pool(client, organizer, q=email)
        assert sorted(pool[user_id]["licences"]) == ["national_judge", "umpire"]
        assert user_id in await _pool(client, organizer, q=email, licence="umpire")
        assert user_id not in await _pool(client, organizer, q=email, licence="regional_judge")

        # Taking one back is the judge's too.
        await client.put("/api/me/jury/licences", headers=judge, json={"licences": ["umpire"]})
        assert (await _mine(client, judge))["licences"] == ["umpire"]

    async def test_only_a_judge_states_licences(self, client, caplog):
        """JU-2: anyone else is refused."""
        email = _address("nojudge")
        await account(email)
        headers = await _headers(client, caplog, email)
        response = await client.put(
            "/api/me/jury/licences", headers=headers, json={"licences": ["umpire"]}
        )
        assert response.status_code == 403
        assert _problem_code(response) == "not-a-judge"


class TestAsking:
    async def test_many_events_and_judges_in_one_step_one_mail_each(self, client, caplog, ids):
        """JU-3: events × judges, a pair asked before left as it was, one mail per judge
        naming the events newly asked."""
        organizer = await _organizer(client, caplog)
        a, a_email, judge_a = await _judge(client, caplog, organizer)
        b, b_email, _ = await _judge(client, caplog, organizer)
        kiel, hamburg = ids.event(KIEL), ids.event(HAMBURG)

        await client.post(
            "/api/jury/invitations", headers=organizer, json={"event_ids": [kiel], "user_ids": [a]}
        )
        caplog.clear()
        with caplog.at_level(logging.WARNING, logger="app.mail"):
            response = await client.post(
                "/api/jury/invitations",
                headers=organizer,
                json={
                    "event_ids": [kiel, hamburg],
                    "user_ids": [a, b],
                    "note": "Bitte bis Freitag.",
                },
            )
        assert response.status_code == 200, response.text
        assert response.json() == {"created": 3, "existing": 1, "mailed": 2}
        assert sorted(_mailed(caplog)) == sorted([a_email, b_email])

        requests = {
            r["event"]["id"]: r["state"] for r in (await _mine(client, judge_a))["requests"]
        }
        assert requests == {kiel: "invited", hamburg: "invited"}

    async def test_an_event_over_or_someone_outside_the_pool_is_refused(self, client, caplog, ids):
        """JU-3: an event already over, and an account not in the pool."""
        organizer = await _organizer(client, caplog)
        judge, _, _ = await _judge(client, caplog, organizer)
        over = await client.post(
            "/api/jury/invitations",
            headers=organizer,
            json={"event_ids": [ids.event(OVER)], "user_ids": [judge]},
        )
        assert over.status_code == 409
        assert _problem_code(over) == "jury-event-closed"

        stranger = await account(_address("stranger"))
        response = await client.post(
            "/api/jury/invitations",
            headers=organizer,
            json={"event_ids": [ids.event(KIEL)], "user_ids": [stranger]},
        )
        assert response.status_code == 422
        assert _problem_code(response) == "not-a-judge"

    async def test_the_pool_filters_by_each_event_including_or_excluding(self, client, caplog, ids):
        """JU-3: each picked event's state per judge, and a filter on it — `<id>:<state>`,
        `!` excluding."""
        organizer = await _organizer(client, caplog)
        tag = uuid4().hex[:6]
        asked, _, asked_headers = await _judge(client, caplog, organizer, name=f"Asked {tag}")
        approved, _, _ = await _judge(client, caplog, organizer, name=f"Approved {tag}")
        never, _, _ = await _judge(client, caplog, organizer, name=f"Never {tag}")
        kiel, hamburg = ids.event(KIEL), ids.event(HAMBURG)
        await client.post(
            "/api/jury/invitations",
            headers=organizer,
            json={"event_ids": [kiel], "user_ids": [asked, approved]},
        )
        await client.put(
            f"/api/me/jury/requests/{kiel}", headers=asked_headers, json={"available": True}
        )
        await client.put(f"/api/jury/events/{hamburg}/judges/{approved}", headers=organizer)

        async def found(*event: str) -> set[int]:
            pool = await _pool(
                client, organizer, q=tag, events=f"{kiel},{hamburg}", event=",".join(event)
            )
            return set(pool)

        everyone = await _pool(client, organizer, q=tag, events=f"{kiel},{hamburg}")
        assert set(everyone) == {asked, approved, never}
        assert everyone[asked]["states"] == {str(kiel): "available"}
        assert everyone[approved]["states"] == {str(kiel): "invited", str(hamburg): "approved"}
        assert everyone[never]["states"] == {}

        assert await found(f"{kiel}:available") == {asked}
        assert await found(f"{kiel}:asked") == {asked, approved}
        assert await found(f"{kiel}:!asked") == {never}
        assert await found(f"{hamburg}:!approved") == {asked, never}
        # Several events combine: asked for Kiel, not approved for Hamburg.
        assert await found(f"{kiel}:asked", f"{hamburg}:!approved") == {asked}

        bad = await client.get(
            "/api/jury/judges", headers=organizer, params={"event": f"{kiel}:maybe"}
        )
        assert bad.status_code == 422

    async def test_the_events_offered_are_those_not_over(self, client, caplog, ids):
        """JU-3: drafts included, an event over not."""
        organizer = await _organizer(client, caplog)
        listed = {
            e["id"]
            for e in (
                await client.get("/api/jury/events", headers=organizer, params={"limit": 100})
            ).json()["items"]
        }
        assert ids.event(KIEL) in listed
        assert ids.event(OVER) not in listed

    async def test_the_organizer_writes_to_judges(self, client, caplog):
        """JU-3: a message to the judges ticked, one mail each — only to the pool."""
        organizer = await _organizer(client, caplog)
        a, a_email, _ = await _judge(client, caplog, organizer)
        caplog.clear()
        with caplog.at_level(logging.WARNING, logger="app.mail"):
            response = await client.post(
                "/api/jury/messages",
                headers=organizer,
                json={"user_ids": [a], "subject": "Schulung", "text": "Am 3. März in Kiel."},
            )
        assert response.status_code == 200, response.text
        assert response.json() == {"mailed": 1}
        assert _mailed(caplog) == [a_email]

        stranger = await account(_address("stranger"))
        response = await client.post(
            "/api/jury/messages",
            headers=organizer,
            json={"user_ids": [stranger], "subject": "x", "text": "y"},
        )
        assert _problem_code(response) == "not-a-judge"


class TestAnswering:
    async def test_a_judge_answers_and_may_change_until_approved(self, client, caplog, ids):
        """JU-4: available is the application, declined says no; an unanswered request is
        a to-do on Me; after approval the answer is the organizer's to change."""
        organizer = await _organizer(client, caplog)
        user_id, _, judge = await _judge(client, caplog, organizer)
        kiel = ids.event(KIEL)
        await client.post(
            "/api/jury/invitations",
            headers=organizer,
            json={"event_ids": [kiel], "user_ids": [user_id]},
        )
        assert await _todo(client, judge, "me", "jury_invited") == 1

        response = await client.put(
            f"/api/me/jury/requests/{kiel}", headers=judge, json={"available": False}
        )
        assert response.status_code == 200, response.text
        assert response.json()["state"] == "declined"
        assert await _todo(client, judge, "me", "jury_invited") == 0
        response = await client.put(
            f"/api/me/jury/requests/{kiel}", headers=judge, json={"available": True}
        )
        assert response.json()["state"] == "available"

        await client.put(f"/api/jury/events/{kiel}/judges/{user_id}", headers=organizer)
        late = await client.put(
            f"/api/me/jury/requests/{kiel}", headers=judge, json={"available": False}
        )
        assert late.status_code == 409
        assert _problem_code(late) == "jury-already-approved"

    async def test_only_a_request_that_exists(self, client, caplog, ids):
        """JU-4: an event nobody asked me for answers 404."""
        organizer = await _organizer(client, caplog)
        _, _, judge = await _judge(client, caplog, organizer)
        response = await client.put(
            f"/api/me/jury/requests/{ids.event(HAMBURG)}", headers=judge, json={"available": True}
        )
        assert response.status_code == 404


class TestApproving:
    async def test_the_approved_judge_is_the_event_jury_and_may_claim(self, client, caplog, ids):
        """JU-5: approving writes the event's `jury` tuple — the event in their space, a
        claim on it to the host club's treasurer — and mails the judge; taking them off
        deletes it."""
        organizer = await _organizer(client, caplog)
        user_id, email, judge = await _judge(client, caplog, organizer)
        kiel = ids.event(KIEL)
        await client.post(
            "/api/jury/invitations",
            headers=organizer,
            json={"event_ids": [kiel], "user_ids": [user_id]},
        )
        await client.put(f"/api/me/jury/requests/{kiel}", headers=judge, json={"available": True})

        caplog.clear()
        with caplog.at_level(logging.WARNING, logger="app.mail"):
            response = await client.put(
                f"/api/jury/events/{kiel}/judges/{user_id}", headers=organizer
            )
        assert response.status_code == 200, response.text
        assert response.json()["state"] == "approved"
        assert _mailed(caplog) == [email]

        contexts = (await client.get("/api/me/contexts", headers=judge)).json()["contexts"]
        event = next(c for c in contexts if c["kind"] == "event" and c["id"] == kiel)
        assert "jury" in event["relations"]
        targets = (await client.get("/api/me/claim-targets", headers=judge)).json()["targets"]
        assert {"kind": "event", "id": kiel} in [
            {"kind": t["kind"], "id": t["id"]} for t in targets
        ]

        # Approving twice keeps the one tuple.
        assert (
            await client.put(f"/api/jury/events/{kiel}/judges/{user_id}", headers=organizer)
        ).status_code == 200

        off = await client.delete(f"/api/jury/events/{kiel}/judges/{user_id}", headers=organizer)
        assert off.status_code == 200, off.text
        assert off.json()["state"] == "available"
        contexts = (await client.get("/api/me/contexts", headers=judge)).json()["contexts"]
        assert not any(c["kind"] == "event" and c["id"] == kiel for c in contexts)

    async def test_assigning_needs_no_request(self, client, caplog, ids):
        """JU-5: a judge agreed with on the phone is put on the event directly."""
        organizer = await _organizer(client, caplog)
        user_id, _, judge = await _judge(client, caplog, organizer)
        hamburg = ids.event(HAMBURG)
        response = await client.put(
            f"/api/jury/events/{hamburg}/judges/{user_id}", headers=organizer
        )
        assert response.status_code == 200, response.text
        requests = {r["event"]["id"]: r["state"] for r in (await _mine(client, judge))["requests"]}
        assert requests == {hamburg: "approved"}

    async def test_only_a_judge_and_not_on_an_event_over(self, client, caplog, ids):
        """JU-5: someone outside the pool, or an event over, is refused."""
        organizer = await _organizer(client, caplog)
        stranger = await account(_address("stranger"))
        response = await client.put(
            f"/api/jury/events/{ids.event(KIEL)}/judges/{stranger}", headers=organizer
        )
        assert _problem_code(response) == "not-a-judge"
        judge, _, _ = await _judge(client, caplog, organizer)
        response = await client.put(
            f"/api/jury/events/{ids.event(OVER)}/judges/{judge}", headers=organizer
        )
        assert _problem_code(response) == "jury-event-closed"
