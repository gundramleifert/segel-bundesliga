"""Paying through the bank (Stories F-7, F-4): a club's account, the payment run that
turns approved claims into one SEPA file, the bank's answer, and the spreadsheets.

The site never talks to the bank. The file goes *to* the bank through the treasurer's own
online banking, which asks for its TAN as for any batch — no bank login is stored here.
The libraries do the formats: ``sepaxml`` writes pain.001.001.09 and validates it against
the XSD, ``schwifty`` checks IBANs and finds BICs, ``openpyxl`` writes the spreadsheets.
"""

from __future__ import annotations

import io
import uuid
from collections import defaultdict
from datetime import date, datetime

from openpyxl import Workbook
from openpyxl.utils import get_column_letter
from schwifty import IBAN
from schwifty.exceptions import SchwiftyException
from sepaxml import SepaTransfer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AuditLog,
    ClaimStatus,
    Club,
    ClubBankAccount,
    ExpenseClaim,
    Payment,
    PaymentAllocation,
    PaymentMethod,
    PaymentRun,
    PaymentStatus,
)
from app.models.auth import Relation, User
from app.problems import Problem

#: The format German banks take since the SEPA 2025 changes (DK data format 3.7+).
SEPA_SCHEMA = "pain.001.001.09"
#: SEPA's remittance line: at most 140 characters.
REMITTANCE_MAX = 140


# ---------------------------------------------------------------------- who


def may_pay_for(user: User, club_id: int) -> bool:
    """The club's manager or treasurer (and their admins): the people who hold its money
    (Story F-3). The club's account and its runs are theirs alone."""
    return user.can(Relation.MANAGER, Relation.TREASURER, on=Club(id=club_id))


def require_pay_for(user: User, club_id: int) -> None:
    if not may_pay_for(user, club_id):
        raise Problem(
            403,
            "club-money-forbidden",
            "Only the club's manager or treasurer handles its account and payments.",
        )


# ---------------------------------------------------------------------- reading


async def club_account(session: AsyncSession, club_id: int) -> ClubBankAccount | None:
    return (
        await session.execute(select(ClubBankAccount).where(ClubBankAccount.club_id == club_id))
    ).scalar_one_or_none()


