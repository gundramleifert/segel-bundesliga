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
    render_pdf,
    renderer_available,
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
async def test_the_organizers_font_size_wins_over_the_tools_own():
    """The organizer knows the venue's printer; the tool only knows the configuration."""
    small = await render_pdf(request_for(teams=18, flights=16, settings=PrintSettings(font_size=6)))
    large = await render_pdf(
        request_for(teams=18, flights=16, settings=PrintSettings(font_size=12))
    )

    assert page_count(large) > page_count(small), "a bigger font needs more paper"


def test_no_font_size_is_sent_unless_the_organizer_chose_one():
    """The size a sheet is printed at is the tool's decision, from the rows it has.

    It used to be decided here, which meant a plain command-line run of the tool got a flat
    10pt that does not fit a league matchday on one page. The table moved into
    `DisplayConfig.fontsize`, so every caller gets it — and this sends nothing at all unless
    somebody overruled it.
    """
    display = yaml.safe_load(request_for(teams=18, flights=16).files()["display_cfg.yml"])
    assert "fontsize" not in display

    chosen = request_for(settings=PrintSettings(font_size=11)).files()["display_cfg.yml"]
    assert yaml.safe_load(chosen)["fontsize"] == 11


@needs_jar
async def test_the_tool_sizes_a_league_matchday_onto_one_page():
    """48 rows, nothing configured: the tool's own default has to be the small one."""
    pdf = await render_pdf(
        request_for(teams=18, flights=16, settings=PrintSettings(team_pages=False))
    )

    assert page_count(pdf) == 1


def test_an_installation_without_the_tool_says_so_instead_of_pretending():
    """Story B-3: the screen asks this to leave the download out.

    A deployment may carry no renderer at all — the free test image did until Java was
    added to it — and a button whose only possible answer is 503 is worse than no button.
    """
    assert renderer_available(jar=Path("/does/not/exist.jar")) is False


@needs_jar
def test_an_installation_with_the_tool_offers_it():
    assert renderer_available() is True


def test_a_stored_setting_that_makes_no_sense_still_prints():
    """Read back, never validated: a sheet that will not print is worse than a small one."""
    assert PrintSettings.from_json(None) == PrintSettings()
    assert PrintSettings.from_json("nonsense") == PrintSettings()
    assert PrintSettings.from_json({"font_size": 11}).font_size == 11
    assert PrintSettings.from_json({"font_size": "big"}).font_size is None


@needs_jar
async def test_a_color_the_tool_does_not_know_still_renders():
    """Hex and names both work; anything else prints in the default colour, with a warning.

    A race committee hands this sheet out on the morning of an event, so one boat in the
    wrong colour has to beat no sheet at all. The tool decides that now — it used to be
    decided here, by sending it no colour at all (Story B-3).
    """
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


def test_a_color_is_handed_over_exactly_as_it_is_stored():
    """Hex included — the tool reads it (`PdfCreator.parseHexColor`).

    This used to translate a hex value into an invented upper-case palette entry plus an
    `additional_colors` map, because the tool knew named colors only. It knows hex now, so
    there is nothing to translate: what the organizer picked is what the sheet is printed
    with, and a command-line user can write `#1a2b3c` in their own configuration too.
    """
    request = PdfRequest(
        teams=["A", "B"],
        boats=[BoatSpec(number=1, color="#123456"), BoatSpec(number=2, color="BLACK")],
        slots=slots_for(teams=2, flights=1, boats=2),
        title="Colors",
    )
    files = request.files()

    colors = [boat["color"] for boat in yaml.safe_load(files["schedule_cfg.yml"])["boats"]]
    assert colors == ["#123456", "BLACK"]
    assert "additional_colors" not in yaml.safe_load(files["display_cfg.yml"])
