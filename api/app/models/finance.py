"""Expense claims and the payments that settle them (Stories F-2 to F-5).

Race officers, jury, umpires and helpers travel to an event, and **the club hosting it pays
their costs**; a club also pays back what its members spend for it. So a claim belongs to
one event **or** one club, and that event's or club's manager or treasurer (Stories F-1,
F-3) decides and pays it. The plan is ``docs/PLAN_DATA_MODEL.md``.

Three rules shape the model:

* **Approval and payment are two state machines, not one.** A claim stops at the
  decision (``ClaimStatus``); a ``Payment`` is its own record with its own lifecycle
  (``PaymentStatus``), linked to claims through ``PaymentAllocation`` — one transfer can
  settle several claims, one claim can be paid in parts. A transfer that bounces days
  after approval must not reopen the approval. Odoo, ERPNext, SAP Concur and Stripe all
  split it the same way.
* **Totals and "paid" are derived, never stored** — the same rule as points. What is
  claimed and approved are sums over the items; whether a claim is paid follows from the
  *settled* payments allocated to it. A failed payment is never edited: it stops
  counting, and the claim is unpaid again by itself.
* **Money is integer cents, in EUR.** Never a float. A currency column waits for the
  first claim that is not in euros.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.competition import Event
    from app.models.org import Club

#: The largest document a claim takes (Story F-5) — the same limit as a waiver scan.
DOCUMENT_MAX_BYTES = 10 * 1024 * 1024


class ClaimStatus(StrEnum):
    """Where a claim stands — up to the decision, and no further.

    ``draft`` → ``submitted`` → ``approved`` | ``rejected``; ``returned`` sends it back
    to the claimant with a note, ``withdrawn`` is the claimant's way out before a
    decision. Whether it is *paid* is not a status: see :class:`PaymentState`.
    """

    DRAFT = "draft"
    SUBMITTED = "submitted"
    RETURNED = "returned"
    APPROVED = "approved"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class ExpenseKind(StrEnum):
    TRAVEL_CAR = "travel_car"
    """Kilometres × the paying club's rate, frozen on the item at submission."""

    TRAVEL_PUBLIC = "travel_public"
    ACCOMMODATION = "accommodation"
    PER_DIEM = "per_diem"
    MEALS = "meals"
    OTHER = "other"


class PaymentStatus(StrEnum):
    """Where one transfer stands — names after Odoo's ``account.payment`` and SEPA.

    ``draft`` → ``issued`` (transferred, or the SEPA file exported) → ``settled``
    (on the bank statement). ``failed`` is a rejection or a return, also after
    settlement; ``cancelled`` drops a payment that was never issued. A failed payment is
    kept as it is, and a new one is made.
    """

    DRAFT = "draft"
    ISSUED = "issued"
    SETTLED = "settled"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PaymentMethod(StrEnum):
    TRANSFER = "transfer"
    SEPA_FILE = "sepa_file"
    CASH = "cash"


class PaymentState(StrEnum):
    """Whether an approved claim is paid — **computed** from its allocations, never
    stored (names after Odoo's ``payment_state``)."""

    UNPAID = "unpaid"
    IN_PAYMENT = "in_payment"
    PARTIALLY_PAID = "partially_paid"
    PAID = "paid"


