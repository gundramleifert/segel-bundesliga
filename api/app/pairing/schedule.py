"""Pairing lists: which team sails in which race on which boat — the slot, and the
quality report a person judges a list by.

The lists themselves come from the Java tool, run in its own repository, through the
catalog (``app.pairing.catalog``). A Python generator lived here as a fallback until
2026-11-11; it balanced boats and opponents but not the boat changes between flights
(about 27 where the tool's lists have none, ``docs/findings.md`` § 2), so it was never a
replacement — and with the catalog it had no caller left.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from itertools import combinations


@dataclass(frozen=True)
class PairingSlot:
    flight: int  # 1-based
    race_in_flight: int  # 1-based
    sequence: int  # sequential race number across the matchday
    team_index: int  # index in the provided team list
    boat_number: int  # 1-based


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
