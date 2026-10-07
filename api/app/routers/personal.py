"""My space — Stories S-5, S-6: a person's own documents and bank account.

The documents are read by their owner and by the person's organizers
(``app/services/personal.py::may_see_documents``), and every look by anyone but the owner
is written to the audit log, as for a waiver scan. The bank account is read by its owner
alone; whoever decides a claim sees the copy taken at submission, never this.
"""

from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import current_user
from app.db import get_session
from app.models import AuditLog, BankAccount, DocumentKind, PersonalDocument
from app.models.auth import User
from app.problems import Problem
from app.services import uploads
from app.services.personal import DOCUMENTS, bic_for, checked_iban, may_see_documents

router = APIRouter(tags=["personal"])


class PersonalDocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: DocumentKind
    title: str | None
    valid_until: date | None
    expired: bool
    original_name: str
    content_type: str
    size_bytes: int
    created_at: datetime


class BankAccountIn(BaseModel):
    holder: str = Field(min_length=1, max_length=160)
    iban: str = Field(min_length=15, max_length=50, description="Spaces are allowed.")
    bic: str | None = Field(
        default=None, max_length=11, description="Empty: taken from the IBAN's bank code."
    )


class BankAccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    holder: str
    iban: str
    bic: str | None


# ------------------------------------------------------------------ documents


@router.get(
    "/api/me/documents",
    response_model=list[PersonalDocumentOut],
    summary="My documents",
)
async def list_my_documents(
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> list[PersonalDocument]:
    return await _documents_of(session, acting.id)


@router.post(
    "/api/me/documents",
    response_model=PersonalDocumentOut,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a document",
)
async def upload_my_document(
    file: UploadFile = File(...),
    kind: DocumentKind = Form(...),
    title: str | None = Form(default=None, max_length=200),
    valid_until: date | None = Form(default=None),
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> PersonalDocument:
    """A licence or certificate with its label (Story S-5). ``other`` needs a title —
    otherwise nobody can tell what it is."""
    title = (title or "").strip() or None
    if kind == DocumentKind.OTHER and title is None:
        raise Problem(422, "document-title-required", "Say what this document is.")
    raw = await file.read()
    media_type = uploads.validated(raw, file.content_type, code="document", what="A document")
    document = PersonalDocument(
        user_id=acting.id,
        kind=kind,
        title=title,
        valid_until=valid_until,
        stored_name=uploads.store(DOCUMENTS, raw, media_type),
        original_name=(file.filename or "document")[:255],
        content_type=media_type,
        size_bytes=len(raw),
    )
    session.add(document)
    await session.commit()
    await session.refresh(document)
    return document


@router.delete(
    "/api/me/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete one of my documents",
)
async def delete_my_document(
    document_id: int,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> Response:
    document = await session.get(PersonalDocument, document_id)
    # Someone else's reads as absent: it is nobody's business that it exists.
    if document is None or document.user_id != acting.id:
        raise Problem(404, "document-not-found", "No such document.")
    uploads.discard(DOCUMENTS, document.stored_name)
    await session.delete(document)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/api/people/{user_id}/documents",
    response_model=list[PersonalDocumentOut],
    summary="A person's documents, for their organizers",
)
async def list_person_documents(
    user_id: int,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> list[PersonalDocument]:
    """For the managers of the events the person works at and of the clubs they belong to
    (Story S-5) — the boat licence of a RIB driver, checked before the day."""
    if not await may_see_documents(session, acting, user_id):
        raise _forbidden()
    return await _documents_of(session, user_id)


@router.get(
    "/api/documents/{document_id}/file",
    summary="The file of a personal document",
    response_class=FileResponse,
)
async def get_document_file(
    document_id: int,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> FileResponse:
    document = await session.get(PersonalDocument, document_id)
    found = uploads.path(DOCUMENTS, document.stored_name) if document is not None else None
    if document is None or found is None:
        raise Problem(404, "document-not-found", "No such document.")
    if not await may_see_documents(session, acting, document.user_id):
        raise _forbidden()
    if acting.id != document.user_id:
        session.add(
            AuditLog(
                entity_type="personal_document",
                entity_id=document.id,
                action="viewed",
                actor=acting.email,
                payload={"owner_user_id": document.user_id},
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


def _forbidden() -> Problem:
    return Problem(
        403,
        "documents-forbidden",
        "A person's documents are shown only to them and to the organizers of the events "
        "and clubs they belong to.",
    )


async def _documents_of(session: AsyncSession, user_id: int) -> list[PersonalDocument]:
    return list(
        (
            await session.execute(
                select(PersonalDocument)
                .where(PersonalDocument.user_id == user_id)
                .order_by(PersonalDocument.kind, PersonalDocument.id)
            )
        )
        .scalars()
        .all()
    )


# ------------------------------------------------------------------ bank account


@router.get(
    "/api/me/bank-account",
    response_model=BankAccountOut | None,
    summary="My bank account",
)
async def get_my_bank_account(
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> BankAccount | None:
    """Empty (``null``) until one is saved — not a 404: having none is the normal start."""
    return await _bank_account(session, acting.id)


@router.put(
    "/api/me/bank-account",
    response_model=BankAccountOut,
    summary="Save my bank account",
)
async def save_my_bank_account(
    body: BankAccountIn,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> BankAccount:
    iban = checked_iban(body.iban)
    bic = bic_for(iban, body.bic)
    account = await _bank_account(session, acting.id)
    if account is None:
        account = BankAccount(user_id=acting.id, holder="", iban="")
        session.add(account)
    account.holder = body.holder.strip()
    account.iban = iban.compact
    account.bic = bic
    await session.commit()
    return account


@router.delete(
    "/api/me/bank-account",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete my bank account",
)
async def delete_my_bank_account(
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> Response:
    account = await _bank_account(session, acting.id)
    if account is not None:
        await session.delete(account)
        await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


async def _bank_account(session: AsyncSession, user_id: int) -> BankAccount | None:
    return (
        await session.execute(select(BankAccount).where(BankAccount.user_id == user_id))
    ).scalar_one_or_none()
