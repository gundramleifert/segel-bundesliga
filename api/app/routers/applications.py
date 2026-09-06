"""Request, accept, and reject participations — Stories V-5, V-6, and A-9.

Two paths lead to the same row:

* The **admin sets directly** (`PUT /api/admin/clubs/{id}/series`,
  `PUT /api/admin/series/{id}/clubs`, `PUT /api/admin/events/{id}/clubs`) — the participation
  is accepted immediately. The club need not consent: it doesn't need the admin's permission,
  and the admin doesn't need the club's.
* The **club applies** and gets accepted — this path. This direction requires
  admin approval.

Only the **club officer** can request for their own club. Both paths end in
a ``Team`` row; only its ``status`` differs.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth import current_user, require_admin
from app.db import get_session
from app.i18n import Locale, resolve_locale, tr
from app.models import AuditLog, Club, Event, Series, Team, TeamStatus
from app.models.auth import Role, User
from app.schemas.public import ClubOut, SeriesOut
from app.services import TeilnahmeFehler, hat_ergebnisse, neuer_antritt

router = APIRouter(tags=["applications"])


class AntragStellen(BaseModel):
    """An application is for **one** series or **one** event."""

    club_id: int
    series_id: int | None = None
    event_id: int | None = None

    @model_validator(mode="after")
    def _genau_eines(self) -> AntragStellen:
        if (self.series_id is None) == (self.event_id is None):
            raise ValueError(
                "Specify either a series or an event, not both."
            )
        return self


class Entscheidung(BaseModel):
    note: str | None = Field(
        default=None,
        max_length=500,
        description="If rejected: the reason. The club should know why.",
    )


class AntragEventOut(BaseModel):
    """Only as much event detail as an application needs."""

    id: int
    title: str
    starts_on: date


class AntragOut(BaseModel):
    team_id: int
    status: str
    decision_note: str | None = None
    club: ClubOut
    # Exactly one is set: the competition in question.
    series: SeriesOut | None = None
    event: AntragEventOut | None = None


def _out(team: Team) -> AntragOut:
    return AntragOut(
        team_id=team.id,
        status=team.status,
        decision_note=team.decision_note,
        club=ClubOut.model_validate(team.club),
        series=SeriesOut.model_validate(team.series) if team.event is None else None,
        event=(
            AntragEventOut(
                id=team.event.id, title=team.event.title, starts_on=team.event.starts_on
            )
            if team.event is not None
            else None
        ),
    )


@router.post(
    "/api/applications",
    response_model=AntragOut,
    status_code=status.HTTP_201_CREATED,
    summary="Request participation",
)
async def antrag_stellen(
    request: AntragStellen,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
    locale: Locale = Depends(resolve_locale),
) -> AntragOut:
    """Registers own club for a series or event.

    The application doesn't count anywhere until the admin accepts it: the club doesn't
    appear publicly or in any standings, and won't be drawn.
    """
    _darf_beantragen(acting, request.club_id, locale)
    club = await _verein(session, request.club_id, locale)

    if request.series_id is not None:
        team = await _serienantrag(session, club, request.series_id, locale)
    else:
        team = await _veranstaltungsantrag(session, club, request.event_id or 0, locale)

    await session.commit()
    return _out(await _mit_bezuegen(session, team.id, locale))


@router.get(
    "/api/applications",
    response_model=list[AntragOut],
    summary="View own applications",
)
async def eigene_antraege(
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
    locale: Locale = Depends(resolve_locale),
) -> list[AntragOut]:
    """Lists the participations of own club and their status — both requested and accepted."""
    if acting.club_id is None:
        return []
    teams = (
        await session.execute(
            select(Team)
            .options(
                selectinload(Team.club), selectinload(Team.series), selectinload(Team.event)
            )
            .where(Team.club_id == acting.club_id)
            .order_by(Team.id)
        )
    ).scalars()
    return [_out(team) for team in teams]


@router.delete(
    "/api/applications/{team_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Withdraw application",
)
async def antrag_zuruecknehmen(
    team_id: int,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
    locale: Locale = Depends(resolve_locale),
) -> None:
    """Withdraws an application while it's still pending."""
    team = await _mit_bezuegen(session, team_id, locale)
    if not acting.has_any(Role.ADMIN) and acting.club_id != team.club_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=tr(locale, en="This is not your application.", de="Das ist nicht Ihr Antrag."),
        )
    if team.status == TeamStatus.ACCEPTED:
        raise HTTPException(
            status_code=409,
            detail=tr(
                locale,
                en="An accepted participation cannot be withdrawn.",
                de="Eine angenommene Teilnahme lässt sich nicht zurückziehen.",
            ),
        )
    await session.delete(team)
    await session.commit()


