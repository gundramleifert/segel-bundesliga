"""Printing a pairing list — rendered by the Java tool, which owns the layout.

The list is read on a phone, but it is also **printed**: pinned up in the clubhouse, handed
to crews at registration, carried to the boat. That sheet has looked the same for years, and
the layout lives in ``reference/PairingList`` (``PdfCreator``) — a second one in Python would
be a second thing to keep in step with the first.

So the same process boundary the draw already crosses is crossed again, with the same file
exchange, but against a different entry point:

    java -cp <jar> gundramleifert.pairing_list.PdfExport \\
         -s schedule_cfg.yml -pli pairing_list.yml -dc display_cfg.yml -plp out.pdf -t <title>

``PdfExport`` renders **one** PDF and writes nothing else — unlike ``Optimizer``, which
prints as a by-product of a draw that takes minutes, and unlike ``ReuseSchedule``, which
writes a whole event directory.

Rendering takes a second or two, not minutes, so this one *can* answer an HTTP request. Two
things keep it that way: a **timeout** far below the optimizer's, and a **cache keyed by the
rendered content**, so eighteen crews downloading the same list start one JVM, not eighteen.
Because the key *is* the content, nothing has to be invalidated when a list is redrawn — a
different draw is simply a different key.
"""

from __future__ import annotations

import asyncio
import hashlib
import re
import shutil
import tempfile
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from app.config import settings
from app.pairing.importer import BoatSpec
from app.pairing.logistics import to_flights
from app.pairing.schedule import PairingSlot

MAIN_CLASS = "gundramleifert.pairing_list.PdfExport"

# A rendering is seconds; the optimizer's half hour would be the wrong limit here, because
# this one runs inside a request and a hung JVM must not hold it open.
RENDER_TIMEOUT_SECONDS = 120

# How many rendered lists are kept. A matchday is one entry per title, and only the events
# people are currently looking at matter — a handful covers a race weekend.
CACHE_SIZE = 8

# The color names ``PdfCreator.defaultColorMap()`` knows, German and English mixed. Anything
# else has to be handed over as an RGB triple under an invented name, or it is a hard error
# in the tool ("cannot interpret key ...").
KNOWN_COLORS = frozenset(
    {
        "BLACK", "DARK_GRAY", "GRAY", "LIGHT_GRAY", "WHITE", "BLUE", "CYAN", "GREEN",
        "ORANGE", "PINK", "RED", "YELLOW", "HELLBLAU", "DUNKELBLAU", "LIGHTBLUE",
        "DARKBLUE", "GELB", "LILA", "GRUEN", "GREY", "GRAU", "SCHWARZ", "WEISS", "BLAU",
        "ROT",
    }
)

_HEX_COLOR = re.compile(r"#?(?P<digits>[0-9a-fA-F]{3}|[0-9a-fA-F]{6})\Z")


class PairingPdfError(RuntimeError):
    """The pairing list could not be rendered."""


#: Font size by the number of rows a sheet has (``flights * races_per_flight``), read off
#: the 43 event directories in ``reference/PairingList/events`` — every one of them a sheet
#: that was actually printed and sailed by. Their ``display_cfg.yml`` files vary in exactly
#: two things, ``fontsize`` and (once) ``landscape``; ``factor_flight_race_width: 0.5`` and
#: ``teamwise_list: true`` are unanimous across all 43. Read as: up to this many rows, that
#: size. The table is the *default* — the organizer who knows the venue's printer overrides
#: it on the event (Story B-3).
FONT_SIZE_BY_ROWS = ((42, 10), (56, 8), (64, 7))
SMALLEST_FONT_SIZE = 6


def default_font_size(rows: int) -> int:
    """The size the fleet would have chosen for a sheet of this many rows."""
    for limit, size in FONT_SIZE_BY_ROWS:
        if rows <= limit:
            return size
    return SMALLEST_FONT_SIZE


