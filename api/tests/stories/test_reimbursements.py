"""Reimbursements (Stories VA-12, F-2, F-3, F-4, F-5, F-6): a claim on an event or a club,
decided and paid by that event's or club's manager or treasurer.

Every test builds its own host club, its own event and its own people, so no count here
depends on what another story did to the seed (docs/gotchas).
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from datetime import date
from uuid import uuid4

from PIL import Image
from sqlalchemy import select

from app.db import SessionLocal
from app.models import AuditLog, Club, Event, Series
from app.models.auth import Grant, Relation, Role, User
from tests.stories.test_login_and_roles import _headers, _problem_code

IBAN = "DE89370400440532013000"


def _png() -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (8, 8), "white").save(out, format="PNG")
    return out.getvalue()


async def person(email: str, *grants: Grant) -> int:
    """An account holding exactly these tuples (an old one of that address goes first)."""
    async with SessionLocal() as session:
        old = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if old is not None:
            await session.delete(old)
            await session.commit()
        user = User(email=email, display_name=email.split("@")[0], grants=list(grants))
        session.add(user)
        await session.commit()
        return user.id


@dataclass
class World:
    club: int
    other_club: int
    series: int
    event: int
    orphan_event: int  # no host club


async def world() -> World:
    tag = uuid4().hex[:6]
    async with SessionLocal() as session:
        club = Club(slug=f"host-{tag}", name=f"Host {tag}", short_name="HST")
        other = Club(slug=f"other-{tag}", name=f"Other {tag}", short_name="OTH")
        series = Series(slug=f"s-{tag}", name=f"Series {tag}", short_name="S")
        session.add_all([club, other, series])
        await session.flush()
        event = Event(
            slug=f"e-{tag}",
            title=f"Act {tag}",
            host_club_id=club.id,
            series_id=series.id,
            starts_on=date(2026, 6, 1),
        )
        orphan = Event(slug=f"o-{tag}", title=f"Orphan {tag}")
        session.add_all([event, orphan])
        await session.commit()
        return World(club.id, other.id, series.id, event.id, orphan.id)


async def login(client, caplog, email: str, *grants: Grant) -> dict[str, str]:
    await person(email, *grants)
    return await _headers(client, caplog, email)


async def bank(client, headers) -> None:
    response = await client.put(
        "/api/me/bank-account",
        headers=headers,
        json={"holder": "Hel Per", "iban": IBAN},
    )
    assert response.status_code == 200, response.text


async def draft(client, headers, *, event: int | None = None, club: int | None = None) -> dict:
    body = {"title": "Travel", "event_id": event, "club_id": club}
    response = await client.post("/api/claims", headers=headers, json=body)
    assert response.status_code == 201, response.text
    return response.json()


async def add_item(client, headers, claim_id: int, **fields) -> dict:
    body = {"kind": "meals", "incurred_on": "2026-06-01", "description": "Lunch"} | fields
    response = await client.post(f"/api/claims/{claim_id}/items", headers=headers, json=body)
    assert response.status_code == 200, response.text
    return response.json()


async def submitted(client, headers, *, event: int | None = None, club: int | None = None) -> dict:
    """A claim of 12.50 € in meals, submitted."""
    await bank(client, headers)
    claim = await draft(client, headers, event=event, club=club)
    await add_item(client, headers, claim["id"], amount_cents=1250)
    response = await client.post(f"/api/claims/{claim['id']}/submit", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


class TestHelperRelation:
    """Story VA-12: `helper` is a tuple on an event, and it grants nothing but a claim."""

    def test_a_helper_holds_no_power_on_the_event(self):
        helper = User(
            email="h@example.org",
            display_name="h",
            grants=[Grant(relation=Relation.HELPER, event_id=31)],
        )
        event = Event(id=31, title="Act", host_club_id=11)

        assert helper.can(Relation.HELPER, on=event)
        for power in (
            Relation.MANAGER,
            Relation.RACE_OFFICER,
            Relation.JURY,
            Relation.TREASURER,
            Relation.ADMIN,
        ):
            assert not helper.can(power, on=event)
        assert helper.roles == {Role.HELPER}

    async def test_the_event_admin_names_a_helper_on_the_event_only(self, client, caplog):
        w = await world()
        admin = await login(
            client, caplog, f"adm-{uuid4().hex[:6]}@example.org", Grant(relation=Relation.ADMIN)
        )
        email = f"helper-{uuid4().hex[:6]}@example.org"
        await person(email)

        ok = await client.post(
            "/api/auth/tuples",
            headers=admin,
            json={"user": email, "relation": "helper", "object": f"event:{w.event}"},
        )
        assert ok.status_code == 201, ok.text
        on_series = await client.post(
            "/api/auth/tuples",
            headers=admin,
            json={"user": email, "relation": "helper", "object": f"series:{w.series}"},
        )
        assert on_series.status_code == 422
        assert _problem_code(on_series) == "tuple-relation-invalid"


class TestFilingAClaim:
    """Story F-2: who may file on an event or a club, and what submitting takes."""

    async def test_a_helper_files_on_the_event_and_the_host_club_pays(self, client, caplog):
        w = await world()
        me = await login(
            client,
            caplog,
            f"h-{uuid4().hex[:6]}@example.org",
            Grant(relation=Relation.HELPER, event_id=w.event),
        )

        targets = (await client.get("/api/me/claim-targets", headers=me)).json()
        assert {"kind": "event", "id": w.event} in [
            {"kind": t["kind"], "id": t["id"]} for t in targets
        ]

        claim = await submitted(client, me, event=w.event)
        assert claim["status"] == "submitted"
        assert claim["payer_club_id"] == w.club
        assert claim["claimed_cents"] == 1250
        # The account's bank details are copied onto the claim at submission.
        assert claim["iban"] == IBAN and claim["payee_name"] == "Hel Per"

    async def test_a_member_files_on_their_club(self, client, caplog):
        w = await world()
        me = await login(
            client,
            caplog,
            f"m-{uuid4().hex[:6]}@example.org",
            Grant(relation=Relation.MEMBER, club_id=w.club),
        )

        claim = await submitted(client, me, club=w.club)
        assert claim["club_id"] == w.club and claim["payer_club_id"] == w.club

    async def test_nobody_else_may_file(self, client, caplog):
        w = await world()
        # Member of another club; editor of the site (manager of every event by rewrite).
        me = await login(
            client,
            caplog,
            f"x-{uuid4().hex[:6]}@example.org",
            Grant(relation=Relation.MEMBER, club_id=w.other_club),
            Grant(relation=Relation.EDITOR),
        )
        for body in ({"event_id": w.event}, {"club_id": w.club}):
            response = await client.post("/api/claims", headers=me, json={"title": "x"} | body)
            assert response.status_code == 403
            assert _problem_code(response) == "claim-not-eligible"

    async def test_jury_of_the_series_may_file_on_its_events(self, client, caplog):
        w = await world()
        me = await login(
            client,
            caplog,
            f"j-{uuid4().hex[:6]}@example.org",
            Grant(relation=Relation.JURY, series_id=w.series),
        )
        assert (await draft(client, me, event=w.event))["status"] == "draft"

    async def test_an_event_without_a_host_club_takes_no_claim(self, client, caplog):
        w = await world()
        me = await login(
            client,
            caplog,
            f"o-{uuid4().hex[:6]}@example.org",
            Grant(relation=Relation.HELPER, event_id=w.orphan_event),
        )
        response = await client.post(
            "/api/claims", headers=me, json={"title": "x", "event_id": w.orphan_event}
        )
        assert _problem_code(response) == "event-has-no-host-club"

    async def test_a_claim_names_an_event_or_a_club_never_both(self, client, caplog):
        w = await world()
        me = await login(
            client,
            caplog,
            f"b-{uuid4().hex[:6]}@example.org",
            Grant(relation=Relation.MEMBER, club_id=w.club),
            Grant(relation=Relation.HELPER, event_id=w.event),
        )
        for body in ({"event_id": w.event, "club_id": w.club}, {}):
            response = await client.post("/api/claims", headers=me, json={"title": "x"} | body)
            assert response.status_code == 422

    async def test_submitting_needs_a_bank_account_and_an_item(self, client, caplog):
        w = await world()
        me = await login(
            client,
            caplog,
            f"n-{uuid4().hex[:6]}@example.org",
            Grant(relation=Relation.MEMBER, club_id=w.club),
        )
        claim = await draft(client, me, club=w.club)

        empty = await client.post(f"/api/claims/{claim['id']}/submit", headers=me)
        assert _problem_code(empty) == "claim-empty"

        await add_item(client, me, claim["id"], amount_cents=500)
        no_bank = await client.post(f"/api/claims/{claim['id']}/submit", headers=me)
        assert _problem_code(no_bank) == "bank-account-missing"

    async def test_a_car_item_is_kilometres_times_the_clubs_rate(self, client, caplog):
        w = await world()
        async with SessionLocal() as session:
            club = await session.get(Club, w.club)
            assert club is not None
            club.expense_policy = {"km_rate_cents": 35}
            await session.commit()
        me = await login(
            client,
            caplog,
            f"c-{uuid4().hex[:6]}@example.org",
            Grant(relation=Relation.MEMBER, club_id=w.club),
        )
        claim = await draft(client, me, club=w.club)

        out = await add_item(
            client, me, claim["id"], kind="travel_car", distance_km=120, description="Kiel and back"
        )
        item = out["items"][0]
        assert item["rate_cents"] == 35 and item["amount_cents"] == 4200

    async def test_a_submitted_claim_is_frozen_until_returned(self, client, caplog):
        w = await world()
        me = await login(
            client,
            caplog,
            f"f-{uuid4().hex[:6]}@example.org",
            Grant(relation=Relation.MEMBER, club_id=w.club),
        )
        claim = await submitted(client, me, club=w.club)

        response = await client.post(
            f"/api/claims/{claim['id']}/items",
            headers=me,
            json={
                "kind": "meals",
                "incurred_on": "2026-06-01",
                "description": "more",
                "amount_cents": 1,
            },
        )
        assert response.status_code == 409
        assert _problem_code(response) == "claim-not-editable"

        withdrawn = await client.post(f"/api/claims/{claim['id']}/withdraw", headers=me)
        assert withdrawn.json()["status"] == "withdrawn"


class TestDecidingAClaim:
    """Story F-3: the event's or club's manager or treasurer decides; never their own."""

    async def test_the_event_manager_and_the_host_clubs_treasurer_decide(self, client, caplog):
        w = await world()
        helper = await login(
            client,
            caplog,
            f"h-{uuid4().hex[:6]}@example.org",
            Grant(relation=Relation.HELPER, event_id=w.event),
        )
        manager = await login(
            client,
            caplog,
            f"em-{uuid4().hex[:6]}@example.org",
            Grant(relation=Relation.MANAGER, event_id=w.event),
        )
        treasurer = await login(
            client,
            caplog,
            f"t-{uuid4().hex[:6]}@example.org",
            Grant(relation=Relation.TREASURER, club_id=w.club),
        )

        first = await submitted(client, helper, event=w.event)
        approved = await client.post(
            f"/api/claims/{first['id']}/approve", headers=manager, json={"items": []}
        )
        assert approved.status_code == 200, approved.text
        assert approved.json()["status"] == "approved"

        second = await submitted(client, helper, event=w.event)
        returned = await client.post(
            f"/api/claims/{second['id']}/return",
            headers=treasurer,
            json={"note": "Please add the receipt."},
        )
        assert returned.json()["status"] == "returned"
        assert returned.json()["decision_note"] == "Please add the receipt."

        async with SessionLocal() as session:
            actions = (
                (
                    await session.execute(
                        select(AuditLog.action).where(
                            AuditLog.entity_type == "expense_claim",
                            AuditLog.entity_id == second["id"],
                        )
                    )
                )
                .scalars()
                .all()
            )
        assert "submitted" in actions and "returned" in actions

    async def test_the_club_manager_decides_a_club_claim(self, client, caplog):
        w = await world()
        member = await login(
            client,
            caplog,
            f"m-{uuid4().hex[:6]}@example.org",
            Grant(relation=Relation.MEMBER, club_id=w.club),
        )
        manager = await login(
            client,
            caplog,
            f"cm-{uuid4().hex[:6]}@example.org",
            Grant(relation=Relation.MANAGER, club_id=w.club),
        )
        claim = await submitted(client, member, club=w.club)

        rejected = await client.post(
            f"/api/claims/{claim['id']}/reject",
            headers=manager,
            json={"note": "Not a club expense."},
        )
        assert rejected.json()["status"] == "rejected"

    async def test_inherited_managers_do_not_hold_the_money(self, client, caplog):
        """A series' manager and the site's editor are managers of the event by rewrite,
        another club's manager is nothing — none of them decides its claims."""
        w = await world()
        helper = await login(
            client,
            caplog,
            f"h-{uuid4().hex[:6]}@example.org",
            Grant(relation=Relation.HELPER, event_id=w.event),
        )
        claim = await submitted(client, helper, event=w.event)
        for grant in (
            Grant(relation=Relation.MANAGER, series_id=w.series),
            Grant(relation=Relation.EDITOR),
            Grant(relation=Relation.MANAGER, club_id=w.other_club),
        ):
            outsider = await login(client, caplog, f"out-{uuid4().hex[:6]}@example.org", grant)
            response = await client.post(
                f"/api/claims/{claim['id']}/approve", headers=outsider, json={"items": []}
            )
            assert response.status_code == 403, grant.relation

    async def test_nobody_decides_their_own_claim(self, client, caplog):
        w = await world()
        both = await login(
            client,
            caplog,
            f"own-{uuid4().hex[:6]}@example.org",
            Grant(relation=Relation.MANAGER, event_id=w.event),
            Grant(relation=Relation.TREASURER, club_id=w.club),
        )
        claim = await submitted(client, both, event=w.event)

        response = await client.post(
            f"/api/claims/{claim['id']}/approve", headers=both, json={"items": []}
        )
        assert response.status_code == 403
        assert _problem_code(response) == "claim-own-decision"

    async def test_approval_may_lower_an_item_never_raise_it(self, client, caplog):
        w = await world()
        member = await login(
            client,
            caplog,
            f"m-{uuid4().hex[:6]}@example.org",
            Grant(relation=Relation.MEMBER, club_id=w.club),
        )
        treasurer = await login(
            client,
            caplog,
            f"t-{uuid4().hex[:6]}@example.org",
            Grant(relation=Relation.TREASURER, club_id=w.club),
        )
        claim = await submitted(client, member, club=w.club)
        item = claim["items"][0]["id"]

        too_much = await client.post(
            f"/api/claims/{claim['id']}/approve",
            headers=treasurer,
            json={"items": [{"item_id": item, "approved_cents": 9999}]},
        )
        assert too_much.status_code == 422

        cut = await client.post(
            f"/api/claims/{claim['id']}/approve",
            headers=treasurer,
            json={"items": [{"item_id": item, "approved_cents": 1000}]},
        )
        assert cut.json()["approved_cents"] == 1000