@router.get(
    "/api/admin/applications",
    response_model=list[AntragOut],
    dependencies=[Depends(require_admin)],
    summary="Pending applications",
)
async def offene_antraege(
    series_id: int | None = None,
    event_id: int | None = None,
    status_filter: str = "requested",
    session: AsyncSession = Depends(get_session),
) -> list[AntragOut]:
    stmt = (
        select(Team)
        .options(
            selectinload(Team.club), selectinload(Team.series), selectinload(Team.event)
        )
        .where(Team.status == status_filter)
        .order_by(Team.id)
    )
    if series_id is not None:
        stmt = stmt.where(Team.series_id == series_id)
    if event_id is not None:
        stmt = stmt.where(Team.event_id == event_id)
    return [_out(team) for team in (await session.execute(stmt)).scalars()]


@router.post(
    "/api/admin/applications/{team_id}/accept",
    response_model=AntragOut,
    summary="Accept application",
)
async def annehmen(
    team_id: int,
    request: Entscheidung | None = None,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(require_admin),
    locale: Locale = Depends(resolve_locale),
) -> AntragOut:
    """Accepts an application, making the club a participant.

    Afterwards everything works like direct assignment.
    """
    team = await _entscheiden(
        session, team_id, TeamStatus.ACCEPTED, request.note if request else None, acting, locale
    )
    return _out(team)


@router.post(
    "/api/admin/applications/{team_id}/reject",
    response_model=AntragOut,
    summary="Reject application",
)
async def ablehnen(
    team_id: int,
    request: Entscheidung | None = None,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(require_admin),
    locale: Locale = Depends(resolve_locale),
) -> AntragOut:
    team = await _entscheiden(
        session, team_id, TeamStatus.REJECTED, request.note if request else None, acting, locale
    )
    return _out(team)


# ------------------------------------------------------------------ Helper functions


def _darf_beantragen(acting: User, club_id: int, locale: Locale) -> None:
    """Only club officers can register — for their own club.

    Admins can also register because they can set directly anyway; a request in their
    name is the weaker intervention.
    """
    if not acting.has_any(Role.ADMIN, Role.CLUB_MANAGER):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=tr(
                locale,
                en="Only club officers register participants.",
                de="Teilnehmer meldet die Vereinsleitung.",
            ),
        )
    if not acting.has_any(Role.ADMIN) and acting.club_id != club_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=tr(
                locale,
                en="You can only register your own club.",
                de="Sie können nur den eigenen Verein anmelden.",
            ),
        )


async def _verein(session: AsyncSession, club_id: int, locale: Locale) -> Club:
    club = (
        await session.execute(select(Club).where(Club.id == club_id))
    ).scalar_one_or_none()
    if club is None:
        raise HTTPException(
            status_code=404,
            detail=tr(
                locale,
                en=f"Club {club_id} not found",
                de=f"Verein {club_id} nicht gefunden",
            ),
        )
    return club


