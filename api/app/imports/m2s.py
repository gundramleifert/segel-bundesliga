"""An event's entries and notice-board documents from Manage2Sail (Story A-14).

Reads only what the public event page reads (``docs/manage2sail.md`` §3) — no access
token: the event page itself (its title, and the days and classes it bootstraps as
``window.boostrapedResourceData``), the entry list per class, and the document list.
Documents are **linked**, not copied (``EventDocument``).

**A club code is not unique at Manage2Sail.** One entry list of the Junioren-Liga 2026
has `KYC` for both the Kieler and the Konstanzer Yacht-Club, and `BYC` for the Bayerischer
and the Berliner. So a club's key here is code **and** M2S's own club name, and a code two
clubs share is never used to find a club this site already has — those entries are
reported as unassigned until ``--link`` says which club each is.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from collections.abc import Mapping
from datetime import UTC, date, datetime
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.imports.common import (
    Report,
    link,
    link_key,
    linked,
    resolve_club,
    run_import,
    unique_slug,
)
from app.models import (
    Club,
    Event,
    EventDocument,
    EventDocumentKind,
    Series,
    Source,
    Team,
)

SOURCE = Source.MANAGE2SAIL
BASE_URL = "https://www.manage2sail.com"

_BOOTSTRAP = re.compile(r"window\.boostrapedResourceData\s*=\s*(\{.*?\});\s*$", re.S | re.M)
_TITLE = re.compile(r"<title>\s*(.*?)\s*(?:manage2sail)?\s*</title>", re.S | re.I)


def document_kind(title: str) -> EventDocumentKind:
    """What a document is, by its title — organizers name their files, there is no field.

    Numbered notices first: `NO 1_ACT 2_Change SI` is a notice that amends the SI.
    `(?<![a-z])` instead of `\\b`, because `_` is a word character and the titles are
    full of them (`20260506_SI_DJSL`).
    """
    t = title.lower()
    if re.search(r"ausschreibung|notice of race|(?<![a-z])nor(?![a-z])", t):
        return EventDocumentKind.NOTICE_OF_RACE
    if re.search(r"(?<![a-z])no\s*\d|bekanntmachung|notice to competitors|amendment|änderung", t):
        return EventDocumentKind.NOTICE
    if re.search(r"(?<![a-z])si(?![a-z])|segelanweisung|sailing instructions", t):
        return EventDocumentKind.SAILING_INSTRUCTIONS
    return EventDocumentKind.OTHER


def document_url(document_id: str) -> str:
    return f"{BASE_URL}/en-US/Home/DownloadDocument/{document_id}"


class Manage2SailClient:
    def __init__(self, http: httpx.AsyncClient, base_url: str = BASE_URL):
        self._http = http
        self._base = base_url.rstrip("/")

    async def _get(self, path: str, **params: str) -> httpx.Response:
        response = await self._http.get(f"{self._base}/{path}", params=params or None)
        response.raise_for_status()
        return response

    async def event_page(self, event_id: str) -> dict[str, Any]:
        """Title, days and classes — what the page bootstraps into its own script."""
        html = (await self._get(f"en-US/event/{event_id}")).text
        boot = _BOOTSTRAP.search(html)
        if boot is None:
            raise ValueError(f"Manage2Sail event {event_id}: no event data on its page")
        data = json.loads(boot.group(1))
        title = _TITLE.search(html)
        return {
            "title": title.group(1).strip() if title else None,
            "days": (data.get("EventData") or {}).get("EventDays") or [],
            "classes": data.get("Regatta") or [],
        }

    async def entries(self, event_id: str, class_id: str) -> list[dict[str, Any]]:
        response = await self._get(f"api/event/{event_id}/regattaentry", regattaId=class_id)
        return response.json().get("Entries") or []

    async def documents(self, event_id: str, owner_id: str) -> list[dict[str, Any]]:
        """The documents of the event (``owner_id`` = the event) or of one class."""
        return (await self._get(f"api/event/{event_id}/document/{owner_id}")).json() or []


async def import_m2s(
    sessions: async_sessionmaker[AsyncSession],
    client: Manage2SailClient,
    event_uuid: str,
    *,
    to_event: int | None = None,
    series_slug: str | None = None,
    matchday: int | None = None,
    links: Mapping[str, str] | None = None,
    publish: bool = False,
    log=print,
) -> Report:
    """One Manage2Sail event → one event here, its entries and its documents.

    ``links`` maps a Manage2Sail club key (``CODE|Club name``, as an unassigned line
    prints it) to the slug of a club here — the way out of an ambiguous code.
    """
    report = Report()
    log(f"Manage2Sail: event {event_uuid}")
    page = await client.event_page(event_uuid)
    classes = [c for c in page["classes"] if not c.get("IsCancelled")]
    entries = [
        entry
        for cls in classes
        if cls.get("HasEntries", True)
        for entry in await client.entries(event_uuid, cls["Id"])
    ]
    documents: dict[str, dict[str, Any]] = {}
    for owner in [event_uuid, *(c["Id"] for c in classes)]:
        for document in await client.documents(event_uuid, owner):
            documents.setdefault(document["Id"], document)

    async def work(session: AsyncSession, report: Report) -> None:
        event = await _event(
            session,
            report,
            event_uuid,
            page,
            to_event,
            series_slug,
            matchday,
            publish,
            team_count=len(entries),
        )
        await _links(session, report, links or {})
        await _entries(session, report, event, entries)
        await _documents(session, report, event, documents.values())

    return await run_import(sessions, SOURCE, event_uuid, work, report)


def _same(stored: Any, value: Any) -> bool:
    """Equal, reading a moment SQLite gave back without its offset as UTC."""
    if isinstance(stored, datetime) and isinstance(value, datetime):
        if stored.tzinfo is None:
            stored = stored.replace(tzinfo=UTC)
        return stored == value
    return stored == value


def _day(value: str) -> date:
    return datetime.fromisoformat(value).date()


async def _event(
    session: AsyncSession,
    report: Report,
    event_uuid: str,
    page: dict[str, Any],
    to_event: int | None,
    series_slug: str | None,
    matchday: int | None,
    publish: bool,
    *,
    team_count: int,
) -> Event:
    event = await linked(session, Event, SOURCE, event_uuid)
    if to_event is not None:
        target = await session.get(Event, to_event)
        if target is None:
            raise ValueError(f"No event {to_event} here")
        if event is not None and event.id != target.id:
            raise ValueError(
                f"Manage2Sail event {event_uuid} is already linked to event {event.id} here"
            )
        if event is None:
            if await link_key(session, Event, SOURCE, target.id) is not None:
                raise ValueError(f"Event {to_event} is already linked to another M2S event")
            await link(session, target, SOURCE, event_uuid)
            report.tally("updated", "events (linked)")
        else:
            report.tally("unchanged", "events")
        event = target
    elif event is not None:
        report.tally("unchanged", "events")
    else:
        series = None
        if series_slug:
            series = (
                await session.execute(select(Series).where(Series.slug == series_slug))
            ).scalar_one_or_none()
            if series is None:
                raise ValueError(f"No series {series_slug!r} here")
        days = sorted(_day(d) for d in page["days"])
        title = page["title"] or f"Manage2Sail {event_uuid}"
        event = Event(
            slug=await unique_slug(session, Event, title),
            title=title,
            series_id=series.id if series else None,
            matchday=matchday if series else None,
            starts_on=days[0] if days else None,
            ends_on=days[-1] if days else None,
            team_count=team_count or 18,
            published=publish,
        )
        session.add(event)
        await session.flush()
        await link(session, event, SOURCE, event_uuid)
        report.tally("created", "events")
    if publish and not event.published:
        event.published = True
        report.tally("updated", "events (published)")
    return event


async def _links(session: AsyncSession, report: Report, links: Mapping[str, str]) -> None:
    """``--link KEY=slug``: tie a Manage2Sail club key to a club here, by hand."""
    for key, slug in links.items():
        club = (await session.execute(select(Club).where(Club.slug == slug))).scalar_one_or_none()
        if club is None:
            report.errors.append(f"--link {key}={slug}: no club {slug!r} here")
            continue
        current = await linked(session, Club, SOURCE, key)
        if current is not None:
            if current.id != club.id:
                report.errors.append(f"--link {key}: already linked to {current.slug}")
            continue
        if await link_key(session, Club, SOURCE, club.id) is not None:
            report.errors.append(f"--link {key}={slug}: {slug} is linked to another M2S club")
            continue
        await link(session, club, SOURCE, key)
        report.tally("updated", "clubs (linked)")


def club_key(entry: dict[str, Any]) -> str:
    return (
        f"{(entry.get('ClubCode') or '').strip().upper()}|{(entry.get('ClubName') or '').strip()}"
    )


async def _entries(
    session: AsyncSession, report: Report, event: Event, entries: list[dict[str, Any]]
) -> None:
    # Which codes name more than one club in this list — those are never matched by code.
    clubs_per_code = Counter(
        code for code, _ in {tuple(club_key(e).split("|", 1)) for e in entries}
    )
    for entry in entries:
        code = (entry.get("ClubCode") or "").strip()
        name = (entry.get("ClubName") or "").strip()
        label = f"{entry.get('TeamName') or entry.get('SailNumber')} ({club_key(entry)})"
        if not code:
            report.unassigned.append(f"{label}: no club code at Manage2Sail")
            continue
        key = club_key(entry)
        ambiguous = clubs_per_code[code.upper()] > 1
        if ambiguous and await linked(session, Club, SOURCE, key) is None:
            report.unassigned.append(
                f"{label}: the code {code} names several clubs at Manage2Sail — "
                f'tie it with --link "{key}=<club slug>"'
            )
            continue
        club = await resolve_club(
            session,
            report,
            source=SOURCE,
            key=key,
            code=code,
            name=name or code,
            match_by_code=not ambiguous,
        )
        await _team(session, report, club, event, entry)


async def _team(
    session: AsyncSession, report: Report, club: Club, event: Event, entry: dict[str, Any]
) -> None:
    team = await linked(session, Team, SOURCE, entry["EntryId"])
    if team is not None:
        report.tally("unchanged", "event entries")
        return
    team = (
        await session.execute(
            select(Team).where(Team.club_id == club.id, Team.event_id == event.id)
        )
    ).scalar_one_or_none()
    if team is not None:
        if await link_key(session, Team, SOURCE, team.id) is not None:
            # A club enters an event once here; M2S allows a second boat of the same club.
            report.unassigned.append(
                f"{entry.get('TeamName')}: a second entry of {club.short_name} — "
                "a club enters an event once here"
            )
            return
        report.tally("updated", "event entries (linked)")
    else:
        if event.series_id is not None:
            registration = (
                await session.execute(
                    select(Team).where(
                        Team.club_id == club.id,
                        Team.series_id == event.series_id,
                        Team.event_id.is_(None),
                    )
                )
            ).scalar_one_or_none()
            if registration is None:
                session.add(Team(name=club.short_name, club_id=club.id, series_id=event.series_id))
                report.tally("created", "series registrations")
        team = Team(
            name=club.short_name,
            club_id=club.id,
            series_id=event.series_id,
            event_id=event.id,
        )
        session.add(team)
        await session.flush()
        report.tally("created", "event entries")
    await link(session, team, SOURCE, entry["EntryId"])


async def _documents(session: AsyncSession, report: Report, event: Event, documents) -> None:
    for document in documents:
        title = (document.get("Title") or "").strip() or document["Id"]
        values = {
            "title": title[:300],
            "kind": document_kind(title),
            "url": document_url(document["Id"]),
            "extension": (document.get("Extension") or "").lower()[:16] or None,
            # In UTC: SQLite keeps a moment's wall time and drops its offset.
            "published_at": (
                datetime.fromisoformat(document["PublishedDate"]).astimezone(UTC)
                if document.get("PublishedDate")
                else None
            ),
            "position": int(document.get("Order") or 0),
        }
        row = await linked(session, EventDocument, SOURCE, document["Id"])
        if row is None:
            row = EventDocument(event_id=event.id, **values)
            session.add(row)
            await session.flush()
            await link(session, row, SOURCE, document["Id"])
            report.tally("created", "documents")
            continue
        changed = {
            field: value
            for field, value in values.items()
            if field != "kind" and not _same(getattr(row, field), value)
        }
        # The kind is guessed from the title; once someone here corrected it, it stays.
        if "title" in changed:
            changed["kind"] = values["kind"]
        for field, value in changed.items():
            setattr(row, field, value)
        report.tally("updated" if changed else "unchanged", "documents")
