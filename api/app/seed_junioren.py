"""The Junioren-Liga's real 2026 season in the seed — Stories A-14, VA-13.

Its four acts as SAP Sailing recorded them on the juniors' own host
(`hnv.sapsailing.com`, read on 2026-10-23, `app/seed_data/junioren-2026/`): the clubs that
really sail, their second teams, every result — imported by the import itself
(`app.imports.sap`), from these files instead of the network, so the seed, the tests and a
laptop offline all have the same season (decided 2026-10-23: the Junioren-Liga shows the
real teams and results, not made-up ones). `python -m app.imports sap --base-url …` refreshes
it from SAP, which a Finale still being sailed needs.

Results are public sporting facts; the files hold no picture and no person — the juniors'
squads are made up afterwards by the seed, like every other.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import unquote

import httpx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.imports.common import Report
from app.imports.sap import SapClient, import_sap

FOLDER = Path(__file__).parent / "seed_data" / "junioren-2026"
API = "https://hnv.sapsailing.com/sailingserver/api"


def _recorded() -> httpx.MockTransport:
    """The juniors' host as it answered: the regatta list and each act's leaderboard."""

    def handler(request: httpx.Request) -> httpx.Response:
        path = unquote(request.url.path).removeprefix("/sailingserver/api/")
        if path == "v1/regattas":
            return httpx.Response(200, content=(FOLDER / "regattas.json").read_bytes())
        if path.startswith("v2/leaderboards/"):
            name = path.removeprefix("v2/leaderboards/")
            act = name.split(" - Act ")[1].split()[0]
            return httpx.Response(200, content=(FOLDER / f"act-{act}.json").read_bytes())
        # Crests: none recorded — the seed's clubs keep their own.
        return httpx.Response(200, json=[])

    return httpx.MockTransport(handler)


async def seed_junioren(sessions: async_sessionmaker[AsyncSession]) -> Report:
    """Imports the four acts of 2026 into the seed's Junioren-Segelliga 2026, published."""
    async with httpx.AsyncClient(transport=_recorded()) as http:
        report = await import_sap(
            sessions, SapClient(http, API), years=[2026], publish=True, log=lambda _: None
        )
    print(
        f"Junioren-Liga 2026: {report.created.get('events', 0)} acts, "
        f"{report.created.get('event entries', 0)} entries, "
        f"{report.created.get('results', 0)} results"
    )
    return report
