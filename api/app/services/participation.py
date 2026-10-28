"""Participation: who is registered for a series, and who is entered in an event.

Both are ``Team`` rows; ``event_id`` tells them apart (see ``app/models/org.py``). The
rules live here in one place because four routers need them:

* Whoever enters an act **must be registered for its series**.
* A participation that has already been raced under can no longer be withdrawn.
* When a series event is created, the **same clubs** enter by default as in the series;
  the admin can deviate afterwards.
* A club enters one team, or as many as the event's ``teams_per_club`` allows (Story
  VA-13) — numbered, and all lined up from the club's one squad.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    Club,
    ClubMembership,
    Event,
    MembershipStatus,
    Person,
    RaceEntry,
    Team,
    TeamStatus,
)
from app.problems import Problem


class ParticipationError(Problem):
    """A participation that isn't allowed to exist like this — a typed 422."""

    def __init__(self, code: str, title: str, **extra: object) -> None:
        super().__init__(422, code, title, **extra)


async def series_registrations(
    session: AsyncSession, series_id: int, *, accepted_only: bool = True
) -> list[Team]:
    """The clubs registered for the series — not their entries in individual acts."""
    stmt = select(Team).where(Team.series_id == series_id, Team.event_id.is_(None))
    if accepted_only:
        stmt = stmt.where(Team.status == TeamStatus.ACCEPTED)
    return list((await session.execute(stmt.order_by(Team.name, Team.id))).scalars())


async def event_entries(
    session: AsyncSession, event_id: int, *, accepted_only: bool = True, with_club: bool = False
) -> list[Team]:
    """The teams entered in this event — the one query for it.

    The pairing list belongs to the event, and so do the teams in it: the draw is among
    those entering *here*, not among everyone registered for the series. Sorted by name so
    the same input always produces the same pairing — a draw has to be reproducible.
    ``with_club`` loads each team's club with it, for a page that names it.
    """
    stmt = select(Team).where(Team.event_id == event_id)
    if with_club:
        stmt = stmt.options(selectinload(Team.club))
    if accepted_only:
        stmt = stmt.where(Team.status == TeamStatus.ACCEPTED)
    return list((await session.execute(stmt.order_by(Team.name, Team.id))).scalars())


async def series_registration(session: AsyncSession, series_id: int, club_id: int) -> Team | None:
    return (
        await session.execute(
            select(Team).where(
                Team.series_id == series_id,
                Team.event_id.is_(None),
                Team.club_id == club_id,
            )
        )
    ).scalar_one_or_none()


async def event_entry(
    session: AsyncSession, event_id: int, club_id: int, number: int = 1
) -> Team | None:
    """The club's team ``number`` in this event — its first unless it enters several."""
    return (
        await session.execute(
            select(Team).where(
                Team.event_id == event_id, Team.club_id == club_id, Team.number == number
            )
        )
    ).scalar_one_or_none()


def team_name(club: Club, number: int = 1) -> str:
    """`KYC (SH)`, and from the second team on `KYC (SH) 2` (Story VA-13)."""
    return club.short_name if number == 1 else f"{club.short_name} {number}"


def membership_of(person: Person, club_id: int) -> ClubMembership | None:
    """The person's row for this club, whatever its status."""
    return next((link for link in person.club_memberships if link.club_id == club_id), None)


def connect_person(person: Person, club_id: int) -> None:
    """The person is an active member of this club from now on (Stories V-4, Z-5) — and
    sails for it: the ``club`` edge their permissions walk, and their account's ``member``.
    An invitation or a request there becomes the membership. Idempotent; who may do it is
    the caller's to check."""
    for link in person.club_memberships:
        if link.club_id == club_id:
            link.status = MembershipStatus.ACTIVE
            return
    person.club_memberships.append(ClubMembership(club_id=club_id, status=MembershipStatus.ACTIVE))


async def squad_team(session: AsyncSession, team: Team) -> Team:
    """The team the squad hangs off.

    For an act, that's the same club's series registration: you register for the series,
    and field a lineup for the individual matchday — every team the club enters there,
    from the one squad (Story VA-13). If the event stands on its own, the squad hangs off
    the club's first team there.
    """
    if team.is_series_registration:
        return team
    if team.series_id is None:
        if team.number == 1 or team.event_id is None:
            return team
        first = await event_entry(session, team.event_id, team.club_id)
        return first or team
    registration = await series_registration(session, team.series_id, team.club_id)
    if registration is None:
        raise ParticipationError(
            "squad-without-series-registration",
            "This club is entered in the event but isn't registered for its series — "
            "so there's no squad.",
        )
    return registration


