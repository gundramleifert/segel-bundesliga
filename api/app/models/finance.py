"""Expense claims and the payments that settle them (Stories F-2 to F-5).

Race officers, jury, umpires and helpers travel to an event, and **the club hosting it pays
their costs**; a club also pays back what its members spend for it. So a claim belongs to
one event **or** one club, and that event's or club's manager or treasurer (Stories F-1,
F-3) decides and pays it. The plan is ``docs/PLAN_DATA_MODEL.md``.

Three rules shape the model:

* **Approval and payment are two state machines, not one.** A claim stops at the
  decision (``ClaimStatus``); a ``Payment`` is its own record with its own lifecycle
  (``PaymentStatus``), linked to claims through ``PaymentClaim`` — one transfer can
  settle several claims of one payee. A claim is paid **whole**, never in parts (decided
  2026-11-11): a transfer that bounces days after approval must not reopen the approval.
* **One claim, one live payment — the database says so.** A partial unique index on
  ``payment_claim(claim_id) WHERE active`` refuses a second payment while one is issued
  or settled, whichever screen, run or double click asks; a failed payment's link turns
  inactive and the claim is open again.
* **Decided money is frozen.** What was approved is stored at approval
  (``ExpenseClaim.approved_total_cents``), what a payment transfers at its issue
  (``Payment.amount_cents``), and the SEPA file a run exported is kept byte for byte
  (``PaymentRun.sepa_xml``). Whether a claim is *paid* is still derived — from its live
  payment's status.
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
    Index,
    LargeBinary,
    String,
    UniqueConstraint,
    text,
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

    ``draft`` → ``submitted`` → ``approved`` | ``rejected``. A rejected claim, like a
    submitted one, is the claimant's to change — and a change makes it a ``draft`` again,
    to be submitted again (decided 2026-10-24). ``withdrawn`` is the claimant's way out
    before approval. Whether it is *paid* is not a status: see :class:`PaymentState`.
    """

    DRAFT = "draft"
    SUBMITTED = "submitted"
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

    ``issued`` (in a SEPA file, or a GiroCode handed to a banking app) → ``settled`` (on
    the bank statement, or marked paid). ``failed`` is a rejection, a return, or a "paid"
    taken back — also after settlement. A failed payment is kept as it is, and a new one
    is made.
    """

    ISSUED = "issued"
    SETTLED = "settled"
    FAILED = "failed"


class PaymentMethod(StrEnum):
    TRANSFER = "transfer"
    SEPA_FILE = "sepa_file"
    CASH = "cash"


class PaymentState(StrEnum):
    """Whether an approved claim is paid — **computed** from its live payment, never
    stored (names after Odoo's ``payment_state``)."""

    UNPAID = "unpaid"
    IN_PAYMENT = "in_payment"
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
        # Exactly one — compared as booleans (Postgres cannot add them).
        CheckConstraint("(event_id IS NULL) <> (club_id IS NULL)", name="event_or_club"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int | None] = mapped_column(ForeignKey("event.id"), index=True, default=None)
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
    decided_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("app_user.id"), default=None)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    decision_note: Mapped[str | None] = mapped_column(String(1000), default=None)
    # What the approval owes, frozen at it: the items' sum then. Empty before.
    approved_total_cents: Mapped[int | None] = mapped_column(default=None)

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
    links: Mapped[list[PaymentClaim]] = relationship(back_populates="claim", lazy="selectin")

    @property
    def claimed_cents(self) -> int:
        return sum(item.amount_cents for item in self.items)

    @property
    def approved_cents(self) -> int:
        """What is owed once approved — frozen at the approval (Story F-3: the decider
        approves or rejects, and changes no amount)."""
        if self.status != ClaimStatus.APPROVED:
            return 0
        return self.approved_total_cents if self.approved_total_cents is not None else 0

    @property
    def payment(self) -> Payment | None:
        """The one live payment — issued or settled — or none."""
        return next((link.payment for link in self.links if link.active), None)

    @property
    def unconfirmed_payment(self) -> Payment | None:
        """The live payment when it is a GiroCode's transfer (no run) not yet marked
        paid: the decider confirms it, or takes it back."""
        payment = self.payment
        if (
            payment is not None
            and payment.status == PaymentStatus.ISSUED
            and payment.run_id is None
        ):
            return payment
        return None

    @property
    def paid_cents(self) -> int:
        payment = self.payment
        return self.approved_cents if payment and payment.status == PaymentStatus.SETTLED else 0

    @property
    def open_cents(self) -> int:
        """What is still to be paid: the approved total while no payment is live."""
        return self.approved_cents if self.payment is None else 0

    @property
    def payment_state(self) -> PaymentState | None:
        """``None`` until approved: nothing is owed on a claim that is not."""
        if self.status != ClaimStatus.APPROVED:
            return None
        payment = self.payment
        if payment is None:
            return PaymentState.UNPAID
        if payment.status == PaymentStatus.SETTLED:
            return PaymentState.PAID
        return PaymentState.IN_PAYMENT


