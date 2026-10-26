"""Reimbursements (Stories VA-12, F-2, F-3, F-4, F-5, F-6): a claim on an event or a club,
decided and paid by that event's manager or treasurer, or the club's treasurer.

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
from tests.accounts import account
from tests.stories.test_login_and_roles import _headers, _problem_code

IBAN = "DE89370400440532013000"


def _png() -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (8, 8), "white").save(out, format="PNG")
    return out.getvalue()


async def person(email: str, *grants: Grant) -> int:
    """An account holding exactly these tuples (an old one of that address goes first); a
    club's ``member`` among them is its person's membership (`tests/accounts.py`)."""
    return await account(email, *grants)


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


async def _title_tag(event_id: int) -> str:
    async with SessionLocal() as session:
        return (await session.get(Event, event_id)).title.removeprefix("Orphan ")


async def login(client, caplog, email: str, *grants: Grant) -> dict[str, str]:
    await person(email, *grants)
    return await _headers(client, caplog, email)


async def bank(client, headers, iban: str = IBAN) -> None:
    response = await client.put(
        "/api/me/bank-account",
        headers=headers,
        json={"holder": "Hel Per", "iban": iban},
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


async def submitted(
    client, headers, *, event: int | None = None, club: int | None = None, iban: str = IBAN
) -> dict:
    """A claim of 12.50 € in meals, submitted."""
    await bank(client, headers, iban)
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

        targets = (await client.get("/api/me/claim-targets", headers=me)).json()["targets"]
        assert {"kind": "event", "id": w.event} in [
            {"kind": t["kind"], "id": t["id"]} for t in targets
        ]

        claim = await submitted(client, me, event=w.event)
        assert claim["status"] == "submitted"
        assert claim["payer_club_id"] == w.club
        assert claim["claimed_cents"] == 1250
        # The account's bank details are copied onto the claim at submission.
        assert claim["iban"] == IBAN and claim["payee_name"] == "Hel Per"

    async def test_the_jury_of_an_event_without_a_host_is_told_why(self, client, caplog):
        """Story F-2: working at an event that has no host club yet is no target — and the
        page is told what the person is there and why, so it need not say "no role"."""
        w = await world()
        me = await login(
            client,
            caplog,
            f"j-{uuid4().hex[:6]}@example.org",
            Grant(relation=Relation.JURY, event_id=w.orphan_event),
        )
        body = (await client.get("/api/me/claim-targets", headers=me)).json()
        assert body["targets"] == []
        assert body["unavailable"] == [
            {
                "id": w.orphan_event,
                "name": f"Orphan {(await _title_tag(w.orphan_event))}",
                "starts_on": None,
                "relations": ["jury"],
                "reason": "no_host_club",
            }
        ]

    async def test_work_the_host_does_not_pay_for_is_told_too(self, client, caplog):
        """Story F-2: the host club's rules leave helpers out — the helper is told that,
        not that they hold nothing."""
        w = await world()
        async with SessionLocal() as session:
            club = await session.get(Club, w.club)
            club.expense_policy = {"eligible": ["race_officer", "jury", "manager"]}
            await session.commit()
        me = await login(
            client,
            caplog,
            f"h-{uuid4().hex[:6]}@example.org",
            Grant(relation=Relation.HELPER, event_id=w.event),
        )
        body = (await client.get("/api/me/claim-targets", headers=me)).json()
        assert body["targets"] == []
        assert [(u["id"], u["relations"], u["reason"]) for u in body["unavailable"]] == [
            (w.event, ["helper"], "not_covered")
        ]

    async def test_someone_who_works_nowhere_has_nothing_unavailable(self, client, caplog):
        """Story F-2: a club's member has the club to claim on, and no event to explain."""
        w = await world()
        me = await login(
            client,
            caplog,
            f"m-{uuid4().hex[:6]}@example.org",
            Grant(relation=Relation.MEMBER, club_id=w.club),
        )
        body = (await client.get("/api/me/claim-targets", headers=me)).json()
        assert [(t["kind"], t["id"]) for t in body["targets"]] == [("club", w.club)]
        assert body["unavailable"] == []

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

    async def test_a_submitted_claim_changed_is_a_draft_again(self, client, caplog):
        """Story F-2 (2026-10-24): the claimant changes a submitted claim — an item added,
        one changed — and it is a draft again, to be submitted again."""
        w = await world()
        me = await login(
            client,
            caplog,
            f"f-{uuid4().hex[:6]}@example.org",
            Grant(relation=Relation.MEMBER, club_id=w.club),
        )
        claim = await submitted(client, me, club=w.club)
        # A member files on their club, and the club pays.
        assert claim["club_id"] == w.club and claim["payer_club_id"] == w.club

        changed = await add_item(client, me, claim["id"], amount_cents=1, description="more")
        assert changed["status"] == "draft"
        assert changed["may_edit"] is True
        item = changed["items"][0]["id"]
        corrected = await client.put(
            f"/api/claims/{claim['id']}/items/{item}",
            headers=me,
            json={
                "kind": "per_diem",
                "incurred_on": "2026-06-05",
                "incurred_until": "2026-06-07",
                "description": "Three days",
                "amount_cents": 4200,
            },
        )
        assert corrected.status_code == 200, corrected.text
        hotel = next(i for i in corrected.json()["items"] if i["id"] == item)
        assert hotel["incurred_until"] == "2026-06-07" and hotel["amount_cents"] == 4200

        again = await client.post(f"/api/claims/{claim['id']}/submit", headers=me)
        assert again.json()["status"] == "submitted"
        withdrawn = await client.post(f"/api/claims/{claim['id']}/withdraw", headers=me)
        assert withdrawn.json()["status"] == "withdrawn"

    async def test_a_claim_submitted_once_is_withdrawn_never_deleted(self, client, caplog):
        """Story F-2: a change makes a submitted claim a draft again, but it stays on record
        — deleting it is refused, it is withdrawn instead, and the books leave the draft
        out until it is submitted again."""
        from app.services import payments

        w = await world()
        me = await login(
            client,
            caplog,
            f"f-{uuid4().hex[:6]}@example.org",
            Grant(relation=Relation.MEMBER, club_id=w.club),
        )
        claim = await submitted(client, me, club=w.club)
        await add_item(client, me, claim["id"], amount_cents=1, description="more")

        async with SessionLocal() as session:
            books = await payments.claims_for_books(session, w.club, date.today().year)
        assert claim["id"] not in {c.id for c in books}

        refused = await client.delete(f"/api/claims/{claim['id']}", headers=me)
        assert refused.status_code == 409
        assert _problem_code(refused) == "claim-was-submitted"
        withdrawn = await client.post(f"/api/claims/{claim['id']}/withdraw", headers=me)
        assert withdrawn.json()["status"] == "withdrawn"

        never = await draft(client, me, club=w.club)
        assert (await client.delete(f"/api/claims/{never['id']}", headers=me)).status_code == 204

    async def test_a_range_of_dates_ends_after_it_begins(self, client, caplog):
        """Story F-2: an item is a day or a range; a range of one day is that day."""
        w = await world()
        me = await login(
            client,
            caplog,
            f"r-{uuid4().hex[:6]}@example.org",
            Grant(relation=Relation.MEMBER, club_id=w.club),
        )
        claim = await draft(client, me, club=w.club)
        one_day = await add_item(
            client, me, claim["id"], amount_cents=100, incurred_until="2026-06-01"
        )
        assert one_day["items"][0]["incurred_until"] is None
        backwards = await client.post(
            f"/api/claims/{claim['id']}/items",
            headers=me,
            json={
                "kind": "meals",
                "incurred_on": "2026-06-03",
                "incurred_until": "2026-06-01",
                "description": "x",
                "amount_cents": 1,
            },
        )
        assert backwards.status_code == 422
        assert _problem_code(backwards) == "expense-range-backwards"

    async def test_an_approved_claim_is_frozen(self, client, caplog):
        """Story F-2: only an approved claim (and a withdrawn one) is frozen."""
        w = await world()
        me = await login(
            client,
            caplog,
            f"z-{uuid4().hex[:6]}@example.org",
            Grant(relation=Relation.MEMBER, club_id=w.club),
        )
        treasurer = await login(
            client,
            caplog,
            f"zt-{uuid4().hex[:6]}@example.org",
            Grant(relation=Relation.TREASURER, club_id=w.club),
        )
        claim = await submitted(client, me, club=w.club)
        await client.post(f"/api/claims/{claim['id']}/approve", headers=treasurer, json={})
        response = await client.post(
            f"/api/claims/{claim['id']}/items",
            headers=me,
            json={
                "kind": "meals",
                "incurred_on": "2026-06-01",
                "description": "x",
                "amount_cents": 1,
            },
        )
        assert response.status_code == 409
        assert _problem_code(response) == "claim-not-editable"
        assert (
            await client.post(f"/api/claims/{claim['id']}/withdraw", headers=me)
        ).status_code == 409


