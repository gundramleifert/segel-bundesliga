"""Logistical quality of a pairing list: boat changes and shuttle trips.

The expensive part of a matchday is not the combinatorics, but the boat traffic. If
a team sails in the last race of a flight and in the first of the next on
**the same boat position**, it simply stays on board — nobody needs to pick it up. If it
changes boats, it must switch. If it is not in one of the two races at all, it needs
a shuttle trip. A shuttle takes two teams.

These metrics are a faithful port of
``CostCalculatorBoatSchedule.getInterFlightStat`` from the Java tool
(``reference/PairingList``), so lists from both sources can be compared.
It is intentionally **only the measurement** ported, not the optimizer.

``saved_shuttles_*`` counts **saved** trips compared to the case where each team
had to be taken individually — higher is better. For ``boat_changes``, fewer is
better.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from app.pairing.schedule import PairingSlot


@dataclass(frozen=True)
class LogisticsReport:
    """What boat traffic the draw causes."""

    saved_shuttles_harbour: int
    saved_shuttles_at_sea: int
    boat_changes: int
    teams_staying_on_boat: int

    def as_dict(self) -> dict[str, int]:
        return {
            "saved_shuttles_harbour": self.saved_shuttles_harbour,
            "saved_shuttles_at_sea": self.saved_shuttles_at_sea,
            "boat_changes": self.boat_changes,
            "teams_staying_on_boat": self.teams_staying_on_boat,
        }


def to_flights(slots: list[PairingSlot], boats: int = 6) -> list[list[list[int]]]:
    """Transforms slots into ``flights -> races -> teams by boat position``.

    Empty positions in an incompletely filled fleet are padded with ``-1`` so that
    boat positions keep their position — otherwise the comparisons ``i == j`` would shift.
    """
    by_race: dict[tuple[int, int], dict[int, int]] = defaultdict(dict)
    for slot in slots:
        by_race[(slot.flight, slot.race_in_flight)][slot.boat_number] = slot.team_index

    flights: dict[int, list[list[int]]] = defaultdict(list)
    for (flight, _race), seats in sorted(by_race.items()):
        flights[flight].append([seats.get(boat, -1) for boat in range(1, boats + 1)])
    return [flights[key] for key in sorted(flights)]


def logistics_report(slots: list[PairingSlot], boats: int = 6) -> LogisticsReport:
    flights = to_flights(slots, boats)
    if len(flights) < 2:
        return LogisticsReport(0, 0, 0, 0)

    shuttles_each_race = _shuttles_for(len(flights[0][0]))
    harbour = at_sea = changes = staying = 0

    for before, after in zip(flights, flights[1:], strict=False):
        stat = _between(before, after)
        harbour += shuttles_each_race - _shuttles_for(stat.between_flights)
        at_sea += shuttles_each_race - _shuttles_for(stat.first_race)
        at_sea += shuttles_each_race - _shuttles_for(stat.last_race)
        changes += stat.boat_changes
        staying += stat.staying_on_boat

    return LogisticsReport(
        saved_shuttles_harbour=harbour,
        saved_shuttles_at_sea=at_sea,
        boat_changes=changes,
        teams_staying_on_boat=staying,
    )


@dataclass(frozen=True)
class _InterFlight:
    between_flights: int
    first_race: int
    last_race: int
    boat_changes: int
    staying_on_boat: int


def _between(before: list[list[int]], after: list[list[int]]) -> _InterFlight:
    last = before[-1]
    first = after[0]

    to_transfer = max(_participants(last), _participants(first))
    staying = 0
    changes = 0
    for seat, team in enumerate(last):
        if team < 0:
            continue
        if team not in first:
            continue
        if first[seat] == team:
            # Same boat position: the team stays on board and does not need to move.
            staying += 1
            to_transfer -= 1
        else:
            changes += 1

    first_race = last_race = 0
    if len(before) > 1 and len(after) > 1:
        # Those already out in the second-to-last race are still on the water.
        last_race = _transfers(before[-2], after[0])
        first_race = _transfers(before[-1], after[1])

    return _InterFlight(
        between_flights=to_transfer,
        first_race=first_race,
        last_race=last_race,
        boat_changes=changes,
        staying_on_boat=staying,
    )


def _transfers(race1: list[int], race2: list[int]) -> int:
    """How many teams must move between two races."""
    count = max(len(race1), len(race2))
    for team in race1:
        if team >= 0 and team in race2:
            count -= 1
    return count


def _participants(race: list[int]) -> int:
    return sum(1 for team in race if team >= 0)


def _shuttles_for(teams: int) -> int:
    """A shuttle takes two teams."""
    return (teams + 1) // 2
