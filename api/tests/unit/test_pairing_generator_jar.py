"""Generator call against the real Java tool.

Skipped if Java or the JAR is missing — the backend runs without it, just without
the ability to compute new pairing lists.

Deliberately with heavily reduced optimization: this tests the **chain** (write configuration,
start process, read result), not the quality of the optimizer. A run with production
configuration takes many minutes and does not belong in a test suite.
"""

import shutil
from pathlib import Path

import pytest

from app.config import settings
from app.pairing import BoatSpec
from app.pairing.generator import (
    GenerationRequest,
    OptimizerSettings,
    PairingGeneratorError,
    generate_pairing,
    parse_optimizer_log,
)

JAR = Path(settings.pairing_jar)

needs_jar = pytest.mark.skipif(
    not JAR.is_file() or shutil.which(settings.java_binary) is None,
    reason="Java runtime or pairing-list JAR not available",
)

BOAT_COLORS = ["BLACK", "GREEN", "DARKBLUE", "RED", "GRAY", "ORANGE"]
FAST = OptimizerSettings(
    loops=200, match_individuals=30, boat_individuals=40, swap_teams=15,
    swap_boats=20, swap_races=10,
)


def request_for(teams: int, flights: int, boats: int = 6) -> GenerationRequest:
    return GenerationRequest(
        teams=[f"T{i:02d}" for i in range(teams)],
        boats=[BoatSpec(number=n + 1, color=BOAT_COLORS[n % 6]) for n in range(boats)],
        flights=flights,
        optimizer=FAST,
    )


@needs_jar
async def test_a_generated_pairing_covers_the_whole_matchday():
    result = await generate_pairing(request_for(teams=18, flights=6), timeout=180)

    assert result.pairing.flights == 6
    assert result.pairing.races_per_flight == 3
    assert len(result.pairing.slots) == 6 * 18


@needs_jar
async def test_every_team_sails_once_per_flight():
    """The hard constraint — the importer checks it already, here against actual output."""
    result = await generate_pairing(request_for(teams=18, flights=6), timeout=180)

    for flight in range(1, 7):
        teams = [s.team_index for s in result.pairing.slots if s.flight == flight]
        assert sorted(teams) == list(range(18))


@needs_jar
async def test_the_quality_report_is_available_before_publishing():
    """VA-3: The organizer should see the quality before publishing."""
    result = await generate_pairing(request_for(teams=18, flights=6), timeout=180)
    summary = result.summary()

    assert summary["races"] == 18
    assert summary["repeated_groups"] == 0
    for key in ("boat_spread_max", "boat_changes", "saved_shuttles_harbour"):
        assert key in summary


@needs_jar
async def test_our_metrics_agree_with_the_tools_own_numbers():
    """Sanity check: if they differ, one side is measuring incorrectly."""
    result = await generate_pairing(request_for(teams=18, flights=6), timeout=180)
    reported = parse_optimizer_log(result.log)

    assert reported is not None, "The tool did not output shuttle statistics"
    assert reported["boat_changes"] == result.logistics.boat_changes
    assert reported["saved_shuttles_harbour"] == result.logistics.saved_shuttles_harbour
    assert reported["saved_shuttles_at_sea"] == result.logistics.saved_shuttles_at_sea


@needs_jar
async def test_progress_is_reported_while_the_optimizer_runs():
    """VA-3: A minute-long run must not be a black box for the organizer."""
    seen: list = []
    await generate_pairing(request_for(teams=18, flights=6), timeout=180, on_progress=seen.append)

    assert seen, "No progress messages were received"
    assert {p.phase for p in seen} == {"matching", "boats"}
    flights = [p.flight for p in seen if p.phase == "matching" and p.flight]
    assert flights == sorted(flights), "Flights should be reported in ascending order"
    assert max(flights) == 6
    assert all(0.0 <= p.fraction <= 1.0 for p in seen)


@needs_jar
async def test_a_fleet_that_is_not_filled_evenly_still_works():
    """17 teams on 6 boats: the tool pads with empty slots."""
    result = await generate_pairing(request_for(teams=17, flights=4), timeout=180)

    assert len(result.pairing.slots) == 4 * 17
    for flight in range(1, 5):
        teams = [s.team_index for s in result.pairing.slots if s.flight == flight]
        assert sorted(teams) == list(range(17))


@needs_jar
async def test_a_run_that_takes_too_long_is_aborted_with_a_clear_message():
    request = GenerationRequest(
        teams=[f"T{i:02d}" for i in range(18)],
        boats=[BoatSpec(number=n + 1, color=BOAT_COLORS[n]) for n in range(6)],
        flights=16,
        optimizer=OptimizerSettings(),  # Production configuration: takes minutes
    )
    with pytest.raises(PairingGeneratorError, match="stopped"):
        await generate_pairing(request, timeout=3)


async def test_a_missing_jar_is_reported_helpfully():
    with pytest.raises(PairingGeneratorError, match="mvn -DskipTests package"):
        await generate_pairing(request_for(18, 4), jar=Path("/nicht/vorhanden.jar"))


def test_the_optimizer_log_is_parsed():
    log = (
        "costs = 3020.550 .. 3072.550\n"
        "saved Shuttles: in habour: 8 at sea: 30 - boat changes: 3\n"
    )
    assert parse_optimizer_log(log) == {
        "saved_shuttles_harbour": 8,
        "saved_shuttles_at_sea": 30,
        "boat_changes": 3,
    }


def test_an_unparseable_log_yields_none():
    assert parse_optimizer_log("nothing useful") is None