async def candidate_clubs(session: AsyncSession, event: Event) -> list[Club]:
    """The clubs that may be entered in this event — the rule ``new_event_entry`` enforces.

    For an act of a series, its **accepted** registrations; for an event standing alone,
    every club, which is what makes the site a service to clubs outside the association's
    own series. Asked by the organizer's clubs step, so the screen offers exactly what the
    server will accept rather than recomputing the rule from every series and every club.
    """
    if event.series_id is None:
        stmt = select(Club)
    else:
        stmt = (
            select(Club)
            .join(Team, Team.club_id == Club.id)
            .where(
                Team.series_id == event.series_id,
                Team.event_id.is_(None),
                Team.status == TeamStatus.ACCEPTED,
            )
        )
    return list((await session.execute(stmt.order_by(Club.name, Club.id))).scalars())


async def new_event_entry(
    session: AsyncSession,
    event: Event,
    club: Club,
    *,
    status: str = TeamStatus.ACCEPTED,
    number: int = 1,
) -> Team:
    """Creates a club's entry in an event — its team ``number``.

    The rule at stake: if the event belongs to a series, the club must be **registered
    and accepted** for it there. Otherwise it would show up in the daily standings but in
    no series table. And it enters no more teams than the event allows (Story VA-13).
    """
    if number > event.teams_per_club:
        raise ParticipationError(
            "too-many-teams-per-club",
            f"{club.short_name} may enter {event.teams_per_club} team(s) in this event.",
            club=club.short_name,
            teams_per_club=event.teams_per_club,
        )
    if event.series_id is not None:
        registration = await series_registration(session, event.series_id, club.id)
        if registration is None or registration.status != TeamStatus.ACCEPTED:
            raise ParticipationError(
                "series-registration-required",
                f"{club.short_name} isn't registered for this event's series. "
                "Register for the series first, then enter the act.",
                club=club.short_name,
            )

    team = Team(
        name=team_name(club, number),
        number=number,
        club_id=club.id,
        series_id=event.series_id,
        event_id=event.id,
        status=status,
    )
    session.add(team)
    return team


async def adopt_series_registrations(session: AsyncSession, event: Event) -> list[Team]:
    """Enters the series' registered clubs as participants of the event.

    The normal case: the same clubs enter every act of a series. Deviations are then
    tracked by the admin via ``PUT /api/admin/events/{id}/clubs``.
    """
    if event.series_id is None:
        return []

    already_entered = {
        team.club_id for team in await event_entries(session, event.id, accepted_only=False)
    }
    new_teams = [
        Team(
            name=registration.name,
            club_id=registration.club_id,
            series_id=event.series_id,
            event_id=event.id,
            status=TeamStatus.ACCEPTED,
        )
        for registration in await series_registrations(session, event.series_id)
        if registration.club_id not in already_entered
    ]
    session.add_all(new_teams)
    return new_teams


async def has_results(session: AsyncSession, team: Team) -> bool:
    """Whether racing has already happened under this participation.

    Results hang off the entry in an event. For a series registration, that means whether
    any of its acts have been raced — otherwise a club could be removed from a series
    whose results still appear in the table.
    """
    team_ids = [team.id]
    if team.is_series_registration and team.series_id is not None:
        team_ids += list(
            (
                await session.execute(
                    select(Team.id).where(
                        Team.series_id == team.series_id,
                        Team.club_id == team.club_id,
                        Team.event_id.is_not(None),
                    )
                )
            ).scalars()
        )

    hit = (
        await session.execute(select(RaceEntry.id).where(RaceEntry.team_id.in_(team_ids)).limit(1))
    ).scalar_one_or_none()
    return hit is not None


async def delete_event_entries(session: AsyncSession, series_id: int, club_id: int) -> None:
    """Removes a club from every act of a series — when its series registration is dropped."""
    for team in (
        await session.execute(
            select(Team).where(
                Team.series_id == series_id,
                Team.club_id == club_id,
                Team.event_id.is_not(None),
            )
        )
    ).scalars():
        await session.delete(team)


def check_squad_limits(squad_min: int | None, squad_max: int | None) -> None:
    """A minimum above the maximum is a typo, not a rule — refused (Story V-1)."""
    from app.problems import Problem

    if squad_min is not None and squad_max is not None and squad_min > squad_max:
        raise Problem(
            422,
            "squad-limits-invalid",
            "The squad's minimum cannot be larger than its maximum.",
            squad_min=squad_min,
            squad_max=squad_max,
        )
