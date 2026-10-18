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

import asyncio
from datetime import date, datetime
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, Header, Query, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import authz
from app.auth import current_user, optional_user, require_admin
from app.authz import ObjectRef
from app.db import get_session
from app.i18n import Locale
from app.models import (
    Club,
    Event,
    EventStatus,
    Sailor,
    Series,
    Team,
    TeamMembership,
    TeamStatus,
    WaiverConfirmation,
    WaiverMethod,
    WaiverText,
)
from app.models.auth import ObjectType, Relation, User
from app.problems import Problem
from app.services import current_waiver_text, event_waiver_status, is_minor, uploads
from app.services.audit import EntityType, audit
from app.services.contexts import require_linked_sailor
from app.services.lookup import get_or_404
from app.services.waiver_form import render_waiver_form
from app.services.waivers import (
    STATUS_CLEARED,
    Competition,
    SailorWaiver,
    competition_status,
    discard_scan,
    event_reference_date,
    sailor_waivers,
    scan_media_type,
    scan_path,
    series_reference_date,
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


class ClubCompetitionWaivers(BaseModel):
    """One competition of a club and its sailors' waivers — a series squad, or the
    entry of an event in no series (Story V-14)."""

    scope: Scope
    scope_id: int
    name: str
    starts_on: date | None = None
    cleared: int
    outstanding: int
    sailors: list[SailorWaiverRow]


class ClubWaiverList(BaseModel):
    club_id: int
    required_version: int | None
    competitions: list[ClubCompetitionWaivers]


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
        raise Problem(404, "no-waiver-published", "No liability waiver has been published yet.")
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
    sailor = await require_linked_sailor(session, acting)
    return await _waivers_of(session, sailor, await current_waiver_text(session))


@router.get(
    "/api/waiver/wards",
    response_model=list[MyWaivers],
    summary="My children's waivers — the sailors I am guardian of",
)
async def ward_waivers(
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> list[MyWaivers]:
    """Story S-8: one entry per sailor the child's club linked me to as guardian (Story
    V-13), each exactly as that sailor's own page shows it (S-1) — the same function."""
    ward_ids = authz.list_objects(acting, Relation.GUARDIAN, ObjectType.SAILOR)
    if not ward_ids:
        return []
    wards = (
        await session.execute(
            select(Sailor)
            .where(Sailor.id.in_(ward_ids))
            .order_by(Sailor.first_name, Sailor.last_name)
        )
    ).scalars()
    required = await current_waiver_text(session)
    return [await _waivers_of(session, ward, required) for ward in wards]


async def _waivers_of(
    session: AsyncSession, sailor: Sailor, required: WaiverText | None
) -> MyWaivers:
    """A sailor's competitions with their waiver status — for the sailor (S-1) and for
    their guardian (S-8). ``required`` is read once per request by the caller."""
    rows: list[MyCompetitionWaiver] = []
    for competition, judged in await sailor_waivers(session, sailor, required):
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
    await _may_confirm_for(session, acting, sailor)
    required = await current_waiver_text(session)
    if required is None:
        raise Problem(404, "no-waiver-published", "No liability waiver has been published yet.")
    name, reference_date = await _scope(session, scope, scope_id)
    # ReportLab is CPU work: off the event loop. The rows it reads are loaded already, and
    # no session work happens in the thread.
    pdf = await asyncio.to_thread(
        render_waiver_form,
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
        (await session.execute(select(WaiverText).order_by(WaiverText.version.desc())))
        .scalars()
        .all()
    )
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
    series = await get_or_404(session, Series, series_id)

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
    event = await get_or_404(session, Event, event_id)

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
    audit(
        session,
        EntityType.WAIVER_SCAN,
        row.id,
        "viewed",
        acting,
        sailor_id=sailor.id,
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
    event = await get_or_404(session, Event, event_id)

    # The event's manager includes its host club's (the model's `manager from host_club`).
    if not authz.check(acting, Relation.MANAGER, Relation.RACE_OFFICER, on=event):
        raise Problem(
            403,
            "waiver-checklist-forbidden",
            "The check-in list is for the event organizer and the league office.",
        )

    required = await current_waiver_text(session)
    people = await _squad_people(session, event)
    status_by_id = await event_waiver_status(
        session, event, [pid for pid, _, _, _ in people], required
    )

    rows = [_row(first, last, status_by_id[pid], club=club) for pid, first, last, club in people]
    return EventWaiverList(
        event_id=event.id,
        required_version=required.version if required else None,
        **_tally(rows),
    )


# --------------------------------------------------------------------- Club view


@router.get(
    "/api/clubs/{club_id}/waivers",
    response_model=ClubWaiverList,
    summary="Waiver status of a club's sailors",
)
async def club_waivers(
    club_id: int,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> ClubWaiverList:
    """Who of the club's sailors has signed — Story V-14, for its team manager.

    One block per competition the club is in and has not finished: each series squad
    (its waiver covers every matchday) and each entry in an event that belongs to no
    series. The status is the one the sailor's own page and the check-in list show.
    """
    club = await get_or_404(session, Club, club_id)
    if not acting.can(Relation.MANAGER, on=club):
        raise Problem(
            403,
            "club-waivers-forbidden",
            "The club's waiver overview is for its team manager and admin.",
        )

    today = date.today()
    required = await current_waiver_text(session)
    squads = (
        await session.execute(
            select(Team.id, Series)
            .join(Series, Team.series_id == Series.id)
            .where(
                Team.club_id == club_id,
                Team.event_id.is_(None),
                Team.status == TeamStatus.ACCEPTED,
                Series.ends_on.is_(None) | (Series.ends_on >= today),
            )
            .order_by(Series.starts_on, Series.name)
        )
    ).all()
    entries = (
        await session.execute(
            select(Team.id, Event)
            .join(Event, Team.event_id == Event.id)
            .where(
                Team.club_id == club_id,
                Team.status == TeamStatus.ACCEPTED,
                Event.series_id.is_(None),
                Event.status.in_([EventStatus.PLANNED, EventStatus.LIVE]),
            )
            .order_by(Event.starts_on, Event.title)
        )
    ).all()
    members = await _team_sailors(session, [team_id for team_id, _ in [*squads, *entries]])

    competitions: list[ClubCompetitionWaivers] = []
    for team_id, series in squads:
        sailors = members.get(team_id, [])
        judged = await competition_status(session, Competition.of_series(series), sailors, required)
        competitions.append(
            _competition("series", series.id, series.name, series.starts_on, sailors, judged)
        )
    for team_id, event in entries:
        sailors = members.get(team_id, [])
        judged = await competition_status(session, Competition.of_event(event), sailors, required)
        competitions.append(
            _competition("event", event.id, event.title, event.starts_on, sailors, judged)
        )
    return ClubWaiverList(
        club_id=club_id,
        required_version=required.version if required else None,
        competitions=competitions,
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
    sailor = await get_or_404(session, Sailor, request.sailor_id)

    capacity = await _may_confirm_for(session, acting, sailor)

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
    if capacity == GUARDIAN and not minor:
        # Story S-8: an adult's own click is their statement — the guardianship gives
        # the parent nothing to sign once the child is of age.
        raise Problem(
            422,
            "waiver-ward-is-adult",
            "This sailor is an adult on the competition's reference date and confirms "
            "the waiver themselves.",
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
            "This sailor has already confirmed the current waiver version for this competition.",
            required_version=required.version,
            scope=scope,
        )

    method = request.method
    if minor and capacity == GUARDIAN:
        # The linked guardian's own click, from their own account (Story S-8): it clears
        # the child like a signed scan does, with nothing on paper.
        method = WaiverMethod.GUARDIAN_ONLINE
        guardian_name = guardian_name or acting.display_name or acting.email
    elif minor:
        if method in (WaiverMethod.ONLINE, WaiverMethod.GUARDIAN_ONLINE):
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
    sailor = await get_or_404(session, Sailor, sailor_id)
    return sailor


async def _scope(session: AsyncSession, scope: Scope, scope_id: int) -> tuple[str, date]:
    """The competition's display name and the date a sailor's age is judged against."""
    if scope == "series":
        series = await get_or_404(session, Series, scope_id)
        return series.name, series_reference_date(series)
    event = await get_or_404(session, Event, scope_id)
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


async def _validated_scan(raw: bytes, content_type: str | None) -> str:
    """The media type the bytes really are — or a ``waiver-scan-…`` refusal
    (``app/services/uploads.py``). A guardian's signature is not the place to guess."""
    return await uploads.validated(raw, content_type, code="waiver-scan", what="The signed form")


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
    await _may_confirm_for(session, acting, sailor)

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
    media_type = await _validated_scan(raw, file.content_type)
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
    audit(
        session,
        EntityType.WAIVER_SCAN,
        row.id,
        action,
        acting,
        sailor_id=sailor.id,
        scope=scope,
        scope_id=scope_id,
        media_type=media_type,
        bytes=len(raw),
    )
    await session.commit()
    return _out(row, scope, scope_id, required.version, cleared=True)


async def _may_view_scan(
    session: AsyncSession, acting: User, row: WaiverConfirmation, sailor: Sailor
) -> bool:
    """Who is connected closely enough to see a minor's signed form (Story S-1)."""
    # The league office; an event's organizer or race committee — held on the event, its
    # series or its host club — only for that event's forms.
    if authz.check(acting, Relation.ADMIN, Relation.EDITOR, Relation.RACE_OFFICER):
        return True
    if row.event_id is not None:
        event = await session.get(Event, row.event_id)
        if event is not None and authz.check(
            acting, Relation.MANAGER, Relation.RACE_OFFICER, on=event
        ):
            return True
    if (
        acting.email_verified
        and sailor.email is not None
        and sailor.email.lower() == acting.email.lower()
    ):
        return True
    managed = authz.list_objects(acting, Relation.MANAGER, ObjectType.CLUB)
    return bool(managed and managed & await _sailor_clubs(session, sailor.id))


async def _sailor_clubs(session: AsyncSession, sailor_id: int) -> set[int]:
    """The clubs that have this sailor in a squad or an event entry — "the sailor's club"."""
    return set(
        (
            await session.execute(
                select(Team.club_id)
                .join(TeamMembership, TeamMembership.team_id == Team.id)
                .where(TeamMembership.sailor_id == sailor_id)
            )
        )
        .scalars()
        .all()
    )


#: In which capacity someone may confirm for a sailor (`_may_confirm_for`).
OWN, STAFF, GUARDIAN = "own", "staff", "guardian"


async def _may_confirm_for(session: AsyncSession, acting: User, sailor: Sailor) -> str:
    """The sailor's own (verified) account; the league office or the manager of a club
    that has the sailor in a squad — they collect their club's paper forms (Stories S-1,
    S-3); or a guardian the child's club linked to the sailor (Stories V-13, S-8). Not any
    club's manager: the `team_manager` *summary* role once let one club sign for every
    sailor on the site. Returns which of the three it is — the first that applies."""
    own = (
        acting.email_verified
        and sailor.email is not None
        and sailor.email.lower() == acting.email.lower()
    )
    if own:
        return OWN
    if authz.check(acting, Relation.ADMIN, Relation.EDITOR):
        return STAFF
    managed = authz.list_objects(acting, Relation.MANAGER, ObjectType.CLUB)
    if managed and managed & await _sailor_clubs(session, sailor.id):
        return STAFF
    if authz.read(acting, Relation.GUARDIAN, ObjectRef(ObjectType.SAILOR, sailor.id)):
        return GUARDIAN
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


def _row(
    first: str, last: str, judged: SailorWaiver, *, club: str | None = None
) -> SailorWaiverRow:
    return SailorWaiverRow(first_name=first, last_name=last, club=club, **_status_fields(judged))


def _tally(rows: list[SailorWaiverRow]) -> dict:
    """The rows with who still has to sign at the top — that is what someone opens the
    list for — and the two counts above them."""
    rows.sort(key=lambda r: (r.status == STATUS_CLEARED, r.last_name, r.first_name))
    cleared = sum(1 for r in rows if r.status == STATUS_CLEARED)
    return dict(cleared=cleared, outstanding=len(rows) - cleared, sailors=rows)


def _competition(
    scope: Scope,
    scope_id: int,
    name: str,
    starts_on: date | None,
    sailors: list[Sailor],
    judged: dict[int, SailorWaiver],
) -> ClubCompetitionWaivers:
    rows = [_row(s.first_name, s.last_name, judged[s.id]) for s in sailors]
    return ClubCompetitionWaivers(
        scope=scope, scope_id=scope_id, name=name, starts_on=starts_on, **_tally(rows)
    )


async def _team_sailors(session: AsyncSession, team_ids: list[int]) -> dict[int, list[Sailor]]:
    """The members of each of these teams, in one query."""
    out: dict[int, list[Sailor]] = {}
    rows = await session.execute(
        select(TeamMembership.team_id, Sailor)
        .join(Sailor, TeamMembership.sailor_id == Sailor.id)
        .where(TeamMembership.team_id.in_(team_ids))
    )
    for team_id, sailor in rows:
        out.setdefault(team_id, []).append(sailor)
    return out


async def _squad_people(
    session: AsyncSession, event: Event
) -> list[tuple[int, str, str, str | None]]:
    """(sailor_id, first, last, club short name) for everyone in this event's squads.

    For a series event, the squad hangs off each club's series registration; for a
    standalone event, off the event entry itself (same rule as the lineup).
    """
    entries = (
        (
            await session.execute(
                select(Team.club_id).where(
                    Team.event_id == event.id, Team.status == TeamStatus.ACCEPTED
                )
            )
        )
        .scalars()
        .all()
    )
    if not entries:
        return []

    squad_teams = select(Team.id).where(Team.club_id.in_(entries))
    if event.series_id is not None:
        squad_teams = squad_teams.where(Team.series_id == event.series_id, Team.event_id.is_(None))
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
