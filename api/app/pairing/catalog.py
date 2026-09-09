"""Catalog of pre-computed pairing lists.

A pairing list depends on just three numbers: **teams, boats, flights**. For 18 teams on
6 boats over 16 flights, the structure is always the same — which club sits at which
starting position is decided only when publishing.

This is why it is **computed once and stored**, not recalculated for each event. The
optimization run of the Java tool takes minutes; looking it up in the catalog takes
milliseconds, and shuffling the starting positions via a seed takes the same. An organizer
gets their draw immediately without waiting for a background job.

**Exactly one file is stored per entry** — the ``out.yml`` that the Java tool writes anyway.
It carries all the information:

    flights:
    - races:
      - "2,0,15,12,1,13"     # Team 2 on boat 1, team 0 on boat 2, ...

The size follows automatically: the number of flights is the length of the list,
the number of boats is the length of a row, the number of races per flight is the length of
``races`` — and from that, the team count. The catalog does not need a ``schedule_cfg.yml``:
team names come from the registered clubs, boat colors from the boats of the event.
A file from the Java tool can be placed in unchanged.

**Shuffling does not change quality.** Boat distribution, matchups, and boat changes depend on
the structure of the list, not on which name stands at which starting position — a
permutation of team indices leaves all these metrics unchanged. The seed makes the
draw reproducible at the same time: in case of dispute, it can be reconstructed from the
catalog entry and seed.

To compute and store a new entry::

    uv run python -m app.pairing.catalog --teams 18 --boats 6 --flights 16
"""

from __future__ import annotations

import random
from dataclasses import dataclass, replace
from functools import lru_cache
from pathlib import Path

import yaml

from app.pairing.importer import ImportedPairing, PairingImportError, load_pairing_yaml
from app.pairing.schedule import PairingSlot

SCHEDULE_DIR = Path(__file__).parent / "schedules"


class CatalogError(LookupError):
    """No pre-computed pairing list is available for this size."""


