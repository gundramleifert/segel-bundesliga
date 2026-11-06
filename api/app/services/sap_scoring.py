"""An event scored on SAP Sailing: its results fetched from there (Story WL-5).

The other half of `app/imports/sap_send.py` — **configuration flows to SAP, results flow
back** (CLAUDE.md). The import (`app/imports/sap.py`) reads the sent event's leaderboard
and puts each result on the team and boat of our draw, through the links the send stored;
the points are derived here as for every event, and SAP's own are only compared.

Two ways in: a race officer asks for it (``POST …/sap/results`` — also how a protest
decided at SAP weeks later reaches a final event), and :func:`poll`, which asks for every
live event on SAP every ``sap_poll_seconds`` while the server runs. One asker on the
server, never one per visitor against SAP. Every open page follows through the live
stream, published after the import's commit (B-5).
"""

from __future__ import annotations

import asyncio
import logging
from base64 import b64encode
from urllib.parse import quote

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings
from app.imports.common import USER_AGENT, Report
from app.imports.sap import SapClient, import_sap
from app.live import event_topic, hub
from app.models import Event, EventStatus, ResultsSource
from app.problems import Problem

logger = logging.getLogger(__name__)


def sap_http() -> httpx.AsyncClient:
    """The client every call to SAP goes through — the site's account where one is set.
    `app/routers/sap.py::sap_client` hands it out, so a test can put a simulated SAP there."""
    auth = (settings.sap_user, settings.sap_password or "") if settings.sap_user else None
    return httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT}, timeout=60, follow_redirects=True, auth=auth
    )


async def fetch_results(
    sessions: async_sessionmaker[AsyncSession], http: httpx.AsyncClient, event: Event
) -> Report:
    """Takes the event's results from its SAP leaderboard, then tells every open page."""
    assert event.sap_leaderboard is not None
    report = await import_sap(
        sessions,
        SapClient(http, settings.sap_base_url),
        names=[event.sap_leaderboard],
        log=lambda _: None,
    )
    hub.publish(event_topic(event.id))
    return report


def sap_configured() -> bool:
    """Whether this installation can write to SAP Sailing — its account is set (Story
    VA-14). Without one, an event can only be scored here."""
    return bool(settings.sap_user)


def results_from_sap(event: Event) -> bool:
    """Whether the event's results came from SAP Sailing — scored there (VA-14) or imported
    from it (A-14): both name the SAP leaderboard. Every page showing them credits SAP
    (Story B-21), which SAP requires for anything served from a server it hosts."""
    return event.sap_leaderboard is not None


def sap_leaderboard_url(event: Event) -> str | None:
    """The event's results on SAP's own site, on the server they came from — where the
    credit under the act leads (Story B-21). ``None`` for an event not from SAP."""
    if not event.sap_leaderboard or not event.sap_server:
        return None
    if event.sap_event_id:
        # The event page's Leaderboard tab; the regatta by its name in Base64, as SAP's
        # own links name it (`AbstractEventPlace.Tokenizer`).
        regatta = quote(b64encode(event.sap_leaderboard.encode()).decode())
        return (
            f"{event.sap_server}/gwt/Home.html#/regatta/leaderboard/"
            f":eventId={event.sap_event_id}&regattaId={regatta}"
        )
    # Without SAP's event id: the legacy leaderboard page, which needs only the name.
    return f"{event.sap_server}/gwt/Leaderboard.html?name={quote(event.sap_leaderboard)}"


def sap_viewer_url(event: Event) -> str | None:
    """Where the act's page shows SAP's live view of the event (Story B-20): its
    leaderboard on SAP's site, every team's races in the race colours — while SAP scores
    it. The server must list our domain in its frame-ancestors to be embedded; a link
    works regardless."""
    if event.results_source != ResultsSource.SAP:
        return None
    return sap_leaderboard_url(event)


def refuse_if_scored_on_sap(event: Event) -> None:
    """Result entry on an event scored on SAP: SAP is its one source of results, and two
    places to type a result would be two results (Story WL-5) — so here it is refused,
    with where results are entered instead."""
    if event.results_source == ResultsSource.SAP:
        raise Problem(
            409,
            "event-scored-on-sap",
            "This event is scored on SAP Sailing; results are entered there.",
            leaderboard=event.sap_leaderboard,
        )


async def live_events(session: AsyncSession) -> list[Event]:
    """The events whose results SAP is scoring right now."""
    return list(
        (
            await session.execute(
                select(Event).where(
                    Event.status == EventStatus.LIVE,
                    Event.results_source == ResultsSource.SAP,
                    Event.sap_leaderboard.is_not(None),
                )
            )
        ).scalars()
    )


async def poll_once(sessions: async_sessionmaker[AsyncSession], http: httpx.AsyncClient) -> None:
    async with sessions() as session:
        events = await live_events(session)
    for event in events:
        try:
            report = await fetch_results(sessions, http, event)
        except httpx.HTTPError as error:
            # SAP unreachable: the last results stay, and the next round tries again.
            logger.warning("SAP results for %s: %s", event.slug, error)
            continue
        if report.errors or report.conflicts:
            logger.warning("SAP results for %s:\n%s", event.slug, report.render())


async def poll(sessions: async_sessionmaker[AsyncSession]) -> None:
    """Runs while the server does: every ``sap_poll_seconds`` the live events on SAP."""
    async with sap_http() as http:
        while True:
            await asyncio.sleep(settings.sap_poll_seconds)
            try:
                await poll_once(sessions, http)
            except Exception:  # one bad round must not end the polling
                logger.exception("SAP results polling")
