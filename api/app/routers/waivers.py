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

from datetime import date, datetime

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import current_user, optional_user, require_admin
from app.db import get_session
from app.i18n import Locale
from app.models import (
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
from app.services import current_waiver_text, event_waiver_status, is_minor
from app.services.waivers import (
    STATUS_CLEARED,
    event_reference_date,
    series_reference_date,
)

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


class EventWaiverList(BaseModel):
    event_id: int
    required_version: int | None
    cleared: int
    outstanding: int
    sailors: list[SailorWaiverRow]


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
