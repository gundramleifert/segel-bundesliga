"""Printing a pairing list (Story B-3).

The sheet is drawn here, in Python, so its layout is ours to assert: the pages a caller
asks for, the names and numbers on them, the paper's orientation — read back from the
PDF itself, as a printer would get it.
"""

from io import BytesIO

import pytest
from pypdf import PdfReader

from app.pairing import BoatSpec, PairingSlot
from app.pairing.pdf import (
    PairingPdfError,
    PdfRequest,
    PrintSettings,
    boat_color,
    render_pdf,
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


def pages(pdf: bytes) -> list:
    return PdfReader(BytesIO(pdf)).pages


def text(page) -> str:
    return page.extract_text()


def lines(page) -> list[str]:
    """The page's text, a cell or a heading to a line."""
    return [line.strip() for line in text(page).splitlines()]


async def test_every_team_gets_its_own_page():
    """The overview plus one page per club — the sheet a crew takes to the boat."""
    pdf = await render_pdf(request_for(teams=12))

    assert len(pages(pdf)) == 1 + 12
    assert lines(pages(pdf)[6])[1] == "T05", "page 7 is T05's, named under the title"


async def test_the_overview_alone_is_one_page():
    pdf = await render_pdf(request_for(teams=12, settings=PrintSettings(team_pages=False)))

    assert len(pages(pdf)) == 1


async def test_the_overview_carries_the_title_every_boat_and_every_race():
    pdf = await render_pdf(
        request_for(teams=18, flights=16, title="Act 5", settings=PrintSettings(team_pages=False))
    )

    page = text(pages(pdf)[0])
    assert page.startswith("Act 5")
    assert all(f"Boat {n}" in page for n in range(1, 7))
    assert "48" in page.split(), "16 flights of 3 races: the last race is 48"


async def test_a_league_matchday_fits_one_page_at_its_own_size():
    """48 rows, nothing configured: 8pt, the size league matchdays have always printed at.
    The organizer knows the venue's printer — a size they chose overrules it, even when
    that takes more paper."""
    own = await render_pdf(
        request_for(teams=18, flights=16, settings=PrintSettings(team_pages=False))
    )
    organizers = await render_pdf(
        request_for(teams=18, flights=16, settings=PrintSettings(font_size=14, team_pages=False))
    )

    assert len(pages(own)) == 1
    assert len(pages(organizers)) > 1, "a bigger font needs more paper"


@pytest.mark.parametrize(
    ("teams", "flights", "size"),
    [(12, 7, 10), (18, 14, 10), (18, 16, 8), (18, 18, 8), (18, 20, 7), (24, 16, 7), (24, 17, 6)],
)
def test_the_font_size_follows_the_number_of_rows(teams, flights, size):
    """Up to 42 rows 10pt, 56 8pt, 64 7pt, beyond 6pt — read off the archive's sheets."""
    assert request_for(teams=teams, flights=flights).font_size == size
    assert (
        request_for(teams=teams, flights=flights, settings=PrintSettings(font_size=11)).font_size
        == 11
    )


async def test_a_crew_can_print_its_own_sheet_alone():
    """Story B-3: one team's page, not the file with a page for every club in it.

    Each names its own club — the cache must not hand one crew another's page.
    """
    first = await render_pdf(request_for(teams=12, flights=3, team_index=0))
    second = await render_pdf(request_for(teams=12, flights=3, team_index=1))

    assert len(pages(first)) == len(pages(second)) == 1
    assert lines(pages(first)[0])[1] == "T00"
    assert lines(pages(second)[0])[1] == "T01"


async def test_a_team_outside_the_list_is_refused():
    with pytest.raises(PairingPdfError, match="no team 99"):
        await render_pdf(request_for(teams=12, team_index=99))


async def test_landscape_turns_the_paper():
    pdf = await render_pdf(request_for(settings=PrintSettings(landscape=True, team_pages=False)))

    box = pages(pdf)[0].mediabox
    assert box.width > box.height


def test_a_stored_setting_that_makes_no_sense_still_prints():
    """Read back, never validated: a sheet that will not print is worse than a small one."""
    assert PrintSettings.from_json(None) == PrintSettings()
    assert PrintSettings.from_json("nonsense") == PrintSettings()
    assert PrintSettings.from_json({"font_size": 11}).font_size == 11
    assert PrintSettings.from_json({"font_size": "big"}).font_size is None


def test_a_boat_colour_is_a_known_name_or_hex():
    """What the organizer picked is what the sheet is printed with: the Java tool's names,
    German ones included, and the `#rrggbb` (or `#rgb`) a colour picker produces."""
    assert boat_color("BLACK") == (0, 0, 0)
    assert boat_color("darkblue") == boat_color("DUNKELBLAU") == (0, 0, 139)
    assert boat_color("#123456") == (0x12, 0x34, 0x56)
    assert boat_color("abc") == (0xAA, 0xBB, 0xCC)
    assert boat_color("rebeccapurple") is None
    assert boat_color(None) is None


async def test_a_colour_nobody_knows_still_prints():
    """One boat in the wrong colour beats no sheet on the morning of an event."""
    plain = request_for(teams=6, boats=6)
    colors = ["#123456", "#abc", "BLACK", "rebeccapurple", None, "GREEN"]
    request = PdfRequest(
        teams=plain.teams,
        boats=[BoatSpec(number=n + 1, color=color) for n, color in enumerate(colors)],
        slots=plain.slots,
        title=plain.title,
    )

    assert len(pages(await render_pdf(request))) == 1 + 6


async def test_a_fleet_that_is_not_filled_evenly_still_prints():
    """17 teams on 6 boats: one seat per flight stays empty, printed as such, and the
    padding seat gets no page of its own."""
    pdf = await render_pdf(request_for(teams=17, flights=2))

    assert len(pages(pdf)) == 1 + 17
    assert "empty boat" in text(pages(pdf)[0])


async def test_a_named_boat_is_headed_by_its_name():
    plain = request_for(teams=6, boats=6, settings=PrintSettings(team_pages=False))
    request = PdfRequest(
        teams=plain.teams,
        boats=[BoatSpec(number=1, color="RED", name="Rot 1")]
        + [BoatSpec(number=n + 1, color="GRAY") for n in range(1, 6)],
        slots=plain.slots,
        title=plain.title,
        settings=plain.settings,
    )

    header = lines(pages(await render_pdf(request))[0])[1:8]
    assert header == ["Flight", "Race", "Rot 1", "Boat 1", "Boat 2", "Boat 3", "Boat 4"], (
        "the unnamed boats count from 1 again"
    )


async def test_a_second_print_of_the_same_list_comes_from_the_cache(monkeypatch):
    """Eighteen crews downloading one list render it once."""
    from app.pairing import pdf as module

    calls = 0
    real = module._render

    def counting(request):
        nonlocal calls
        calls += 1
        return real(request)

    monkeypatch.setattr(module, "_render", counting)
    first = await render_pdf(request_for(title="Cache probe"))
    second = await render_pdf(request_for(title="Cache probe"))

    assert first == second
    assert calls == 1


async def test_a_different_title_renders_a_different_file():
    """The cache is keyed by what is rendered, and the title is part of that."""
    second = await render_pdf(request_for(title="Act 2"))

    assert text(pages(second)[0]).startswith("Act 2")
