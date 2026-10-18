"""Recording a race's raw result — Story WL-2.

``code``/``finish_position``/``redress_points`` are the authoritative raw data
(``docs/concepts.md``, "Points are derived, not entered"); this module writes them and
then recomputes the standings, so ``points``/``is_discarded`` and the published tables
never lag behind a correction.

Split in two on purpose: :func:`resolve_results` is the validation — codes, required
positions and redress, no two boats in one place — and touches no database, so it is
unit-tested on its own (``tests/unit/test_results.py``). :func:`record_results` is the
operation around it: the race state machine's refusals, the audit of an overwrite, the
version, the race finishing itself, the recompute. Like ``race_state``, **nothing here
commits** — the caller commits and then publishes on the live stream (``app/live.py``).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import NamedTuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Event
from app.models.racing import Boat, Race, RaceEntry, ResultCode
from app.problems import Problem
from app.services import race_state
from app.services.audit import EntityType, audit
from app.services.standings import recompute_after_change

# Codes for which the underlying finish order (``finish_position``) is real and thus
# participates in the "no two boats in the same place" check — RDG and the
# not-a-finish codes (DNS, DNF, ...) carry no position at all.
POSITION_CODES = (ResultCode.FINISHED, ResultCode.ZFP, ResultCode.SCP)


class SubmittedResult(NamedTuple):
    """One boat's result as the race officer (or an import) submits it.

    ``code`` is the raw string so an unknown one is refused with a typed problem rather
    than failing earlier; ``None`` means "nothing recorded for this boat".
    """

    boat_number: int
    code: str | None = None
    finish_position: int | None = None
    redress_points: float | None = None


class RawResult(NamedTuple):
    """A boat's raw result as stored on its ``RaceEntry``."""

    code: ResultCode | None
    finish_position: int | None
    redress_points: float | None


NO_RESULT = RawResult(None, None, None)

# Raw results keyed by boat number.
ResultsByBoat = dict[int, RawResult]


class RecordedResults(NamedTuple):
    """What :func:`record_results` did, for the response."""

    overwrote_existing: bool


def resolve_results(
    current: Mapping[int, RawResult], submitted: Sequence[SubmittedResult], race_id: int
) -> ResultsByBoat:
    """The raw result each submitted boat is to get, or the first reason it cannot.

    ``current`` is every boat of the race with what it has now: a boat not submitted keeps
    its result, and still counts in the duplicate-position check — that check runs over
    the *resulting* state of the race, so fixing one entry after a protest cannot put it
    on a place another boat already holds.
    """
    updates: ResultsByBoat = {}
    for result in submitted:
        if result.boat_number not in current:
            raise Problem(
                422,
                "race-result-unknown-boat",
                f"Boat {result.boat_number} has no entry in race {race_id}.",
                boat_number=result.boat_number,
            )
        if result.code is None:
            # "Nothing recorded for this boat" — not a code, and deliberately not an
            # error. Position and redress go with it: a boat with no result must not keep
            # the place it used to have (Story WL-2).
            updates[result.boat_number] = NO_RESULT
            continue

        try:
            code = ResultCode(result.code)
        except ValueError as exc:
            raise Problem(
                422,
                "race-result-invalid-code",
                f"'{result.code}' is not a valid result code.",
                boat_number=result.boat_number,
            ) from exc

        if code in POSITION_CODES and result.finish_position is None:
            raise Problem(
                422,
                "race-result-position-required",
                f"Boat {result.boat_number}: a finish position is required for {code}.",
                boat_number=result.boat_number,
            )
        if code == ResultCode.RDG and result.redress_points is None:
            raise Problem(
                422,
                "race-result-redress-required",
                f"Boat {result.boat_number}: redress points are required for RDG.",
                boat_number=result.boat_number,
            )

        updates[result.boat_number] = RawResult(
            code,
            result.finish_position if code in POSITION_CODES else None,
            result.redress_points if code == ResultCode.RDG else None,
        )

    position_owners: dict[int, int] = {}
    for boat_number, now in current.items():
        code, position, _ = updates.get(boat_number, now)
        if code not in POSITION_CODES or position is None:
            continue
        if position in position_owners:
            raise Problem(
                422,
                "race-result-duplicate-position",
                f"Finish position {position} is claimed by more than one boat.",
                finish_position=position,
            )
        position_owners[position] = boat_number
    return updates


def _raw(entry: RaceEntry) -> RawResult:
    return RawResult(
        ResultCode(entry.code) if entry.code is not None else None,
        entry.finish_position,
        entry.redress_points,
    )


async def record_results(
    session: AsyncSession,
    event: Event,
    race: Race,
    submitted: Sequence[SubmittedResult],
    *,
    actor: str,
    seen_version: int | None = None,
) -> RecordedResults:
    """Write the submitted boats' raw results into ``race`` and recompute the standings.

    A boat not submitted keeps its current result. Two refusals come from the race state
    machine (Story WL-3, ``race_state``): an ``abandoned`` race takes no result, and a
    ``scheduled`` race takes none while another race is running. A ``finished`` race is
    always correctable — the protest case.

    ``seen_version`` is the race version the submitter last loaded. If someone changed the
    race since, the later entry still wins — a rocking boat is no place for a hard
    conflict — but the state about to be discarded is written to ``AuditLog`` first (WL-2:
    "the overridden status is not lost but logged").
    """
    race_state.guard_result_entry(race)
    await race_state.refuse_if_another_is_running(session, event, race)

    entry_rows = (
        await session.execute(
            select(RaceEntry, Boat.number)
            .join(Boat, RaceEntry.boat_id == Boat.id)
            .where(RaceEntry.race_id == race.id)
        )
    ).all()
    entry_by_boat: dict[int, RaceEntry] = {number: entry for entry, number in entry_rows}

    updates = resolve_results(
        {number: _raw(entry) for number, entry in entry_by_boat.items()}, submitted, race.id
    )

    overwrote_existing = seen_version is not None and seen_version != race.version
    if overwrote_existing:
        audit(
            session,
            EntityType.RACE,
            race.id,
            "result_overwrite",
            actor,
            submitted_on_version=seen_version,
            actual_version=race.version,
            discarded_entries={
                str(boat_number): {
                    "code": entry_by_boat[boat_number].code,
                    "finish_position": entry_by_boat[boat_number].finish_position,
                    "redress_points": entry_by_boat[boat_number].redress_points,
                }
                for boat_number in updates
            },
        )

    for boat_number, (code, position, redress_points) in updates.items():
        entry = entry_by_boat[boat_number]
        entry.code = code
        entry.finish_position = position
        entry.redress_points = redress_points

    race.version += 1
    if all(entry.code is not None for entry in entry_by_boat.values()):
        # Every boat has a result: the race is over. The fifth transition of Story WL-3,
        # reached through the result rather than a button of its own.
        race_state.finish_race(session, race, actor=actor)

    await recompute_after_change(session, event)
    return RecordedResults(overwrote_existing=overwrote_existing)
