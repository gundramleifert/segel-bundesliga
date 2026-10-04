"""Expense claims and payments (Stories F-2, F-4, F-5) — the data model.

A claim belongs to one event and stops at the decision; a **payment** is its own record
with its own lifecycle, linked to claims through allocations, and "paid" is computed from
the settled ones — never stored (``docs/PLAN_DATA_MODEL.md`` §2.5). The endpoints come
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
    PaymentAllocation,
    PaymentState,
    PaymentStatus,
)


def _item(amount: int, *, approved: int | None = None, kind=ExpenseKind.OTHER) -> ExpenseItem:
    return ExpenseItem(
        kind=kind,
        incurred_on=date(2026, 6, 1),
        description="x",
        amount_cents=amount,
        approved_cents=approved,
    )


def _claim(*items: ExpenseItem, status=ClaimStatus.APPROVED) -> ExpenseClaim:
    return ExpenseClaim(title="Act 3", status=status, items=list(items), allocations=[])


def _pay(claim: ExpenseClaim, amount: int, status: PaymentStatus) -> None:
    payment = Payment(status=status)
    claim.allocations.append(PaymentAllocation(payment=payment, amount_cents=amount))


class TestClaimTotals:
    """Story F-2/F-3: what is claimed and what is approved are sums over the items —
    computed, never stored."""

    def test_claimed_and_approved_are_sums_over_the_items(self):
        claim = _claim(_item(4500), _item(12000, approved=10000), _item(800, approved=0))

        assert claim.claimed_cents == 17300
        assert claim.approved_cents == 14500


class TestPaymentState:
    """Story F-4: whether a claim is paid follows from the settled payments allocated
    to it. A failed or cancelled payment simply stops counting."""

    def test_an_approved_claim_without_payments_is_unpaid(self):
        assert _claim(_item(10000)).payment_state is PaymentState.UNPAID

    def test_an_issued_payment_puts_it_in_payment(self):
        claim = _claim(_item(10000))
        _pay(claim, 10000, PaymentStatus.ISSUED)

        assert claim.payment_state is PaymentState.IN_PAYMENT

    def test_settled_in_full_is_paid(self):
        claim = _claim(_item(10000))
        _pay(claim, 6000, PaymentStatus.SETTLED)
        _pay(claim, 4000, PaymentStatus.SETTLED)

        assert claim.paid_cents == 10000
        assert claim.payment_state is PaymentState.PAID

    def test_settled_in_part_is_partially_paid(self):
        claim = _claim(_item(10000))
        _pay(claim, 6000, PaymentStatus.SETTLED)

        assert claim.payment_state is PaymentState.PARTIALLY_PAID

    def test_a_failed_transfer_falls_back_to_unpaid_by_itself(self):
        """Never edit, reverse: the failed payment stays as it was, and the claim is
        unpaid again because the computation no longer counts it."""
        claim = _claim(_item(10000))
        _pay(claim, 10000, PaymentStatus.FAILED)
        _pay(claim, 10000, PaymentStatus.CANCELLED)

        assert claim.paid_cents == 0
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

    async def test_amounts_are_never_negative_and_approval_never_exceeds_the_claim(self, ids):
        claim_id = await _stored_claim(ids)
        base = {"claim_id": claim_id, "kind": ExpenseKind.OTHER, "incurred_on": date(2026, 6, 1)}

        await _refused(ExpenseItem(**base, description="negative", amount_cents=-100))
        await _refused(
            ExpenseItem(**base, description="more", amount_cents=100, approved_cents=150)
        )

    async def test_a_claim_is_allocated_to_a_payment_once(self, ids):
        claim_id = await _stored_claim(ids, _item(10000))
        async with SessionLocal() as session:
            payment = Payment(payer_club_id=ids.club("nrv"), payee_name="Wanda")
            session.add(payment)
            await session.commit()
            payment_id = payment.id
        async with SessionLocal() as session:
            session.add(PaymentAllocation(payment_id=payment_id, claim_id=claim_id, amount_cents=1))
            await session.commit()

        await _refused(PaymentAllocation(payment_id=payment_id, claim_id=claim_id, amount_cents=1))
        await _refused(
            PaymentAllocation(
                payment_id=payment_id, claim_id=await _stored_claim(ids), amount_cents=0
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
