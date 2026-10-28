#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Record the 1. and 2. Segel-Bundesliga 2026 results into `api/app/seed_data/dsbl-2026/`.

    scripts/record-dsbl-2026.py ~/Downloads        # the folder with the scoreboard PDFs

The league sailed 2026 on TracTrac, which has no open data (docs/PLAN_SEEDING.md,
"Results"): what there is, is the **event scoreboard** each act's viewer exports as a PDF
— per club its place in every flight — and the **pairing list** each matchday page of
deutsche-segelbundesliga.de publishes — per flight which club sailed which boat in which
race. Together they are the raw results our scoring derives points from (RaceEntry), so
this records both, as written, one JSON file per act and division:

* the scoreboard by **club code**, through the reviewed table below — never a name
  comparison (CLAUDE.md, "External systems are matched via ExternalId");
* the pairing list as the league published it, its codes unchanged (`BYC (BA)`,
  `BOH-YC`): mapping them onto this site's clubs is the importer's job, not the record's.

Nothing is written unless every race checks out: the clubs of one race placed 1 to 6,
each place once — a redress (`1.7*`) stands in for the place it replaces — and each
club's places plus its matchday penalty adding up to the scoreboard's points. A name
mapped to the wrong code breaks that at once, which is what makes a hand-written table
safe. TracTrac's notation, as found in the 2026 exports:

* a flight cell is the place (`3`), a redress worth points (`1.7*`, `6*`), or a bare
  `RDG` whose points the scoreboard shows only inside the total — recorded as derived
  (total − places − penalty), never invented;
* the `P` column is the matchday penalty (`3`, `3*`), part of the total (Story WL-4);
* the total is shown rounded to one decimal at times (28.59 as `28.6`), so it is
  compared to within 0.05.

Needs `pdftotext` (poppler-utils). The pairing lists are downloaded; the scoreboards are
not online, so they come from the folder they were exported to.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path
from typing import NamedTuple

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "api" / "app" / "seed_data" / "dsbl-2026"
UPLOADS = "https://deutsche-segelbundesliga.de/wp-content/uploads/2025/11/"


class Act(NamedTuple):
    """One act of one division: its number, the scoreboard's title, the pairing list, the
    city it was sailed from, the host club(s) its pairing list names (league codes), and
    its days as the league's matchday page states them
    (deutsche-segelbundesliga.de/dsbl-event/<n>-spieltag-2026/, read 2026-10-27) — not
    TracTrac's event addresses, whose day is sometimes the practice day before."""

    division: int
    act: int
    scoreboard_title: str
    pairing_list: str
    city: str
    hosts: tuple[str, ...]
    starts_on: str
    ends_on: str


# The 2. Liga sailed no act 4 (Hamburg was the 1. Liga's alone): the season scoreboard's
# columns are 2. Liga (1), (2), (3), (5), (F).
STARNBERG_1 = ("1. & 2. Bundesliga 2026 Starnberg (1)", "Starnberg", ("MRSV", "DTYC"), "2026-04-17", "2026-04-19")
STARNBERG_2 = ("1. & 2. Bundesliga 2026 Starnberg (2)", "Starnberg", ("BYC (BA)",), "2026-05-01", "2026-05-03")
KIEL = ("1. & 2. Bundesliga 2026 Kiel (3)", "Kiel", (), "2026-07-10", "2026-07-12")
HAMBURG = ("4. Spieltag der Deutschen Segel-Bundesliga 2026", "Hamburg", ("NRV",), "2026-07-31", "2026-08-02")
WANNSEE = ("5. Spieltag Deutsche Segel-Bundesliga 2026", "Berlin", ("PYC",), "2026-09-18", "2026-09-20")
FINALE = ("Finale der Deutschen Segel-Bundesliga 2026", "Berlin", ("VSaW",), "2026-10-15", "2026-10-17")
ACTS = [
    Act(1, 1, STARNBERG_1[0], "pairing_list_0.pdf", *STARNBERG_1[1:]),
    Act(2, 1, STARNBERG_1[0], "pairing_list_0-1.pdf", *STARNBERG_1[1:]),
    Act(1, 2, STARNBERG_2[0], "pairing_list_1-1.pdf", *STARNBERG_2[1:]),
    Act(2, 2, STARNBERG_2[0], "pairing_list_1.pdf", *STARNBERG_2[1:]),
    Act(1, 3, KIEL[0], "pairing_list_2.pdf", *KIEL[1:]),
    Act(2, 3, KIEL[0], "pairing_list_2-3.pdf", *KIEL[1:]),
    Act(1, 4, HAMBURG[0], "Pairing-Liste-1.-Liga-NRV.pdf", *HAMBURG[1:]),
    Act(1, 5, WANNSEE[0], "Pairing-Liste-1.-Liga-PYC.pdf", *WANNSEE[1:]),
    Act(2, 5, WANNSEE[0], "Pairing-Liste-2.-Liga-PYC.pdf", *WANNSEE[1:]),
    Act(1, 6, FINALE[0], "Pairing-Liste-1.-Liga-Finale.pdf", *FINALE[1:]),
    Act(2, 6, FINALE[0], "Pairing-Liste-2.-Liga-Finale.pdf", *FINALE[1:]),
]

