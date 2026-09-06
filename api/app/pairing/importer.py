"""Import of pairing lists from the Java tool ``PairingList``.

This is the main path to a pairing list: the draw is created there, printed as PDF,
and just needs to be imported here. The own generator in ``app.pairing.schedule``
is the fallback for special cases.

Two input formats, both from the same run:

``schedule_cfg.yml`` describes the framework — teams in fixed order, boats with color,
number of flights. ``pairing_list.yml`` contains the draw as 0-based indices into the
team list, where the position in the string is the boat number:

    flights:
    - races:
      - "2,0,15,12,1,13"     # Team 2 on boat 1, team 0 on boat 2, ...

``pairing_list.csv`` contains the same information 1-based and with trailing
semicolon per line:

    Race;Flight;Boat 1;Boat 2;Boat 3;Boat 4;Boat 5;Boat 6
    1;1;3;1;16;13;2;14;

**Preferably import the YAML version.** In events through and including 2023, the
CSV column ``Flight`` contains not the flight number, but the number of the race within
the flight — grouping by this column would produce wrong flights there. The
CSV path remains for external lists that do not come from the Java tool.

The importer validates the draw rather than trusting it: each team must appear in each flight
exactly once, and each boat in each race exactly once. An incorrect
pairing list would otherwise not be noticed until the event day.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass

import yaml

from app.pairing.schedule import PairingSlot


class PairingImportError(ValueError):
    """The input is not a valid pairing list."""


@dataclass(frozen=True)
class BoatSpec:
    number: int
    color: str | None


@dataclass(frozen=True)
class ImportedPairing:
    """An imported and validated draw."""

    teams: list[str]
    boats: list[BoatSpec]
    flights: int
    races_per_flight: int
    slots: list[PairingSlot]

    def team_name(self, slot: PairingSlot) -> str:
        return self.teams[slot.team_index]


@dataclass(frozen=True)
class ScheduleConfig:
    teams: list[str]
    boats: list[BoatSpec]
    flights: int
    titles: list[str]


def parse_schedule_config(text: str) -> ScheduleConfig:
    """Reads ``schedule_cfg.yml``."""
    data = yaml.safe_load(text) or {}

    teams = [str(t) for t in data.get("teams", [])]
    if not teams:
        raise PairingImportError("schedule_cfg.yml contains no teams")
    if len(set(teams)) != len(teams):
        duplicates = sorted({t for t in teams if teams.count(t) > 1})
        raise PairingImportError(
            f"Team abbreviations assigned multiple times: {', '.join(duplicates)}"
        )

    raw_boats = data.get("boats") or []
    if not raw_boats:
        raise PairingImportError("schedule_cfg.yml contains no boats")
    boats = [
        BoatSpec(number=index, color=_boat_color(entry))
        for index, entry in enumerate(raw_boats, start=1)
    ]

    flights = int(data.get("flights", 0))
    if flights < 1:
        raise PairingImportError(f"Implausible flight count: {flights}")

    return ScheduleConfig(
        teams=teams,
        boats=boats,
        flights=flights,
        titles=[str(t) for t in data.get("titles", [])],
    )


def _boat_color(entry: object) -> str | None:
    # Boats are stored as a list of mappings: "- color: BLACK".
    if isinstance(entry, dict):
        color = entry.get("color")
        return str(color) if color is not None else None
    return str(entry) if entry is not None else None


def load_pairing_yaml(schedule_cfg: str, pairing_yaml: str) -> ImportedPairing:
    """Reads ``schedule_cfg.yml`` plus ``pairing_list.yml`` (0-based indices)."""
    config = parse_schedule_config(schedule_cfg)
    data = yaml.safe_load(pairing_yaml) or {}

    flights = data.get("flights")
    if not isinstance(flights, list) or not flights:
        raise PairingImportError("pairing_list.yml contains no flights")

    grouped: list[list[list[int]]] = []
    for flight_number, flight in enumerate(flights, start=1):
        races = (flight or {}).get("races")
        if not isinstance(races, list) or not races:
            raise PairingImportError(f"Flight {flight_number} contains no races")
        grouped.append([_parse_race_line(line, flight_number) for line in races])

    return _build(config, grouped)


def load_pairing_csv(schedule_cfg: str, pairing_csv: str) -> ImportedPairing:
    """Reads ``schedule_cfg.yml`` plus ``pairing_list.csv`` (1-based team numbers)."""
    config = parse_schedule_config(schedule_cfg)
    reader = csv.DictReader(io.StringIO(pairing_csv), delimiter=";")

    if not reader.fieldnames or "Flight" not in reader.fieldnames:
        raise PairingImportError(
            "pairing_list.csv has no header with 'Flight' — wrong delimiter?"
        )
    boat_columns = [name for name in reader.fieldnames if name and name.startswith("Boat ")]
    if not boat_columns:
        raise PairingImportError("pairing_list.csv contains no boat columns")

    by_flight: dict[int, list[list[int]]] = {}
    for line_number, row in enumerate(reader, start=2):
        try:
            flight = int(row["Flight"])
        except (KeyError, TypeError, ValueError) as exc:
            raise PairingImportError(f"Line {line_number}: Flight not readable") from exc

        race: list[int] = []
        for column in boat_columns:
            value = (row.get(column) or "").strip()
            if not value:
                raise PairingImportError(f"Line {line_number}: column '{column}' is empty")
            try:
                # CSV is 1-based, internally we use 0-based like the YAML version.
                race.append(int(value) - 1)
            except ValueError as exc:
                raise PairingImportError(
                    f"Line {line_number}, column '{column}': '{value}' is not a team number"
                ) from exc
        by_flight.setdefault(flight, []).append(race)

    if not by_flight:
        raise PairingImportError("pairing_list.csv contains no races")

    grouped = [by_flight[flight] for flight in sorted(by_flight)]
    return _build(config, grouped)


def _parse_race_line(line: object, flight_number: int) -> list[int]:
    if not isinstance(line, str):
        raise PairingImportError(f"Flight {flight_number}: race is not text: {line!r}")
    try:
        return [int(part) for part in line.split(",")]
    except ValueError as exc:
        raise PairingImportError(
            f"Flight {flight_number}: '{line}' is not a list of team numbers"
        ) from exc


def _build(config: ScheduleConfig, grouped: list[list[list[int]]]) -> ImportedPairing:
    """Validates the draw and transforms it into ``PairingSlot``s.

    If the team count is not divisible by the boat count (17 teams on 6 boats, for example),
    the Java tool internally pads the team list with empty slots. In the draw,
    indices beyond the actual team count then appear — they mean "boat remains empty" and
    create no slot here.
    """
    team_count = len(config.teams)
    boat_count = len(config.boats)
    races_per_flight = len(grouped[0])
    # Padded size: as many positions as a flight's races can hold.
    slot_count = -(-team_count // boat_count) * boat_count

    if len(grouped) != config.flights:
        raise PairingImportError(
            f"schedule_cfg.yml lists {config.flights} flights, "
            f"the pairing list contains {len(grouped)}"
        )

    slots: list[PairingSlot] = []
    for flight_index, races in enumerate(grouped):
        flight_number = flight_index + 1

        if len(races) != races_per_flight:
            raise PairingImportError(
                f"Flight {flight_number} has {len(races)} races, "
                f"flight 1 had {races_per_flight}"
            )

        seen: list[int] = []
        for race_index, race in enumerate(races):
            if len(race) != boat_count:
                raise PairingImportError(
                    f"Flight {flight_number}, race {race_index + 1}: "
                    f"{len(race)} teams on {boat_count} boats"
                )
            for boat_index, team_index in enumerate(race):
                if not 0 <= team_index < slot_count:
                    raise PairingImportError(
                        f"Flight {flight_number}, race {race_index + 1}: "
                        f"Team {team_index} is outside the {slot_count} positions"
                    )
                if team_index >= team_count:
                    # Empty position in an incompletely filled fleet: the boat does not sail.
                    continue
                slots.append(
                    PairingSlot(
                        flight=flight_number,
                        race_in_flight=race_index + 1,
                        sequence=flight_index * races_per_flight + race_index + 1,
                        team_index=team_index,
                        boat_number=config.boats[boat_index].number,
                    )
                )
            seen.extend(race)

        # The hard constraint of the league format: each team sails exactly once per flight.
        if sorted(seen) != list(range(slot_count)):
            missing = sorted(set(range(slot_count)) - set(seen))
            twice = sorted({t for t in seen if seen.count(t) > 1})
            raise PairingImportError(
                f"Flight {flight_number} is not a complete round — "
                f"missing: {missing or 'none'}, duplicate: {twice or 'none'}"
            )

    return ImportedPairing(
        teams=config.teams,
        boats=config.boats,
        flights=config.flights,
        races_per_flight=races_per_flight,
        slots=slots,
    )