class TestPayingAClaim:
    """Story F-4: "mark as paid" is one settled payment over what is open."""

    async def test_mark_as_paid_settles_the_claim(self, client, caplog):
        w = await world()
        member = await login(
            client,
            caplog,
            f"m-{uuid4().hex[:6]}@example.org",
            Grant(relation=Relation.MEMBER, club_id=w.club),
        )
        manager = await login(
            client,
            caplog,
            f"cm-{uuid4().hex[:6]}@example.org",
            Grant(relation=Relation.MANAGER, club_id=w.club),
        )
        claim = await submitted(client, member, club=w.club)

        early = await client.post(f"/api/claims/{claim['id']}/pay", headers=manager, json={})
        assert _problem_code(early) == "claim-not-approved"

        await client.post(f"/api/claims/{claim['id']}/approve", headers=manager, json={"items": []})
        paid = await client.post(
            f"/api/claims/{claim['id']}/pay", headers=manager, json={"reference": "Act 3 meals"}
        )
        assert paid.status_code == 200, paid.text
        assert paid.json()["payment_state"] == "paid"
        assert paid.json()["paid_cents"] == 1250

        again = await client.post(f"/api/claims/{claim['id']}/pay", headers=manager, json={})
        assert _problem_code(again) == "claim-already-paid"