@dataclass(frozen=True)
class PrintSettings:
    """What the organizer decides about the printed sheet.

    Every field may stay unset, and unset is the normal case: the organizer of a league
    matchday has nothing to say about font size, and the default derived from the
    configuration is what the same matchday has been printed at for years. Someone running
    a twenty-flight cup on one page, or handing the sheet to a venue with a poor printer,
    does have something to say — and this is where they say it.
    """

    #: ``None`` means: whatever :func:`default_font_size` makes of the configuration.
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
    def flights(self) -> int:
        return max((slot.flight for slot in self.slots), default=0)

    @property
    def races_per_flight(self) -> int:
        return max((slot.race_in_flight for slot in self.slots), default=0)

    @property
    def font_size(self) -> int:
        """What the organizer set, or what a sheet of this many rows is printed at."""
        return self.settings.font_size or default_font_size(
            self.flights * self.races_per_flight
        )

    def files(self) -> dict[str, str]:
        """The three input files of the tool, by name.

        Returned together rather than written out here, because they are also the cache
        key: two requests that produce the same files produce the same PDF.
        """
        colors, additional = _resolve_colors(self.boats)
        schedule = {
            "flights": self.flights,
            "titles": [self.title],
            "teams": list(self.teams),
            "boats": [
                {"color": color, "name": boat.name}
                for boat, color in zip(self.boats, colors, strict=True)
            ],
        }
        display = {
            "fontsize": self.font_size,
            # The flight and race columns carry a number, not a club name — half width.
            # Unanimous across every event in the archive, so not the organizer's business.
            "factor_flight_race_width": 0.5,
            "teamwise_list": self.settings.team_pages,
            "landscape": self.settings.landscape,
            # Table width in points. 600 is what 41 of 43 archived events print at; across
            # a rotated A4 there is room for more.
            "width": 820 if self.settings.landscape else 600,
            "additional_colors": additional,
        }
        return {
            "schedule_cfg.yml": _yaml(schedule),
            "pairing_list.yml": _yaml({"flights": self._flight_rows()}),
            "display_cfg.yml": _yaml(display),
        }

    def _flight_rows(self) -> list[dict[str, list[str]]]:
        """The draw as the tool reads it: 0-based team indices, position = boat.

        An empty seat — a fleet the boats do not divide evenly — is written as an index
        *past* the last team. The tool pads its own team list to ``races * boats`` with
        empty names, so those indices resolve to "empty boat" and, crucially, every seat
        keeps its position; dropping them would shift every boat after the gap.
        """
        rows = []
        for races in to_flights(self.slots, len(self.boats)):
            empty_seat = len(self.teams)
            flight = []
            for race in races:
                seats = []
                for index in race:
                    if index < 0:
                        index = empty_seat
                        empty_seat += 1
                    seats.append(str(index))
                flight.append(",".join(seats))
            rows.append({"races": flight})
        return rows


async def render_pdf(
    request: PdfRequest, *, jar: Path | None = None, timeout: int | None = None
) -> bytes:
    """Renders the list and returns the PDF."""
    if request.team_index is not None and not 0 <= request.team_index < len(request.teams):
        raise PairingPdfError(
            f"There is no team {request.team_index} in a list of {len(request.teams)}."
        )
    files = request.files()
    key = _cache_key(files, request.team_index)

    async with _RENDER_LOCK:
        cached = _CACHE.get(key)
        if cached is not None:
            _CACHE.move_to_end(key)
            return cached

        pdf = await _render(files, request.title, request.team_index, jar, timeout)
        _CACHE[key] = pdf
        while len(_CACHE) > CACHE_SIZE:
            _CACHE.popitem(last=False)
        return pdf


# Rendered lists, newest last. The lock is held across the rendering as well, so the
# eighteen crews that download at once wait for one JVM instead of starting eighteen.
_CACHE: OrderedDict[str, bytes] = OrderedDict()
_RENDER_LOCK = asyncio.Lock()


def _cache_key(files: dict[str, str], team_index: int | None) -> str:
    digest = hashlib.sha256()
    for name in sorted(files):
        digest.update(name.encode("utf-8"))
        digest.update(files[name].encode("utf-8"))
    # Not in any of the files, and it decides what comes out: one team's page or all of it.
    digest.update(f"team={team_index}".encode())
    return digest.hexdigest()


