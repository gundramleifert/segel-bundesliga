"""From a claim to the bank — the whole way, through the HTTP API.

Journey J-7 (``docs/journeys/money.md``) — each ``step(...)`` below is one of its steps, in
the table's order; Stories F-1, F-7, VA-12, S-6, F-2, F-5, F-6, F-3, F-8, F-4. Every step
is tested on its own elsewhere (``test_treasurer.py``, ``test_reimbursements.py``,
``test_payment_runs.py``, ``test_personal_space.py``); this test is the order: the
treasurer the club's admin names is the one who sees the claim, the account the helper
saves is the one the claim carries, the approval is what the run pays, and the bank's
answer is what the claim reads in the end.

A fresh club, event and people, so it runs beside the rest of the suite.
"""

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from uuid import uuid4

from app.models.auth import Grant, Relation
from tests.journeys import step
from tests.stories.test_login_and_roles import _headers, _problem_code, _write
from tests.stories.test_payment_runs import CLUB_IBAN, NS
from tests.stories.test_reimbursements import IBAN, World, _png, person, world

HOTEL = {
    "kind": "accommodation",
    "incurred_on": "2026-05-30",
    "incurred_until": "2026-06-01",
    "description": "Hotel, two nights",
    "amount_cents": 18000,
}


@dataclass
class Cast:
    w: World
    club_admin: dict[str, str]
    treasurer_email: str
    helper_email: str


async def _cast(client, caplog) -> Cast:
    """The start: a club hosting an event (Journeys J-1, J-4 make one), its admin, and
    two people with accounts — the treasurer to be and a helper of the day. The club and
    the event are arranged in the database because neither is this journey's."""
    w = await world()
    tag = uuid4().hex[:6]
    await person(f"chair-{tag}@example.org", Grant(relation=Relation.ADMIN, club_id=w.club))
    club_admin = await _headers(client, caplog, f"chair-{tag}@example.org")
    cast = Cast(w, club_admin, f"purse-{tag}@example.org", f"rib-{tag}@example.org")
    await person(cast.treasurer_email)
    await person(cast.helper_email)
    return cast


async def _names_the_treasurer(client, caplog, cast: Cast) -> dict[str, str]:
    await _write(client, cast.club_admin, cast.treasurer_email, "treasurer", f"club:{cast.w.club}")
    return await _headers(client, caplog, cast.treasurer_email)


async def _saves_the_clubs_account(client, cast: Cast, treasurer) -> None:
    saved = await client.put(
        f"/api/clubs/{cast.w.club}/bank-account",
        headers=treasurer,
        json={"holder": "Host Sailing Club", "iban": CLUB_IBAN},
    )
    assert saved.status_code == 200, saved.text


async def _names_the_helper(client, caplog, cast: Cast) -> dict[str, str]:
    await _write(client, cast.club_admin, cast.helper_email, "helper", f"event:{cast.w.event}")
    return await _headers(client, caplog, cast.helper_email)


async def _saves_their_account(client, helper) -> None:
    saved = await client.put(
        "/api/me/bank-account", headers=helper, json={"holder": "Rita Rib", "iban": IBAN}
    )
    assert saved.status_code == 200, saved.text


async def _starts_a_claim(client, cast: Cast, helper) -> dict:
    targets = (await client.get("/api/me/claim-targets", headers=helper)).json()
    assert ("event", cast.w.event) in {(t["kind"], t["id"]) for t in targets["targets"]}
    started = await client.post(
        "/api/claims", headers=helper, json={"title": "Act weekend", "event_id": cast.w.event}
    )
    assert started.status_code == 201, started.text
    claim_id = started.json()["id"]
    with_item = await client.post(f"/api/claims/{claim_id}/items", headers=helper, json=HOTEL)
    assert with_item.status_code == 200, with_item.text
    # A hotel needs its invoice: the host club's policy says so (the site's default).
    missing = await client.post(f"/api/claims/{claim_id}/submit", headers=helper)
    assert _problem_code(missing) == "expense-document-missing"
    return with_item.json()


async def _attaches_the_invoice(client, helper, claim: dict) -> None:
    uploaded = await client.post(
        f"/api/claims/{claim['id']}/documents",
        headers=helper,
        data={"item_id": str(claim["items"][0]["id"])},
        files={"file": ("hotel.png", _png(), "image/png")},
    )
    assert uploaded.status_code == 200, uploaded.text


async def _submits(client, cast: Cast, helper, claim: dict) -> dict:
    submitted = await client.post(f"/api/claims/{claim['id']}/submit", headers=helper)
    assert submitted.status_code == 200, submitted.text
    claim = submitted.json()
    assert claim["status"] == "submitted"
    assert claim["payer_club_id"] == cast.w.club
    assert (claim["payee_name"], claim["iban"]) == ("Rita Rib", IBAN)
    return claim