class TestClaimDocuments:
    """Story F-5: receipts on a claim, frozen at submission, read by claimant and decider."""

    async def test_receipts_are_uploaded_required_and_read_by_the_decider(self, client, caplog):
        w = await world()
        member = await login(
            client,
            caplog,
            f"m-{uuid4().hex[:6]}@example.org",
            Grant(relation=Relation.MEMBER, club_id=w.club),
        )
        manager = await login(
            client,
            caplog,
            f"cm-{uuid4().hex[:6]}@example.org",
            Grant(relation=Relation.MANAGER, club_id=w.club),
        )
        stranger = await login(
            client,
            caplog,
            f"s-{uuid4().hex[:6]}@example.org",
            Grant(relation=Relation.MEMBER, club_id=w.club),
        )
        await bank(client, member)
        claim = await draft(client, member, club=w.club)
        out = await add_item(
            client,
            member,
            claim["id"],
            kind="accommodation",
            description="Hotel",
            amount_cents=9000,
        )
        item = out["items"][0]["id"]

        missing = await client.post(f"/api/claims/{claim['id']}/submit", headers=member)
        assert _problem_code(missing) == "expense-document-missing"
        assert missing.json()["item_ids"] == [item]

        fake = await client.post(
            f"/api/claims/{claim['id']}/documents",
            headers=member,
            files={"file": ("x.pdf", b"not a pdf", "application/pdf")},
        )
        assert fake.status_code == 422

        uploaded = await client.post(
            f"/api/claims/{claim['id']}/documents",
            headers=member,
            data={"item_id": str(item)},
            files={"file": ("hotel.png", _png(), "image/png")},
        )
        assert uploaded.status_code == 200, uploaded.text
        doc = uploaded.json()["documents"][0]
        assert doc["original_name"] == "hotel.png" and doc["item_id"] == item

        assert (
            await client.post(f"/api/claims/{claim['id']}/submit", headers=member)
        ).status_code == 200
        frozen = await client.delete(
            f"/api/claims/{claim['id']}/documents/{doc['id']}", headers=member
        )
        assert _problem_code(frozen) == "claim-not-editable"

        url = f"/api/claims/{claim['id']}/documents/{doc['id']}"
        assert (await client.get(url, headers=member)).status_code == 200
        assert (await client.get(url, headers=manager)).content == _png()
        assert (await client.get(url, headers=stranger)).status_code == 403