class ExpenseItem(Base, TimestampMixin):
    """One cost on a claim.

    A car item's amount is ``distance_km × rate_cents`` — and the database says so, so
    no route can store a rounded-up figure. The rate is the paying club's at submission,
    frozen here: a later rate change reprices nothing already filed.

    A date, or a range: ``incurred_until`` is the last day of a hotel's nights or a
    weekend's per-diem, empty for one day.
    """

    __tablename__ = "expense_item"
    __table_args__ = (
        CheckConstraint("amount_cents >= 0", name="amount_not_negative"),
        CheckConstraint(
            "incurred_until IS NULL OR incurred_until > incurred_on", name="range_ends_later"
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
    incurred_until: Mapped[date | None] = mapped_column(Date, default=None)
    description: Mapped[str] = mapped_column(String(300))
    # Car only.
    distance_km: Mapped[int | None] = mapped_column(default=None)
    rate_cents: Mapped[int | None] = mapped_column(default=None)
    amount_cents: Mapped[int] = mapped_column()

    claim: Mapped[ExpenseClaim] = relationship(back_populates="items")


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
    uploaded_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("app_user.id"), default=None)

    claim: Mapped[ExpenseClaim] = relationship(back_populates="documents")


class ClubBankAccount(Base, TimestampMixin):
    """The account a club pays from (Story F-7) — the debtor of its SEPA files.

    Its own table, not columns on ``Club``: a club is read by the public site, and no
    public serializer can carry an IBAN it never sees. Read and written by the club's
    manager or treasurer only.
    """

    __tablename__ = "club_bank_account"

    id: Mapped[int] = mapped_column(primary_key=True)
    club_id: Mapped[int] = mapped_column(ForeignKey("club.id"), unique=True)
    holder: Mapped[str] = mapped_column(String(160))
    iban: Mapped[str] = mapped_column(String(34))
    bic: Mapped[str | None] = mapped_column(String(11), default=None)


class PaymentRun(Base, TimestampMixin):
    """One SEPA file: the payments a club exported together (Story F-7).

    The debtor account is copied here when the run is made, so downloading the file again
    weeks later gives the same file — and the same message id, which a bank refuses to
    book twice. Whether the run is still *open* (a payment still ``issued``) is derived.
    """

    __tablename__ = "payment_run"

    id: Mapped[int] = mapped_column(primary_key=True)
    payer_club_id: Mapped[int] = mapped_column(ForeignKey("club.id"), index=True)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("app_user.id"), default=None)
    execution_date: Mapped[date] = mapped_column(Date)
    # SEPA ``MsgId``: at most 35 characters, unique per debtor at the bank.
    message_id: Mapped[str] = mapped_column(String(35), unique=True)
    debtor_name: Mapped[str] = mapped_column(String(160))
    debtor_iban: Mapped[str] = mapped_column(String(34))
    debtor_bic: Mapped[str | None] = mapped_column(String(11), default=None)
    # The file as exported, kept: downloading it again gives what the bank got.
    sepa_xml: Mapped[bytes | None] = mapped_column(LargeBinary, default=None)

    payments: Mapped[list[Payment]] = relationship(
        back_populates="run", lazy="selectin", order_by="Payment.id"
    )

    @property
    def open(self) -> bool:
        return any(p.status == PaymentStatus.ISSUED for p in self.payments)

    @property
    def total_cents(self) -> int:
        return sum(p.amount_cents for p in self.payments if p.status != PaymentStatus.FAILED)


class Payment(Base, TimestampMixin):
    """One transfer from a club to one payee, over one or more of their claims.

    Its amount is frozen at issue — the claims' approved totals then. The service checks
    that every claim is the payee's and the paying club's.
    """

    __tablename__ = "payment"
    __table_args__ = (CheckConstraint("amount_cents > 0", name="amount_positive"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    payer_club_id: Mapped[int] = mapped_column(ForeignKey("club.id"), index=True)
    payee_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("app_user.id"), index=True, default=None
    )
    payee_name: Mapped[str] = mapped_column(String(160), default="")
    iban: Mapped[str | None] = mapped_column(String(34), default=None)
    amount_cents: Mapped[int] = mapped_column()
    status: Mapped[str] = mapped_column(String(16), index=True)
    method: Mapped[str] = mapped_column(String(16), default=PaymentMethod.TRANSFER)
    # The remittance line on the statement; SEPA allows 140 characters.
    reference: Mapped[str | None] = mapped_column(String(140), default=None)
    # The second pair of eyes: who issued it. Never the payee (enforced by the service).
    issued_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("app_user.id"), default=None)
    issued_on: Mapped[date | None] = mapped_column(Date, default=None)
    settled_on: Mapped[date | None] = mapped_column(Date, default=None)
    # A SEPA reason code (``AC04`` closed account) or a sentence.
    failure_reason: Mapped[str | None] = mapped_column(String(200), default=None)

    # The SEPA file it went out in; empty for a GiroCode or a payment marked paid by hand.
    run_id: Mapped[int | None] = mapped_column(
        ForeignKey("payment_run.id"), index=True, default=None
    )

    links: Mapped[list[PaymentClaim]] = relationship(
        back_populates="payment", cascade="all, delete-orphan", lazy="selectin"
    )
    run: Mapped[PaymentRun | None] = relationship(back_populates="payments")

    @property
    def claim_ids(self) -> list[int]:
        return [link.claim_id for link in self.links]


class PaymentClaim(Base, TimestampMixin):
    """A claim one payment settles. ``active`` while the payment is issued or settled;
    a failed payment's links turn inactive, and the claim is open again. At most one
    active link per claim — the database refuses a second payment of it."""

    __tablename__ = "payment_claim"
    __table_args__ = (
        UniqueConstraint("payment_id", "claim_id"),
        Index(
            "uq_payment_claim_one_live_payment",
            "claim_id",
            unique=True,
            postgresql_where=text("active"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    payment_id: Mapped[int] = mapped_column(ForeignKey("payment.id"), index=True)
    claim_id: Mapped[int] = mapped_column(ForeignKey("expense_claim.id"), index=True)
    active: Mapped[bool] = mapped_column(default=True)

    payment: Mapped[Payment] = relationship(back_populates="links", lazy="selectin")
    claim: Mapped[ExpenseClaim] = relationship(back_populates="links")
