"""Taking a pairing list into the database.

Publishing a pairing list means creating the boats, flights, races and the team-to-boat
assignment. It replaces an existing list **completely** — hence the safeguard that a race
already sailed is never overwritten (Story VA-3).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import NamedTuple

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Boat, Event, Flight, Race, RaceEntry, RaceStatus, Team
from app.pairing import BoatSpec, ImportedPairing, PairingSlot, logistics_report, pairing_report
from app.pairing.pdf import PdfRequest, PrintSettings
from app.problems import Problem
from app.services.participation import event_entries


class PairingPublishError(Problem):
    """This pairing list cannot be published as it stands — a typed 409."""

    def __init__(self, code: str, title: str, **extra: object) -> None:
        super().__init__(409, code, title, **extra)


class TeamNotInPairing(RuntimeError):
    """This team has no seat in the list that was drawn."""


class PublishedPairing(NamedTuple):
    """What publishing a pairing list created."""

    boats: int
    flights: int
    races: int
    entries: int


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
                "pairing-team-mapping-mismatch",
                f"The list names {len(pairing.teams)} teams, but {len(team_ids)} were mapped",
                listed=len(pairing.teams),
                mapped=len(team_ids),
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


async def stored_pairing(
    session: AsyncSession, event: Event, *, title: str, team_id: int | None = None
) -> PdfRequest | None:
    """The list an event has been drawn, in the shape the printer wants (Story B-3).

    ``None`` when nothing has been drawn: there is no empty sheet worth printing.

    The teams come from **the draw**, not from the event's current entry list. Those two
    can differ — a club entered after the draw has no seat in it, one taken out still has
    one — and the printed sheet has to show the list that will be sailed. Naming a club the
    draw does not know would push every index along and put whole flights on the wrong
    boat. Ordered by name like everywhere else, so the same draw always prints the same way.

    With ``team_id`` the request is for that club's own page instead of the whole sheet,
    and the print settings are the ones the organizer stored on the event.
    """
    boats = list(
        (
            await session.execute(
                select(Boat).where(Boat.event_id == event.id).order_by(Boat.number)
            )
        ).scalars()
    )

    stmt = (
        select(Race, RaceEntry, Flight, Team)
        .join(Flight, Race.flight_id == Flight.id)
        .join(RaceEntry, RaceEntry.race_id == Race.id)
        .join(Team, RaceEntry.team_id == Team.id)
        .where(Flight.event_id == event.id)
        .order_by(Race.sequence)
    )
    rows = (await session.execute(stmt)).all()
    if not rows or not boats:
        return None

    teams = sorted({team.id: team for _, _, _, team in rows}.values(), key=lambda t: (t.name, t.id))
    index_by_team = {team.id: index for index, team in enumerate(teams)}
    boat_number = {boat.id: boat.number for boat in boats}

    if team_id is not None and team_id not in index_by_team:
        raise TeamNotInPairing(
            f"Team {team_id} has no seat in the pairing list of event {event.id}"
        )

    return PdfRequest(
        teams=[team.name for team in teams],
        boats=[BoatSpec(number=boat.number, color=boat.color, name=boat.name) for boat in boats],
        slots=[
            PairingSlot(
                flight=flight.number,
                race_in_flight=race.number_in_flight,
                sequence=race.sequence,
                team_index=index_by_team[entry.team_id],
                boat_number=boat_number[entry.boat_id],
            )
            for race, entry, flight, _team in rows
        ],
        title=title,
        settings=PrintSettings.from_json(event.print_settings),
        team_index=None if team_id is None else index_by_team[team_id],
    )


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
) -> PublishedPairing:
    """Replaces a matchday's pairing list. Returns what was created.

    Doesn't commit: the caller commits, then publishes the change to ``app.live``."""
    already_sailed = await sailed_races(session, event.id)
    if already_sailed:
        raise PairingPublishError(
            "pairing-has-results",
            f"This matchday already has results from {already_sailed} races. "
            "A new draw would discard them.",
            races_sailed=already_sailed,
        )

    known_teams = {team.id for team in await event_entries(session, event.id)}
    unknown = [team_id for team_id in draft.team_ids if team_id not in known_teams]
    if unknown:
        raise PairingPublishError(
            "pairing-teams-not-entered",
            f"These teams are not entered in this event: {unknown}",
            team_ids=unknown,
        )

    await clear_pairing(session, event.id)

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

    await session.flush()
    return PublishedPairing(
        boats=len(boats),
        flights=len(flights),
        races=len(races),
        entries=len(draft.slots),
    )


async def _boats(session: AsyncSession, event: Event, specs: list[BoatSpec]) -> list[Boat]:
    """The event's boats, matched to the draw.

    **Existing boats stay.** They belong to the event, not to the draw: the organizer gave
    them their colour and name when creating it, and the same boats are at the dock however
    often the list is drawn again. Only what is missing gets added; surplus boats go when
    the new list needs fewer.
    """
    existing = {
        boat.number: boat
        for boat in (await session.execute(select(Boat).where(Boat.event_id == event.id))).scalars()
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


async def clear_pairing(session: AsyncSession, event_id: int) -> None:
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
