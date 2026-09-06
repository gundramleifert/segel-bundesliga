"""Pairing lists: which team sails in which race on which boat.

A flight comprises ``team_count / boats`` races in which each team sails exactly once
(18 teams / 6 boats = 3 races). This is the hard constraint. Alongside it are
two soft goals that make a pairing list fair:

* each team sails each boat about equally often,
* any two teams encounter each other about equally often.

Satisfying both exactly at the same time is a combinatorial problem (related to the
*Social Golfer Problem*) for which there is no closed-form solution. The approach here:

1. **Groups** via local search — random start, then swap moves that balance
   opponent distribution. The objective is the sum of squared encounter counts; it
   is minimal precisely when encounters are evenly distributed.
2. **Boats** via exact assignment per group — with six boats, that is 720 permutations
   that can be fully computed. The assignment is chosen where teams get
   the boats they have used least so far.

Randomness is fixed via ``seed``: the same input produces the same list. A
draw must be reproducible, otherwise it cannot be proven in case of dispute.
"""

from __future__ import annotations

import random
from collections import Counter
from dataclasses import dataclass
from itertools import combinations, permutations


@dataclass(frozen=True)
class PairingSlot:
    flight: int  # 1-based
    race_in_flight: int  # 1-based
    sequence: int  # sequential race number across the matchday
    team_index: int  # index in the provided team list
    boat_number: int  # 1-based


def build_pairing(
    team_count: int,
    flights: int,
    boats: int = 6,
    *,
    seed: int = 0,
    iterations: int = 60_000,
) -> list[PairingSlot]:
    """Generates the pairing list for a matchday."""
    if team_count % boats != 0:
        raise ValueError(
            f"{team_count} teams cannot be evenly distributed across {boats} boats"
        )
    if flights < 1:
        raise ValueError("A matchday needs at least one flight")

    rng = random.Random(seed)
    groups = _optimise_groups(team_count, flights, boats, rng, iterations)
    return _assign_boats(groups, team_count, boats)


# --------------------------------------------------------------------------- Groups


