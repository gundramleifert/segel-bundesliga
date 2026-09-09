"""Computing and storing the standings.

The flow runs in exactly one direction:

    RaceEntry (raw data) -> app.scoring -> RaceEntry.points, EventStanding, SeriesStanding

The stored points and tables are **derived**. They're rewritten after every change to the
raw data and can be fully rebuilt at any time. Nothing outside this module may write them
— otherwise it would no longer be clear which number is authoritative.

A protest decision therefore changes ``code`` or ``finish_position`` on a single row;
everything else follows from that.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.competition import Event, EventStatus, Series
from app.models.org import Team, TeamStatus
from app.models.racing import Flight, Race, RaceEntry
from app.models.standings import EventStanding, SeriesStanding
from app.scoring import RaceResult, ScoringConfig, TeamScore, score_event

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
    series = (
        await session.get(Series, event.series_id) if event.series_id is not None else None
    )

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

    config = ScoringConfig.from_json(series.scoring) if series else ScoringConfig()
    return score_event(by_team, config)


async def recompute_event(session: AsyncSession, event_id: int) -> list[TeamScore]:
    """Computes the daily standings and writes points and table forward.

    Call after every result change. Doesn't commit itself — the caller decides when the
    change takes effect.
    """
    scores = await compute_event(session, event_id)
    now = datetime.now(UTC)

    entries = (
        await session.execute(
            select(RaceEntry)
            .join(Race, RaceEntry.race_id == Race.id)
            .join(Flight, Race.flight_id == Flight.id)
            .where(Flight.event_id == event_id)
        )
    ).scalars()

    points_by_team_race = {
        (score.team_id, race_id): points
        for score in scores
        for race_id, points in score.points_by_race.items()
    }
    discarded = {
        (score.team_id, race_id) for score in scores for race_id in score.discarded_races
    }

    for entry in entries:
        key = (entry.team_id, entry.race_id)
        entry.points = points_by_team_race.get(key)
        entry.is_discarded = key in discarded

    await session.execute(delete(EventStanding).where(EventStanding.event_id == event_id))
    session.add_all(
        EventStanding(
            event_id=event_id,
            team_id=score.team_id,
            rank=score.rank,
            total_points=score.total,
            net_points=score.net,
            races_scored=len(score.points_by_race),
            computed_at=now,
        )
        for score in scores
    )
    await session.flush()
    return scores


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


async def compute_series(session: AsyncSession, series_id: int) -> list[SeriesRow]:
    """Series table: the placements of all acts, summed. Lower is better.

    **Whoever misses an act gets field size + 1 there.** The same logic as an unsailed
    race: not entering must never be better than entering and finishing last. A club can
    take part in Act 1 and not in Act 2 — the series still stands.

    ASSUMPTION, still to be confirmed from the league regulations: the series table sums
    the acts' placements. Should a points table (place -> points) apply instead, that
    mapping belongs in ``Series.scoring`` and would be substituted here instead of
    ``rank`` — the model already supports it.
    """
    events = (
        await session.execute(
            select(Event)
            .where(Event.series_id == series_id)
            .order_by(Event.matchday.nulls_last(), Event.starts_on)
        )
    ).scalars().all()
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

    # Entry -> club, to map the daily standings onto the series registration.
    club_id_by_entry = dict(
        (
            await session.execute(
                select(Team.id, Team.club_id).where(
                    Team.series_id == series_id, Team.event_id.is_not(None)
                )
            )
        ).all()
    )

    for event in scored_events:
        ranks_by_row: dict[int, int] = {}
        for score in await compute_event(session, event.id):
            club_id = club_id_by_entry.get(score.team_id)
            # Without a series registration, the entry stands on its own — it then shows
            # up below as its own row instead of silently disappearing.
            row_id = team_id_by_club.get(club_id, score.team_id) if club_id else score.team_id
            ranks_by_row[row_id] = score.rank
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
    # Ties: the better result in the most recent act decides.
    rows.sort(key=lambda row: (row.points, _latest_rank(row)))
    for position, row in enumerate(rows, start=1):
        row.rank = position
    return rows


async def recompute_series(session: AsyncSession, series_id: int) -> list[SeriesRow]:
    """Rebuilds the series table and writes it forward."""
    events = (
        await session.execute(
            select(Event.id, Event.status).where(Event.series_id == series_id)
        )
    ).all()
    for event_id, status in events:
        if status in SCORED_STATES:
            await recompute_event(session, event_id)

    rows = await compute_series(session, series_id)

    now = datetime.now(UTC)
    await session.execute(
        delete(SeriesStanding).where(SeriesStanding.series_id == series_id)
    )
    session.add_all(
        SeriesStanding(
            series_id=series_id,
            team_id=row.team_id,
            rank=row.rank,
            points=row.points,
            events_sailed=row.events_sailed,
            events_missed=len(row.missed_events),
            computed_at=now,
        )
        for row in rows
    )
    await session.flush()
    return rows


def _latest_rank(row: SeriesRow) -> int:
    if not row.event_ranks:
        return 999
    return row.event_ranks[max(row.event_ranks)]


# The public API's read paths recompute on every request: 48 races for 18 teams is a
# matter of microseconds, so a forgotten recompute can never lead to wrong numbers on the
# website. The stored tables exist for sorting, filtering and export.
event_standings = compute_event
series_standings = compute_series
