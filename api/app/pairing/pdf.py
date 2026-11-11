"""Printing a pairing list (Story B-3).

The list is read on a phone, but it is also **printed**: pinned up in the clubhouse, handed
to crews at registration, carried to the boat. The sheet keeps the layout the Java tool
(``reference/PairingList``, ``PdfCreator``) has printed for years — title, a grid of a
narrow Flight and Race column and one column per boat headed in its colour, a thin gap
between flights, a crew's own seat dark — drawn here with reportlab, so printing needs
nothing outside this process (decided 2026-11-11).

A rendering takes a fraction of a second, but eighteen crews download the same list on
the same morning: a **cache keyed by the rendered content** answers all but the first.
Because the key *is* the content, nothing has to be invalidated when a list is redrawn —
a different draw is simply a different key.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
from collections import OrderedDict
from dataclasses import dataclass, field
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Table, TableStyle

from app.pairing.importer import BoatSpec
from app.pairing.logistics import to_flights
from app.pairing.schedule import PairingSlot

# How many rendered lists are kept. A matchday is one entry per title, and only the events
# people are currently looking at matter — a handful covers a race weekend.
CACHE_SIZE = 8

FONT = "Helvetica"
# Margins as the Java tool printed them: iText's 36pt at the sides, 10pt top and bottom.
SIDE_MARGIN = 36
TOP_MARGIN = 10
# The Flight and Race columns carry a number, not a club name — half a boat column.
NUMBER_COLUMN = 0.5
EMPTY_SEAT = "empty boat"
OWN_SEAT = colors.Color(100 / 255, 100 / 255, 100 / 255)

# The names the Java tool knows (`PdfCreator.defaultColorMap`), German ones included —
# what organizers have typed for years — as RGB.
_NAMED_COLORS: dict[str, tuple[int, int, int]] = {
    "BLACK": (0, 0, 0),
    "DARK_GRAY": (64, 64, 64),
    "GRAY": (102, 102, 102),
    "LIGHT_GRAY": (192, 192, 192),
    "WHITE": (255, 255, 255),
    "BLUE": (0, 0, 255),
    "CYAN": (0, 255, 255),
    "GREEN": (106, 168, 79),
    "ORANGE": (255, 153, 0),
    "PINK": (195, 44, 195),
    "RED": (255, 0, 0),
    "YELLOW": (255, 255, 0),
    "HELLBLAU": (0, 167, 226),
    "DUNKELBLAU": (0, 0, 139),
}
for _alias, _name in {
    "LIGHTBLUE": "HELLBLAU",
    "DARKBLUE": "DUNKELBLAU",
    "GELB": "YELLOW",
    "LILA": "PINK",
    "GRUEN": "GREEN",
    "GREY": "GRAY",
    "GRAU": "GRAY",
    "SCHWARZ": "BLACK",
    "WEISS": "WHITE",
    "BLAU": "BLUE",
    "ROT": "RED",
}.items():
    _NAMED_COLORS[_alias] = _NAMED_COLORS[_name]

_HEX = re.compile(r"#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6})")


class PairingPdfError(RuntimeError):
    """The pairing list could not be rendered."""


def boat_color(value: str | None) -> tuple[int, int, int] | None:
    """A boat's colour as RGB: a name the Java tool knew, or the hex a colour picker
    produced (``#1a2b3c``, short ``#abc``, with or without ``#``). ``None`` for anything
    else — the sheet then prints that heading white rather than not at all."""
    if not value:
        return None
    named = _NAMED_COLORS.get(value.strip().upper())
    if named is not None:
        return named
    match = _HEX.fullmatch(value.strip())
    if match is None:
        return None
    digits = match.group(1)
    if len(digits) == 3:
        digits = "".join(digit * 2 for digit in digits)
    return int(digits[0:2], 16), int(digits[2:4], 16), int(digits[4:6], 16)


@dataclass(frozen=True)
class PrintSettings:
    """What the organizer decides about the printed sheet.

    Every field may stay unset, and unset is the normal case: the organizer of a league
    matchday has nothing to say about font size, and the default derived from the
    configuration is what the same matchday has been printed at for years. Someone running
    a twenty-flight cup on one page, or handing the sheet to a venue with a poor printer,
    does have something to say — and this is where they say it.
    """

    #: ``None`` means: from the number of rows the sheet has (`PdfRequest.font_size`).
    font_size: int | None = None
    #: A wide fleet reads better across the page. One event in the whole archive does this.
    landscape: bool = False
    #: One page per team after the overview. Off for the overview alone.
    team_pages: bool = True

    @classmethod
    def from_json(cls, data: object) -> PrintSettings:
        """Reads what is stored on the event, tolerating anything else.

        A stored setting is not input to be validated on the way out: if the column holds
        something unexpected — hand-edited, or written by an older version — the sheet
        still has to print, with defaults, rather than 500.
        """
        if not isinstance(data, dict):
            return cls()
        font_size = data.get("font_size")
        return cls(
            font_size=int(font_size) if isinstance(font_size, int | float) else None,
            landscape=bool(data.get("landscape", False)),
            team_pages=bool(data.get("team_pages", True)),
        )

    def as_json(self) -> dict:
        return {
            "font_size": self.font_size,
            "landscape": self.landscape,
            "team_pages": self.team_pages,
        }


@dataclass(frozen=True)
class PdfRequest:
    """Everything the printed sheet is made of.

    Deliberately not an ``Event``: the renderer knows nothing about the database, which is
    what makes it testable without one — and what lets a list that was never published be
    printed for a check.
    """

    teams: list[str]
    boats: list[BoatSpec]
    slots: list[PairingSlot]
    title: str
    settings: PrintSettings = field(default_factory=PrintSettings)
    #: Only this team's page — the sheet one crew takes to its boat — instead of the
    #: overview plus a page for everybody. An index into ``teams``.
    team_index: int | None = None

    @property
    def font_size(self) -> int:
        """The organizer's choice, or one from the sheet's rows (``flights × races``): up
        to 42 rows 10pt, up to 56 8pt, up to 64 7pt, beyond that 6pt — the table the Java
        tool read off its 43 archived events, every one printed and sailed by."""
        if self.settings.font_size is not None:
            return self.settings.font_size
        flights = len({slot.flight for slot in self.slots})
        races = -(-len(self.teams) // max(len(self.boats), 1))
        rows = flights * races
        if rows <= 42:
            return 10
        if rows <= 56:
            return 8
        if rows <= 64:
            return 7
        return 6

    def key(self) -> str:
        """What the cache knows this rendering by: everything that decides the file."""
        content = {
            "teams": self.teams,
            "boats": [(boat.number, boat.color, boat.name) for boat in self.boats],
            "slots": [
                (s.flight, s.race_in_flight, s.boat_number, s.team_index) for s in self.slots
            ],
            "title": self.title,
            "settings": self.settings.as_json(),
            "team": self.team_index,
        }
        return hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()


async def render_pdf(request: PdfRequest) -> bytes:
    """Renders the list and returns the PDF."""
    if request.team_index is not None and not 0 <= request.team_index < len(request.teams):
        raise PairingPdfError(
            f"There is no team {request.team_index} in a list of {len(request.teams)}."
        )
    key = request.key()
    async with _RENDER_LOCK:
        cached = _CACHE.get(key)
        if cached is not None:
            _CACHE.move_to_end(key)
            return cached
        pdf = await asyncio.to_thread(_render, request)
        _CACHE[key] = pdf
        while len(_CACHE) > CACHE_SIZE:
            _CACHE.popitem(last=False)
        return pdf


# Rendered lists, newest last. The lock is held across the rendering as well, so the
# crews that download at once wait for one rendering instead of starting one each.
_CACHE: OrderedDict[str, bytes] = OrderedDict()
_RENDER_LOCK = asyncio.Lock()


def _render(request: PdfRequest) -> bytes:
    size = request.font_size
    pagesize = landscape(A4) if request.settings.landscape else A4
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=pagesize,
        leftMargin=SIDE_MARGIN,
        rightMargin=SIDE_MARGIN,
        topMargin=TOP_MARGIN,
        bottomMargin=TOP_MARGIN,
        title=request.title,
        subject="Pairing List",
        creator="Deutsche Segel-Liga",
        invariant=True,  # no timestamp or random id: the same list is the same file
    )
    if request.team_index is not None:
        highlights = [request.team_index]
    elif request.settings.team_pages:
        highlights = [None, *range(len(request.teams))]
    else:
        highlights = [None]

    story: list = []
    for number, highlight in enumerate(highlights):
        if number:
            story.append(PageBreak())
        story += _page(request, highlight, size, doc.width)
    doc.build(story)
    return buffer.getvalue()


def _page(request: PdfRequest, highlight: int | None, size: int, width: float) -> list:
    """One sheet: the title, the team it is for, and the grid."""
    heading = ParagraphStyle(
        "title", fontName=FONT, fontSize=size * 2, leading=size * 2.4, spaceAfter=size * 0.5
    )
    heading.alignment = TA_CENTER
    flowables: list = [Paragraph(_escape(request.title), heading)]
    if highlight is not None:
        team = ParagraphStyle(
            "team", fontName=FONT, fontSize=size * 1.5, leading=size * 1.8, spaceAfter=size * 0.5
        )
        team.alignment = TA_CENTER
        flowables.append(Paragraph(_escape(request.teams[highlight]), team))
    flowables.append(_grid(request, highlight, size, width))
    return flowables


def _grid(request: PdfRequest, highlight: int | None, size: int, width: float) -> Table:
    boats = len(request.boats)
    column = width / (boats + 2 * NUMBER_COLUMN)
    widths = [column * NUMBER_COLUMN] * 2 + [column] * boats
    row_height = size * 1.25
    gap = 1.0

    rows: list[list[str]] = [["Flight", "Race", *_boat_names(request.boats)]]
    heights: list[float] = [row_height]
    style: list[tuple] = []
    for boat, spec in enumerate(request.boats):
        rgb = boat_color(spec.color) or (255, 255, 255)
        fill = colors.Color(*(channel / 255 for channel in rgb))
        style += [
            ("BACKGROUND", (2 + boat, 0), (2 + boat, 0), fill),
            ("TEXTCOLOR", (2 + boat, 0), (2 + boat, 0), _readable_on(rgb)),
        ]

    race_number = 0
    for flight_number, races in enumerate(to_flights(request.slots, boats), start=1):
        # The gap between flights: a thin row without lines, as the Java sheet has it.
        gap_row = len(rows)
        rows.append([""] * (2 + boats))
        heights.append(gap)
        style.append(("LINEABOVE", (0, gap_row), (-1, gap_row), 0, colors.white))
        style.append(("LINEBEFORE", (0, gap_row), (-1, gap_row), 0, colors.white))
        first = len(rows)
        for race_in_flight, seats in enumerate(races):
            race_number += 1
            row = len(rows)
            names = []
            for boat, team in enumerate(seats):
                names.append(request.teams[team] if team >= 0 else EMPTY_SEAT)
                if highlight is not None and team == highlight:
                    style += [
                        ("BACKGROUND", (2 + boat, row), (2 + boat, row), OWN_SEAT),
                        ("TEXTCOLOR", (2 + boat, row), (2 + boat, row), colors.white),
                    ]
            flight_cell = str(flight_number) if race_in_flight == 0 else ""
            rows.append([flight_cell, str(race_number), *names])
            heights.append(row_height)
        style.append(("SPAN", (0, first), (0, len(rows) - 1)))
        style.append(("BOX", (0, first), (-1, len(rows) - 1), 0.5, colors.black))
        style.append(("INNERGRID", (0, first), (-1, len(rows) - 1), 0.5, colors.black))

    table = Table(rows, colWidths=widths, rowHeights=heights, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("FONT", (0, 0), (-1, -1), FONT, size),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ("LEFTPADDING", (0, 0), (-1, -1), 1),
                ("RIGHTPADDING", (0, 0), (-1, -1), 1),
                ("BOX", (0, 0), (-1, 0), 0.5, colors.black),
                ("INNERGRID", (0, 0), (-1, 0), 0.5, colors.black),
                *style,
            ]
        )
    )
    return table


def _boat_names(boats: list[BoatSpec]) -> list[str]:
    """A boat's own name, or "Boat n" — counted among the unnamed ones only, as the Java
    sheet does."""
    names: list[str] = []
    unnamed = 0
    for boat in boats:
        if boat.name:
            names.append(boat.name)
        else:
            unnamed += 1
            names.append(f"Boat {unnamed}")
    return names


def _readable_on(rgb: tuple[int, int, int]) -> colors.Color:
    """Black text on a light heading, white on a dark one — by the channels' mean, the
    Java tool's rule."""
    return colors.black if sum(rgb) / (3 * 255) > 0.5 else colors.white


def _escape(text: str) -> str:
    """A title or club name as Paragraph text, which reads a small markup of its own."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