def renderer_available(jar: Path | None = None) -> bool:
    """Whether this installation can print at all: the JAR is there and Java can run it.

    A deployment may legitimately have neither — the test image on Render carries no JRE
    for a long time, and a developer without the tool built still runs the whole site. The
    screens ask this so they can leave the download out rather than offer a button whose
    only possible answer is 503 (Story B-3).

    Deliberately **not** cached: it is two stat-cheap checks, and a cached "no" would
    outlive the deploy that added Java, which is exactly when someone is looking.
    """
    try:
        _require_renderer(jar)
    except PairingPdfError:
        return False
    return True


def _require_renderer(jar: Path | None = None) -> Path:
    """The JAR to run, or the reason there is none."""
    jar_path = Path(jar) if jar else Path(settings.pairing_jar)
    if not jar_path.is_file():
        raise PairingPdfError(
            f"The pairing JAR is missing at {jar_path}. "
            "Build with: mvn -DskipTests package in the reference/PairingList directory"
        )
    if shutil.which(settings.java_binary) is None:
        raise PairingPdfError(
            f"Java was not found ('{settings.java_binary}'). "
            "Printing a pairing list needs a Java runtime version 17 or later."
        )
    return jar_path


async def _render(
    files: dict[str, str],
    title: str,
    team_index: int | None,
    jar: Path | None,
    timeout: int | None,
) -> bytes:
    jar_path = _require_renderer(jar)

    workdir = Path(tempfile.mkdtemp(prefix="sbl-pairing-pdf-"))
    try:
        for name, content in files.items():
            (workdir / name).write_text(content, encoding="utf-8")

        process = await asyncio.create_subprocess_exec(
            settings.java_binary,
            "-cp", str(jar_path.resolve()),
            MAIN_CLASS,
            "-s", "schedule_cfg.yml",
            "-pli", "pairing_list.yml",
            "-dc", "display_cfg.yml",
            "-plp", "out.pdf",
            "-t", title,
            *(() if team_index is None else ("-team", str(team_index))),
            cwd=workdir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        limit = timeout if timeout is not None else RENDER_TIMEOUT_SECONDS
        try:
            output, _ = await asyncio.wait_for(process.communicate(), timeout=limit)
        except TimeoutError:
            process.kill()
            await process.wait()
            raise PairingPdfError(
                f"Rendering the pairing list was stopped after {limit} seconds."
            ) from None

        log = output.decode("utf-8", errors="replace")
        if process.returncode != 0:
            raise PairingPdfError(
                f"The renderer exited with code {process.returncode}.\n{_tail(log)}"
            )

        out = workdir / "out.pdf"
        if not out.is_file():
            raise PairingPdfError(f"The renderer wrote no PDF.\n{_tail(log)}")
        return out.read_bytes()
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def _resolve_colors(boats: list[BoatSpec]) -> tuple[list[str | None], dict[str, list[int]]]:
    """Boat colors as the tool wants them, plus the palette entries it needs for ours.

    Three cases, and the third is the one that matters: a name the tool knows goes through
    untouched (its palette is the one the printed list has always used), a hex value — what
    the color picker in Story VA-6 produces — becomes an invented, upper-case palette entry,
    and anything else becomes no color at all. The tool would rather throw than guess, and a
    matchday's sheet must not fail to print over a boat someone called "sea green".
    """
    names: list[str | None] = []
    additional: dict[str, list[int]] = {}
    for boat in boats:
        raw = (boat.color or "").strip()
        if raw.upper() in KNOWN_COLORS:
            names.append(raw.upper())
            continue
        rgb = _rgb(raw)
        if rgb is None:
            names.append(None)
            continue
        # Upper case is not cosmetic: `PdfCreator.createColorMap` throws on anything else.
        name = f"BOAT_{boat.number}"
        additional[name] = rgb
        names.append(name)
    return names, additional


def _rgb(color: str) -> list[int] | None:
    match = _HEX_COLOR.match(color)
    if match is None:
        return None
    digits = match.group("digits")
    if len(digits) == 3:
        digits = "".join(digit * 2 for digit in digits)
    return [int(digits[index : index + 2], 16) for index in (0, 2, 4)]


def _yaml(data: dict) -> str:
    return yaml.safe_dump(data, sort_keys=False, allow_unicode=True)


def _tail(log: str, lines: int = 15) -> str:
    return "\n".join(log.strip().splitlines()[-lines:])
