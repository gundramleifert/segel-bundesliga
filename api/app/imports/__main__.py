"""Import from SAP Sailing Analytics, Manage2Sail and TracTrac's recorded scoreboards
(Story A-14).

    uv run python -m app.imports sap --year 2023            # both divisions of 2023
    uv run python -m app.imports sap --years 2021-2023      # a range (also 2019,2021-2023)
    uv run python -m app.imports sap --regatta "1. Segel-Bundesliga 2023 - Berlin (1)"
    uv run python -m app.imports sap --all                  # every DSBL season on SAP
    uv run python -m app.imports sap --list                 # what SAP has, nothing written

    uv run python -m app.imports m2s ee214292-a957-44af-81fc-3e6923a97161
    uv run python -m app.imports m2s <uuid> --to 12         # attach to event 12 here
    uv run python -m app.imports m2s <uuid> --series junioren-2026 --matchday 1
    uv run python -m app.imports m2s <uuid> --link "KYC|Kieler Yacht-Club e. V.=kyc"
    uv run python -m app.imports m2s <uuid> --regatta 1.Segel-Bundesliga --to 12  # one class
    uv run python -m app.imports m2s <uuid> --to-series dsbl-1-2026   # the season's documents

    uv run python -m app.imports tractrac                   # the 1./2. Liga 2026, recorded
    uv run python -m app.imports tractrac --folder <dir>    # another recording

SAP's address is ``https://www.sapsailing.com/sailingserver/api``, or ``SBL_SAP_BASE_URL``
/ ``--base-url`` for another SAP instance — the public one has no season after 2023.

Repeatable: a second run with the same data changes nothing. Imported competitions stay
drafts unless ``--publish``. Uses the database of ``SBL_DATABASE_URL`` (``api/sbl.db``).
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

import httpx

from app.db import SessionLocal, engine
from app.imports.common import USER_AGENT, Report
from app.imports.m2s import Manage2SailClient, import_m2s
from app.imports.sap import BASE_URL as SAP_BASE_URL
from app.imports.sap import SapClient, import_sap, parse_regatta_name, parse_years
from app.imports.tractrac import FOLDER as TRACTRAC_FOLDER
from app.imports.tractrac import import_tractrac


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.imports",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="source", required=True)

    sap = sub.add_parser("sap", help="DSBL matchdays, clubs and results from SAP Sailing")
    sap.add_argument("--year", type=int, action="append", default=[], help="a season, repeatable")
    sap.add_argument(
        "--years", action="append", default=[], metavar="RANGE", help="2025-2026, or 2019,2021"
    )
    sap.add_argument(
        "--base-url",
        default=os.environ.get("SBL_SAP_BASE_URL") or SAP_BASE_URL,
        help="the SAP server's API root (default: www.sapsailing.com, or SBL_SAP_BASE_URL)",
    )
    sap.add_argument("--regatta", action="append", default=[], help="one regatta by its SAP name")
    sap.add_argument("--all", action="store_true", help="every DSBL regatta SAP has")
    sap.add_argument("--list", action="store_true", help="list the DSBL regattas, import nothing")
    sap.add_argument("--publish", action="store_true", help="publish what is imported")

    m2s = sub.add_parser("m2s", help="an event's entries and documents from Manage2Sail")
    m2s.add_argument("event", help="the Manage2Sail event id (the UUID in its URL)")
    m2s.add_argument("--to", type=int, help="attach to this existing event (its id here)")
    m2s.add_argument("--series", help="a new event belongs to this series (its slug)")
    m2s.add_argument("--matchday", type=int, help="… as this matchday")
    m2s.add_argument(
        "--link",
        action="append",
        default=[],
        metavar="KEY=SLUG",
        help='tie a Manage2Sail club ("CODE|Club name") to a club here, repeatable',
    )
    m2s.add_argument("--publish", action="store_true", help="publish the event if it is new")
    m2s.add_argument(
        "--regatta", help='only this class, by its Manage2Sail name ("1.Segel-Bundesliga")'
    )
    m2s.add_argument(
        "--no-entries", action="store_true", help="documents only — the teams came from elsewhere"
    )
    m2s.add_argument(
        "--to-series", help="the season's notice board: its documents go to this series (slug)"
    )

    tractrac = sub.add_parser(
        "tractrac",
        help="the 1./2. Liga 2026 from TracTrac's scoreboards (scripts/record-dsbl-2026.py)",
    )
    tractrac.add_argument(
        "--folder", default=str(TRACTRAC_FOLDER), help="the recorded acts (default: seed_data)"
    )
    tractrac.add_argument("--publish", action="store_true", help="publish what is imported")
    return parser


async def _run(args: argparse.Namespace) -> Report | None:
    if args.source == "tractrac":
        return await import_tractrac(SessionLocal, Path(args.folder), publish=args.publish)
    async with httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT}, timeout=60, follow_redirects=True
    ) as http:
        if args.source == "sap":
            client = SapClient(http, args.base_url)
            if args.list:
                for regatta in await client.regattas():
                    parsed = parse_regatta_name(regatta["name"])
                    if parsed:
                        print(f"{parsed.year}  {parsed.level}. Liga  {parsed.name}")
                return None
            try:
                years = set(args.year).union(*(parse_years(spec) for spec in args.years))
            except ValueError as error:
                raise SystemExit(f"sap: --years {error}") from error
            if not (years or args.regatta or args.all):
                raise SystemExit("sap: say what — --year(s), --regatta, --all or --list")
            return await import_sap(
                SessionLocal,
                client,
                years=years,
                names=args.regatta,
                everything=args.all,
                publish=args.publish,
            )
        links = {}
        for item in args.link:
            key, sep, slug = item.rpartition("=")
            if not sep or not key or not slug:
                raise SystemExit(f"--link {item!r}: expected CODE|Club name=club-slug")
            links[key] = slug
        return await import_m2s(
            SessionLocal,
            Manage2SailClient(http),
            args.event,
            to_event=args.to,
            series_slug=args.series,
            matchday=args.matchday,
            links=links,
            publish=args.publish,
            regatta=args.regatta,
            to_series=args.to_series,
            with_entries=not args.no_entries,
        )


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        report = asyncio.run(_run(args))
    finally:
        # Closing the last connection folds the WAL back into the file — without it the
        # build leaves an `sbl.db-wal` beside the database (docs/gotchas: copying a
        # WAL-mode SQLite file copies half the database).
        asyncio.run(engine.dispose())
    if report is None:
        return 0
    print(report.render())
    return 1 if report.errors else 0


if __name__ == "__main__":
    sys.exit(main())
