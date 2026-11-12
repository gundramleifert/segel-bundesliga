"""Expense claims and payments (Stories F-2, F-4, F-5) — the data model.

A claim belongs to one event and stops at the decision; a **payment** is its own record
with its own lifecycle, linked to the claims it pays, and "paid" is computed from the one
live payment — never stored (``docs/PLAN_DATA_MODEL.md`` §2.5). The endpoints come
later; what is tested here is what the model itself guarantees: the totals, the payment
state, and the rules the database enforces so no route can break them.

The computed parts are checked on objects built in memory — they read only loaded
relations. The constraints are checked against the real (migrated) database.
"""

from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.db import SessionLocal
from app.models import (
    ClaimStatus,
    ExpenseClaim,
    ExpenseDocument,
    ExpenseItem,
    ExpenseKind,
    Payment,
    PaymentClaim,
    PaymentState,
    PaymentStatus,
)


def _item(amount: int, *, kind=ExpenseKind.OTHER) -> ExpenseItem:
    return ExpenseItem(
        kind=kind, incurred_on=date(2026, 6, 1), description="x", amount_cents=amount
    )


def _claim(*items: ExpenseItem, status=ClaimStatus.APPROVED) -> ExpenseClaim:
    claim = ExpenseClaim(title="Act 3", status=status, items=list(items), links=[])
    if status == ClaimStatus.APPROVED:
        claim.approved_total_cents = claim.claimed_cents
    return claim


def _pay(claim: ExpenseClaim, status: PaymentStatus) -> None:
    payment = Payment(status=status, amount_cents=claim.approved_cents)
    claim.links.append(PaymentClaim(payment=payment, active=status != PaymentStatus.FAILED))


class TestClaimTotals:
    """Story F-2/F-3: what is claimed is the sum over the items — computed, never stored —
    and what is approved is that sum once approved: the decider changes no amount."""

    def test_claimed_and_approved_are_sums_over_the_items(self):
        claim = _claim(_item(4500), _item(12000), _item(800))
        assert claim.claimed_cents == 17300
        assert claim.approved_cents == 17300
        assert _claim(_item(4500), status=ClaimStatus.SUBMITTED).approved_cents == 0

    def test_what_was_approved_stays_what_is_owed(self):
        """Decided money is frozen: an item changed after the approval — by a bug, a
        script, a migration — changes what was claimed, never what is owed."""
        claim = _claim(_item(4500))
        claim.items.append(_item(99900))

        assert claim.claimed_cents == 104400
        assert claim.approved_cents == 4500


class TestPaymentState:
    """Story F-4: whether a claim is paid follows from its one live payment. A claim is
    paid whole, never in parts; a failed payment simply stops counting."""

    def test_settled_is_paid(self):
        claim = _claim(_item(10000))
        _pay(claim, PaymentStatus.SETTLED)

        assert claim.paid_cents == 10000
        assert claim.open_cents == 0
        assert claim.payment_state is PaymentState.PAID

    def test_issued_is_in_payment_and_nothing_is_open(self):
        claim = _claim(_item(10000))
        _pay(claim, PaymentStatus.ISSUED)

        assert claim.payment_state is PaymentState.IN_PAYMENT
        assert claim.open_cents == 0 and claim.paid_cents == 0

    def test_a_failed_transfer_falls_back_to_unpaid_by_itself(self):
        """An approved claim without payments is unpaid. Never edit, reverse: the failed
        payment stays as it was, and the claim is unpaid again because the computation no
        longer counts it."""
        claim = _claim(_item(10000))
        assert claim.payment_state is PaymentState.UNPAID
        _pay(claim, PaymentStatus.FAILED)

        assert claim.paid_cents == 0
        assert claim.open_cents == 10000
        assert claim.payment_state is PaymentState.UNPAID

    @pytest.mark.parametrize(
        "status",
        [ClaimStatus.DRAFT, ClaimStatus.SUBMITTED, ClaimStatus.REJECTED, ClaimStatus.WITHDRAWN],
    )
    def test_only_an_approved_claim_has_a_payment_state(self, status):
        assert _claim(_item(10000), status=status).payment_state is None