class ExpenseClaim(Base, TimestampMixin):
    """What one person claims for one event, or for one club.

    Exactly one of ``event_id`` and ``club_id`` is set — the database says so. The payer
    is the event's host club, or the club itself, recorded at submission
    (``payer_club_id``): if the host changes afterwards, the claim stays with the club it
    was addressed to. Who may decide is checked on the event or the club regardless
    (``app/services/expenses.py::may_decide``).

    The claimant's name is kept beside the account link: the books must stay readable
    after the account is deleted (Story Z-7), which clears ``claimant_user_id``.
    """

    __tablename__ = "expense_claim"
    __table_args__ = (
        CheckConstraint(
            "(event_id IS NOT NULL) + (club_id IS NOT NULL) = 1", name="event_or_club"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int | None] = mapped_column(
        ForeignKey("event.id"), index=True, default=None
    )
    # A claim on the club itself (Story F-2): what a member spent for it.
    club_id: Mapped[int | None] = mapped_column(ForeignKey("club.id"), index=True, default=None)
    claimant_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("app_user.id"), index=True, default=None
    )
    claimant_name: Mapped[str] = mapped_column(String(160), default="")
    # Empty until submitted; then the event's host club at that moment.
    payer_club_id: Mapped[int | None] = mapped_column(
        ForeignKey("club.id"), index=True, default=None
    )
    title: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(16), default=ClaimStatus.DRAFT, index=True)

    # Where the money goes, as the claimant named it when submitting — a payout goes to
    # that account, not to whatever the profile says later. Shown only to the claimant
    # and the event's treasurer.
    payee_name: Mapped[str | None] = mapped_column(String(160), default=None)
    iban: Mapped[str | None] = mapped_column(String(34), default=None)

    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    # The decision — approved, returned or rejected — and who made it. Never the claimant
    # (four eyes, enforced by the service).
    decided_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("app_user.id"), default=None
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    decision_note: Mapped[str | None] = mapped_column(String(1000), default=None)

    event: Mapped[Event | None] = relationship(lazy="selectin")
    club: Mapped[Club | None] = relationship(foreign_keys=[club_id], lazy="selectin")
    payer_club: Mapped[Club | None] = relationship(foreign_keys=[payer_club_id], lazy="selectin")
    # Loaded eagerly: the totals and the payment state read them, and a claim has a
    # handful of each.
    items: Mapped[list[ExpenseItem]] = relationship(
        back_populates="claim",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="ExpenseItem.incurred_on",
    )
    documents: Mapped[list[ExpenseDocument]] = relationship(
        back_populates="claim", cascade="all, delete-orphan", lazy="selectin"
    )
    allocations: Mapped[list[PaymentAllocation]] = relationship(
        back_populates="claim", lazy="selectin"
    )

    @property
    def claimed_cents(self) -> int:
        return sum(item.amount_cents for item in self.items)

    @property
    def approved_cents(self) -> int:
        """An item not cut by the treasurer counts as claimed."""
        return sum(item.approved_amount for item in self.items)

    @property
    def paid_cents(self) -> int:
        return sum(
            a.amount_cents for a in self.allocations if a.payment.status == PaymentStatus.SETTLED
        )

    @property
    def payment_state(self) -> PaymentState | None:
        """``None`` until approved: nothing is owed on a claim that is not."""
        if self.status != ClaimStatus.APPROVED:
            return None
        paid = self.paid_cents
        if paid >= self.approved_cents:
            return PaymentState.PAID
        if paid > 0:
            return PaymentState.PARTIALLY_PAID
        if any(a.payment.status == PaymentStatus.ISSUED for a in self.allocations):
            return PaymentState.IN_PAYMENT
        return PaymentState.UNPAID


