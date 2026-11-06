"""An event and SAP Sailing — send it there, take its results back (Stories VA-15, WL-5).

    POST /api/events/{id}/sap/send       the event, its teams and draw to SAP
    POST /api/events/{id}/sap/results    its results from SAP, now

Both refuse an event whose results are entered here (``results_source``, Story VA-14).
"""

from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_event_control, require_event_manager_for
from app.config import settings
from app.db import SessionLocal, get_session
from app.imports.sap_send import SapWriter, SendRefused, send_event
from app.live import event_topic, hub
from app.models import Event, ResultsSource
from app.problems import Problem
from app.services.sap_scoring import fetch_results, sap_http

router = APIRouter(prefix="/api/events", tags=["sap"])


async def sap_client():
    """A dependency of its own, so the tests put a simulated SAP behind it."""
    async with sap_http() as http:
        yield http


class SapSendOut(BaseModel):
    leaderboard: str = Field(description="The SAP leaderboard the event now is")
    teams_created: int
    teams_kept: int = Field(description="Teams already at SAP from an earlier send")
    races: int = Field(description="Races whose team-on-boat draw was sent")


class SapResultsOut(BaseModel):
    results: int = Field(description="Results taken or changed")
    warnings: list[str]


async def _sap_event(session: AsyncSession, event_id: int) -> Event:
    event = await session.get(Event, event_id)
    if event is None:
        raise Problem(404, "event-not-found", "No such event.")
    if event.results_source != ResultsSource.SAP:
        raise Problem(409, "event-not-scored-on-sap", "This event's results are entered here.")
    return event


@router.post(
    "/{event_id}/sap/send",
    response_model=SapSendOut,
    dependencies=[Depends(require_event_manager_for)],
)
async def send_event_to_sap(
    event_id: int,
    session: AsyncSession = Depends(get_session),
    http: httpx.AsyncClient = Depends(sap_client),
) -> SapSendOut:
    """Story VA-15: the event, its teams under their club codes and our pairing list race
    by race to SAP Sailing — again after a new draw, until the first race froze it."""
    await _sap_event(session, event_id)
    if not settings.sap_boats:
        raise Problem(503, "sap-not-configured", "No SAP boats are configured (SBL_SAP_BOATS).")
    try:
        report = await send_event(
            session, SapWriter(http, settings.sap_base_url), event_id, settings.sap_boats
        )
    except SendRefused as refused:
        raise Problem(409, refused.code, str(refused)) from refused
    except httpx.HTTPError as error:
        raise Problem(502, "sap-unreachable", f"SAP Sailing did not answer: {error}") from error
    if report.errors:
        raise Problem(
            502, "sap-refused", "SAP Sailing refused a step of the send.", errors=report.errors
        )
    hub.publish(event_topic(event_id))
    return SapSendOut(
        leaderboard=report.leaderboard,
        teams_created=report.teams_created,
        teams_kept=report.teams_kept,
        races=report.races,
    )


@router.post(
    "/{event_id}/sap/results",
    response_model=SapResultsOut,
    dependencies=[Depends(require_event_control)],
)
async def fetch_results_from_sap(
    event_id: int,
    session: AsyncSession = Depends(get_session),
    http: httpx.AsyncClient = Depends(sap_client),
) -> SapResultsOut:
    """Story WL-5: the event's results from SAP now — while live the server asks by itself;
    after the day this is how a protest decided at SAP reaches the results here."""
    event = await _sap_event(session, event_id)
    if event.sap_leaderboard is None:
        raise Problem(409, "event-not-sent-to-sap", "The event has not been sent to SAP yet.")
    try:
        report = await fetch_results(SessionLocal, http, event)
    except httpx.HTTPError as error:
        raise Problem(502, "sap-unreachable", f"SAP Sailing did not answer: {error}") from error
    if report.errors:
        raise Problem(
            502, "sap-refused", "The results could not be read from SAP.", errors=report.errors
        )
    changed = report.created["results"] + sum(
        n for what, n in report.updated.items() if what.startswith("results")
    )
    return SapResultsOut(results=changed, warnings=report.warnings + report.conflicts)
