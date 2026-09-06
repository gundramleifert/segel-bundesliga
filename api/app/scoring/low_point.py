"""Low-Point scoring per World Sailing RRS Appendix A.

Points are never stored, but always calculated from raw data (``RaceEntry.code`` and
``finish_position``). A protest decision thus changes one row, not derived tables.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.models.racing import ResultCode

# Codes treated as "not scored": points = starters + 1 (RRS A9/A10).
DID_NOT_FINISH_CODES = frozenset(
    {
        ResultCode.DNS,
        ResultCode.DNF,
        ResultCode.OCS,
        ResultCode.DSQ,
        ResultCode.DNE,
        ResultCode.RET,
    }
)

# Non-discardable (RRS A2.1): a DNE remains even when discards apply.
NON_DISCARDABLE_CODES = frozenset({ResultCode.DNE})


@dataclass(frozen=True)
class ScoringConfig:
    """Scoring parameters of a league. Comes from ``League.scoring``, not from code."""

    # After how many races sailed, each discard applies, in ascending order.
    # Empty = no discards (the normal case for a Bundesliga matchday).
    discard_after: tuple[int, ...] = ()
    # Percentage penalty (ZFP/SCP) based on starters.
    penalty_percent: int = 20

    @classmethod
    def from_json(cls, data: dict[str, Any] | None) -> ScoringConfig:
        data = data or {}
        return cls(
            discard_after=tuple(data.get("discard_after", ())),
            penalty_percent=int(data.get("penalty_percent", 20)),
        )


@dataclass(frozen=True)
class RaceResult:
    """A team's result in a race, enriched with the starter count."""

    race_id: int
    sequence: int
    starters: int
    code: str | None = None
    finish_position: int | None = None
    redress_points: float | None = None

    @property
    def scored(self) -> bool:
        """Whether the race is scored for this team (result is present)."""
        return self.code is not None


@dataclass
class TeamScore:
    team_id: int
    total: float
    net: float
    points_by_race: dict[int, float] = field(default_factory=dict)
    discarded_races: set[int] = field(default_factory=set)
    rank: int = 0


def race_points(result: RaceResult, config: ScoringConfig) -> float:
    """A team's points in a race. Lower is better."""
    if result.code is None:
        raise ValueError(f"Race {result.race_id} has no result for this team")

    dnf_points = float(result.starters + 1)

    if result.code == ResultCode.RDG:
        if result.redress_points is None:
            raise ValueError(f"RDG in race {result.race_id} with no awarded points")
        return float(result.redress_points)

    if result.code in DID_NOT_FINISH_CODES:
        return dnf_points

    if result.finish_position is None:
        raise ValueError(f"Race {result.race_id}: code {result.code} with no finish position")

    base = float(result.finish_position)

    if result.code in (ResultCode.ZFP, ResultCode.SCP):
        # RRS 44.3(c): penalty of N% of starters, commercial rounding, at least 1 point.
        # The result is never worse than DNF.
        penalty = max(1, round(result.starters * config.penalty_percent / 100))
        return min(base + penalty, dnf_points)

    return base


def _tiebreak_key(score: TeamScore, results: list[RaceResult], config: ScoringConfig) -> tuple:
    """RRS A8: on a tie, the better series decides, finally the last race.

    A8.1 compares the count of first, second, third … places; A8.2 decides by
    the result of the last race.
    """
    counted = [r for r in results if r.race_id not in score.discarded_races and r.scored]
    points = sorted(score.points_by_race[r.race_id] for r in counted)
    last = max(counted, key=lambda r: r.sequence, default=None)
    last_points = score.points_by_race[last.race_id] if last else 0.0
    return (score.net, points, last_points)


def score_event(
    results_by_team: dict[int, list[RaceResult]],
    config: ScoringConfig | None = None,
) -> list[TeamScore]:
    """Daily scoring: points per team, discards applied, sorted by placement."""
    config = config or ScoringConfig()
    scores: list[TeamScore] = []

    for team_id, results in results_by_team.items():
        scored_results = [r for r in results if r.scored]
        points = {r.race_id: race_points(r, config) for r in scored_results}
        total = sum(points.values())

        discards = _discard_count(len(scored_results), config)
        discarded = _pick_discards(scored_results, points, discards)
        net = total - sum(points[rid] for rid in discarded)

        scores.append(
            TeamScore(
                team_id=team_id,
                total=total,
                net=net,
                points_by_race=points,
                discarded_races=discarded,
            )
        )

    scores.sort(key=lambda s: _tiebreak_key(s, results_by_team[s.team_id], config))
    for rank, score in enumerate(scores, start=1):
        score.rank = rank
    return scores


def _discard_count(races_sailed: int, config: ScoringConfig) -> int:
    return sum(1 for threshold in config.discard_after if races_sailed >= threshold)


def _pick_discards(
    results: list[RaceResult], points: dict[int, float], count: int
) -> set[int]:
    """Discards the worst results — non-discardable codes excluded."""
    if count <= 0:
        return set()
    candidates = [r for r in results if r.code not in NON_DISCARDABLE_CODES]
    candidates.sort(key=lambda r: points[r.race_id], reverse=True)
    return {r.race_id for r in candidates[:count]}
