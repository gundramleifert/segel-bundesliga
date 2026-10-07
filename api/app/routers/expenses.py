"""Expense claims — Stories F-2 to F-6. The rules are ``app/services/expenses.py``; this
module only turns requests into its calls and claims into responses.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import current_user
from app.db import get_session
from app.models import (
    AuditLog,
    ClaimStatus,
    Event,
    ExpenseClaim,
    ExpenseDocument,
    ExpenseKind,
    PaymentMethod,
    PaymentState,
)
from app.models.auth import User
from app.problems import Problem
from app.services import expenses, payments, uploads
from app.services.personal import RECEIPTS

router = APIRouter(tags=["expenses"])


# ------------------------------------------------------------------ schemas


class ClaimTarget(BaseModel):
    kind: Literal["event", "club"]
    id: int
    name: str
    starts_on: date | None = None


class ClaimCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    event_id: int | None = None
    club_id: int | None = None

    @model_validator(mode="after")
    def _one_target(self) -> ClaimCreate:
        if (self.event_id is None) == (self.club_id is None):
            raise ValueError("Name exactly one of event_id and club_id.")
        return self


class ClaimUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class ItemCreate(BaseModel):
    kind: ExpenseKind
    incurred_on: date
    description: str = Field(min_length=1, max_length=300)
    distance_km: int | None = Field(default=None, ge=1, le=10000, description="Car only.")
    amount_cents: int | None = Field(
        default=None, ge=0, le=10_000_000, description="Every kind but car; whole cents."
    )


class ItemOut(BaseModel):
    id: int
    kind: ExpenseKind
    incurred_on: date
    description: str
    distance_km: int | None
    rate_cents: int | None
    amount_cents: int
    approved_cents: int | None


class ClaimDocumentOut(BaseModel):
    id: int
    item_id: int | None
    original_name: str
    content_type: str
    size_bytes: int


class ClaimOut(BaseModel):
    id: int
    title: str
    status: ClaimStatus
    event_id: int | None
    event_title: str | None
    club_id: int | None
    club_name: str | None
    payer_club_id: int | None
    payer_club_name: str | None
    claimant_user_id: int | None
    claimant_name: str
    # The copy taken at submission; shown to the claimant and whoever decides.
    payee_name: str | None
    iban: str | None
    submitted_at: datetime | None
    decided_at: datetime | None
    decision_note: str | None
    claimed_cents: int
    approved_cents: int
    paid_cents: int
    payment_state: PaymentState | None
    items: list[ItemOut]
    documents: list[ClaimDocumentOut]
    # What the asking person may do with it — the screen shows buttons from these.
    may_edit: bool
    may_decide: bool
    # In the pending list: what the decider is to do — ``decide`` or ``pay``.
    action: Literal["decide", "pay"] | None


class ItemCut(BaseModel):
    item_id: int
    approved_cents: int = Field(ge=0)


class ApproveBody(BaseModel):
    items: list[ItemCut] = Field(
        default_factory=list, description="Items approved below their claim; others as claimed."
    )
    note: str | None = Field(default=None, max_length=1000)


class NoteBody(BaseModel):
    note: str = Field(min_length=1, max_length=1000)


class PayBody(BaseModel):
    paid_on: date | None = Field(default=None, description="Empty: today.")
    reference: str | None = Field(default=None, max_length=140)
    method: PaymentMethod = PaymentMethod.TRANSFER


def _out(claim: ExpenseClaim, acting: User) -> ClaimOut:
    own = claim.claimant_user_id == acting.id
    return ClaimOut(
        id=claim.id,
        title=claim.title,
        status=ClaimStatus(claim.status),
        event_id=claim.event_id,
        event_title=claim.event.title if claim.event is not None else None,
        club_id=claim.club_id,
        club_name=claim.club.name if claim.club is not None else None,
        payer_club_id=claim.payer_club_id,
        payer_club_name=claim.payer_club.name if claim.payer_club is not None else None,
        claimant_user_id=claim.claimant_user_id,
        claimant_name=claim.claimant_name,
        payee_name=claim.payee_name,
        iban=claim.iban,
        submitted_at=claim.submitted_at,
        decided_at=claim.decided_at,
        decision_note=claim.decision_note,
        claimed_cents=claim.claimed_cents,
        approved_cents=claim.approved_cents,
        paid_cents=claim.paid_cents,
        payment_state=claim.payment_state,
        items=[
            ItemOut(
                id=i.id,
                kind=ExpenseKind(i.kind),
                incurred_on=i.incurred_on,
                description=i.description,
                distance_km=i.distance_km,
                rate_cents=i.rate_cents,
                amount_cents=i.amount_cents,
                approved_cents=i.approved_cents,
            )
            for i in claim.items
        ],
        documents=[
            ClaimDocumentOut(
                id=d.id,
                item_id=d.item_id,
                original_name=d.original_name,
                content_type=d.content_type,
                size_bytes=d.size_bytes,
            )
            for d in claim.documents
        ],
        may_edit=own and claim.status in expenses.EDITABLE,
        may_decide=not own and expenses.may_decide(acting, claim),
        action=expenses.action(claim) if not own and expenses.may_decide(acting, claim) else None,
    )


async def _visible(session: AsyncSession, claim_id: int, acting: User) -> ExpenseClaim:
    claim = await expenses.load(session, claim_id)
    if not expenses.may_see(acting, claim):
        # Someone else's claim reads as absent.
        raise Problem(404, "claim-not-found", "No such claim.")
    return claim


async def _saved(session: AsyncSession, claim_id: int, acting: User) -> ClaimOut:
    await session.commit()
    return _out(await expenses.load(session, claim_id), acting)


# ------------------------------------------------------------------ the claimant


@router.get(
    "/api/me/claim-targets", response_model=list[ClaimTarget], summary="What I may claim on"
)
async def list_my_claim_targets(
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> list[ClaimTarget]:
    """The events I worked at and the clubs I belong to (Story F-2)."""
    out: list[ClaimTarget] = []
    for _, obj in await expenses.targets(session, acting):
        if isinstance(obj, Event):
            out.append(
                ClaimTarget(kind="event", id=obj.id, name=obj.title, starts_on=obj.starts_on)
            )
        else:
            out.append(ClaimTarget(kind="club", id=obj.id, name=obj.name))
    return out


@router.get("/api/me/claims", response_model=list[ClaimOut], summary="My claims")
async def list_my_claims(
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> list[ClaimOut]:
    rows = (
        await session.execute(
            select(ExpenseClaim)
            .where(ExpenseClaim.claimant_user_id == acting.id)
            .order_by(ExpenseClaim.id.desc())
        )
    ).scalars()
    return [_out(claim, acting) for claim in rows]


@router.post("/api/claims", response_model=ClaimOut, status_code=201, summary="Start a claim")
async def create_claim(
    body: ClaimCreate,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> ClaimOut:
    claim = await expenses.create(
        session, acting, title=body.title.strip(), event_id=body.event_id, club_id=body.club_id
    )
    return await _saved(session, claim.id, acting)


@router.get("/api/claims/pending", response_model=list[ClaimOut], summary="Claims waiting for me")
async def list_pending_claims(
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> list[ClaimOut]:
    """To decide or to pay, on every event and club whose money I hold (Story F-6)."""
    return [_out(claim, acting) for claim in await expenses.pending(session, acting)]


@router.get("/api/claims/{claim_id}", response_model=ClaimOut, summary="One claim")
async def get_claim(
    claim_id: int,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> ClaimOut:
    return _out(await _visible(session, claim_id, acting), acting)


@router.patch("/api/claims/{claim_id}", response_model=ClaimOut, summary="Rename a claim")
async def update_claim(
    claim_id: int,
    body: ClaimUpdate,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> ClaimOut:
    claim = await _visible(session, claim_id, acting)
    expenses.require_claimant(acting, claim)
    expenses.require_editable(claim)
    claim.title = body.title.strip()
    return await _saved(session, claim_id, acting)


@router.delete("/api/claims/{claim_id}", status_code=204, summary="Delete a draft claim")
async def delete_claim(
    claim_id: int,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> None:
    """Only a draft — once submitted, a claim is withdrawn, never deleted."""
    claim = await _visible(session, claim_id, acting)
    expenses.require_claimant(acting, claim)
    if claim.status != ClaimStatus.DRAFT:
        raise Problem(409, "claim-not-editable", "Only a draft is deleted; withdraw it instead.")
    for document in claim.documents:
        uploads.discard(RECEIPTS, document.stored_name)
    await session.delete(claim)
    await session.commit()


@router.post("/api/claims/{claim_id}/items", response_model=ClaimOut, summary="Add an item")
async def add_claim_item(
    claim_id: int,
    body: ItemCreate,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> ClaimOut:
    claim = await _visible(session, claim_id, acting)
    await expenses.add_item(
        session,
        acting,
        claim,
        kind=body.kind,
        incurred_on=body.incurred_on,
        description=body.description.strip(),
        distance_km=body.distance_km,
        amount_cents=body.amount_cents,
    )
    return await _saved(session, claim_id, acting)


@router.delete(
    "/api/claims/{claim_id}/items/{item_id}", response_model=ClaimOut, summary="Remove an item"
)
async def delete_claim_item(
    claim_id: int,
    item_id: int,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> ClaimOut:
    claim = await _visible(session, claim_id, acting)
    expenses.require_claimant(acting, claim)
    expenses.require_editable(claim)
    item = next((i for i in claim.items if i.id == item_id), None)
    if item is None:
        raise Problem(404, "expense-item-unknown", "That item is not on this claim.")
    for document in claim.documents:
        if document.item_id == item_id:
            document.item_id = None
    claim.items.remove(item)
    return await _saved(session, claim_id, acting)


@router.post(
    "/api/claims/{claim_id}/documents", response_model=ClaimOut, summary="Attach a receipt"
)
async def upload_claim_document(
    claim_id: int,
    file: UploadFile = File(...),
    item_id: int | None = Form(default=None),
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> ClaimOut:
    """A receipt, invoice or ticket (Story F-5) — for one item, or the whole claim."""
    claim = await _visible(session, claim_id, acting)
    expenses.require_claimant(acting, claim)
    expenses.require_editable(claim)
    if item_id is not None and all(i.id != item_id for i in claim.items):
        raise Problem(404, "expense-item-unknown", "That item is not on this claim.")
    raw = await file.read()
    media_type = uploads.validated(
        raw, file.content_type, code="expense-document", what="A receipt"
    )
    claim.documents.append(
        ExpenseDocument(
            item_id=item_id,
            stored_name=uploads.store(RECEIPTS, raw, media_type),
            original_name=(file.filename or "receipt")[:255],
            content_type=media_type,
            size_bytes=len(raw),
            uploaded_by_user_id=acting.id,
        )
    )
    return await _saved(session, claim_id, acting)


@router.delete(
    "/api/claims/{claim_id}/documents/{document_id}",
    response_model=ClaimOut,
    summary="Remove a receipt",
)
async def delete_claim_document(
    claim_id: int,
    document_id: int,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> ClaimOut:
    claim = await _visible(session, claim_id, acting)
    expenses.require_claimant(acting, claim)
    expenses.require_editable(claim)
    document = next((d for d in claim.documents if d.id == document_id), None)
    if document is None:
        raise Problem(404, "expense-document-not-found", "No such receipt on this claim.")
    uploads.discard(RECEIPTS, document.stored_name)
    claim.documents.remove(document)
    return await _saved(session, claim_id, acting)


@router.get(
    "/api/claims/{claim_id}/documents/{document_id}",
    summary="The file of a receipt",
    response_class=FileResponse,
)
async def get_claim_document(
    claim_id: int,
    document_id: int,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> FileResponse:
    claim = await expenses.load(session, claim_id)
    if not expenses.may_see(acting, claim):
        raise Problem(
            403,
            "claim-forbidden",
            "A receipt is shown only to the claimant and whoever decides the claim.",
        )
    document = next((d for d in claim.documents if d.id == document_id), None)
    found = uploads.path(RECEIPTS, document.stored_name) if document is not None else None
    if document is None or found is None:
        raise Problem(404, "expense-document-not-found", "No such receipt on this claim.")
    if claim.claimant_user_id != acting.id:
        session.add(
            AuditLog(
                entity_type="expense_document",
                entity_id=document.id,
                action="viewed",
                actor=acting.email,
                payload={"claim_id": claim.id},
            )
        )
        await session.commit()
    return FileResponse(
        found,
        media_type=document.content_type,
        filename=document.original_name,
        content_disposition_type="inline",
        headers={"Cache-Control": "private, no-store"},
    )


@router.post("/api/claims/{claim_id}/submit", response_model=ClaimOut, summary="Submit a claim")
async def submit_claim(
    claim_id: int,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> ClaimOut:
    claim = await _visible(session, claim_id, acting)
    await expenses.submit(session, acting, claim)
    return await _saved(session, claim_id, acting)


@router.post("/api/claims/{claim_id}/withdraw", response_model=ClaimOut, summary="Withdraw a claim")
async def withdraw_claim(
    claim_id: int,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> ClaimOut:
    claim = await _visible(session, claim_id, acting)
    expenses.withdraw(session, acting, claim)
    return await _saved(session, claim_id, acting)


# ------------------------------------------------------------------ the decider


async def _decidable(session: AsyncSession, claim_id: int, acting: User) -> ExpenseClaim:
    """The claim, or the refusal that says why this person may not decide it — 403 rather
    than the claimant's 404, so a manager learns it is not theirs."""
    claim = await expenses.load(session, claim_id)
    expenses.require_decider(acting, claim)
    return claim


