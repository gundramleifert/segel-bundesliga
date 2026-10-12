"""Import from SAP Sailing Analytics and Manage2Sail (Story A-14).

    uv run python -m app.imports sap --year 2023            # both divisions of 2023
    uv run python -m app.imports sap --regatta "1. Segel-Bundesliga 2023 - Berlin (1)"
    uv run python -m app.imports sap --all                  # every DSBL season on SAP
    uv run python -m app.imports sap --list                 # what SAP has, nothing written

    uv run python -m app.imports m2s ee214292-a957-44af-81fc-3e6923a97161
    uv run python -m app.imports m2s <uuid> --to 12         # attach to event 12 here
    uv run python -m app.imports m2s <uuid> --series junioren-2026 --matchday 1
    uv run python -m app.imports m2s <uuid> --link "KYC|Kieler Yacht-Club e. V.=kyc"

Repeatable: a second run with the same data changes nothing. Imported competitions stay
drafts unless ``--publish``. Uses the database of ``SBL_DATABASE_URL`` (``api/sbl.db``).
"""

from __future__ import annotations

import argparse
import asyncio
import sys

import httpx

from app.db import SessionLocal
from app.imports.common import USER_AGENT, Report
from app.imports.m2s import Manage2SailClient, import_m2s
from app.imports.sap import SapClient, import_sap, parse_regatta_name


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.imports",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="source", required=True)

    sap = sub.add_parser("sap", help="DSBL matchdays, clubs and results from SAP Sailing")
    sap.add_argument("--year", type=int, action="append", default=[], help="a season, repeatable")
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
    return parser


async def _run(args: argparse.Namespace) -> Report | None:
    async with httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT}, timeout=60, follow_redirects=True
    ) as http:
        if args.source == "sap":
            client = SapClient(http)
            if args.list:
                for regatta in await client.regattas():
                    parsed = parse_regatta_name(regatta["name"])
                    if parsed:
                        print(f"{parsed.year}  {parsed.level}. Liga  {parsed.name}")
                return None
            if not (args.year or args.regatta or args.all):
                raise SystemExit("sap: say what — --year, --regatta, --all or --list")
            return await import_sap(
                SessionLocal,
                client,
                years=args.year,
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
        )


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    report = asyncio.run(_run(args))
    if report is None:
        return 0
    print(report.render())
    return 1 if report.errors else 0


if __name__ == "__main__":
    sys.exit(main())
