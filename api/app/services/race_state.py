"""The race committee's transitions of one race — Story WL-3.

Until this module existed, ``RaceStatus.RUNNING`` and ``Race.started_at`` were never set:
a race went from ``scheduled`` straight to ``finished`` when a result was saved, and
nothing in the system knew a race was *underway*. Every live feature (B-5's running-race
view, the tracking stories) reads ``started_at``/``finished_at``, so the transitions have
one owner, here, and the result PUT goes through it too.

The rules, each of which has a reason:

* **Races run strictly one at a time.** Starting a race while another is ``running`` is
  refused, and so is entering a result for a *scheduled* race while another one runs —
  otherwise the state machine would be advisory: race 18 finished from the results tab
  while race 17 is on the water. Correcting a ``finished`` race is always allowed; that is
  the protest case and the reason the results tab exists.
* **Recall and abandon clear the race's entries** (code, position, redress) *before* the
  standings are recomputed. Scoring reads ``RaceEntry``, never ``Race.status`` — so this,
  not the status, is what makes "unscored" true.
* **A race that has started once keeps the event frozen.** The configuration freeze counts
  the ``AuditLog`` rows these transitions write, so a general recall of race 1 — which
  puts its status back to ``scheduled`` and clears its entries — does not un-freeze the
  event with the fleet on the water (``services/event_readiness.py``).
* **Signals are two kinds.** The gun, First Substitute and N are transitions and change
  the status. AP, X and S stay hoisted and are *state* on the race (``Race.signal``),
  one at a time, cleared when hauled down; each hoist is an audit row like every other
  action here. AP is allowed only while ``scheduled``, X and S only while ``running``.
* **Every transition is idempotent** where a second tap can happen: starting a running
  race answers with the race, unchanged. A rocking boat is no place for a 409 on a
  double tap.
* **Nothing here commits.** The router commits and then publishes on the live stream
  (``app/live.py``: after the commit, never inside the transaction).
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, Event, EventStatus, Flight, Race, RaceEntry, RaceStatus
from app.models.racing import PreparatoryFlag, RaceSignal
from app.problems import Problem
from app.services.event_readiness import RACE_STARTED_ACTION
from app.services.standings import recompute_event, recompute_series


def require_live(event: Event) -> None:
    """A race can only be run while its event is: the page invents no state of its own."""
    if event.status != EventStatus.LIVE:
        raise Problem(
            409,
            "event-not-live",
            "This event is not being sailed right now, so its races cannot be run.",
            event_id=event.id,
            event_status=event.status,
        )


async def running_race(
    session: AsyncSession, event_id: int, *, other_than: int | None = None
) -> Race | None:
    """The race of this event that is on the water right now, if any."""
    stmt = (
        select(Race)
        .join(Flight, Race.flight_id == Flight.id)
        .where(Flight.event_id == event_id, Race.status == RaceStatus.RUNNING)
    )
    if other_than is not None:
        stmt = stmt.where(Race.id != other_than)
    return (await session.execute(stmt.order_by(Race.sequence).limit(1))).scalar_one_or_none()


def _already_running(other: Race) -> Problem:
    return Problem(
        409,
        "race-already-running",
        f"Race {other.sequence} is still running; races run one at a time.",
        race_id=other.id,
        sequence=other.sequence,
    )


def _not_running(race: Race) -> Problem:
    return Problem(
        409,
        "race-not-running",
        f"Race {race.sequence} is not running.",
        race_id=race.id,
        race_status=race.status,
    )


def _audit(session: AsyncSession, race: Race, action: str, actor: str, **payload: object) -> None:
    session.add(
        AuditLog(entity_type="race", entity_id=race.id, action=action, actor=actor, payload=payload)
    )


async def _clear_entries(session: AsyncSession, race: Race) -> int:
    """Nothing recorded for any boat — what a recall or an abandonment means for scoring."""
    entries = list(
        (await session.execute(select(RaceEntry).where(RaceEntry.race_id == race.id))).scalars()
    )
    for entry in entries:
        entry.code = None
        entry.finish_position = None
        entry.redress_points = None
        entry.points = None
        entry.is_discarded = False
    return len(entries)


async def _recompute(session: AsyncSession, event: Event) -> None:
    await recompute_event(session, event.id)
    if event.series_id is not None:
        await recompute_series(session, event.series_id)


async def start_race(
    session: AsyncSession,
    event: Event,
    race: Race,
    *,
    actor: str,
    preparatory: PreparatoryFlag = PreparatoryFlag.P,
) -> Race:
    """The gun: ``scheduled`` → ``running``. Idempotent for a race already running."""
    require_live(event)
    if race.status == RaceStatus.RUNNING:
        return race
    if race.status == RaceStatus.FINISHED:
        raise Problem(
            409,
            "race-already-finished",
            f"Race {race.sequence} has a result; correct it in the results tab instead.",
            race_id=race.id,
        )
    if race.status == RaceStatus.ABANDONED:
        raise Problem(
            409,
            "race-abandoned",
            f"Race {race.sequence} was abandoned without a resail.",
            race_id=race.id,
        )
    other = await running_race(session, event.id, other_than=race.id)
    if other is not None:
        raise _already_running(other)

    race.status = RaceStatus.RUNNING
    race.started_at = datetime.now(UTC)
    race.finished_at = None
    race.signal = None
    race.preparatory = preparatory
    race.version += 1
    _audit(session, race, RACE_STARTED_ACTION, actor, preparatory=str(preparatory))
    return race


async def recall_race(session: AsyncSession, event: Event, race: Race, *, actor: str) -> Race:
    """First Substitute: back to ``scheduled``, with nothing recorded for any boat."""
    require_live(event)
    if race.status != RaceStatus.RUNNING:
        raise _not_running(race)
    cleared = await _clear_entries(session, race)
    race.status = RaceStatus.SCHEDULED
    race.started_at = None
    race.signal = None
    race.version += 1
    _audit(session, race, "recall", actor, cleared_entries=cleared)
    await _recompute(session, event)
    return race


async def abandon_race(
    session: AsyncSession, event: Event, race: Race, *, actor: str, resail: bool
) -> Race:
    """N: the race is void. With a resail it is ``scheduled`` again, without one it is
    ``abandoned`` and scores nothing — because its entries are cleared, not because of
    the status."""
    require_live(event)
    if race.status == RaceStatus.ABANDONED and not resail:
        return race
    if race.status != RaceStatus.RUNNING:
        raise _not_running(race)
    cleared = await _clear_entries(session, race)
    race.status = RaceStatus.SCHEDULED if resail else RaceStatus.ABANDONED
    race.started_at = None
    race.signal = None
    race.version += 1
    _audit(session, race, "abandon", actor, resail=resail, cleared_entries=cleared)
    await _recompute(session, event)
    return race


async def set_signal(
    session: AsyncSession,
    event: Event,
    race: Race,
    *,
    actor: str,
    signal: RaceSignal | None,
) -> Race:
    """Hoist a displayed signal, or haul it down (``None``)."""
    require_live(event)
    if signal == RaceSignal.AP and race.status != RaceStatus.SCHEDULED:
        raise Problem(
            409,
            "race-not-scheduled",
            f"Race {race.sequence} has started; a postponement needs a race that has not.",
            race_id=race.id,
            race_status=race.status,
        )
    if signal in (RaceSignal.X, RaceSignal.S) and race.status != RaceStatus.RUNNING:
        raise _not_running(race)
    if race.signal == (None if signal is None else str(signal)):
        return race
    race.signal = None if signal is None else str(signal)
    race.version += 1
    _audit(session, race, "signal", actor, signal=race.signal)
    return race


def guard_result_entry(session: AsyncSession, event: Event, race: Race) -> None:
    """What the result PUT must refuse, so this state machine is not advisory.

    Synchronous on purpose so the caller can also use it before it has loaded entries;
    the one query it needs is done by :func:`refuse_if_another_is_running`.
    """
    if race.status == RaceStatus.ABANDONED:
        raise Problem(
            409,
            "race-abandoned",
            f"Race {race.sequence} was abandoned; it has no result.",
            race_id=race.id,
        )


async def refuse_if_another_is_running(session: AsyncSession, event: Event, race: Race) -> None:
    """A *scheduled* race gets no result while another race is on the water.

    A ``running`` race may (that is the finish), and a ``finished`` one may (that is a
    correction, the protest case).
    """
    if race.status != RaceStatus.SCHEDULED:
        return
    other = await running_race(session, event.id, other_than=race.id)
    if other is not None:
        raise _already_running(other)


def finish_race(session: AsyncSession, race: Race, *, actor: str) -> None:
    """Every boat has a result: the race is over. Called by the result PUT."""
    if race.status == RaceStatus.FINISHED:
        return
    race.status = RaceStatus.FINISHED
    race.finished_at = datetime.now(UTC)
    race.signal = None
    _audit(session, race, "finish", actor)
