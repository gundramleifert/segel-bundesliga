"""Liability waiver — versioned text and its confirmation — Stories S-2, VA-2, VA-5.

A sailor confirms **one specific version** of the waiver, for **one competition**: an
event, or a whole series. A series confirmation covers every event of that series, so a
sailor who competes all season signs once.

The text is versioned and frozen: a confirmation always names the exact version, and a
later change to the wording is a new version that everyone re-confirms — it never
retroactively alters what was already agreed.

**Minors** (under 18 on the reference date — the event start, or the series start) cannot
clear the waiver by their own click. Their confirmation must be recorded as ``guardian``
with the guardian's name and a reference to the signed statement on file.
"""

from __future__ import annotations

import io
from datetime import date, datetime
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import current_user, optional_user, require_admin
from app.db import get_session
from app.i18n import Locale
from app.models import (
    AuditLog,
    Club,
    Event,
    Sailor,
    Series,
    Team,
    TeamMembership,
    TeamStatus,
    WaiverConfirmation,
    WaiverMethod,
    WaiverText,
)
from app.models.auth import Role, User
from app.problems import Problem
from app.routers.sailors import _my_sailor as my_sailor
from app.services import current_waiver_text, event_waiver_status, is_minor
from app.services.waiver_form import render_waiver_form
from app.services.waivers import (
    SCAN_MAX_BYTES,
    SCAN_MEDIA_TYPES,
    STATUS_CLEARED,
    SailorWaiver,
    discard_scan,
    event_reference_date,
    sailor_competitions,
    scan_media_type,
    scan_path,
    series_reference_date,
    series_waiver_status,
    store_scan,
)

Scope = Literal["series", "event"]

router = APIRouter(tags=["waiver"])


# --------------------------------------------------------------------- Schemas


class WaiverTextOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    version: int
    published_at: datetime
    title_en: str
    body_en: str
    title_de: str
    body_de: str
    notes: str | None = None


class WaiverTextCreate(BaseModel):
    """A new version. The version number is assigned automatically (previous + 1)."""

    title_en: str = Field(min_length=1, max_length=200)
    body_en: str = Field(min_length=1)
    title_de: str = Field(min_length=1, max_length=200)
    body_de: str = Field(min_length=1)
    notes: str | None = Field(default=None, max_length=500)


class ConfirmWaiver(BaseModel):
    sailor_id: int
    locale_shown: Locale = Field(
        default="en", description="Which language of the text the sailor was shown."
    )
    method: WaiverMethod | None = Field(
        default=None,
        description=(
            "Left empty, an adult is recorded as 'online' and a minor must be 'guardian'. "
            "Passing 'online' for a minor is rejected."
        ),
    )
    guardian_name: str | None = Field(default=None, max_length=160)
    guardian_signature_ref: str | None = Field(
        default=None,
        max_length=500,
        description="Where the signed statement lives: a URL, an object key, or a note.",
    )


class WaiverConfirmationOut(BaseModel):
    id: int
    sailor_id: int
    version: int
    scope: str
    scope_id: int
    method: str
    locale_shown: str
    confirmed_at: datetime
    guardian_name: str | None = None
    # Whether this sailor is now cleared for the competition.
    cleared: bool


class SailorWaiverRow(BaseModel):
    sailor_id: int
    first_name: str
    last_name: str
    club: str | None = None
    status: str
    minor: bool | None = None
    required_version: int | None = None
    confirmed_version: int | None = None
    confirmed_at: datetime | None = None
    method: str | None = None
    guardian_name: str | None = None
    # The uploaded form, if there is one — the organizer opens it from the list.
    confirmation_id: int | None = None
    scan_available: bool = False


class EventWaiverList(BaseModel):
    event_id: int
    required_version: int | None
    cleared: int
    outstanding: int
    sailors: list[SailorWaiverRow]


class MyCompetitionWaiver(BaseModel):
    """One competition the signed-in sailor has to sign for, and where they stand."""

    scope: Scope
    scope_id: int
    name: str
    reference_date: date
    sailor_id: int
    status: str
    minor: bool | None = None
    required_version: int | None = None
    confirmed_version: int | None = None
    confirmed_at: datetime | None = None
    method: str | None = None
    guardian_name: str | None = None
    # The row behind the status — the address of the scan endpoint. Empty until something
    # was recorded.
    confirmation_id: int | None = None
    scan_available: bool = False