class TestPendingList:
    """Story F-6: one list of what waits for the person — to decide, or to pay."""

    async def test_the_list_holds_what_is_mine_to_decide_or_pay(self, client, caplog):
        w = await world()
        member = await login(
            client,
            caplog,
            f"m-{uuid4().hex[:6]}@example.org",
            Grant(relation=Relation.MEMBER, club_id=w.club),
        )
        treasurer = await login(
            client,
            caplog,
            f"t-{uuid4().hex[:6]}@example.org",
            Grant(relation=Relation.TREASURER, club_id=w.club),
            Grant(relation=Relation.MEMBER, club_id=w.club),
        )
        other = await login(
            client,
            caplog,
            f"o-{uuid4().hex[:6]}@example.org",
            Grant(relation=Relation.TREASURER, club_id=w.other_club),
        )

        to_decide = await submitted(client, member, club=w.club)
        to_pay = await submitted(client, member, club=w.club)
        await client.post(
            f"/api/claims/{to_pay['id']}/approve", headers=treasurer, json={"items": []}
        )
        await draft(client, member, club=w.club)  # a draft is the claimant's own
        await submitted(client, treasurer, club=w.club)  # their own: not theirs to decide

        rows = (await client.get("/api/claims/pending", headers=treasurer)).json()
        assert {(r["id"], r["action"]) for r in rows} == {
            (to_decide["id"], "decide"),
            (to_pay["id"], "pay"),
        }
        assert (await client.get("/api/claims/pending", headers=other)).json() == []