# TracTrac's club names → the league's codes in the pairing lists. Reviewed by hand,
# 2026-10-27, against the season scoreboards and the pairing lists; the race check below
# is what proves it. A name is matched only after its spaces are collapsed.
CODES = {
    # 1. Liga
    "Norddeutscher Regatta Verein": "NRV",
    "Joersfelder Segel-Club": "JSC",
    "Münchner Yacht-Club": "MYC",
    "Mühlenberger Segel-Club": "MSC",
    "Segel- und Motorboot Club Überlingen": "SMCÜ",
    "Bayerischer Yacht-Club": "BYC (BA)",
    "Bodensee-Yacht-Club Überlingen": "BYCÜ",
    "Blankeneser Segel-Club": "BSC",
    "Potsdamer Yacht Club": "PYC",
    "Berliner Yacht-Club": "BYC (BE)",
    "Düsseldorfer Yachtclub": "DYC",
    "Kieler Yacht-Club": "KYC (SH)",
    "Bocholter Yacht Club": "BOH-YC",
    "Württembergischer Yacht-Club": "WYC",
    "Klub am Rupenhorn": "KaR",
    "Entdecker - & Seefahrer Fördervereinigung": "EnSFr",
    "Segler-Vereinigung-Wuppertal": "SVWu",
    "Seglervereinigung Itzehoe": "SVI",
    # 2. Liga
    "Konstanzer Yacht Club": "KYC (BW)",
    "Lübecker Yacht-Club": "LYC",
    "Regatta-Segler-Neuruppin": "RSN",
    "Segel-Club Ville": "SCV",
    "Akademischer SegelVerein Warnemünde": "ASVW",
    "Verein Seglerhaus am Wannsee": "VSaW",
    "Flensburger Segel-Club": "FSC",
    "Seglervereinigung 1903 Berlin": "SV03",
    "Essener Turn-& Fechtclub": "ETUF",
    "Wir sind Wir": "WSW",
    "Hamburger Segelclub": "HSC",
    "Frankfurter Yachtclub": "FYC",
    "Lübecker Segler-Verein von 1885": "LSV",
    'Münchener Ruder- und Segelverein "Bayern" von 1910': "MRSV",
    "Segelclub Hansa Münster": "SHM",
    "Bucerius Sailing": "BuSC",
    "Segelclub Rheingau": "SCR",
    "Deutscher Touring Yacht Club": "DTYC",
}

FLIGHTS = 16
_CELL = re.compile(r"^(-|\d+(?:\.\d+)?\*?|[A-Z]{3})$")


def text_of(pdf: Path) -> list[str]:
    out = subprocess.run(["pdftotext", "-layout", str(pdf), "-"], capture_output=True, text=True, check=True)
    return out.stdout.splitlines()


def clean(name: str) -> str:
    return re.sub(r"\s+", " ", name).strip()


