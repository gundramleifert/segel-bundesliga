"""Request, accept, and reject participations — Stories V-5, V-6, and A-9.

Two paths lead to the same row:

* The **admin sets directly** (`PUT /api/admin/clubs/{id}/series`,
  `PUT /api/admin/series/{id}/clubs`, `PUT /api/admin/events/{id}/clubs`) — the participation
  is accepted immediately. The club need not consent: it doesn't need the admin's permission,
  and the admin doesn't need the club's.
* The **club applies** and gets accepted — this path. This direction requires the
  approval of administration or of the competition's organizer: the ``manager`` of the
  series (or of the event, for an application to one event), who could set the clubs
  directly anyway (Story A-9).

Only the **club officer** can request for their own club. Both paths end in
a ``Team`` row; only its ``status`` differs.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app import authz
from app.auth import current_user
from app.authz import ObjectRef
from app.db import get_session
from app.models import Club, Event, Series, Team, TeamStatus
from app.models.auth import ObjectType, Relation, User
from app.problems import Problem
from app.schemas.public import ClubOut, SeriesOut
from app.services import has_results, new_event_entry
from app.services.audit import EntityType, audit
from app.services.lookup import get_or_404

router = APIRouter(tags=["applications"])


class ApplicationCreate(BaseModel):
    """An application is for **one** series or **one** event."""

    club_id: int
    series_id: int | None = None
    event_id: int | None = None

    @model_validator(mode="after")
    def _exactly_one(self) -> ApplicationCreate:
        if (self.series_id is None) == (self.event_id is None):
            raise ValueError("Specify either a series or an event, not both.")
        return self


class ApplicationDecision(BaseModel):
    note: str | None = Field(
        default=None,
        max_length=500,
        description="If rejected: the reason. The club should know why.",
    )


class ApplicationEventOut(BaseModel):
    """Only as much event detail as an application needs."""

    id: int
    title: str
    # Absent while the date is still open — an event is savable incomplete (Story VA-8).
    starts_on: date | None = None


class ApplicationOut(BaseModel):
    team_id: int
    status: str
    decision_note: str | None = None
    club: ClubOut
    # Exactly one is set: the competition in question.
    series: SeriesOut | None = None
    event: ApplicationEventOut | None = None


def _out(team: Team) -> ApplicationOut:
    return ApplicationOut(
        team_id=team.id,
        status=team.status,
        decision_note=team.decision_note,
        club=ClubOut.model_validate(team.club),
        series=SeriesOut.model_validate(team.series) if team.event is None else None,
        event=(
            ApplicationEventOut(
                id=team.event.id, title=team.event.title, starts_on=team.event.starts_on
            )
            if team.event is not None
            else None
        ),
    )


@router.post(
    "/api/applications",
    response_model=ApplicationOut,
    status_code=status.HTTP_201_CREATED,
    summary="Request participation",
)
async def submit_application(
    request: ApplicationCreate,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> ApplicationOut:
    """Registers own club for a series or event.

    The application doesn't count anywhere until the admin accepts it: the club doesn't
    appear publicly or in any standings, and won't be drawn.
    """
    _can_apply(acting, request.club_id)
    club = await _get_club(session, request.club_id)

    if request.series_id is not None:
        team = await _apply_for_series(session, club, request.series_id)
    else:
        team = await _apply_for_event(session, club, request.event_id or 0)

    await session.commit()
    return _out(await _with_relations(session, team.id))


@router.get(
    "/api/applications",
    response_model=list[ApplicationOut],
    summary="View own applications",
)
async def list_own_applications(
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> list[ApplicationOut]:
    """Lists the participations of every club the acting user organizes, and their status —
    both requested and accepted.
    """
    club_ids = authz.list_objects(acting, Relation.MANAGER, ObjectType.CLUB)
    if not club_ids:
        return []
    teams = (
        await session.execute(
            select(Team)
            .options(selectinload(Team.club), selectinload(Team.series), selectinload(Team.event))
            .where(Team.club_id.in_(club_ids))
            .order_by(Team.id)
        )
    ).scalars()
    return [_out(team) for team in teams]


@router.delete(
    "/api/applications/{team_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Withdraw application",
)
async def withdraw_application(
    team_id: int,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> None:
    """Withdraws an application while it's still pending."""
    team = await _with_relations(session, team_id)
    if not authz.check(acting, Relation.MANAGER, on=ObjectRef(ObjectType.CLUB, team.club_id)):
        raise Problem(403, "application-not-yours", "This is not your application.")
    if team.status == TeamStatus.ACCEPTED:
        raise Problem(
            409, "participation-accepted", "An accepted participation cannot be withdrawn."
        )
    await session.delete(team)
    await session.commit()