async def _serienantrag(
    session: AsyncSession, club: Club, series_id: int, locale: Locale
) -> Team:
    serie = (
        await session.execute(select(Series).where(Series.id == series_id))
    ).scalar_one_or_none()
    if serie is None:
        raise HTTPException(
            status_code=404,
            detail=tr(
                locale,
                en=f"Series {series_id} not found",
                de=f"Serie {series_id} nicht gefunden",
            ),
        )

    vorhanden = (
        await session.execute(
            select(Team).where(
                Team.club_id == club.id,
                Team.series_id == serie.id,
                Team.event_id.is_(None),
            )
        )
    ).scalar_one_or_none()
    if vorhanden is not None:
        return _erneut_versuchen(vorhanden, "this series", locale)

    team = Team(
        name=club.short_name,
        club_id=club.id,
        series_id=serie.id,
        status=TeamStatus.REQUESTED,
    )
    session.add(team)
    return team


async def _veranstaltungsantrag(
    session: AsyncSession, club: Club, event_id: int, locale: Locale
) -> Team:
    event = (
        await session.execute(select(Event).where(Event.id == event_id))
    ).scalar_one_or_none()
    if event is None:
        raise HTTPException(
            status_code=404,
            detail=tr(
                locale,
                en=f"Event {event_id} not found",
                de=f"Veranstaltung {event_id} nicht gefunden",
            ),
        )

    vorhanden = (
        await session.execute(
            select(Team).where(Team.club_id == club.id, Team.event_id == event.id)
        )
    ).scalar_one_or_none()
    if vorhanden is not None:
        return _erneut_versuchen(vorhanden, "this event", locale)

    try:
        return await neuer_antritt(session, event, club, status=TeamStatus.REQUESTED)
    except TeilnahmeFehler as fehler:
        raise HTTPException(status_code=422, detail=str(fehler)) from fehler


def _erneut_versuchen(team: Team, where: str, locale: Locale) -> Team:
    """A new attempt after rejection is allowed — a duplicate application is not."""
    if team.status == TeamStatus.REJECTED:
        team.status = TeamStatus.REQUESTED
        team.decision_note = None
        team.decided_at = None
        return team
    raise HTTPException(
        status_code=409,
        detail=tr(
            locale,
            en=(
                f"This club already has a participation for {where} "
                f"(status: {team.status})."
            ),
            de=(
                f"Für diesen Verein liegt bei {where} bereits eine Teilnahme vor "
                f"(Stand: {team.status})."
            ),
        ),
    )


async def _mit_bezuegen(session: AsyncSession, team_id: int, locale: Locale) -> Team:
    team = (
        await session.execute(
            select(Team)
            .options(
                selectinload(Team.club), selectinload(Team.series), selectinload(Team.event)
            )
            .where(Team.id == team_id)
        )
    ).scalar_one_or_none()
    if team is None:
        raise HTTPException(
            status_code=404,
            detail=tr(
                locale,
                en=f"Application {team_id} not found",
                de=f"Antrag {team_id} nicht gefunden",
            ),
        )
    return team


async def _entscheiden(
    session: AsyncSession,
    team_id: int,
    neuer_status: str,
    note: str | None,
    acting: User,
    locale: Locale,
) -> Team:
    team = await _mit_bezuegen(session, team_id, locale)

    if team.status == TeamStatus.ACCEPTED and neuer_status != TeamStatus.ACCEPTED:
        if await hat_ergebnisse(session, team):
            raise HTTPException(
                status_code=409,
                detail=tr(
                    locale,
                    en=(
                        "This participation cannot be revoked: race results already "
                        "exist."
                    ),
                    de=(
                        "Diese Teilnahme lässt sich nicht widerrufen: es liegen bereits "
                        "Wettfahrtergebnisse vor."
                    ),
                ),
            )

    vorher = team.status
    team.status = neuer_status
    team.decision_note = note
    team.decided_at = datetime.now(UTC)

    # Who decided what and when must be auditable.
    session.add(
        AuditLog(
            entity_type="team",
            entity_id=team.id,
            action="decide_participation",
            actor=acting.email,
            payload={"from": vorher, "to": neuer_status, "note": note},
        )
    )
    await session.commit()
    return await _mit_bezuegen(session, team.id, locale)