async def load_run(session: AsyncSession, run_id: int) -> PaymentRun:
    run = (
        await session.execute(
            select(PaymentRun)
            .where(PaymentRun.id == run_id)
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    if run is None:
        raise Problem(404, "payment-run-not-found", "No such payment run.")
    return run


async def open_runs(session: AsyncSession, user: User) -> list[PaymentRun]:
    """Runs still waiting for the bank, of every club this person pays for."""
    runs = (
        (await session.execute(select(PaymentRun).order_by(PaymentRun.id.desc()))).scalars().all()
    )
    return [run for run in runs if run.open and may_pay_for(user, run.payer_club_id)]


async def claims_of(session: AsyncSession, claim_ids: set[int]) -> dict[int, ExpenseClaim]:
    if not claim_ids:
        return {}
    rows = (
        await session.execute(select(ExpenseClaim).where(ExpenseClaim.id.in_(claim_ids)))
    ).scalars()
    return {claim.id: claim for claim in rows}


# ---------------------------------------------------------------------- the run


async def create_run(
    session: AsyncSession,
    user: User,
    club_id: int,
    *,
    claim_ids: list[int] | None,
    execution_date: date | None,
) -> PaymentRun:
    """One run over the chosen approved claims — by default every one with something
    open — and one ``issued`` payment per payee and IBAN."""
    require_pay_for(user, club_id)
    account = await club_account(session, club_id)
    if account is None:
        raise Problem(
            409,
            "club-bank-account-missing",
            "Save the account the club pays from first.",
        )

    if claim_ids is None:
        candidates = (
            (
                await session.execute(
                    select(ExpenseClaim)
                    .where(
                        ExpenseClaim.payer_club_id == club_id,
                        ExpenseClaim.status == ClaimStatus.APPROVED,
                    )
                    .order_by(ExpenseClaim.id)
                )
            )
            .scalars()
            .all()
        )
        # Left to choose, the run leaves out what this person may not pay themselves.
        chosen = [c for c in candidates if c.open_cents > 0 and c.claimant_user_id != user.id]
    else:
        found = await claims_of(session, set(claim_ids))
        chosen = []
        for claim_id in dict.fromkeys(claim_ids):
            claim = found.get(claim_id)
            if claim is None or claim.payer_club_id != club_id or claim.open_cents <= 0:
                raise Problem(
                    422,
                    "claim-not-payable",
                    "Only an approved claim of this club with something left open is paid.",
                    claim_id=claim_id,
                )
            if claim.claimant_user_id == user.id:
                raise Problem(403, "claim-own-decision", "Nobody decides or pays their own claim.")
            chosen.append(claim)
    if not chosen:
        raise Problem(422, "payment-run-empty", "There is nothing to pay.")

    day = execution_date or date.today()
    run = PaymentRun(
        payer_club_id=club_id,
        created_by_user_id=user.id,
        execution_date=day,
        message_id=f"SBL-{uuid.uuid4().hex[:28]}",
        debtor_name=account.holder,
        debtor_iban=account.iban,
        debtor_bic=account.bic,
    )
    session.add(run)

    by_payee: dict[tuple[int | None, str], list[ExpenseClaim]] = defaultdict(list)
    for claim in chosen:
        assert claim.iban is not None  # copied at submission (Story F-2)
        by_payee[(claim.claimant_user_id, claim.iban)].append(claim)
    for (payee_id, iban), claims in by_payee.items():
        payment = Payment(
            payer_club_id=club_id,
            payee_user_id=payee_id,
            payee_name=claims[0].payee_name or claims[0].claimant_name,
            iban=iban,
            status=PaymentStatus.ISSUED,
            method=PaymentMethod.SEPA_FILE,
            reference=remittance(claims),
            issued_by_user_id=user.id,
            issued_on=day,
        )
        for claim in claims:
            payment.allocations.append(
                PaymentAllocation(claim=claim, amount_cents=claim.open_cents)
            )
            _audit(session, "expense_claim", claim.id, "issued", user)
        run.payments.append(payment)
    await session.flush()
    _audit(session, "payment_run", run.id, "created", user, claims=len(chosen))
    return run


def remittance(claims: list[ExpenseClaim]) -> str:
    """The line the payee reads on their statement: every claim's number first — so a
    long list still names them all — then the first title."""
    ids = " ".join(f"C-{c.id}" for c in claims)
    return f"{ids} {claims[0].title}"[:REMITTANCE_MAX].strip()


class _RunTransfer(SepaTransfer):
    """``SepaTransfer`` with the run's message id instead of a fresh random one.

    The library writes the group header — message id included — inside its constructor,
    so assigning ``msg_id`` afterwards changes nothing in the file (docs/gotchas). The id
    is set here, just before the header is written.
    """

    def __init__(self, config: dict, message_id: str) -> None:
        self._message_id = message_id
        super().__init__(config, schema=SEPA_SCHEMA, clean=True)

    def _create_header(self) -> None:
        self.msg_id = self._message_id
        super()._create_header()


def sepa_file(run: PaymentRun) -> bytes:
    """The run as pain.001.001.09, validated against its XSD by ``sepaxml``. Every
    payment the run issued is in it, whatever became of it since: the file is what was
    sent, and its message id is the run's, so a bank refuses it a second time."""
    config = {
        "name": run.debtor_name,
        "IBAN": run.debtor_iban,
        "batch": True,
        "currency": "EUR",
    }
    if run.debtor_bic:
        config["BIC"] = run.debtor_bic
    transfer = _RunTransfer(config, run.message_id)
    for payment in run.payments:
        assert payment.iban is not None
        transfer.add_payment(
            {
                "name": payment.payee_name,
                "IBAN": payment.iban,
                "amount": payment.amount_cents,
                "execution_date": run.execution_date,
                "description": payment.reference or "",
                "endtoend_id": f"SBL-P-{payment.id}",
            }
        )
    return transfer.export(validate=True)


# ---------------------------------------------------------------------- the bank's answer


def settle_run(session: AsyncSession, user: User, run: PaymentRun, on: date | None) -> None:
    """ "Booked": every payment of the run still ``issued`` is ``settled``."""
    require_pay_for(user, run.payer_club_id)
    day = on or date.today()
    for payment in run.payments:
        if payment.status == PaymentStatus.ISSUED:
            payment.status = PaymentStatus.SETTLED
            payment.settled_on = day
    _audit(session, "payment_run", run.id, "settled", user)


def fail_payment(session: AsyncSession, user: User, payment: Payment, reason: str) -> None:
    """A transfer the bank refused or returned — also after it was booked. Kept as it
    is; its claims are open again and go into the next run (Story F-4)."""
    require_pay_for(user, payment.payer_club_id)
    if payment.status not in (PaymentStatus.ISSUED, PaymentStatus.SETTLED):
        raise Problem(
            409,
            "payment-not-failable",
            "Only an issued or booked payment can come back.",
            detail=f"The payment is {payment.status}.",
        )
    payment.status = PaymentStatus.FAILED
    payment.failure_reason = reason
    _audit(session, "payment", payment.id, "failed", user, reason=reason)


# ---------------------------------------------------------------------- spreadsheets

RUN_COLUMNS = [
    "Payment", "Claim", "Title", "Event / club", "Claimant", "Payee", "IBAN", "BIC",
    "Amount (EUR)", "Remittance", "Execution date", "Status",
]  # fmt: skip

BOOK_COLUMNS = [
    "Claim", "Submitted", "Claimant", "Event / club", "Title", "Date", "Kind",
    "Description", "km", "Claimed (EUR)", "Approved (EUR)", "Status", "Decided",
    "Note", "Payment state", "Paid (EUR)",
]  # fmt: skip


async def run_workbook(session: AsyncSession, run: PaymentRun) -> bytes:
    """The run, one row per claim — for the books, or a bank that takes no XML."""
    # Loaded here, not through ``allocation.claim``: that relationship is lazy, and a lazy
    # load in async code fails outright (MissingGreenlet) instead of querying.
    claims = await claims_of(session, {a.claim_id for p in run.payments for a in p.allocations})
    rows = []
    for payment in run.payments:
        for allocation in payment.allocations:
            claim = claims[allocation.claim_id]
            rows.append([
                f"P-{payment.id}", f"C-{claim.id}", claim.title, _target(claim),
                claim.claimant_name, payment.payee_name, payment.iban, _bic(payment.iban),
                allocation.amount_cents / 100, payment.reference, run.execution_date,
                payment.status,
            ])  # fmt: skip
    return _workbook("Payment run", RUN_COLUMNS, rows, money={"Amount (EUR)"})


def book_workbook(claims: list[ExpenseClaim]) -> bytes:
    """A year's claims of a club, one row per item — what a cash audit asks for."""
    rows = []
    for claim in claims:
        for item in claim.items:
            rows.append([
                f"C-{claim.id}", _day(claim.submitted_at), claim.claimant_name,
                _target(claim), claim.title, item.incurred_on, item.kind, item.description,
                item.distance_km, item.amount_cents / 100, item.approved_amount / 100,
                claim.status, _day(claim.decided_at), claim.decision_note,
                claim.payment_state, None,
            ])  # fmt: skip
        if rows and claim.items:
            # The paid total belongs to the claim, not to an item: on its first row.
            rows[-len(claim.items)][-1] = claim.paid_cents / 100
    return _workbook(
        "Claims", BOOK_COLUMNS, rows, money={"Claimed (EUR)", "Approved (EUR)", "Paid (EUR)"}
    )


async def claims_for_books(session: AsyncSession, club_id: int, year: int) -> list[ExpenseClaim]:
    """Every claim the club pays that was submitted in this year. A draft has no payer
    yet and is the claimant's own, so it is never in the books."""
    rows = (
        (
            await session.execute(
                select(ExpenseClaim)
                .where(ExpenseClaim.payer_club_id == club_id)
                .order_by(ExpenseClaim.submitted_at, ExpenseClaim.id)
            )
        )
        .scalars()
        .all()
    )
    return [c for c in rows if c.submitted_at is not None and c.submitted_at.year == year]


def _workbook(title: str, columns: list[str], rows: list[list], *, money: set[str]) -> bytes:
    book = Workbook()
    sheet = book.active
    assert sheet is not None
    sheet.title = title
    sheet.append(columns)
    for row in rows:
        sheet.append([str(v) if hasattr(v, "value") else v for v in row])
    for index, name in enumerate(columns, start=1):
        letter = get_column_letter(index)
        sheet.column_dimensions[letter].width = max(12, len(name) + 2)
        if name in money:
            for cell in sheet[letter][1:]:
                cell.number_format = "#,##0.00"
    sheet.freeze_panes = "A2"
    out = io.BytesIO()
    book.save(out)
    return out.getvalue()


def _target(claim: ExpenseClaim) -> str:
    if claim.event is not None:
        return claim.event.title
    return claim.club.name if claim.club is not None else ""


def _bic(iban: str | None) -> str | None:
    """Not stored on a claim — derived from the IBAN where the bank register knows it."""
    if not iban:
        return None
    try:
        bic = IBAN(iban).bic
    except SchwiftyException:
        return None
    return str(bic) if bic is not None else None


def _day(moment: datetime | None) -> date | None:
    return moment.date() if moment is not None else None


def _audit(
    session: AsyncSession, entity: str, entity_id: int, action: str, user: User, **payload
) -> None:
    session.add(
        AuditLog(
            entity_type=entity, entity_id=entity_id, action=action, actor=user.email,
            payload=payload,
        )
    )  # fmt: skip