async def _waits_on_the_treasurer(client, treasurer, claim: dict) -> None:
    pending = (await client.get("/api/claims/pending", headers=treasurer)).json()
    assert (claim["id"], "decide") in {(r["id"], r["action"]) for r in pending}
    document = claim["documents"][0]["id"]
    url = f"/api/claims/{claim['id']}/documents/{document}"
    assert (await client.get(url, headers=treasurer)).content == _png()


async def _event_needs(client, headers, event_id: int) -> dict[str, int]:
    space = (await client.get("/api/me/contexts", headers=headers)).json()
    card = next(c for c in space["contexts"] if c["kind"] == "event" and c["id"] == event_id)
    return {n["code"]: n["count"] for n in card["needs"]}


class TestFromAClaimToTheBank:
    """Journey J-7: as a club that hosts an event I want the people who worked it paid
    back, decided by the club's treasurer and paid through one bank file."""

    async def test_rejected_once_paid_by_a_sepa_file_and_one_transfer_returned(
        self, client, caplog
    ):
        cast = await _cast(client, caplog)
        w = cast.w

        step("J-7.1", "club admin names the club's treasurer")
        treasurer = await _names_the_treasurer(client, caplog, cast)

        step("J-7.2", "treasurer saves the account the club pays from")
        await _saves_the_clubs_account(client, cast, treasurer)

        step("J-7.3", "club admin names the helper on the event the club hosts")
        helper = await _names_the_helper(client, caplog, cast)

        step("J-7.4", "helper saves their bank account")
        await _saves_their_account(client, helper)

        step("J-7.5", "helper starts a claim on the event")
        claim = await _starts_a_claim(client, cast, helper)

        step("J-7.6", "helper attaches the hotel invoice to the item")
        await _attaches_the_invoice(client, helper, claim)

        step("J-7.7", "helper submits; the host club pays, the account is copied on")
        claim = await _submits(client, cast, helper, claim)

        step("J-7.8", "the claim waits on the treasurer's list, to decide")
        await _waits_on_the_treasurer(client, treasurer, claim)
        claim_id = claim["id"]
        item = claim["items"][0]["id"]

        step("J-7.9", "treasurer rejects it, saying why")
        rejected = await client.post(
            f"/api/claims/{claim_id}/reject",
            headers=treasurer,
            json={"note": "The invoice says 160 €."},
        )
        assert rejected.json()["status"] == "rejected"
        assert (await _event_needs(client, helper, w.event)).get("claim_rejected") == 1

        step("J-7.10", "helper corrects the price and submits again")
        fixed = await client.put(
            f"/api/claims/{claim_id}/items/{item}",
            headers=helper,
            json=HOTEL | {"amount_cents": 16000},
        )
        assert fixed.json()["status"] == "draft"
        again = await client.post(f"/api/claims/{claim_id}/submit", headers=helper)
        assert again.json()["status"] == "submitted"
        pending = (await client.get("/api/claims/pending", headers=treasurer)).json()
        assert (claim_id, "decide") in {(r["id"], r["action"]) for r in pending}

        step("J-7.12", "treasurer approves it")
        approved = await client.post(f"/api/claims/{claim_id}/approve", headers=treasurer, json={})
        assert approved.status_code == 200, approved.text
        assert approved.json()["approved_cents"] == 16000
        # Frozen now: the helper changes nothing more.
        frozen = await client.put(
            f"/api/claims/{claim_id}/items/{item}", headers=helper, json=HOTEL
        )
        assert _problem_code(frozen) == "claim-not-editable"
        pending = (await client.get("/api/claims/pending", headers=treasurer)).json()
        assert (claim_id, "pay") in {(r["id"], r["action"]) for r in pending}

        step("J-7.15", "treasurer makes a payment run")
        run = await client.post(
            f"/api/clubs/{w.club}/payment-runs", headers=treasurer, json={"claim_ids": [claim_id]}
        )
        assert run.status_code == 201, run.text
        run = run.json()
        assert [p["amount_cents"] for p in run["payments"]] == [16000]
        state = (await client.get(f"/api/claims/{claim_id}", headers=helper)).json()
        assert state["payment_state"] == "in_payment"

        step("J-7.16", "treasurer downloads the SEPA file")
        sepa = await client.get(f"/api/payment-runs/{run['id']}/sepa", headers=treasurer)
        assert sepa.status_code == 200
        root = ET.fromstring(sepa.content)
        assert root.find(".//p:DbtrAcct/p:Id/p:IBAN", NS).text == CLUB_IBAN
        assert root.find(".//p:CdtrAcct/p:Id/p:IBAN", NS).text == IBAN
        assert root.find(".//p:GrpHdr/p:CtrlSum", NS).text == "160.00"
        assert f"C-{claim_id}" in root.find(".//p:RmtInf/p:Ustrd", NS).text

        # J-7.17 is offline: the treasurer uploads the file to the club's online banking.

        step("J-7.18", "treasurer marks the run booked")
        booked = await client.post(f"/api/payment-runs/{run['id']}/settle", headers=treasurer)
        assert booked.json()["open"] is False
        state = (await client.get(f"/api/claims/{claim_id}", headers=helper)).json()
        assert state["payment_state"] == "paid"

        step("J-7.19", "the bank returns the transfer; treasurer marks it")
        returned = await client.post(
            f"/api/payments/{run['payments'][0]['id']}/fail",
            headers=treasurer,
            json={"reason": "AC04 account closed"},
        )
        assert returned.status_code == 200, returned.text
        state = (await client.get(f"/api/claims/{claim_id}", headers=helper)).json()
        assert state["status"] == "approved" and state["payment_state"] == "unpaid"
        pending = (await client.get("/api/claims/pending", headers=treasurer)).json()
        assert (claim_id, "pay") in {(r["id"], r["action"]) for r in pending}

        step("J-7.20", "the claim goes into the next run")
        next_run = await client.post(
            f"/api/clubs/{w.club}/payment-runs", headers=treasurer, json={}
        )
        assert next_run.status_code == 201, next_run.text
        assert claim_id in {c for p in next_run.json()["payments"] for c in p["claim_ids"]}

    async def test_the_organizer_cannot_decide_their_own_and_one_claim_paid_by_girocode(
        self, client, caplog
    ):
        cast = await _cast(client, caplog)
        w = cast.w

        step("J-7.1", "club admin names the club's treasurer")
        treasurer = await _names_the_treasurer(client, caplog, cast)

        step("J-7.2", "treasurer saves the account the club pays from")
        await _saves_the_clubs_account(client, cast, treasurer)

        step("J-7.3", "club admin names the helper on the event the club hosts")
        helper = await _names_the_helper(client, caplog, cast)

        step("J-7.4", "helper saves their bank account")
        await _saves_their_account(client, helper)

        step("J-7.5", "helper starts a claim on the event")
        claim = await _starts_a_claim(client, cast, helper)

        step("J-7.6", "helper attaches the hotel invoice to the item")
        await _attaches_the_invoice(client, helper, claim)

        step("J-7.7", "helper submits; the host club pays, the account is copied on")
        claim = await _submits(client, cast, helper, claim)

        step("J-7.8", "the claim waits on the treasurer's list, to decide")
        await _waits_on_the_treasurer(client, treasurer, claim)
        claim_id = claim["id"]

        step("J-7.11", "the event organizer files a claim too, and cannot decide it")
        organizer_email = f"orga-{uuid4().hex[:6]}@example.org"
        await person(organizer_email)
        await _write(client, cast.club_admin, organizer_email, "manager", f"event:{w.event}")
        organizer = await _headers(client, caplog, organizer_email)
        # The organizer decides others' claims on the event...
        assert (claim_id, "decide") in {
            (r["id"], r["action"])
            for r in (await client.get("/api/claims/pending", headers=organizer)).json()
        }
        # ...but never their own.
        await client.put(
            "/api/me/bank-account", headers=organizer, json={"holder": "Orga", "iban": IBAN}
        )
        own = (
            await client.post(
                "/api/claims", headers=organizer, json={"title": "Fuel", "event_id": w.event}
            )
        ).json()
        await client.post(
            f"/api/claims/{own['id']}/items",
            headers=organizer,
            json={
                "kind": "meals",
                "incurred_on": "2026-06-01",
                "description": "x",
                "amount_cents": 900,
            },
        )
        assert (
            await client.post(f"/api/claims/{own['id']}/submit", headers=organizer)
        ).status_code == 200
        refused = await client.post(f"/api/claims/{own['id']}/approve", headers=organizer, json={})
        assert refused.status_code == 403
        assert _problem_code(refused) == "claim-own-decision"
        assert own["id"] not in {
            r["id"] for r in (await client.get("/api/claims/pending", headers=organizer)).json()
        }

        step("J-7.12", "treasurer approves the helper's claim")
        approved = await client.post(f"/api/claims/{claim_id}/approve", headers=treasurer, json={})
        assert approved.status_code == 200, approved.text

        step("J-7.13", "treasurer scans the claim's GiroCode with the banking app")
        code = await client.get(f"/api/claims/{claim_id}/girocode", headers=treasurer)
        assert code.status_code == 200, code.text
        assert code.headers["content-type"].startswith("image/svg+xml")
        own_code = await client.get(f"/api/claims/{claim_id}/girocode", headers=helper)
        assert _problem_code(own_code) == "claim-own-decision"

        step("J-7.14", "treasurer marks it paid")
        paid = await client.post(
            f"/api/claims/{claim_id}/pay", headers=treasurer, json={"reference": "GiroCode"}
        )
        assert paid.status_code == 200, paid.text
        assert paid.json()["payment_state"] == "paid"
        assert (
            _problem_code(await client.get(f"/api/claims/{claim_id}/girocode", headers=treasurer))
            == "claim-not-payable"
        )
        pending = (await client.get("/api/claims/pending", headers=treasurer)).json()
        assert claim_id not in {r["id"] for r in pending}
