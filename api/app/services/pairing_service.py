"""Taking a pairing list into the database.

Publishing a pairing list means creating the boats, flights, races and the team-to-boat
assignment. It replaces an existing list **completely** — hence the safeguard that a race
already sailed is never overwritten (Story VA-3).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Boat, Event, Flight, Race, RaceEntry, RaceStatus, Team, TeamStatus
from app.pairing import BoatSpec, ImportedPairing, PairingSlot, logistics_report, pairing_report


class PairingPublishError(RuntimeError):
    """This pairing list cannot be published as it stands."""


@dataclass
class PairingDraft:
    """A computed or imported list, not yet published.

    ``team_ids`` maps the draw's team indices onto our teams: index 0 of the draw is
    ``team_ids[0]``. Without that mapping the list would be nothing but a sequence of
    numbers.
    """

    team_ids: list[int]
    boats: list[BoatSpec]
    slots: list[PairingSlot]
    flights: int
    quality: dict = field(default_factory=dict)

    @classmethod
    def from_import(cls, pairing: ImportedPairing, team_ids: list[int]) -> PairingDraft:
        if len(team_ids) != len(pairing.teams):
            raise PairingPublishError(
                f"The list names {len(pairing.teams)} teams, "
                f"but {len(team_ids)} were mapped"
            )
        return cls(
            team_ids=team_ids,
            boats=list(pairing.boats),
            slots=list(pairing.slots),
            flights=pairing.flights,
            quality={
                **pairing_report(pairing.slots, len(pairing.teams), len(pairing.boats)),
                **logistics_report(pairing.slots, len(pairing.boats)).as_dict(),
            },
        )


async def teams_for_event(session: AsyncSession, event: Event) -> list[Team]:
    """The teams entering this event, in a stable order.

    The pairing list belongs to the event, and so do the teams in it: the draw is among
    those entering *here*, not among everyone registered for the series. Sorted by club
    name so the same input always yields the same assignment — a draw has to be
    reproducible.
    """
    result = await session.execute(
        select(Team)
        .where(Team.event_id == event.id, Team.status == TeamStatus.ACCEPTED)
        .order_by(Team.name, Team.id)
    )
    return list(result.scalars())


async def sailed_races(session: AsyncSession, event_id: int) -> int:
    """Races of this matchday that already have results."""
    stmt = (
        select(func.count(func.distinct(Race.id)))
        .join(Flight, Race.flight_id == Flight.id)
        .join(RaceEntry, RaceEntry.race_id == Race.id)
        .where(Flight.event_id == event_id, RaceEntry.code.is_not(None))
    )
    return int((await session.execute(stmt)).scalar_one())


async def publish_pairing(
    session: AsyncSession, event: Event, draft: PairingDraft
) -> dict[str, int]:
    """Replaces a matchday's pairing list. Returns what was created."""
    already_sailed = await sailed_races(session, event.id)
    if already_sailed:
        raise PairingPublishError(
            f"This matchday already has results from {already_sailed} races. "
            "A new draw would discard them."
        )

    known_teams = {team.id for team in await teams_for_event(session, event)}
    unknown = [team_id for team_id in draft.team_ids if team_id not in known_teams]
    if unknown:
        raise PairingPublishError(
            f"These teams are not entered in this event: {unknown}"
        )

    await _clear_pairing(session, event.id)

    boats = await _boats(session, event, draft.boats)
    flights = [Flight(event_id=event.id, number=n) for n in range(1, draft.flights + 1)]
    session.add_all(flights)
    await session.flush()

    boat_id_by_number = {boat.number: boat.id for boat in boats}
    flight_id_by_number = {flight.number: flight.id for flight in flights}

    races: dict[int, Race] = {}
    for slot in draft.slots:
        if slot.sequence in races:
            continue
        race = Race(
            flight_id=flight_id_by_number[slot.flight],
            number_in_flight=slot.race_in_flight,
            sequence=slot.sequence,
            status=RaceStatus.SCHEDULED,
        )
        session.add(race)
        races[slot.sequence] = race
    await session.flush()

    for slot in draft.slots:
        session.add(
            RaceEntry(
                race_id=races[slot.sequence].id,
                team_id=draft.team_ids[slot.team_index],
                boat_id=boat_id_by_number[slot.boat_number],
            )
        )

    await session.commit()
    return {
        "boats": len(boats),
        "flights": len(flights),
        "races": len(races),
        "entries": len(draft.slots),
    }


async def _boats(
    session: AsyncSession, event: Event, specs: list[BoatSpec]
) -> list[Boat]:
    """The event's boats, matched to the draw.

    **Existing boats stay.** They belong to the event, not to the draw: the organizer gave
    them their colour and name when creating it, and the same boats are at the dock however
    often the list is drawn again. Only what is missing gets added; surplus boats go when
    the new list needs fewer.
    """
    existing = {
        boat.number: boat
        for boat in (
            await session.execute(select(Boat).where(Boat.event_id == event.id))
        ).scalars()
    }

    boats: list[Boat] = []
    for spec in specs:
        boat = existing.pop(spec.number, None)
        if boat is None:
            boat = Boat(event_id=event.id, number=spec.number, color=spec.color)
            session.add(boat)
        boats.append(boat)

    for leftover in existing.values():
        await session.delete(leftover)

    await session.flush()
    return boats


async def _clear_pairing(session: AsyncSession, event_id: int) -> None:
    """Clears the old list — from the entries upwards, so no foreign key breaks.

    The boats stay: they belong to the event, not to the draw.
    """
    race_ids = (
        select(Race.id).join(Flight, Race.flight_id == Flight.id).where(Flight.event_id == event_id)
    ).scalar_subquery()

    await session.execute(delete(RaceEntry).where(RaceEntry.race_id.in_(race_ids)))
    await session.execute(delete(Race).where(Race.id.in_(race_ids)))
    await session.execute(delete(Flight).where(Flight.event_id == event_id))
    await session.flush()