def _optimise_groups(
    team_count: int, flights: int, boats: int, rng: random.Random, iterations: int
) -> list[list[list[int]]]:
    """Distributes teams per flight across groups and balances encounters."""
    order_per_flight: list[list[int]] = []
    for _ in range(flights):
        order = list(range(team_count))
        rng.shuffle(order)
        order_per_flight.append(order)

    meetings: Counter[tuple[int, int]] = Counter()
    for order in order_per_flight:
        for group in _chunks(order, boats):
            for pair in combinations(sorted(group), 2):
                meetings[pair] += 1

    cost = sum(count * count for count in meetings.values())

    for step in range(iterations):
        flight = rng.randrange(flights)
        order = order_per_flight[flight]
        # Two positions from different groups — a swap within a group
        # does not change encounters.
        i = rng.randrange(team_count)
        j = rng.randrange(team_count)
        if i // boats == j // boats:
            continue

        group_i = order[(i // boats) * boats : (i // boats + 1) * boats]
        group_j = order[(j // boats) * boats : (j // boats + 1) * boats]
        team_a, team_b = order[i], order[j]

        delta = _swap_delta(meetings, team_a, team_b, group_i, group_j)

        # Equally good moves are accepted: they keep the search moving without
        # worsening the solution. Initially, small worsening is allowed so
        # the search does not get stuck at the first local minimum.
        tolerance = max(0, 4 - step * 4 // max(1, iterations // 2))
        if delta > tolerance:
            continue

        _apply_swap(meetings, team_a, team_b, group_i, group_j)
        order[i], order[j] = team_b, team_a
        cost += delta

    return [list(_chunks(order, boats)) for order in order_per_flight]


def _swap_delta(
    meetings: Counter[tuple[int, int]],
    team_a: int,
    team_b: int,
    group_i: list[int],
    group_j: list[int],
) -> int:
    """Cost change when ``team_a`` and ``team_b`` swap groups.

    Only the pairs that are created or removed are affected — all distinct,
    since the two groups are disjoint and neither ``team_a`` is in ``group_j`` nor ``team_b``
    is in ``group_i``.
    """
    delta = 0
    for other in group_i:
        if other == team_a:
            continue
        delta += _pair_delta(meetings, team_a, other, -1)
        delta += _pair_delta(meetings, team_b, other, +1)
    for other in group_j:
        if other == team_b:
            continue
        delta += _pair_delta(meetings, team_b, other, -1)
        delta += _pair_delta(meetings, team_a, other, +1)
    return delta


def _pair_delta(meetings: Counter[tuple[int, int]], a: int, b: int, change: int) -> int:
    """Pair's contribution to cost change: (m + change)² - m² = 2·m·change + change²."""
    current = meetings[_pair(a, b)]
    return 2 * current * change + change * change


def _apply_swap(
    meetings: Counter[tuple[int, int]],
    team_a: int,
    team_b: int,
    group_i: list[int],
    group_j: list[int],
) -> None:
    for other in group_i:
        if other == team_a:
            continue
        meetings[_pair(team_a, other)] -= 1
        meetings[_pair(team_b, other)] += 1
    for other in group_j:
        if other == team_b:
            continue
        meetings[_pair(team_b, other)] -= 1
        meetings[_pair(team_a, other)] += 1


def _pair(a: int, b: int) -> tuple[int, int]:
    return (a, b) if a < b else (b, a)


def _chunks(items: list[int], size: int):
    for start in range(0, len(items), size):
        yield items[start : start + size]


# ---------------------------------------------------------------------------- Boats


def _assign_boats(
    groups: list[list[list[int]]], team_count: int, boats: int
) -> list[PairingSlot]:
    """Assigns boats to each group so usage is balanced across the matchday."""
    usage = [[0] * (boats + 1) for _ in range(team_count)]
    boat_numbers = list(range(1, boats + 1))
    slots: list[PairingSlot] = []
    races_per_flight = len(groups[0])

    for flight_index, flight_groups in enumerate(groups):
        for race_index, group in enumerate(flight_groups):
            best = min(
                permutations(boat_numbers),
                key=lambda assignment: sum(
                    usage[team][boat] for team, boat in zip(group, assignment, strict=True)
                ),
            )
            for team, boat in zip(group, best, strict=True):
                usage[team][boat] += 1
                slots.append(
                    PairingSlot(
                        flight=flight_index + 1,
                        race_in_flight=race_index + 1,
                        sequence=flight_index * races_per_flight + race_index + 1,
                        team_index=team,
                        boat_number=boat,
                    )
                )
    return slots


# --------------------------------------------------------------------------- Report


def pairing_report(slots: list[PairingSlot], team_count: int, boats: int = 6) -> dict:
    """Quality metrics of a pairing list for human judgment.

    ``boat_spread_max`` is the largest difference between a team's most and least used boats;
    0 or 1 is the achievable optimum. ``opponent_min``/``opponent_max``
    show how often any two teams encounter each other at minimum and maximum.
    """
    boat_usage: dict[int, Counter[int]] = {t: Counter() for t in range(team_count)}
    opponents: Counter[tuple[int, int]] = Counter()
    groups: Counter[tuple[int, ...]] = Counter()

    by_race: dict[int, list[PairingSlot]] = {}
    for slot in slots:
        by_race.setdefault(slot.sequence, []).append(slot)

    for race_slots in by_race.values():
        teams = sorted(s.team_index for s in race_slots)
        groups[tuple(teams)] += 1
        for a, b in combinations(teams, 2):
            opponents[(a, b)] += 1
        for slot in race_slots:
            boat_usage[slot.team_index][slot.boat_number] += 1

    spreads = [
        max(usage[b] for b in range(1, boats + 1)) - min(usage[b] for b in range(1, boats + 1))
        for usage in boat_usage.values()
    ]
    all_pairs = list(combinations(range(team_count), 2))
    counts = [opponents[pair] for pair in all_pairs]
    return {
        "races": len(by_race),
        "boat_spread_max": max(spreads) if spreads else 0,
        "opponent_min": min(counts) if counts else 0,
        "opponent_max": max(counts) if counts else 0,
        "repeated_groups": sum(count - 1 for count in groups.values() if count > 1),
    }