async def _stored_claim(ids, *items: ExpenseItem) -> int:
    async with SessionLocal() as session:
        claim = ExpenseClaim(
            event_id=ids.event("dsbl-1-2026-act-1"),
            claimant_name="Wanda Racecommittee",
            title="Act 1",
            items=list(items),
        )
        session.add(claim)
        await session.commit()
        return claim.id


async def _refused(*rows) -> None:
    async with SessionLocal() as session:
        session.add_all(rows)
        with pytest.raises(IntegrityError):
            await session.commit()


class TestTheDatabaseKeepsTheBooksStraight:
    """Stories F-2, F-4, F-5: the rules a route could forget are the database's."""

    async def test_a_car_item_costs_distance_times_rate(self, ids):
        car = ExpenseItem(
            kind=ExpenseKind.TRAVEL_CAR,
            incurred_on=date(2026, 6, 1),
            description="Hamburg – Kiel and back",
            distance_km=200,
            rate_cents=30,
            amount_cents=6000,
        )
        assert await _stored_claim(ids, car)

        claim_id = await _stored_claim(ids)
        await _refused(
            ExpenseItem(
                claim_id=claim_id,
                kind=ExpenseKind.TRAVEL_CAR,
                incurred_on=date(2026, 6, 1),
                description="rounded up",
                distance_km=200,
                rate_cents=30,
                amount_cents=6500,
            )
        )
        await _refused(
            ExpenseItem(
                claim_id=claim_id,
                kind=ExpenseKind.TRAVEL_CAR,
                incurred_on=date(2026, 6, 1),
                description="no distance",
                amount_cents=6000,
            )
        )

    async def test_amounts_are_never_negative_and_a_range_ends_later(self, ids):
        claim_id = await _stored_claim(ids)
        base = {"claim_id": claim_id, "kind": ExpenseKind.OTHER, "incurred_on": date(2026, 6, 1)}

        await _refused(ExpenseItem(**base, description="negative", amount_cents=-100))
        await _refused(
            ExpenseItem(
                **base, description="backwards", amount_cents=100, incurred_until=date(2026, 5, 30)
            )
        )

    async def test_a_claim_has_one_live_payment_at_most(self, ids):
        """Review 1.1: two screens, a double click, a run made while a GiroCode was out —
        whatever asks, the database refuses a second live payment of one claim. A failed
        one's link is inactive and leaves room for the next."""
        claim_id = await _stored_claim(ids, _item(10000))

        async def payment() -> int:
            async with SessionLocal() as session:
                row = Payment(
                    payer_club_id=ids.club("asvw"),
                    payee_name="Wanda",
                    amount_cents=10000,
                    status=PaymentStatus.ISSUED,
                )
                session.add(row)
                await session.commit()
                return row.id

        first, second, third = await payment(), await payment(), await payment()
        async with SessionLocal() as session:
            session.add(PaymentClaim(payment_id=first, claim_id=claim_id))
            await session.commit()

        await _refused(PaymentClaim(payment_id=first, claim_id=claim_id, active=False))
        await _refused(PaymentClaim(payment_id=second, claim_id=claim_id))
        async with SessionLocal() as session:
            session.add(PaymentClaim(payment_id=second, claim_id=claim_id, active=False))
            await session.commit()
        await _refused(PaymentClaim(payment_id=third, claim_id=claim_id))

    async def test_a_payment_moves_money(self, ids):
        await _refused(
            Payment(
                payer_club_id=ids.club("asvw"),
                payee_name="Wanda",
                amount_cents=0,
                status=PaymentStatus.ISSUED,
            )
        )

    async def test_a_document_is_at_most_ten_megabytes(self, ids):
        claim_id = await _stored_claim(ids)

        def document(size: int) -> ExpenseDocument:
            return ExpenseDocument(
                claim_id=claim_id,
                stored_name=uuid4().hex,
                original_name="hotel.pdf",
                content_type="application/pdf",
                size_bytes=size,
            )

        async with SessionLocal() as session:
            session.add(document(10 * 1024 * 1024))
            await session.commit()
        await _refused(document(10 * 1024 * 1024 + 1))
        await _refused(document(0))