@dataclass(frozen=True)
class CatalogEntry:
    """A stored size: this many teams on this many boats over this many flights."""

    teams: int
    boats: int
    flights: int
    file: Path

    @property
    def name(self) -> str:
        return self.file.stem

    @property
    def races(self) -> int:
        return -(-self.teams // self.boats) * self.flights


def _dimensions(text: str) -> tuple[int, int, int]:
    """Reads teams, boats, and flights from the draw itself.

    The team count is the number of starting positions in a flight — for a padded
    size (17 teams on 6 boats), this includes empty slots that disappear on import.
    The catalog indexes the entry by the padded size; exactly this size is also
    what is requested.
    """
    data = yaml.safe_load(text) or {}
    flights = data.get("flights")
    if not isinstance(flights, list) or not flights:
        raise PairingImportError("The file contains no flights")

    races = (flights[0] or {}).get("races")
    if not isinstance(races, list) or not races:
        raise PairingImportError("The first flight contains no races")

    boats = len(str(races[0]).split(","))
    return len(races) * boats, boats, len(flights)


def _as_schedule_cfg(teams: int, boats: int, flights: int) -> str:
    """The framework that the importer expects — here synthetic, with placeholders.

    The names are starting position numbers, not clubs: which club sits where is decided
    only when publishing. The boat colors remain empty because the boats belong to the
    event, not the list.
    """
    return yaml.safe_dump(
        {
            "flights": flights,
            "titles": ["Catalog"],
            "teams": [f"T{index + 1:02d}" for index in range(teams)],
            "boats": [{"color": None} for _ in range(boats)],
        },
        sort_keys=False,
        allow_unicode=True,
    )


def catalog_entries(base: Path | None = None) -> list[CatalogEntry]:
    """All stored sizes, sorted ascending.

    The size comes from the content, not the filename: a copied-in
    ``out.yml`` finds its place automatically.
    """
    root = base or SCHEDULE_DIR
    if not root.is_dir():
        return []

    entries = []
    for path in sorted(root.glob("*.yml")):
        try:
            teams, boats, flights = _dimensions(path.read_text(encoding="utf-8"))
        except (PairingImportError, yaml.YAMLError, OSError):
            # An unreadable file must not make the catalog unusable.
            continue
        entries.append(
            CatalogEntry(teams=teams, boats=boats, flights=flights, file=path)
        )
    return sorted(entries, key=lambda e: (e.teams, e.boats, e.flights))


def load_entry(
    teams: int, boats: int, flights: int, *, base: Path | None = None
) -> ImportedPairing:
    """Fetches the finished list for this size."""
    matching = [
        entry
        for entry in catalog_entries(base)
        if (entry.teams, entry.boats, entry.flights) == (teams, boats, flights)
    ]
    if not matching:
        available = (
            ", ".join(
                f"{e.teams}/{e.boats}/{e.flights}" for e in catalog_entries(base)
            )
            or "none"
        )
        raise CatalogError(
            f"For {teams} teams on {boats} boats over {flights} flights, no "
            f"pre-computed pairing list is available. Available (Teams/Boats/Flights): {available}."
        )

    entry = matching[0]
    try:
        return load_pairing_yaml(
            _as_schedule_cfg(teams, boats, flights),
            entry.file.read_text(encoding="utf-8"),
        )
    except PairingImportError as error:
        raise CatalogError(
            f"Catalog entry {entry.name} is unusable: {error}"
        ) from error


def shuffle_pairing(pairing: ImportedPairing, seed: int) -> ImportedPairing:
    """Shuffles the starting positions of the list — same structure, new assignment.

    From a stored list, a new draw is created in milliseconds. All quality metrics
    remain the same because they do not depend on which starting position carries which
    name. The same seed always produces the same draw.
    """
    count = len(pairing.teams)
    permutation = list(range(count))
    random.Random(seed).shuffle(permutation)

    slots = [
        replace(slot, team_index=permutation[slot.team_index])
        if slot.team_index < count
        else slot
        for slot in pairing.slots
    ]
    return replace(pairing, slots=slots)


@lru_cache(maxsize=8)
def _cached(teams: int, boats: int, flights: int) -> ImportedPairing:
    return load_entry(teams, boats, flights)


def shuffled(teams: int, boats: int, flights: int, seed: int) -> ImportedPairing:
    """Fetch catalog entry and shuffle — the path taken by the UI."""
    return shuffle_pairing(_cached(teams, boats, flights), seed)


# --------------------------------------------------------------- Extend catalog


def to_yaml(slots: list[PairingSlot], flights: int) -> str:
    """Writes a draw in catalog format (0-based starting position numbers)."""
    by_race: dict[tuple[int, int], dict[int, int]] = {}
    for slot in slots:
        by_race.setdefault((slot.flight, slot.race_in_flight), {})[slot.boat_number] = (
            slot.team_index
        )

    lines = ["flights:"]
    for flight in range(1, flights + 1):
        lines.append("- races:")
        for _, race_in_flight in sorted(key for key in by_race if key[0] == flight):
            boats_by_number = by_race[(flight, race_in_flight)]
            lines.append(
                "  - " + ",".join(str(boats_by_number[nr]) for nr in sorted(boats_by_number))
            )
    return "\n".join(lines) + "\n"


async def _generate(teams: int, boats: int, flights: int, seed: int, loops: int) -> str:
    """Computes a new entry — using the Java tool, falling back to the Python generator."""
    from app.models.racing import BOAT_COLORS
    from app.pairing.generator import (
        GenerationRequest,
        OptimizerSettings,
        PairingGeneratorError,
        generate_pairing,
    )
    from app.pairing.importer import BoatSpec
    from app.pairing.schedule import build_pairing

    request = GenerationRequest(
        teams=[f"T{index + 1:02d}" for index in range(teams)],
        boats=[
            BoatSpec(number=n + 1, color=BOAT_COLORS[n] if n < len(BOAT_COLORS) else None)
            for n in range(boats)
        ],
        flights=flights,
        title=f"Catalog {teams}/{boats}/{flights}",
        optimizer=OptimizerSettings(seed=seed, loops=loops),
    )

    try:
        result = await generate_pairing(request)
        print(f"Java tool: {result.summary()}")
        slots = result.pairing.slots
    except PairingGeneratorError as error:
        print(f"Java tool unavailable ({error}) — Python generator as fallback.")
        slots = build_pairing(team_count=teams, flights=flights, boats=boats, seed=seed)

    return to_yaml(slots, flights)


def main() -> None:
    import argparse
    import asyncio

    parser = argparse.ArgumentParser(description="Store a finished pairing list in the catalog")
    parser.add_argument("--teams", type=int, required=True)
    parser.add_argument("--boats", type=int, default=6)
    parser.add_argument("--flights", type=int, required=True)
    parser.add_argument("--seed", type=int, default=1240)
    parser.add_argument(
        "--loops",
        type=int,
        default=20_000,
        help="Optimizer loops. Fewer is faster and gets worse.",
    )
    args = parser.parse_args()

    content = asyncio.run(
        _generate(args.teams, args.boats, args.flights, args.seed, args.loops)
    )
    SCHEDULE_DIR.mkdir(parents=True, exist_ok=True)
    target = SCHEDULE_DIR / f"t{args.teams}-b{args.boats}-f{args.flights}.yml"
    target.write_text(content, encoding="utf-8")

    checked = load_entry(args.teams, args.boats, args.flights)
    print(f"Stored: {target} — {len(checked.slots)} starting positions, {checked.flights} flights")


if __name__ == "__main__":
    main()
