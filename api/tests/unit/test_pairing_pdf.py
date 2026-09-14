"""Printing a pairing list, against the real Java tool (Story B-3).

Skipped where Java or the JAR is missing — the backend runs without both, just without
the ability to hand out a printable list.

What is worth testing here is the **chain**: our draw written in the shape the tool reads,
the tool started, a PDF read back. The layout inside the PDF belongs to the tool and is not
ours to assert; the number of pages is, because one page per team is what the caller asks
for.
"""

import re
import shutil
from pathlib import Path

import pytest
import yaml

from app.config import settings
from app.pairing import BoatSpec, PairingSlot
from app.pairing.pdf import (
    PairingPdfError,
    PdfRequest,
    PrintSettings,
    default_font_size,
    render_pdf,
)

JAR = Path(settings.pairing_jar)

needs_jar = pytest.mark.skipif(
    not JAR.is_file() or shutil.which(settings.java_binary) is None,
    reason="Java runtime or pairing-list JAR not available",
)

COLORS = ["BLACK", "GREEN", "DARKBLUE", "RED", "GRAY", "ORANGE"]


def slots_for(teams: int, flights: int, boats: int = 6) -> list[PairingSlot]:
    """A valid draw without the optimizer: every team sails once per flight.

    Deliberately not ``build_pairing`` — that one refuses a fleet the boats do not divide
    evenly, and an uneven fleet is exactly one of the cases this file has to cover.
    """
    races_per_flight = -(-teams // boats)
    slots: list[PairingSlot] = []
    sequence = 0
    for flight in range(1, flights + 1):
        order = [(index + flight) % teams for index in range(teams)]
        for race in range(races_per_flight):
            sequence += 1
            for boat in range(boats):
                seat = race * boats + boat
                if seat < teams:
                    slots.append(
                        PairingSlot(
                            flight=flight,
                            race_in_flight=race + 1,
                            sequence=sequence,
                            team_index=order[seat],
                            boat_number=boat + 1,
                        )
                    )
    return slots


def request_for(teams: int = 12, flights: int = 3, boats: int = 6, **kwargs) -> PdfRequest:
    return PdfRequest(
        teams=[f"T{i:02d}" for i in range(teams)],
        boats=[BoatSpec(number=n + 1, color=COLORS[n % len(COLORS)]) for n in range(boats)],
        slots=slots_for(teams, flights, boats),
        title=kwargs.pop("title", "Pairing List — Test"),
        **kwargs,
    )


def page_count(pdf: bytes) -> int:
    """Counts `/Type /Page` objects — enough for a file this tool wrote itself."""
    return len(re.findall(rb"/Type\s*/Page[^s]", pdf))


@needs_jar
async def test_a_pairing_list_renders_as_a_pdf():
    pdf = await render_pdf(request_for())

    assert pdf.startswith(b"%PDF")


@needs_jar
async def test_every_team_gets_its_own_page():
    """The overview plus one page per club — the sheet a crew takes to the boat."""
    pdf = await render_pdf(request_for(teams=12))

    assert page_count(pdf) == 1 + 12


@needs_jar
async def test_the_overview_alone_is_one_page():
    pdf = await render_pdf(request_for(teams=12, settings=PrintSettings(team_pages=False)))

    assert page_count(pdf) == 1


@needs_jar
async def test_a_crew_can_print_its_own_sheet_alone():
    """Story B-3: one team's page, not the file with a page for every club in it."""
    pdf = await render_pdf(request_for(teams=12, flights=3, team_index=5))

    assert page_count(pdf) == 1


@needs_jar
async def test_two_teams_get_different_sheets():
    """Each marks its own races — the cache must not hand one crew another's page."""
    first = await render_pdf(request_for(team_index=0))
    second = await render_pdf(request_for(team_index=1))

    assert first != second


async def test_a_team_outside_the_list_is_refused():
    with pytest.raises(PairingPdfError, match="no team 99"):
        await render_pdf(request_for(teams=12, team_index=99))


@needs_jar
async def test_the_organizers_font_size_wins_over_the_default():
    """The organizer knows the venue's printer; the default only knows the configuration."""
    request = request_for(teams=18, flights=16, settings=PrintSettings(font_size=12))
    assert request.font_size == 12, "the derived size would be 8 for 48 rows"

    small = await render_pdf(
        request_for(teams=18, flights=16, settings=PrintSettings(font_size=6))
    )
    large = await render_pdf(request)

    assert page_count(large) > page_count(small), "a bigger font needs more paper"


def test_the_default_font_size_follows_the_sheets_that_were_printed():
    """The table is read off 43 real events — these are their numbers, not invented ones."""
    assert default_font_size(16 * 3) == 8, "a league matchday: 48 rows"
    assert default_font_size(12 * 3) == 10, "a short cup: 36 rows"
    assert default_font_size(16 * 4) == 7, "24 teams on 6 boats: 64 rows"
    assert default_font_size(18 * 4) == 6, "the largest fleets: 72 rows"


def test_an_event_without_print_settings_uses_the_derived_size():
    assert request_for(teams=18, flights=16).font_size == 8
    assert request_for(teams=8, flights=12, boats=4).font_size == 10


def test_a_stored_setting_that_makes_no_sense_still_prints():
    """Read back, never validated: a sheet that will not print is worse than a small one."""
    assert PrintSettings.from_json(None) == PrintSettings()
    assert PrintSettings.from_json("nonsense") == PrintSettings()
    assert PrintSettings.from_json({"font_size": 11}).font_size == 11
    assert PrintSettings.from_json({"font_size": "big"}).font_size is None


@needs_jar
async def test_a_color_the_tool_does_not_know_still_renders():
    """Our color picker yields hex values; the tool knows names only (Story VA-6)."""
    request = request_for(teams=6, boats=6)
    unknown = ["#123456", "#abc", "BLACK", "rebeccapurple", None, "GREEN"]
    request = PdfRequest(
        teams=request.teams,
        boats=[BoatSpec(number=n + 1, color=color) for n, color in enumerate(unknown)],
        slots=request.slots,
        title=request.title,
    )

    pdf = await render_pdf(request)

    assert pdf.startswith(b"%PDF")


@needs_jar
async def test_a_fleet_that_is_not_filled_evenly_still_prints():
    """17 teams on 6 boats: one seat per flight stays empty and must not shift the rest."""
    pdf = await render_pdf(request_for(teams=17, flights=2))

    assert page_count(pdf) == 1 + 17


@needs_jar
async def test_the_same_list_renders_to_the_same_bytes():
    """A printed list must be reproducible — two prints of one draw cannot disagree."""
    first = await render_pdf(request_for())
    second = await render_pdf(request_for())

    assert first == second


@needs_jar
async def test_a_different_title_renders_a_different_file():
    """The cache is keyed by the content it renders, and the title is part of that."""
    first = await render_pdf(request_for(title="Act 1"))
    second = await render_pdf(request_for(title="Act 2"))

    assert first != second


async def test_a_missing_jar_is_reported_helpfully():
    # A title of its own, because the cache would otherwise answer from a rendering an
    # earlier test in this file already paid for — and never reach the missing JAR.
    with pytest.raises(PairingPdfError, match="mvn -DskipTests package"):
        await render_pdf(request_for(title="No JAR here"), jar=Path("/does/not/exist.jar"))


def test_the_draw_is_written_as_the_tool_reads_it():
    """0-based team indices, position in the string is the boat — no tool needed for this."""
    files = request_for(teams=12, flights=2).files()

    pairing = yaml.safe_load(files["pairing_list.yml"])
    assert len(pairing["flights"]) == 2
    for flight in pairing["flights"]:
        seats = [int(n) for race in flight["races"] for n in race.split(",")]
        assert sorted(seats) == list(range(12)), "each team sails once per flight"

    config = yaml.safe_load(files["schedule_cfg.yml"])
    assert config["flights"] == 2
    assert config["teams"] == [f"T{i:02d}" for i in range(12)]
    assert [boat["color"] for boat in config["boats"]] == COLORS


def test_empty_seats_are_written_as_padding_indices():
    """The tool pads the team list itself; the draw has to name those seats."""
    request = PdfRequest(
        teams=[f"T{i}" for i in range(4)],
        boats=[BoatSpec(number=n + 1, color=None) for n in range(6)],
        slots=slots_for(teams=4, flights=1, boats=6),
        title="Short fleet",
    )

    flights = yaml.safe_load(request.files()["pairing_list.yml"])["flights"]

    assert flights[0]["races"] == ["1,2,3,0,4,5"], "seats 4 and 5 are the empty ones"


def test_a_hex_color_becomes_a_color_the_tool_can_resolve():
    request = PdfRequest(
        teams=["A", "B"],
        boats=[BoatSpec(number=1, color="#123456"), BoatSpec(number=2, color="BLACK")],
        slots=slots_for(teams=2, flights=1, boats=2),
        title="Colors",
    )
    files = request.files()

    colors = [boat["color"] for boat in yaml.safe_load(files["schedule_cfg.yml"])["boats"]]
    additional = yaml.safe_load(files["display_cfg.yml"])["additional_colors"]

    assert colors[1] == "BLACK", "a name the tool knows is passed through"
    assert additional[colors[0]] == [0x12, 0x34, 0x56]