class Row(NamedTuple):
    name: str
    rank: int
    points: float
    penalty: str
    cells: list[str]


def scoreboard(pdf: Path) -> list[Row]:
    """The rows of an event scoreboard: a name (sometimes wrapped onto the next line),
    rank, points, the penalty column `P` and sixteen flight cells."""
    rows: list[Row] = []
    for line in text_of(pdf):
        tokens = line.split()
        if not tokens or tokens[0] == "Name":
            continue
        tail = tokens[-(FLIGHTS + 3) :]
        if len(tokens) > FLIGHTS + 3 and tail[0].isdigit() and all(_CELL.match(t) for t in tail[3:]):
            name = clean(" ".join(tokens[: -(FLIGHTS + 3)]))
            rows.append(Row(name, int(tail[0]), float(tail[1]), tail[2], tail[3:]))
        elif rows and not re.search(r"scoreboard|Bundesliga|Segel-Bundesliga", line):
            # A name wrapped onto its own line, under the row it belongs to.
            last = rows[-1]
            rows[-1] = last._replace(name=clean(f"{last.name} {line}"))
    return rows


def boat_numbers(pdf: Path) -> list[int]:
    """The boats the list's header names — 1..6 for the 1. Liga, 7..12 for the 2."""
    for line in text_of(pdf):
        numbers = re.findall(r"Boat\s+(\d+)", line)
        if numbers:
            return [int(n) for n in numbers]
    raise SystemExit(f"{pdf.name}: no boat numbers in its header")


def pairing(pdf: Path) -> list[list[list[str]]]:
    """flights[f][r] = the codes on boats 1..6 (2. Liga: 7..12) in race r+1 of flight f+1."""
    races: list[list[str]] = []
    code = r"(KYC \((?:SH|BW)\)|BYC \((?:BA|BE)\)|\S+)"
    pattern = re.compile(rf"^\s*(?:\d+\s+)?(\d+)\s+{code}\s+{code}\s+{code}\s+{code}\s+{code}\s+{code}\s*$")
    for line in text_of(pdf):
        m = pattern.match(line)
        # The overview numbers its races 1, 2, 3 … in order; the per-team pages after it
        # have lines of the same shape, which this stops before.
        if m and int(m.group(1)) == len(races) + 1:
            races.append([m.group(i) for i in range(2, 8)])
        elif m and races:
            break
    if len(races) % 3:
        raise SystemExit(f"{pdf.name}: {len(races)} races is not whole flights")
    return [races[i : i + 3] for i in range(0, len(races), 3)]


def cell_value(cell: str) -> dict | None:
    if cell == "-":
        return None
    if cell.endswith("*"):
        return {"redress": float(cell[:-1])}
    if cell.isdigit():
        return {"place": int(cell)}
    return {"code": cell}


def penalty_of(cell: str) -> float | None:
    return None if cell == "-" else float(cell.rstrip("*"))


def counted(value: dict | None) -> float:
    return value.get("place", value.get("redress", 0)) if value else 0


def derive_codes(row: Row, flights: list[dict | None]) -> list[dict | None]:
    """A bare `RDG` gets the points the total leaves for it — only when it is the row's
    one cell without a number, so the arithmetic has a single answer."""
    bare = [i for i, v in enumerate(flights) if v and "code" in v]
    if len(bare) != 1 or flights[bare[0]]["code"] != "RDG":
        return flights
    rest = row.points - sum(counted(v) for v in flights) - (penalty_of(row.penalty) or 0)
    filled = list(flights)
    filled[bare[0]] = {"code": "RDG", "redress": round(rest, 2), "derived": True}
    return filled


