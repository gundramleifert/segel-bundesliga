"""Paying through the bank — Story F-7: the club's account, payment runs, the SEPA file,
the bank's answer, and the spreadsheets. The rules are ``app/services/payments.py``.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import current_user
from app.db import get_session
from app.models import Club, ClubBankAccount, Payment, PaymentRun, PaymentStatus
from app.models.auth import User
from app.problems import Problem
from app.routers.personal import BankAccountIn, BankAccountOut
from app.services import payments
from app.services.personal import bic_for, checked_iban

router = APIRouter(tags=["payments"])

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class RunCreate(BaseModel):
    claim_ids: list[int] | None = Field(
        default=None, description="Empty: every approved claim of the club with something open."
    )
    execution_date: date | None = Field(default=None, description="Empty: today.")


class RunPaymentOut(BaseModel):
    id: int
    payee_name: str
    iban: str | None
    amount_cents: int
    reference: str | None
    status: PaymentStatus
    failure_reason: str | None
    claim_ids: list[int]


class RunOut(BaseModel):
    id: int
    payer_club_id: int
    payer_club_name: str
    execution_date: date
    message_id: str
    debtor_iban: str
    total_cents: int
    open: bool
    payments: list[RunPaymentOut]


class FailBody(BaseModel):
    reason: str = Field(
        min_length=1, max_length=200, description="The bank's reason code, or a sentence."
    )


class SettleBody(BaseModel):
    settled_on: date | None = Field(default=None, description="Empty: today.")


class ClubBankAccountOut(BankAccountOut):
    model_config = ConfigDict(from_attributes=True)


async def _run_out(session: AsyncSession, run: PaymentRun) -> RunOut:
    club = await session.get(Club, run.payer_club_id)
    return RunOut(
        id=run.id,
        payer_club_id=run.payer_club_id,
        payer_club_name=club.name if club is not None else "",
        execution_date=run.execution_date,
        message_id=run.message_id,
        debtor_iban=run.debtor_iban,
        total_cents=run.total_cents,
        open=run.open,
        payments=[
            RunPaymentOut(
                id=p.id,
                payee_name=p.payee_name,
                iban=p.iban,
                amount_cents=p.amount_cents,
                reference=p.reference,
                status=PaymentStatus(p.status),
                failure_reason=p.failure_reason,
                claim_ids=[a.claim_id for a in p.allocations],
            )
            for p in run.payments
        ],
    )


async def _club(session: AsyncSession, club_id: int, acting: User) -> Club:
    club = await session.get(Club, club_id)
    if club is None:
        raise Problem(404, "club-not-found", "No such club.")
    payments.require_pay_for(acting, club_id)
    return club


async def _run(session: AsyncSession, run_id: int, acting: User) -> PaymentRun:
    run = await payments.load_run(session, run_id)
    payments.require_pay_for(acting, run.payer_club_id)
    return run


# ------------------------------------------------------------------ the club's account


@router.get(
    "/api/clubs/{club_id}/bank-account",
    response_model=ClubBankAccountOut | None,
    summary="The account the club pays from",
)
async def get_club_bank_account(
    club_id: int,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> ClubBankAccount | None:
    await _club(session, club_id, acting)
    return await payments.club_account(session, club_id)


@router.put(
    "/api/clubs/{club_id}/bank-account",
    response_model=ClubBankAccountOut,
    summary="Save the account the club pays from",
)
async def save_club_bank_account(
    club_id: int,
    body: BankAccountIn,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> ClubBankAccount:
    await _club(session, club_id, acting)
    iban = checked_iban(body.iban)
    bic = bic_for(iban, body.bic)
    account = await payments.club_account(session, club_id)
    if account is None:
        account = ClubBankAccount(club_id=club_id, holder="", iban="")
        session.add(account)
    account.holder = body.holder.strip()
    account.iban = iban.compact
    account.bic = bic
    await session.commit()
    return account


# ------------------------------------------------------------------ runs


@router.get("/api/payment-runs", response_model=list[RunOut], summary="Runs waiting for the bank")
async def list_open_payment_runs(
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> list[RunOut]:
    return [await _run_out(session, run) for run in await payments.open_runs(session, acting)]


@router.post(
    "/api/clubs/{club_id}/payment-runs",
    response_model=RunOut,
    status_code=status.HTTP_201_CREATED,
    summary="Pay approved claims through one SEPA file",
)
async def create_payment_run(
    club_id: int,
    body: RunCreate,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> RunOut:
    await _club(session, club_id, acting)
    run = await payments.create_run(
        session, acting, club_id, claim_ids=body.claim_ids, execution_date=body.execution_date
    )
    await session.commit()
    return await _run_out(session, await payments.load_run(session, run.id))


@router.get(
    "/api/payment-runs/{run_id}/sepa",
    summary="The run as a SEPA file (pain.001.001.09) for online banking",
    response_class=Response,
)
async def download_payment_run_sepa(
    run_id: int,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> Response:
    run = await _run(session, run_id, acting)
    return Response(
        payments.sepa_file(run),
        media_type="application/xml",
        headers={
            "Content-Disposition": f'attachment; filename="sepa-{run.message_id}.xml"',
            "Cache-Control": "private, no-store",
        },
    )


@router.get(
    "/api/payment-runs/{run_id}/xlsx",
    summary="The run as a spreadsheet",
    response_class=Response,
)
async def download_payment_run_xlsx(
    run_id: int,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> Response:
    run = await _run(session, run_id, acting)
    return _xlsx(await payments.run_workbook(session, run), f"payment-run-{run.id}.xlsx")


@router.post(
    "/api/payment-runs/{run_id}/settle", response_model=RunOut, summary="The bank booked the run"
)
async def settle_payment_run(
    run_id: int,
    body: SettleBody | None = None,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> RunOut:
    run = await _run(session, run_id, acting)
    payments.settle_run(session, acting, run, body.settled_on if body else None)
    await session.commit()
    return await _run_out(session, await payments.load_run(session, run_id))


@router.post(
    "/api/payments/{payment_id}/fail", response_model=RunOut, summary="The bank returned a payment"
)
async def fail_payment(
    payment_id: int,
    body: FailBody,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> RunOut:
    payment = await session.get(Payment, payment_id)
    if payment is None or payment.run_id is None:
        raise Problem(404, "payment-not-found", "No such payment in a run.")
    payments.fail_payment(session, acting, payment, body.reason.strip())
    await session.commit()
    return await _run_out(session, await payments.load_run(session, payment.run_id))


# ------------------------------------------------------------------ the books


@router.get(
    "/api/clubs/{club_id}/claims.xlsx",
    summary="A year's claims of the club as a spreadsheet",
    response_class=Response,
)
async def download_club_claims_xlsx(
    club_id: int,
    year: int | None = Query(default=None, ge=2000, le=2100, description="Empty: this year."),
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> Response:
    club = await _club(session, club_id, acting)
    year = year or date.today().year
    claims = await payments.claims_for_books(session, club_id, year)
    return _xlsx(payments.book_workbook(claims), f"claims-{club.slug}-{year}.xlsx")


def _xlsx(content: bytes, filename: str) -> Response:
    return Response(
        content,
        media_type=XLSX,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "private, no-store",
        },
    )
