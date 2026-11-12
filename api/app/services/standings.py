"""Computing the standings — on every read, never stored.

The flow runs in exactly one direction:

    RaceEntry (raw data) -> app.scoring -> points, daily standings, series table

Nothing here is written back (decided 2026-11-12, review 2.1): the stored copies this
module once kept were read by almost nobody and left stale by every write that forgot to
refresh them — an import, a cancellation, a scoring change. 48 races for 18 teams score in
microseconds; a number that is computed cannot be out of date.

A protest decision therefore changes ``code`` or ``finish_position`` on a single row;
everything else follows from that.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.competition import Event, EventStatus, Series
from app.models.org import Team, TeamStatus
from app.models.racing import Flight, Race, RaceEntry
from app.scoring import RaceResult, ScoringConfig, TeamScore, score_event
from app.scoring.low_point import shared_ranks

# Only what is being raced, or has been raced, counts for the series.
SCORED_STATES = (EventStatus.LIVE, EventStatus.FINAL)


async def compute_event(session: AsyncSession, event_id: int) -> list[TeamScore]:
    """Computes the daily standings from raw data — without storing anything."""
    event = await session.get(Event, event_id)
    if event is None:
        raise LookupError(f"Event {event_id} doesn't exist")

    # Deliberately its own get() instead of selectinload on the relationship: if the event
    # is already in the identity map, get() no longer applies the loading options, and
    # accessing event.series would fail as a lazy load in the async context.
    #
    # A standalone event belongs to no series and thus has no scoring parameters — then
    # the defaults apply.
    series = await session.get(Series, event.series_id) if event.series_id is not None else None

    rows = (
        await session.execute(
            select(RaceEntry, Race)
            .join(Race, RaceEntry.race_id == Race.id)
            .join(Flight, Race.flight_id == Flight.id)
            .where(Flight.event_id == event_id)
        )
    ).all()

    starters: dict[int, int] = defaultdict(int)
    for entry, _race in rows:
        starters[entry.race_id] += 1

    by_team: dict[int, list[RaceResult]] = defaultdict(list)
    for entry, race in rows:
        by_team[entry.team_id].append(
            RaceResult(
                race_id=entry.race_id,
                sequence=race.sequence,
                starters=starters[entry.race_id],
                code=entry.code,
                finish_position=entry.finish_position,
                redress_points=entry.redress_points,
            )
        )

    # A team with a matchday penalty and no race yet still has a row: the penalty is its
    # score so far (Story WL-4).
    penalties = {
        team_id: points
        for team_id, points in (
            await session.execute(
                select(Team.id, Team.penalty_points).where(
                    Team.event_id == event_id, Team.penalty_points.is_not(None)
                )
            )
        ).all()
    }
    for team_id in penalties:
        by_team.setdefault(team_id, [])

    config = ScoringConfig.from_json(series.scoring) if series else ScoringConfig()
    return score_event(by_team, config, penalties)


async def race_flights(session: AsyncSession, event_id: int) -> dict[int, int]:
    """Race ID -> the number of the flight it belongs to — read from the race, never
    reconstructed from its sequence number and an assumed flight length."""
    stmt = (
        select(Race.id, Flight.number)
        .join(Flight, Race.flight_id == Flight.id)
        .where(Flight.event_id == event_id)
    )
    return dict((await session.execute(stmt)).all())


def points_by_flight(score: TeamScore, flights: Mapping[int, int]) -> dict[int, float]:
    """A team's points summed per flight, only for flights it has a result in.

    A flight without a key is one this team has not sailed yet — a dash on the standings,
    not a zero. ``flights`` is ``race_flights``' answer for the event.
    """
    sums: dict[int, float] = defaultdict(float)
    for race_id, points in score.points_by_race.items():
        sums[flights[race_id]] += points
    return dict(sums)


@dataclass
class SeriesRow:
    """A row of the series table."""

    team_id: int
    points: float
    rank: int = 0
    # Placement per act; key is the event id.
    event_ranks: dict[int, int] = field(default_factory=dict)
    # Acts the team didn't enter — the substitute score applies there.
    missed_events: set[int] = field(default_factory=set)

    @property
    def events_sailed(self) -> int:
        return len(self.event_ranks) - len(self.missed_events)


async def compute_series(
    session: AsyncSession,
    series_id: int,
    event_scores: Mapping[int, list[TeamScore]] | None = None,
) -> list[SeriesRow]:
    """Series table: the placements of all acts, summed. Lower is better.

    ``event_scores`` carries daily standings the caller already computed, keyed by event
    id, so an act is scored once per change rather than twice; any act missing from it is
    computed here.

    **Whoever misses an act gets field size + 1 there.** The same logic as an unsailed
    race: not entering must never be better than entering and finishing last. A club can
    take part in Act 1 and not in Act 2 — the series still stands.

    ASSUMPTION, still to be confirmed from the league regulations: the series table sums
    the acts' placements. Should a points table (place -> points) apply instead, that
    mapping belongs in ``Series.scoring`` and would be substituted here instead of
    ``rank`` — the model already supports it.
    """
    events = (
        (
            await session.execute(
                select(Event)
                .where(Event.series_id == series_id)
                .order_by(Event.matchday.nulls_last(), Event.starts_on)
            )
        )
        .scalars()
        .all()
    )
    scored_events = [event for event in events if event.status in SCORED_STATES]

    # The series registrations — including clubs that missed an act. The series table
    # operates at this level; the daily standings come from the entries in individual
    # acts and are translated back here via the club.
    registrations = (
        await session.execute(
            select(Team.id, Team.club_id).where(
                Team.series_id == series_id,
                Team.event_id.is_(None),
                Team.status == TeamStatus.ACCEPTED,
            )
        )
    ).all()
    rows_by_team = {team_id: SeriesRow(team_id=team_id, points=0.0) for team_id, _ in registrations}
    team_id_by_club = {club_id: team_id for team_id, club_id in registrations}

    # Entry -> its series row: a club's first team maps onto the club's series
    # registration; its second, third … team (Story VA-13) is a row of its own — the same
    # row in every act, keyed by that team's entry in the earliest *scored* act — and,
    # like everyone, gets field size + 1 for the acts it missed. Only scored acts count:
    # once their first race is sailed they are frozen, so the entry can't be removed from
    # under the stored row, and entering the team in a later act never re-keys the row.
    entries = (
        await session.execute(
            select(Team.id, Team.club_id, Team.number)
            .join(Event, Team.event_id == Event.id)
            .where(Team.series_id == series_id, Event.status.in_(SCORED_STATES))
            .order_by(Event.matchday.nulls_last(), Event.starts_on, Team.id)
        )
    ).all()
    further_teams: dict[tuple[int, int], int] = {}
    for team_id, club_id, number in entries:
        if number > 1:
            further_teams.setdefault((club_id, number), team_id)
    row_by_entry = {
        team_id: (
            further_teams[(club_id, number)]
            if number > 1
            else team_id_by_club.get(club_id, team_id)
        )
        for team_id, club_id, number in entries
    }
    for team_id in further_teams.values():
        rows_by_team[team_id] = SeriesRow(team_id=team_id, points=0.0)

    known = event_scores or {}
    for event in scored_events:
        ranks_by_row: dict[int, int] = {}
        scores = known.get(event.id)
        if scores is None:
            scores = await compute_event(session, event.id)
        for score in scores:
            # Without a series registration, the entry stands on its own — it then shows
            # up below as its own row instead of silently disappearing.
            ranks_by_row[row_by_entry.get(score.team_id, score.team_id)] = score.rank
        if not ranks_by_row:
            continue
        # Whoever is missing gets field size + 1.
        substitute_rank = len(ranks_by_row) + 1

        for team_id, row in rows_by_team.items():
            rank = ranks_by_row.get(team_id)
            if rank is None:
                row.event_ranks[event.id] = substitute_rank
                row.missed_events.add(event.id)
            else:
                row.event_ranks[event.id] = rank

        # An entry without a series registration still shows up — otherwise its results
        # would silently vanish. Under normal operation this can't happen: entering an
        # act requires being registered for its series.
        for team_id, rank in ranks_by_row.items():
            if team_id not in rows_by_team:
                rows_by_team[team_id] = SeriesRow(team_id=team_id, points=0.0)
                rows_by_team[team_id].event_ranks[event.id] = rank

    for row in rows_by_team.values():
        row.points = float(sum(row.event_ranks.values()))

    rows = [row for row in rows_by_team.values() if row.event_ranks]
    return rank_series(rows, [event.id for event in scored_events])


def rank_series(rows: list[SeriesRow], sailed: list[int]) -> list[SeriesRow]:
    """Sorts and ranks a series table. ``sailed`` is the acts' ids in sailing order
    (matchday, then date). Ties: the better result in the most recent act decides, then
    the one before — never the act's id (review 2.5); what nothing breaks is shared."""
    latest_first = list(reversed(sailed))

    def key(row: SeriesRow) -> tuple:
        return (row.points, tuple(row.event_ranks.get(event_id, 999) for event_id in latest_first))

    rows.sort(key=key)
    for row, rank in zip(rows, shared_ranks([key(row) for row in rows]), strict=True):
        row.rank = rank
    return rows