@router.get(
    "/api/admin/applications",
    response_model=list[ApplicationOut],
    summary="Pending applications",
)
async def list_pending_applications(
    series_id: int | None = None,
    event_id: int | None = None,
    status_filter: str = "requested",
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> list[ApplicationOut]:
    """Every application for administration; one series' or one event's for its
    organizer, who has to name it (Story A-9)."""
    if not authz.check(acting, Relation.ADMIN):
        target = (
            await session.get(Event, event_id)
            if event_id is not None
            else await session.get(Series, series_id)
            if series_id is not None
            else None
        )
        _may_decide(acting, target)
    stmt = (
        select(Team)
        .options(selectinload(Team.club), selectinload(Team.series), selectinload(Team.event))
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
    response_model=ApplicationOut,
    summary="Accept application",
)
async def accept_application(
    team_id: int,
    request: ApplicationDecision | None = None,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> ApplicationOut:
    """Accepts an application, making the club a participant.

    Afterwards everything works like direct assignment.
    """
    team = await _decide(
        session, team_id, TeamStatus.ACCEPTED, request.note if request else None, acting
    )
    return _out(team)


@router.post(
    "/api/admin/applications/{team_id}/reject",
    response_model=ApplicationOut,
    summary="Reject application",
)
async def reject_application(
    team_id: int,
    request: ApplicationDecision | None = None,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> ApplicationOut:
    team = await _decide(
        session, team_id, TeamStatus.REJECTED, request.note if request else None, acting
    )
    return _out(team)


# ------------------------------------------------------------------ Helper functions


def _can_apply(acting: User, club_id: int) -> None:
    """Only club officers can register — for their own club.

    Admins can also register because they can set directly anyway; a request in their
    name is the weaker intervention.
    """
    if not (
        authz.check(acting, Relation.ADMIN)
        or authz.list_objects(acting, Relation.MANAGER, ObjectType.CLUB)
    ):
        raise Problem(
            403, "participant-registration-forbidden", "Only club officers register participants."
        )
    if not authz.check(acting, Relation.MANAGER, on=ObjectRef(ObjectType.CLUB, club_id)):
        raise Problem(
            403,
            "active-club-not-mine",
            "You can only register a club you organize.",
            club_id=club_id,
        )


async def _get_club(session: AsyncSession, club_id: int) -> Club:
    club = await get_or_404(session, Club, club_id)
    return club


async def _apply_for_series(session: AsyncSession, club: Club, series_id: int) -> Team:
    series = await get_or_404(session, Series, series_id)

    existing = (
        await session.execute(
            select(Team).where(
                Team.club_id == club.id,
                Team.series_id == series.id,
                Team.event_id.is_(None),
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return _retry_after_rejection(existing, "this series")

    team = Team(
        name=club.short_name,
        club_id=club.id,
        series_id=series.id,
        status=TeamStatus.REQUESTED,
    )
    session.add(team)
    return team


async def _apply_for_event(session: AsyncSession, club: Club, event_id: int) -> Team:
    event = await get_or_404(session, Event, event_id)

    existing = (
        await session.execute(
            select(Team).where(Team.club_id == club.id, Team.event_id == event.id)
        )
    ).scalar_one_or_none()
    if existing is not None:
        return _retry_after_rejection(existing, "this event")

    # Not registered for the event's series: a typed 422 (`ParticipationError`).
    return await new_event_entry(session, event, club, status=TeamStatus.REQUESTED)


def _retry_after_rejection(team: Team, where: str) -> Team:
    """A new attempt after rejection is allowed — a duplicate application is not."""
    if team.status == TeamStatus.REJECTED:
        team.status = TeamStatus.REQUESTED
        team.decision_note = None
        team.decided_at = None
        return team
    raise Problem(
        409,
        "participation-exists",
        f"This club already has a participation for {where} (status: {team.status}).",
        team_status=str(team.status),
    )


def _may_decide(acting: User, target: Series | Event | None) -> None:
    """Story A-9: administration decides every application; the ``manager`` of the series
    — or of the event, for an application to one event — decides those to theirs. The
    model's ``manager`` is what lets them set the clubs directly, so deciding gives them
    nothing they could not already do."""
    if authz.check(acting, Relation.ADMIN) or (
        target is not None and authz.check(acting, Relation.MANAGER, on=target)
    ):
        return
    raise Problem(
        403,
        "application-decision-forbidden",
        "Applications are decided by administration and by the competition's organizer.",
    )


async def _with_relations(session: AsyncSession, team_id: int) -> Team:
    team = (
        await session.execute(
            select(Team)
            .options(selectinload(Team.club), selectinload(Team.series), selectinload(Team.event))
            .where(Team.id == team_id)
        )
    ).scalar_one_or_none()
    if team is None:
        raise Problem(404, "application-not-found", f"Application {team_id} not found.", id=team_id)
    return team


async def _decide(
    session: AsyncSession,
    team_id: int,
    new_status: str,
    note: str | None,
    acting: User,
) -> Team:
    team = await _with_relations(session, team_id)
    _may_decide(acting, team.event if team.event_id is not None else team.series)

    if team.status == TeamStatus.ACCEPTED and new_status != TeamStatus.ACCEPTED:
        if await has_results(session, team):
            raise Problem(
                409,
                "participation-has-results",
                "This participation cannot be revoked: race results already exist.",
            )

    previous_status = team.status
    team.status = new_status
    team.decision_note = note
    team.decided_at = datetime.now(UTC)

    # Who decided what and when must be auditable.
    audit(
        session,
        EntityType.TEAM,
        team.id,
        "decide_participation",
        acting,
        # "from" is a Python keyword, so this payload stays a mapping.
        **{"from": previous_status, "to": new_status, "note": note},
    )
    await session.commit()
    return await _with_relations(session, team.id)