class ExpenseItem(Base, TimestampMixin):
    """One cost on a claim.

    A car item's amount is ``distance_km × rate_cents`` — and the database says so, so
    no route can store a rounded-up figure. The rate is the paying club's at submission,
    frozen here: a later rate change reprices nothing already filed.
    """

    __tablename__ = "expense_item"
    __table_args__ = (
        CheckConstraint("amount_cents >= 0", name="amount_not_negative"),
        CheckConstraint(
            "approved_cents IS NULL OR (approved_cents >= 0 AND approved_cents <= amount_cents)",
            name="approved_within_claimed",
        ),
        CheckConstraint(
            "kind <> 'travel_car' OR (distance_km IS NOT NULL AND rate_cents IS NOT NULL"
            " AND amount_cents = distance_km * rate_cents)",
            name="car_is_distance_times_rate",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    claim_id: Mapped[int] = mapped_column(ForeignKey("expense_claim.id"), index=True)
    kind: Mapped[str] = mapped_column(String(24))
    incurred_on: Mapped[date] = mapped_column(Date)
    description: Mapped[str] = mapped_column(String(300))
    # Car only.
    distance_km: Mapped[int | None] = mapped_column(default=None)
    rate_cents: Mapped[int | None] = mapped_column(default=None)
    amount_cents: Mapped[int] = mapped_column()
    # Set by the treasurer to cut an item; empty means approved as claimed.
    approved_cents: Mapped[int | None] = mapped_column(default=None)

    claim: Mapped[ExpenseClaim] = relationship(back_populates="items")

    @property
    def approved_amount(self) -> int:
        return self.amount_cents if self.approved_cents is None else self.approved_cents


class ExpenseDocument(Base, TimestampMixin):
    """A receipt, invoice or ticket on a claim (Story F-5).

    Stored under a random name (``stored_name``) like a waiver scan; the uploaded file
    name is only shown, never used as a path. Tied to one item, or — when it covers
    several, like a hotel invoice — to the claim alone.
    """

    __tablename__ = "expense_document"
    __table_args__ = (
        CheckConstraint(
            f"size_bytes > 0 AND size_bytes <= {DOCUMENT_MAX_BYTES}", name="size_within_limit"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    claim_id: Mapped[int] = mapped_column(ForeignKey("expense_claim.id"), index=True)
    item_id: Mapped[int | None] = mapped_column(
        ForeignKey("expense_item.id", ondelete="SET NULL"), index=True, default=None
    )
    stored_name: Mapped[str] = mapped_column(String(64), unique=True)
    original_name: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(64))
    size_bytes: Mapped[int] = mapped_column()
    uploaded_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("app_user.id"), default=None
    )

    claim: Mapped[ExpenseClaim] = relationship(back_populates="documents")


class Payment(Base, TimestampMixin):
    """One transfer from a club to one payee.

    Its amount is the sum of its allocations — derived, like a claim's total. It settles
    claims of **one payee for one paying club**; the service checks both when
    allocating, and refuses an allocation that would pay a claim beyond its approved
    total.
    """

    __tablename__ = "payment"

    id: Mapped[int] = mapped_column(primary_key=True)
    payer_club_id: Mapped[int] = mapped_column(ForeignKey("club.id"), index=True)
    payee_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("app_user.id"), index=True, default=None
    )
    payee_name: Mapped[str] = mapped_column(String(160), default="")
    iban: Mapped[str | None] = mapped_column(String(34), default=None)
    status: Mapped[str] = mapped_column(String(16), default=PaymentStatus.DRAFT, index=True)
    method: Mapped[str] = mapped_column(String(16), default=PaymentMethod.TRANSFER)
    # The remittance line on the statement; SEPA allows 140 characters.
    reference: Mapped[str | None] = mapped_column(String(140), default=None)
    # The second pair of eyes: who issued it. Never the payee (enforced by the service).
    issued_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("app_user.id"), default=None)
    issued_on: Mapped[date | None] = mapped_column(Date, default=None)
    settled_on: Mapped[date | None] = mapped_column(Date, default=None)
    # A SEPA reason code (``AC04`` closed account) or a sentence.
    failure_reason: Mapped[str | None] = mapped_column(String(200), default=None)

    allocations: Mapped[list[PaymentAllocation]] = relationship(
        back_populates="payment", cascade="all, delete-orphan", lazy="selectin"
    )

    @property
    def amount_cents(self) -> int:
        return sum(a.amount_cents for a in self.allocations)


class PaymentAllocation(Base, TimestampMixin):
    """How much of one payment goes to one claim."""

    __tablename__ = "payment_allocation"
    __table_args__ = (
        UniqueConstraint("payment_id", "claim_id"),
        CheckConstraint("amount_cents > 0", name="amount_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    payment_id: Mapped[int] = mapped_column(ForeignKey("payment.id"), index=True)
    claim_id: Mapped[int] = mapped_column(ForeignKey("expense_claim.id"), index=True)
    amount_cents: Mapped[int] = mapped_column()

    payment: Mapped[Payment] = relationship(back_populates="allocations", lazy="selectin")
    claim: Mapped[ExpenseClaim] = relationship(back_populates="allocations")
