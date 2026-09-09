"""Pairing-Listen in die Datenbank übernehmen.

Eine Pairing-Liste zu veröffentlichen heißt: Boote, Flights, Wettfahrten und die Zuordnung
Team-auf-Boot anlegen. Das ersetzt eine vorhandene Liste vollständig — deshalb die
Schutzregel, dass eine bereits gesegelte Wettfahrt niemals überschrieben wird (Story VA-3).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Boat, Event, Flight, Race, RaceEntry, RaceStatus, Team, TeamStatus
from app.pairing import BoatSpec, ImportedPairing, PairingSlot, logistics_report, pairing_report


class PairingPublishError(RuntimeError):
    """Die Pairing-Liste kann so nicht veröffentlicht werden."""


@dataclass
class PairingDraft:
    """Eine berechnete oder eingelesene Liste, noch nicht veröffentlicht.

    ``team_ids`` bildet die Teamindizes der Auslosung auf unsere Teams ab: Index 0 der
    Auslosung ist ``team_ids[0]``. Ohne diese Zuordnung wäre die Liste nur eine Folge von
    Zahlen.
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
                f"Die Liste nennt {len(pairing.teams)} Teams, "
                f"zugeordnet wurden {len(team_ids)}"
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
    """Die Mannschaften, die bei dieser Veranstaltung antreten, in stabiler Reihenfolge.

    Die Pairing-Liste hängt am Event, also auch die Mannschaften darin: gelost wird unter
    denen, die hier antreten — nicht unter allen, die für die Serie gemeldet sind. Nach
    Vereinsnamen sortiert, damit dieselbe Eingabe immer dieselbe Zuordnung ergibt; eine
    Auslosung muss reproduzierbar sein.
    """
    result = await session.execute(
        select(Team)
        .where(Team.event_id == event.id, Team.status == TeamStatus.ACCEPTED)
        .order_by(Team.name, Team.id)
    )
    return list(result.scalars())


async def sailed_races(session: AsyncSession, event_id: int) -> int:
    """Wettfahrten dieses Spieltags, für die schon Ergebnisse vorliegen."""
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
    """Ersetzt die Pairing-Liste eines Spieltags. Gibt zurück, was angelegt wurde."""
    already_sailed = await sailed_races(session, event.id)
    if already_sailed:
        raise PairingPublishError(
            f"Für diesen Spieltag liegen bereits Ergebnisse aus {already_sailed} "
            "Wettfahrten vor. Eine neue Auslosung würde sie verwerfen."
        )

    known_teams = {team.id for team in await teams_for_event(session, event)}
    unknown = [team_id for team_id in draft.team_ids if team_id not in known_teams]
    if unknown:
        raise PairingPublishError(
            f"Diese Mannschaften treten bei dieser Veranstaltung nicht an: {unknown}"
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
    """Die Boote der Veranstaltung, passend zur Auslosung.

    **Vorhandene Boote bleiben stehen.** Sie gehören der Veranstaltung, nicht der
    Auslosung: Farbe und Name hat der Veranstalter beim Anlegen vergeben, und am Steg
    liegen dieselben Boote, gleichgültig wie oft neu gelost wird. Ergänzt wird nur, was
    fehlt; überzählige Boote fallen weg, wenn die neue Liste mit weniger auskommt.
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
    """Räumt die alte Liste ab — von den Einträgen aufwärts, damit keine Fremdschlüssel brechen.

    Die Boote bleiben: sie gehören der Veranstaltung, nicht der Auslosung.
    """
    race_ids = (
        select(Race.id).join(Flight, Race.flight_id == Flight.id).where(Flight.event_id == event_id)
    ).scalar_subquery()

    await session.execute(delete(RaceEntry).where(RaceEntry.race_id.in_(race_ids)))
    await session.execute(delete(Race).where(Race.id.in_(race_ids)))
    await session.execute(delete(Flight).where(Flight.event_id == event_id))
    await session.flush()