@router.post("/api/claims/{claim_id}/approve", response_model=ClaimOut, summary="Approve a claim")
async def approve_claim(
    claim_id: int,
    body: ApproveBody,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> ClaimOut:
    claim = await _decidable(session, claim_id, acting)
    expenses.approve(
        session,
        acting,
        claim,
        cuts={cut.item_id: cut.approved_cents for cut in body.items},
        note=body.note,
    )
    return await _saved(session, claim_id, acting)


@router.post(
    "/api/claims/{claim_id}/return", response_model=ClaimOut, summary="Return a claim for changes"
)
async def return_claim(
    claim_id: int,
    body: NoteBody,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> ClaimOut:
    claim = await _decidable(session, claim_id, acting)
    expenses.send_back(session, acting, claim, ClaimStatus.RETURNED, body.note.strip())
    return await _saved(session, claim_id, acting)


@router.post("/api/claims/{claim_id}/reject", response_model=ClaimOut, summary="Reject a claim")
async def reject_claim(
    claim_id: int,
    body: NoteBody,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> ClaimOut:
    claim = await _decidable(session, claim_id, acting)
    expenses.send_back(session, acting, claim, ClaimStatus.REJECTED, body.note.strip())
    return await _saved(session, claim_id, acting)


@router.post("/api/claims/{claim_id}/pay", response_model=ClaimOut, summary="Mark a claim as paid")
async def pay_claim(
    claim_id: int,
    body: PayBody,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> ClaimOut:
    claim = await _decidable(session, claim_id, acting)
    expenses.pay(
        session, acting, claim, paid_on=body.paid_on, reference=body.reference, method=body.method
    )
    return await _saved(session, claim_id, acting)


@router.get(
    "/api/claims/{claim_id}/girocode",
    summary="The claim as a GiroCode (EPC QR) for a banking app",
    response_class=Response,
)
async def get_claim_girocode(
    claim_id: int,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> Response:
    """Scanned with a banking app's photo transfer, it fills in payee, IBAN, amount and
    line; the app's own TAN pays (Story F-8). "Mark as paid" records it afterwards."""
    claim = await expenses.load(session, claim_id)
    if claim.claimant_user_id != acting.id:
        expenses.require_decider(acting, claim)
    return Response(
        payments.girocode_svg(acting, claim),
        media_type="image/svg+xml",
        headers={"Cache-Control": "private, no-store"},
    )
