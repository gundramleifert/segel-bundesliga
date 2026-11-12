"""Results of an event we sent to SAP Sailing, taken back — and nothing else (Story WL-5).

The live poll's whole job, every few seconds while an act is sailed: read the event's
leaderboard and write SAP's raw results onto **our** draw — the teams the send linked,
the races of our flights. It creates nothing: no club, team, series, event, race or boat,
and it sets no status but a scored race's ``finished`` (review 6.2). A competitor SAP has
that the send did not make is reported, never entered — renaming a team at SAP mid-act
must not make a new club here. The historical importer (`app/imports/sap.py`) is for past
seasons; this is for the one event the site is scoring on SAP.

Points are derived here as for every event; SAP's are only compared.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.imports.common import Report, linked
from app.imports.sap import (
    SOURCE,
    EntryKey,
    apply_cell,
    apply_penalty,
    cells,
)
from app.models import Event, Flight, Race, RaceEntry, Team
from app.services import race_state
from app.services.standings import compute_event


async def apply_results(
    session: AsyncSession, event: Event, leaderboard: dict[str, Any], report: Report
) -> None:
    """SAP's leaderboard for ``event``, onto its teams and races. Doesn't commit."""
    label = event.sap_leaderboard or event.slug
    races = await _our_races(session, event)
    entries = {
        EntryKey(entry.race_id, entry.team_id): entry
        for entry in (
            await session.execute(
                select(RaceEntry).where(RaceEntry.race_id.in_([r.id for r in races.values()]))
            )
        ).scalars()
    }
    teams: dict[str, Team] = {}
    competitors = leaderboard.get("competitors", [])
    for competitor in competitors:
        team = await linked(session, Team, SOURCE, competitor["id"])
        if team is None or team.event_id != event.id:
            name = competitor.get("shortName") or competitor.get("name") or competitor["id"]
            report.unassigned.append(f"{label}: {name} is not a team sent from here")
            continue
        teams[competitor["id"]] = team
        for column, cell in cells(competitor).items():
            apply_cell(session, report, label, races, {}, entries, team, column, cell, True)
        apply_penalty(report, label, team, competitor.get("carriedPoints"), True)
    await session.flush()

    scored = set(
        (
            await session.execute(
                select(RaceEntry.race_id).where(
                    RaceEntry.race_id.in_([r.id for r in races.values()]),
                    RaceEntry.code.is_not(None),
                )
            )
        ).scalars()
    )
    for race in races.values():
        if race.id in scored:
            race_state.record_imported_finish(race, finished_at=race.started_at)
    await _compare(session, report, label, event, competitors, teams)


def changed(report: Report) -> bool:
    """Whether the run wrote anything a page shows — only then is the live stream told."""
    return any(
        what.startswith(("results", "penalties"))
        for counter in (report.created, report.updated)
        for what, n in counter.items()
        if n
    )


async def _our_races(session: AsyncSession, event: Event) -> dict[tuple[str, str], Race]:
    """(column, fleet) → our race, as the send named them: flight *n* is ``F<n>``, its
    race *k* ``Race <k>`` (`app/imports/sap_send.py`)."""
    rows = (
        await session.execute(
            select(Race, Flight.number)
            .join(Flight, Race.flight_id == Flight.id)
            .where(Flight.event_id == event.id)
        )
    ).all()
    return {(f"F{number}", f"Race {race.number_in_flight}"): race for race, number in rows}


async def _compare(
    session: AsyncSession,
    report: Report,
    label: str,
    event: Event,
    competitors: list[dict[str, Any]],
    teams: dict[str, Team],
) -> None:
    ours = {score.team_id: score.net for score in await compute_event(session, event.id)}
    for competitor in competitors:
        team = teams.get(competitor["id"])
        theirs = competitor.get("netPoints")
        if team is None or theirs is None:
            continue
        # The matchday penalty is inside our net already (Story WL-4).
        if abs(float(ours.get(team.id, 0.0)) - float(theirs)) > 0.01:
            report.warnings.append(
                f"{label} {team.name}: {ours.get(team.id)} net points here, {theirs} at SAP"
            )