class TestDecidingAClaim:
    """Story F-3: the event's manager or treasurer, or the club's treasurer, decides; never
    their own."""

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
        rejected = await client.post(
            f"/api/claims/{second['id']}/reject",
            headers=treasurer,
            json={"note": "Please add the receipt."},
        )
        assert rejected.json()["status"] == "rejected"
        assert rejected.json()["decision_note"] == "Please add the receipt."

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
        assert "submitted" in actions and "rejected" in actions

    async def test_the_treasurer_decides_a_club_claim_not_the_team_manager(self, client, caplog):
        """Decided 2026-10-26: a club's manager runs its squads, not its purse."""
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
            f"cm-{uuid4().hex[:6]}@example.org",
            Grant(relation=Relation.TREASURER, club_id=w.club),
        )
        team_manager = await login(
            client,
            caplog,
            f"tm-{uuid4().hex[:6]}@example.org",
            Grant(relation=Relation.MANAGER, club_id=w.club),
        )
        claim = await submitted(client, member, club=w.club)

        refused = await client.post(
            f"/api/claims/{claim['id']}/reject", headers=team_manager, json={"note": "x"}
        )
        assert refused.status_code == 403
        rejected = await client.post(
            f"/api/claims/{claim['id']}/reject",
            headers=treasurer,
            json={"note": "Not a club expense."},
        )
        assert rejected.json()["status"] == "rejected"

    async def test_inherited_managers_do_not_hold_the_money(self, client, caplog):
        """A series' manager and the site's editor are managers of the event by rewrite,
        the host club's manager is its team manager (2026-10-26), another club's manager is
        nothing — none of them decides its claims."""
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
            Grant(relation=Relation.MANAGER, club_id=w.club),
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

    async def test_the_decider_changes_no_price_and_a_rejection_goes_round_again(
        self, client, caplog
    ):
        """Story F-3 (2026-10-24): the decider approves the claim as it stands or rejects
        it with a message; the claimant is told, corrects it and submits again, and the
        decider is told again. Neither ever touches the other's part."""
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

        async def needs(headers) -> dict[str, int]:
            space = (await client.get("/api/me/contexts", headers=headers)).json()
            club = next(c for c in space["contexts"] if c["kind"] == "club" and c["id"] == w.club)
            return {n["code"]: n["count"] for n in club["needs"]}

        assert (await needs(treasurer)).get("claims") == 1
        # The decider cannot change a price, not even by the claimant's own route.
        cut = await client.put(
            f"/api/claims/{claim['id']}/items/{item}",
            headers=treasurer,
            json={
                "kind": "meals",
                "incurred_on": "2026-06-01",
                "description": "x",
                "amount_cents": 1,
            },
        )
        assert cut.status_code == 403

        rejected = await client.post(
            f"/api/claims/{claim['id']}/reject", headers=treasurer, json={"note": "Lunch was 9,50"}
        )
        assert rejected.json()["status"] == "rejected"
        assert (await needs(member)).get("claim_rejected") == 1
        assert "claims" not in await needs(treasurer)

        fixed = await client.put(
            f"/api/claims/{claim['id']}/items/{item}",
            headers=member,
            json={
                "kind": "meals",
                "incurred_on": "2026-06-01",
                "description": "Lunch",
                "amount_cents": 950,
            },
        )
        assert fixed.json()["status"] == "draft"
        # The message stays readable while the claimant corrects the claim.
        assert fixed.json()["decision_note"] == "Lunch was 9,50"
        assert "claim_rejected" not in await needs(member)
        again = await client.post(f"/api/claims/{claim['id']}/submit", headers=member)
        assert again.json()["status"] == "submitted" and again.json()["decision_note"] is None
        assert (await needs(treasurer)).get("claims") == 1

        approved = await client.post(
            f"/api/claims/{claim['id']}/approve", headers=treasurer, json={}
        )
        assert approved.json()["approved_cents"] == 950

    async def test_approving_checks_the_receipts_again(self, client, caplog):
        """Story F-3: the receipts the paying club wants are checked when approving too —
        the club's rules may have changed since the claim was submitted."""
        w = await world()
        member = await login(
            client,
            caplog,
            f"rc-{uuid4().hex[:6]}@example.org",
            Grant(relation=Relation.MEMBER, club_id=w.club),
        )
        treasurer = await login(
            client,
            caplog,
            f"rct-{uuid4().hex[:6]}@example.org",
            Grant(relation=Relation.TREASURER, club_id=w.club),
        )
        claim = await submitted(client, member, club=w.club)
        async with SessionLocal() as session:
            club = await session.get(Club, w.club)
            club.expense_policy = {"document_required": ["meals"]}
            await session.commit()
        refused = await client.post(
            f"/api/claims/{claim['id']}/approve", headers=treasurer, json={}
        )
        assert refused.status_code == 422
        assert _problem_code(refused) == "expense-document-missing"


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
        treasurer = await login(
            client,
            caplog,
            f"cm-{uuid4().hex[:6]}@example.org",
            Grant(relation=Relation.TREASURER, club_id=w.club),
        )
        claim = await submitted(client, member, club=w.club)

        early = await client.post(f"/api/claims/{claim['id']}/pay", headers=treasurer, json={})
        assert _problem_code(early) == "claim-not-approved"

        await client.post(f"/api/claims/{claim['id']}/approve", headers=treasurer, json={"items": []})
        paid = await client.post(
            f"/api/claims/{claim['id']}/pay", headers=treasurer, json={"reference": "Act 3 meals"}
        )
        assert paid.status_code == 200, paid.text
        assert paid.json()["payment_state"] == "paid"
        assert paid.json()["paid_cents"] == 1250

        again = await client.post(f"/api/claims/{claim['id']}/pay", headers=treasurer, json={})
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
        treasurer = await login(
            client,
            caplog,
            f"cm-{uuid4().hex[:6]}@example.org",
            Grant(relation=Relation.TREASURER, club_id=w.club),
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
        url = f"/api/claims/{claim['id']}/documents/{doc['id']}"
        assert (await client.get(url, headers=member)).status_code == 200
        assert (await client.get(url, headers=treasurer)).content == _png()
        assert (await client.get(url, headers=stranger)).status_code == 403

        # Until approved the claimant may still change the receipts — and the claim is a
        # draft again, to be submitted again (Story F-5, 2026-10-24).
        removed = await client.delete(url, headers=member)
        assert removed.status_code == 200, removed.text
        assert removed.json()["status"] == "draft" and removed.json()["documents"] == []


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