class MyWaivers(BaseModel):
    sailor_id: int
    first_name: str
    last_name: str
    # Without it no status can be judged — the page then points at the profile form.
    birth_date_known: bool
    required_version: int | None
    competitions: list[MyCompetitionWaiver]


# --------------------------------------------------------------------- Public text


@router.get("/api/waiver", response_model=WaiverTextOut, summary="Current waiver text")
async def get_current_waiver(
    session: AsyncSession = Depends(get_session),
    _: User | None = Depends(optional_user),
) -> WaiverTextOut:
    """The version in force. Both languages are returned so the client can show either."""
    text_row = await current_waiver_text(session)
    if text_row is None:
        raise Problem(
            404, "no-waiver-published", "No liability waiver has been published yet."
        )
    return WaiverTextOut.model_validate(text_row)


# --------------------------------------------------------------------- My own status


@router.get(
    "/api/waiver/me", response_model=MyWaivers, summary="What I have to sign, and where I stand"
)
async def my_waivers(
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> MyWaivers:
    """Story S-1: the account page's list — one row per series the sailor is registered
    in and per stand-alone event they are entered in, each with the same status the
    organizer's list would show. 404 `no-linked-sailor-record` when the account has no
    sailor, exactly as the profile does."""
    sailor = await my_sailor(session, acting)
    required = await current_waiver_text(session)
    rows: list[MyCompetitionWaiver] = []
    for competition in await sailor_competitions(session, sailor):
        if competition.series is not None:
            judged = await series_waiver_status(session, competition.series, sailor)
        else:
            assert competition.event is not None
            judged = (await event_waiver_status(session, competition.event, [sailor.id]))[sailor.id]
        rows.append(
            MyCompetitionWaiver(
                scope=competition.scope,  # type: ignore[arg-type]
                scope_id=competition.scope_id,
                name=competition.name,
                reference_date=competition.reference_date,
                **_status_fields(judged),
            )
        )
    return MyWaivers(
        sailor_id=sailor.id,
        first_name=sailor.first_name,
        last_name=sailor.last_name,
        birth_date_known=sailor.birth_date is not None,
        required_version=required.version if required else None,
        competitions=rows,
    )


@router.get("/api/waiver/form", summary="The waiver as a printable form (PDF)")
async def waiver_form(
    scope: Scope = Query(...),
    scope_id: int = Query(...),
    sailor_id: int = Query(...),
    locale: Locale = Query("en"),
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> Response:
    """Story S-1: the paper a guardian signs — the wording in force, the sailor, the
    competition, and signature lines. Anyone who may record a confirmation for the sailor
    may print their form. An adult gets the same sheet with their own signature line, for
    whoever prefers paper."""
    sailor = await _sailor(session, sailor_id)
    _may_confirm_for(acting, sailor)
    required = await current_waiver_text(session)
    if required is None:
        raise Problem(404, "no-waiver-published", "No liability waiver has been published yet.")
    name, reference_date = await _scope(session, scope, scope_id)
    pdf = render_waiver_form(
        text=required,
        sailor=sailor,
        competition=name,
        locale=locale,
        minor=is_minor(sailor.birth_date, reference_date) is not False,
    )
    filename = f"waiver-v{required.version}-{scope}-{scope_id}-sailor-{sailor.id}.pdf"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# --------------------------------------------------------------------- Admin: versions


@router.get(
    "/api/admin/waiver/texts",
    response_model=list[WaiverTextOut],
    dependencies=[Depends(require_admin)],
    summary="All waiver versions",
)
async def list_waiver_texts(
    session: AsyncSession = Depends(get_session),
) -> list[WaiverTextOut]:
    rows = (
        await session.execute(
            select(WaiverText).order_by(WaiverText.version.desc())
        )
    ).scalars().all()
    return [WaiverTextOut.model_validate(row) for row in rows]


@router.post(
    "/api/admin/waiver/texts",
    response_model=WaiverTextOut,
    status_code=201,
    dependencies=[Depends(require_admin)],
    summary="Publish a new waiver version",
)
async def publish_waiver_text(
    request: WaiverTextCreate,
    session: AsyncSession = Depends(get_session),
) -> WaiverTextOut:
    """Adds the next version. From now on it is the one in force, and it is frozen.

    Confirmations of earlier versions stay exactly as they were; sailors are simply no
    longer cleared until they confirm this one.
    """
    highest = (
        await session.execute(
            select(WaiverText.version).order_by(WaiverText.version.desc()).limit(1)
        )
    ).scalar_one_or_none()
    text_row = WaiverText(version=(highest or 0) + 1, **request.model_dump())
    session.add(text_row)
    await session.commit()
    return WaiverTextOut.model_validate(text_row)


# --------------------------------------------------------------------- Confirm


@router.post(
    "/api/series/{series_id}/waiver",
    response_model=WaiverConfirmationOut,
    status_code=201,
    summary="Confirm the waiver for a series",
)
async def confirm_for_series(
    series_id: int,
    request: ConfirmWaiver,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
    user_agent: str | None = Header(default=None),
) -> WaiverConfirmationOut:
    """One confirmation here counts for every event of the series."""
    series = (
        await session.execute(select(Series).where(Series.id == series_id))
    ).scalar_one_or_none()
    if series is None:
        raise HTTPException(status_code=404, detail=f"Series {series_id} not found")

    return await _confirm(
        session,
        acting=acting,
        user_agent=user_agent,
        request=request,
        scope="series",
        scope_id=series.id,
        reference_date=series_reference_date(series),
    )


@router.post(
    "/api/events/{event_id}/waiver",
    response_model=WaiverConfirmationOut,
    status_code=201,
    summary="Confirm the waiver for an event",
)
async def confirm_for_event(
    event_id: int,
    request: ConfirmWaiver,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
    user_agent: str | None = Header(default=None),
) -> WaiverConfirmationOut:
    event = (
        await session.execute(select(Event).where(Event.id == event_id))
    ).scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=404, detail=f"Event {event_id} not found")

    return await _confirm(
        session,
        acting=acting,
        user_agent=user_agent,
        request=request,
        scope="event",
        scope_id=event.id,
        reference_date=event_reference_date(event),
    )


@router.post(
    "/api/series/{series_id}/waiver/scan",
    response_model=WaiverConfirmationOut,
    status_code=201,
    summary="Upload the guardian's signed form for a series",
)
async def upload_series_waiver_scan(
    series_id: int,
    file: UploadFile = File(...),
    sailor_id: int = Form(...),
    guardian_name: str | None = Form(default=None, max_length=160),
    locale_shown: Locale = Form("en"),
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> WaiverConfirmationOut:
    """Story S-1, the minors' path: the scan of the signed form creates the `guardian`
    confirmation — or completes one whose name was recorded first — and clears the sailor
    for every event of the series."""
    name, reference_date = await _scope(session, "series", series_id)
    return await _attach_scan(
        session,
        acting=acting,
        file=file,
        sailor_id=sailor_id,
        guardian_name=guardian_name,
        locale_shown=locale_shown,
        scope="series",
        scope_id=series_id,
        reference_date=reference_date,
    )


@router.post(
    "/api/events/{event_id}/waiver/scan",
    response_model=WaiverConfirmationOut,
    status_code=201,
    summary="Upload the guardian's signed form for an event",
)
async def upload_event_waiver_scan(
    event_id: int,
    file: UploadFile = File(...),
    sailor_id: int = Form(...),
    guardian_name: str | None = Form(default=None, max_length=160),
    locale_shown: Locale = Form("en"),
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> WaiverConfirmationOut:
    name, reference_date = await _scope(session, "event", event_id)
    return await _attach_scan(
        session,
        acting=acting,
        file=file,
        sailor_id=sailor_id,
        guardian_name=guardian_name,
        locale_shown=locale_shown,
        scope="event",
        scope_id=event_id,
        reference_date=reference_date,
    )


@router.get(
    "/api/waiver/confirmations/{confirmation_id}/scan",
    summary="The uploaded scan of a signed form",
)
async def get_waiver_scan(
    confirmation_id: int,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> FileResponse:
    """The most sensitive file on the site (Story S-1): a minor's data and a signature.
    Served to the sailor themselves, to `admin`, `editor` and `race_officer`, to the
    leadership of the sailor's club, and to the host club of the event it was signed
    for — and every look is written to the audit log."""
    row = (
        await session.execute(
            select(WaiverConfirmation).where(WaiverConfirmation.id == confirmation_id)
        )
    ).scalar_one_or_none()
    if row is None or scan_path(row.guardian_signature_ref) is None:
        raise Problem(404, "waiver-scan-not-found", "No scan is on file for this confirmation.")
    sailor = await _sailor(session, row.sailor_id)
    if not await _may_view_scan(session, acting, row, sailor):
        raise Problem(
            403,
            "waiver-scan-forbidden",
            "The signed form is shown only to the sailor, their club's leadership, the "
            "event's organizer and the league office.",
        )
    path = scan_path(row.guardian_signature_ref)
    assert path is not None and row.guardian_signature_ref is not None
    session.add(
        AuditLog(
            entity_type="waiver_scan",
            entity_id=row.id,
            action="viewed",
            actor=acting.email,
            payload={"sailor_id": sailor.id},
        )
    )
    await session.commit()
    return FileResponse(
        path,
        media_type=scan_media_type(row.guardian_signature_ref),
        filename=f"waiver-scan-{row.id}{path.suffix}",
        content_disposition_type="inline",
    )


# --------------------------------------------------------------------- Organizer view


@router.get(
    "/api/admin/events/{event_id}/waivers",
    response_model=EventWaiverList,
    summary="Waiver status for an event",
)
async def event_waivers(
    event_id: int,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> EventWaiverList:
    """The check-in list — Stories VA-2 and VA-5.

    One row per person in the participating squads: cleared, missing, or (for a minor)
    waiting on the guardian's signature.
    """
    event = (
        await session.execute(select(Event).where(Event.id == event_id))
    ).scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=404, detail=f"Event {event_id} not found")

    if not (
        acting.has_any(Role.ADMIN, Role.EDITOR, Role.RACE_OFFICER)
        or (acting.has_any(Role.CLUB_MANAGER) and acting.manages_club(event.host_club_id))
    ):
        raise Problem(
            403,
            "waiver-checklist-forbidden",
            "The check-in list is for the event organizer and the league office.",
        )

    required = await current_waiver_text(session)
    people = await _squad_people(session, event)
    status_by_id = await event_waiver_status(session, event, [pid for pid, _, _, _ in people])

    rows = [
        SailorWaiverRow(
            sailor_id=pid,
            first_name=first,
            last_name=last,
            club=club,
            status=status_by_id[pid].status,
            minor=status_by_id[pid].minor,
            required_version=status_by_id[pid].required_version,
            confirmed_version=status_by_id[pid].confirmed_version,
            confirmed_at=status_by_id[pid].confirmed_at,
            method=status_by_id[pid].method,
            guardian_name=status_by_id[pid].guardian_name,
            confirmation_id=status_by_id[pid].confirmation_id,
            scan_available=status_by_id[pid].scan_available,
        )
        for pid, first, last, club in people
    ]
    rows.sort(key=lambda r: (r.status == STATUS_CLEARED, r.last_name, r.first_name))
    cleared = sum(1 for r in rows if r.status == STATUS_CLEARED)
    return EventWaiverList(
        event_id=event.id,
        required_version=required.version if required else None,
        cleared=cleared,
        outstanding=len(rows) - cleared,
        sailors=rows,
    )


# --------------------------------------------------------------------- Helpers


async def _confirm(
    session: AsyncSession,
    *,
    acting: User,
    user_agent: str | None,
    request: ConfirmWaiver,
    scope: str,
    scope_id: int,
    reference_date: date,
) -> WaiverConfirmationOut:
    sailor = (
        await session.execute(select(Sailor).where(Sailor.id == request.sailor_id))
    ).scalar_one_or_none()
    if sailor is None:
        raise HTTPException(status_code=404, detail=f"Sailor {request.sailor_id} not found")

    _may_confirm_for(acting, sailor)

    required = await current_waiver_text(session)
    if required is None:
        raise Problem(
            409,
            "no-waiver-published",
            "No liability waiver has been published yet.",
            detail="There is nothing to confirm.",
        )

    minor = is_minor(sailor.birth_date, reference_date)
    if minor is None:
        raise Problem(
            422,
            "waiver-birth-date-required",
            "The sailor's date of birth is required to confirm the waiver.",
            sailor_id=sailor.id,
        )

    guardian_name = (request.guardian_name or "").strip() or None
    signature_ref = (request.guardian_signature_ref or "").strip() or None

    where_scope = (
        (WaiverConfirmation.series_id == scope_id)
        if scope == "series"
        else (WaiverConfirmation.event_id == scope_id)
    )
    existing = (
        await session.execute(
            select(WaiverConfirmation).where(
                WaiverConfirmation.sailor_id == sailor.id,
                WaiverConfirmation.waiver_text_id == required.id,
                where_scope,
            )
        )
    ).scalar_one_or_none()

    if existing is not None:
        # A guardian row still waiting for the scan can receive it — "the signed form
        # arrived later" (Story S-1), not a duplicate. The name is already on the row.
        if (
            existing.method == WaiverMethod.GUARDIAN
            and not existing.is_guardian_signed
            and signature_ref is not None
        ):
            existing.guardian_signature_ref = signature_ref
            if guardian_name is not None:
                existing.guardian_name = guardian_name
            existing.recorded_by_user_id = acting.id
            await session.commit()
            return _out(existing, scope, scope_id, required.version, cleared=True)
        raise Problem(
            409,
            "waiver-already-confirmed",
            "This sailor has already confirmed the current waiver version for this "
            "competition.",
            required_version=required.version,
            scope=scope,
        )

    method = request.method
    if minor:
        if method == WaiverMethod.ONLINE:
            raise Problem(
                422,
                "guardian-confirmation-needed",
                "A sailor under 18 needs a legal guardian to sign; an online "
                "confirmation alone is not enough.",
                sailor_id=sailor.id,
            )
        method = WaiverMethod.GUARDIAN
    else:
        method = method or WaiverMethod.ONLINE

    if method == WaiverMethod.GUARDIAN and guardian_name is None:
        raise Problem(
            422,
            "guardian-name-required",
            "A guardian confirmation needs the guardian's name.",
        )

    confirmation = WaiverConfirmation(
        sailor_id=sailor.id,
        waiver_text_id=required.id,
        series_id=scope_id if scope == "series" else None,
        event_id=scope_id if scope == "event" else None,
        method=method,
        locale_shown=request.locale_shown,
        recorded_by_user_id=acting.id,
        user_agent=user_agent[:400] if user_agent else None,
        guardian_name=guardian_name,
        guardian_signature_ref=signature_ref,
    )
    session.add(confirmation)
    await session.commit()
    cleared = method == WaiverMethod.ONLINE or confirmation.is_guardian_signed
    return _out(confirmation, scope, scope_id, required.version, cleared=cleared)


async def _sailor(session: AsyncSession, sailor_id: int) -> Sailor:
    sailor = (
        await session.execute(select(Sailor).where(Sailor.id == sailor_id))
    ).scalar_one_or_none()
    if sailor is None:
        raise HTTPException(status_code=404, detail=f"Sailor {sailor_id} not found")
    return sailor


async def _scope(session: AsyncSession, scope: Scope, scope_id: int) -> tuple[str, date]:
    """The competition's display name and the date a sailor's age is judged against."""
    if scope == "series":
        series = (
            await session.execute(select(Series).where(Series.id == scope_id))
        ).scalar_one_or_none()
        if series is None:
            raise HTTPException(status_code=404, detail=f"Series {scope_id} not found")
        return series.name, series_reference_date(series)
    event = (
        await session.execute(select(Event).where(Event.id == scope_id))
    ).scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=404, detail=f"Event {scope_id} not found")
    return event.title, event_reference_date(event)


def _status_fields(judged: SailorWaiver) -> dict:
    return dict(
        sailor_id=judged.sailor_id,
        status=judged.status,
        minor=judged.minor,
        required_version=judged.required_version,
        confirmed_version=judged.confirmed_version,
        confirmed_at=judged.confirmed_at,
        method=judged.method,
        guardian_name=judged.guardian_name,
        confirmation_id=judged.confirmation_id,
        scan_available=judged.scan_available,
    )


def _validated_scan(raw: bytes, content_type: str | None) -> str:
    """The media type the bytes really are — or a typed refusal.

    The declared type is checked first (cheap), then the bytes themselves: a PDF starts
    with its magic, an image must decode in Pillow and be the format it claims. A file
    that lies about its type is refused, not renamed — a guardian's signature is not the
    place to guess.
    """
    if content_type not in SCAN_MEDIA_TYPES:
        raise Problem(
            422,
            "waiver-scan-invalid-type",
            "The signed form must be a PDF, a JPEG or a PNG.",
            detail=f"Got content type '{content_type}'.",
        )
    if not raw:
        raise Problem(422, "waiver-scan-invalid", "The upload is empty.")
    if len(raw) > SCAN_MAX_BYTES:
        raise Problem(
            422,
            "waiver-scan-too-large",
            "The signed form is too large.",
            detail=f"At most {SCAN_MAX_BYTES // (1024 * 1024)} MB.",
        )
    if content_type == "application/pdf":
        if not raw.startswith(b"%PDF"):
            raise Problem(422, "waiver-scan-invalid", "This file is not a readable PDF.")
        return content_type
    from PIL import Image, UnidentifiedImageError

    try:
        with Image.open(io.BytesIO(raw)) as image:
            image.verify()
            detected = image.format
    except (UnidentifiedImageError, OSError, SyntaxError) as error:
        raise Problem(422, "waiver-scan-invalid", "This file is not a readable image.") from error
    real = {"PNG": "image/png", "JPEG": "image/jpeg"}.get(detected or "")
    if real != content_type:
        raise Problem(
            422,
            "waiver-scan-invalid",
            "This file is not the kind of image it claims to be.",
            detail=f"Declared {content_type}, found {detected or 'nothing readable'}.",
        )
    return content_type


async def _attach_scan(
    session: AsyncSession,
    *,
    acting: User,
    file: UploadFile,
    sailor_id: int,
    guardian_name: str | None,
    locale_shown: Locale,
    scope: Scope,
    scope_id: int,
    reference_date: date,
) -> WaiverConfirmationOut:
    sailor = await _sailor(session, sailor_id)
    _may_confirm_for(acting, sailor)

    required = await current_waiver_text(session)
    if required is None:
        raise Problem(
            409,
            "no-waiver-published",
            "No liability waiver has been published yet.",
            detail="There is nothing to confirm.",
        )
    minor = is_minor(sailor.birth_date, reference_date)
    if minor is None:
        raise Problem(
            422,
            "waiver-birth-date-required",
            "The sailor's date of birth is required to confirm the waiver.",
            sailor_id=sailor.id,
        )
    if not minor:
        # An adult's own click is their statement (Story S-1). The scan path stays what it
        # is for: a signature the site cannot collect online. Should the insurer want paper
        # from everyone, this is the one check to drop.
        raise Problem(
            422,
            "waiver-scan-not-needed",
            "An adult confirms the waiver online; a signed form is only needed for a "
            "sailor under 18.",
            sailor_id=sailor.id,
        )

    raw = await file.read()
    media_type = _validated_scan(raw, file.content_type)
    name = (guardian_name or "").strip() or None

    where_scope = (
        (WaiverConfirmation.series_id == scope_id)
        if scope == "series"
        else (WaiverConfirmation.event_id == scope_id)
    )
    row = (
        await session.execute(
            select(WaiverConfirmation).where(
                WaiverConfirmation.sailor_id == sailor.id,
                WaiverConfirmation.waiver_text_id == required.id,
                where_scope,
            )
        )
    ).scalar_one_or_none()
    if row is None and name is None:
        raise Problem(
            422, "guardian-name-required", "A guardian confirmation needs the guardian's name."
        )

    ref = store_scan(raw, media_type)
    if row is None:
        action = "uploaded"
        row = WaiverConfirmation(
            sailor_id=sailor.id,
            waiver_text_id=required.id,
            series_id=scope_id if scope == "series" else None,
            event_id=scope_id if scope == "event" else None,
            method=WaiverMethod.GUARDIAN,
            locale_shown=locale_shown,
            recorded_by_user_id=acting.id,
            guardian_name=name,
            guardian_signature_ref=ref,
        )
        session.add(row)
    else:
        # The form arrived after the name (Story S-1) — or a better scan replaces a bad
        # one. Replacing is allowed but never silent: the audit row says so.
        action = "replaced" if scan_path(row.guardian_signature_ref) else "uploaded"
        discard_scan(row.guardian_signature_ref)
        row.guardian_signature_ref = ref
        row.method = WaiverMethod.GUARDIAN
        row.recorded_by_user_id = acting.id
        if name is not None:
            row.guardian_name = name
    await session.flush()
    session.add(
        AuditLog(
            entity_type="waiver_scan",
            entity_id=row.id,
            action=action,
            actor=acting.email,
            payload={
                "sailor_id": sailor.id,
                "scope": scope,
                "scope_id": scope_id,
                "media_type": media_type,
                "bytes": len(raw),
            },
        )
    )
    await session.commit()
    return _out(row, scope, scope_id, required.version, cleared=True)


async def _may_view_scan(
    session: AsyncSession, acting: User, row: WaiverConfirmation, sailor: Sailor
) -> bool:
    """Who is connected closely enough to see a minor's signed form (Story S-1)."""
    if acting.has_any(Role.ADMIN, Role.EDITOR, Role.RACE_OFFICER):
        return True
    if (
        acting.email_verified
        and sailor.email is not None
        and sailor.email.lower() == acting.email.lower()
    ):
        return True
    managed = acting.managed_club_ids
    if not managed:
        return False
    sailor_clubs = set(
        (
            await session.execute(
                select(Team.club_id)
                .join(TeamMembership, TeamMembership.team_id == Team.id)
                .where(TeamMembership.sailor_id == sailor.id)
            )
        ).scalars().all()
    )
    if managed & sailor_clubs:
        return True
    if row.event_id is not None:
        host = (
            await session.execute(select(Event.host_club_id).where(Event.id == row.event_id))
        ).scalar_one_or_none()
        if host is not None and host in managed:
            return True
    return False


def _may_confirm_for(acting: User, sailor: Sailor) -> None:
    """The sailor's own account, or someone who maintains sailors (they collect the forms)."""
    own = sailor.email is not None and sailor.email.lower() == acting.email.lower()
    if own or acting.has_any(Role.ADMIN, Role.EDITOR, Role.CLUB_MANAGER):
        return
    raise Problem(
        403,
        "waiver-confirmation-forbidden",
        "You can only confirm the waiver for yourself.",
    )


def _out(
    row: WaiverConfirmation, scope: str, scope_id: int, version: int, *, cleared: bool
) -> WaiverConfirmationOut:
    return WaiverConfirmationOut(
        id=row.id,
        sailor_id=row.sailor_id,
        version=version,
        scope=scope,
        scope_id=scope_id,
        method=row.method,
        locale_shown=row.locale_shown,
        confirmed_at=row.confirmed_at,
        guardian_name=row.guardian_name,
        cleared=cleared,
    )


async def _squad_people(
    session: AsyncSession, event: Event
) -> list[tuple[int, str, str, str | None]]:
    """(sailor_id, first, last, club short name) for everyone in this event's squads.

    For a series event, the squad hangs off each club's series registration; for a
    standalone event, off the event entry itself (same rule as the lineup).
    """
    entries = (
        await session.execute(
            select(Team.club_id).where(
                Team.event_id == event.id, Team.status == TeamStatus.ACCEPTED
            )
        )
    ).scalars().all()
    if not entries:
        return []

    squad_teams = select(Team.id).where(Team.club_id.in_(entries))
    if event.series_id is not None:
        squad_teams = squad_teams.where(
            Team.series_id == event.series_id, Team.event_id.is_(None)
        )
    else:
        squad_teams = squad_teams.where(Team.event_id == event.id)

    rows = (
        await session.execute(
            select(Sailor.id, Sailor.first_name, Sailor.last_name, Club.short_name)
            .join(TeamMembership, TeamMembership.sailor_id == Sailor.id)
            .join(Team, TeamMembership.team_id == Team.id)
            .join(Club, Team.club_id == Club.id)
            .where(Team.id.in_(squad_teams))
            .distinct()
        )
    ).all()
    return [(sid, first, last, club) for sid, first, last, club in rows]