def check(act: Act, rows: list[Row], flights: list[list[list[str]]], results: dict[str, list]) -> list[str]:
    problems = []
    for f, races in enumerate(flights):
        for r, boats in enumerate(races):
            values = [results.get(code, [None] * FLIGHTS)[f] for code in boats]
            if all(v is None for v in values):
                continue  # not sailed
            places = sorted(v["place"] for v in values if v and "place" in v)
            redressed = sum(1 for v in values if v and "redress" in v)
            others = [v for v in values if v and "code" in v]
            if len(places) != len(set(places)) or (not redressed and not others and places != list(range(1, 7))):
                problems.append(f"flight {f + 1} race {r + 1}: places {places} for {boats}")
            if any(v is None for v in values):
                problems.append(f"flight {f + 1} race {r + 1}: a club without a result, {boats}")
    for row in rows:
        code = CODES[row.name]
        total = sum(counted(v) for v in results[code]) + (penalty_of(row.penalty) or 0)
        if abs(total - row.points) > 0.05:
            problems.append(f"{code}: places add up to {total:g}, scoreboard says {row.points:g}")
    sailing = {code for races in flights for boats in races for code in boats}
    if sailing != set(results):
        problems.append(f"clubs differ: pairing list only {sorted(sailing - set(results))}, scoreboard only {sorted(set(results) - sailing)}")
    return [f"{act.division}. Liga act {act.act}: {p}" for p in problems]


def main(folder: str) -> int:
    pdfs = sorted(Path(folder).expanduser().glob("*Event scoreboard*.pdf"))
    by_title: dict[str, list[Path]] = {}
    for pdf in pdfs:
        title = clean(text_of(pdf)[0])
        by_title.setdefault(title, []).append(pdf)

    OUT.mkdir(parents=True, exist_ok=True)
    problems: list[str] = []
    records: dict[str, dict] = {}
    with tempfile.TemporaryDirectory() as tmp:
        for act in ACTS:
            listed = Path(tmp) / act.pairing_list
            urllib.request.urlretrieve(UPLOADS + act.pairing_list, listed)  # noqa: S310 — fixed host
            flights = pairing(listed)
            codes = {code for races in flights for boats in races for code in boats}
            # Of the two exports with this title, the one whose clubs this pairing list has;
            # a duplicate export of the same scoreboard is the same rows twice.
            candidates = []
            for pdf in by_title.get(act.scoreboard_title, []):
                rows = scoreboard(pdf)
                unknown = sorted({r.name for r in rows} - set(CODES))
                if unknown:
                    raise SystemExit(f"{pdf.name}: names not in CODES: {unknown}")
                if {CODES[r.name] for r in rows} == codes:
                    candidates.append((pdf, rows))
            if not candidates:
                problems.append(f"{act.division}. Liga act {act.act}: no scoreboard '{act.scoreboard_title}' with this pairing list's clubs")
                continue
            pdf, rows = candidates[0]
            results = {CODES[r.name]: derive_codes(r, [cell_value(c) for c in r.cells]) for r in rows}
            problems += check(act, rows, flights, results)
            records[f"{act.division}-liga-act-{act.act}.json"] = {
                "year": 2026,
                "division": act.division,
                "act": act.act,
                "title": act.scoreboard_title,
                "city": act.city,
                "hosts": list(act.hosts),
                "starts_on": act.starts_on,
                "ends_on": act.ends_on,
                "boats": boat_numbers(listed),
                "sources": {
                    "scoreboard": f"TracTrac event scoreboard, exported as PDF ({pdf.name})",
                    "pairing_list": UPLOADS + act.pairing_list,
                },
                "flights_sailed": max((f + 1 for rs in results.values() for f, v in enumerate(rs) if v), default=0),
                "pairing": [[{"race": r + 1, "boats": boats} for r, boats in enumerate(races)] for races in flights],
                "scoreboard": [
                    {
                        "code": CODES[r.name],
                        "name": r.name,
                        "rank": r.rank,
                        "points": r.points,
                        "penalty": penalty_of(r.penalty),
                        "flights": results[CODES[r.name]],
                    }
                    for r in rows
                ],
            }
    if problems:
        print("\n".join(problems))
        print(f"\n{len(problems)} problems — nothing written")
        return 1
    for name, record in records.items():
        (OUT / name).write_text(json.dumps(record, ensure_ascii=False, indent=1) + "\n", "utf-8")
        print(f"{name}: {len(record['scoreboard'])} clubs, {record['flights_sailed']} flights")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "~/Downloads"))
