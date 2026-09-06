"""Participation: who is registered for a series, and who is entered in an event.

Both are ``Team`` rows; ``event_id`` tells them apart (see ``app/models/org.py``). The
rules live here in one place because four routers need them:

* Whoever enters an act **must be registered for its series**.
* A participation that has already been raced under can no longer be withdrawn.
* When a series event is created, the **same clubs** enter by default as in the series;
  the admin can deviate afterwards.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Club, Event, RaceEntry, Team, TeamStatus


class TeilnahmeFehler(ValueError):
    """A participation that isn't allowed to exist like this."""


async def serienmeldungen(
    session: AsyncSession, series_id: int, *, nur_angenommen: bool = True
) -> list[Team]:
    """The clubs registered for the series — not their entries in individual acts."""
    stmt = select(Team).where(Team.series_id == series_id, Team.event_id.is_(None))
    if nur_angenommen:
        stmt = stmt.where(Team.status == TeamStatus.ACCEPTED)
    return list((await session.execute(stmt.order_by(Team.name, Team.id))).scalars())


async def antritte(
    session: AsyncSession, event_id: int, *, nur_angenommen: bool = True
) -> list[Team]:
    """The teams entered in this event.

    Sorted by name so the same input always produces the same pairing.
    """
    stmt = select(Team).where(Team.event_id == event_id)
    if nur_angenommen:
        stmt = stmt.where(Team.status == TeamStatus.ACCEPTED)
    return list((await session.execute(stmt.order_by(Team.name, Team.id))).scalars())


async def serienmeldung(session: AsyncSession, series_id: int, club_id: int) -> Team | None:
    return (
        await session.execute(
            select(Team).where(
                Team.series_id == series_id,
                Team.event_id.is_(None),
                Team.club_id == club_id,
            )
        )
    ).scalar_one_or_none()


async def antritt(session: AsyncSession, event_id: int, club_id: int) -> Team | None:
    return (
        await session.execute(
            select(Team).where(Team.event_id == event_id, Team.club_id == club_id)
        )
    ).scalar_one_or_none()


async def kader_mannschaft(session: AsyncSession, team: Team) -> Team:
    """The team the squad hangs off.

    For an act, that's the same club's series registration: you register for the series,
    and field a lineup for the individual matchday. If the event stands on its own, the
    squad hangs off it directly.
    """
    if team.ist_serienmeldung or team.series_id is None:
        return team
    meldung = await serienmeldung(session, team.series_id, team.club_id)
    if meldung is None:
        raise TeilnahmeFehler(
            "This club is entered in the event but isn't registered for its series — "
            "so there's no squad."
        )
    return meldung


async def neuer_antritt(
    session: AsyncSession,
    event: Event,
    club: Club,
    *,
    status: str = TeamStatus.ACCEPTED,
) -> Team:
    """Creates a club's entry in an event.

    The rule at stake: if the event belongs to a series, the club must be **registered
    and accepted** for it there. Otherwise it would show up in the daily standings but in
    no series table.
    """
    if event.series_id is not None:
        meldung = await serienmeldung(session, event.series_id, club.id)
        if meldung is None or meldung.status != TeamStatus.ACCEPTED:
            raise TeilnahmeFehler(
                f"{club.short_name} isn't registered for this event's series. "
                "Register for the series first, then enter the act."
            )

    team = Team(
        name=club.short_name,
        club_id=club.id,
        series_id=event.series_id,
        event_id=event.id,
        status=status,
    )
    session.add(team)
    return team


async def uebernehme_serienmeldungen(session: AsyncSession, event: Event) -> list[Team]:
    """Enters the series' registered clubs as participants of the event.

    The normal case: the same clubs enter every act of a series. Deviations are then
    tracked by the admin via ``PUT /api/admin/events/{id}/clubs``.
    """
    if event.series_id is None:
        return []

    schon_da = {team.club_id for team in await antritte(session, event.id, nur_angenommen=False)}
    neu = [
        Team(
            name=meldung.name,
            club_id=meldung.club_id,
            series_id=event.series_id,
            event_id=event.id,
            status=TeamStatus.ACCEPTED,
        )
        for meldung in await serienmeldungen(session, event.series_id)
        if meldung.club_id not in schon_da
    ]
    session.add_all(neu)
    return neu


async def hat_ergebnisse(session: AsyncSession, team: Team) -> bool:
    """Whether racing has already happened under this participation.

    Results hang off the entry in an event. For a series registration, that means whether
    any of its acts have been raced — otherwise a club could be removed from a series
    whose results still appear in the table.
    """
    kennungen = [team.id]
    if team.ist_serienmeldung and team.series_id is not None:
        kennungen += list(
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

    treffer = (
        await session.execute(
            select(RaceEntry.id).where(RaceEntry.team_id.in_(kennungen)).limit(1)
        )
    ).scalar_one_or_none()
    return treffer is not None


async def loesche_antritte(session: AsyncSession, series_id: int, club_id: int) -> None:
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
