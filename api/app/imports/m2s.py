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

**One Manage2Sail event can stand behind two here.** The league registers a weekend once,
with one class per league (`1.Segel-Bundesliga`, `2.Segel-Bundesliga`), where this site has
one act per league: ``regatta`` takes one class's entries and documents, and keys what it
links by event *and* class. The season's own event — its notice of race — goes to a
**series** (``to_series``), its entries ignored.

``recorded_transport`` replays answers recorded by ``scripts/record-m2s.py``, so the seed
imports without asking Manage2Sail (``app/seed_data/m2s-2026/``).
"""

from __future__ import annotations

import json
import re
from collections import Counter
from collections.abc import Mapping
from datetime import UTC, date, datetime
from pathlib import Path
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
from app.services.participation import team_name

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


def recorded_transport(folder: Path) -> httpx.MockTransport:
    """Manage2Sail's public answers as ``scripts/record-m2s.py`` recorded them: per event
    a folder with ``page.html`` (its title and bootstrap data), ``entries-<class>.json``
    and ``documents-<owner>.json``. What was not recorded is a 404."""

    def handler(request: httpx.Request) -> httpx.Response:
        parts = request.url.path.strip("/").split("/")
        if parts[:2] == ["en-US", "event"] and len(parts) == 3:
            name = f"{parts[2]}/page.html"
        elif parts[:2] == ["api", "event"] and len(parts) == 4 and parts[3] == "regattaentry":
            name = f"{parts[2]}/entries-{request.url.params.get('regattaId')}.json"
        elif parts[:2] == ["api", "event"] and len(parts) == 5 and parts[3] == "document":
            name = f"{parts[2]}/documents-{parts[4]}.json"
        else:
            return httpx.Response(404)
        path = folder / name
        if not path.is_file():
            return httpx.Response(404)
        return httpx.Response(200, content=path.read_bytes())

    return httpx.MockTransport(handler)


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
    regatta: str | None = None,
    to_series: str | None = None,
    with_entries: bool = True,
    log=print,
) -> Report:
    """One Manage2Sail event → one event here, its entries and its documents.

    ``links`` maps a Manage2Sail club key (``CODE|Club name``, as an unassigned line
    prints it) to the slug of a club here — the way out of an ambiguous code.
    ``regatta`` names the one class to take (its name at Manage2Sail); ``to_series`` puts
    the documents on that series' notice board instead, and takes no entries; nor does
    ``with_entries=False``, for an event whose teams came from elsewhere.
    """
    report = Report()
    key = f"{event_uuid}|{regatta}" if regatta else event_uuid
    log(f"Manage2Sail: event {key}")
    page = await client.event_page(event_uuid)
    classes = [c for c in page["classes"] if not c.get("IsCancelled")]
    if regatta is not None:
        names = [c.get("Name") for c in classes]
        classes = [c for c in classes if c.get("Name") == regatta]
        if not classes:
            report.errors.append(f"{event_uuid}: no class {regatta!r} — it has {names}")
            return report
    entries = [
        entry
        for cls in classes
        if to_series is None and with_entries and cls.get("HasEntries", True)
        for entry in await client.entries(event_uuid, cls["Id"])
    ]
    documents: dict[str, dict[str, Any]] = {}
    for owner in [event_uuid, *(c["Id"] for c in classes)]:
        for document in await client.documents(event_uuid, owner):
            documents.setdefault(document["Id"], document)

    async def work(session: AsyncSession, report: Report) -> None:
        # A document is keyed by its owner too when a class is chosen: the weekend's
        # event-wide documents reach both leagues' acts.
        prefix = f"{key}/" if regatta else ""
        if to_series is not None:
            series = (
                await session.execute(select(Series).where(Series.slug == to_series))
            ).scalar_one_or_none()
            if series is None:
                raise ValueError(f"No series {to_series!r} here")
            await _documents(session, report, {"series_id": series.id}, documents.values(), prefix)
            return
        event = await _event(
            session,
            report,
            key,
            page,
            to_event,
            series_slug,
            matchday,
            publish,
            team_count=len(entries),
        )
        await _links(session, report, links or {})
        await _entries(session, report, event, entries)
        await _documents(session, report, {"event_id": event.id}, documents.values(), prefix)

    return await run_import(sessions, SOURCE, key, work, report)


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
    """One M2S entry as one team of its club here — the club's next team when it enters
    several, as far as the event allows (Story VA-13)."""
    team = await linked(session, Team, SOURCE, entry["EntryId"])
    if team is not None:
        report.tally("unchanged", "event entries")
        return
    teams = list(
        (
            await session.execute(
                select(Team)
                .where(Team.club_id == club.id, Team.event_id == event.id)
                .order_by(Team.number)
            )
        ).scalars()
    )
    team = None
    for candidate in teams:
        if await link_key(session, Team, SOURCE, candidate.id) is None:
            team = candidate
            break
    if team is not None:
        report.tally("updated", "event entries (linked)")
    else:
        number = len(teams) + 1
        if number > event.teams_per_club:
            report.unassigned.append(
                f"{entry.get('TeamName')}: team {number} of {club.short_name} — the event "
                f"lets a club enter {event.teams_per_club}"
            )
            return
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
            name=team_name(club, number),
            number=number,
            club_id=club.id,
            series_id=event.series_id,
            event_id=event.id,
        )
        session.add(team)
        await session.flush()
        report.tally("created", "event entries")
    await link(session, team, SOURCE, entry["EntryId"])


async def _documents(
    session: AsyncSession, report: Report, owner: dict[str, int], documents, prefix: str
) -> None:
    """``owner`` is ``{"event_id": …}`` or ``{"series_id": …}`` — whose notice board."""
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
        row = await linked(session, EventDocument, SOURCE, prefix + document["Id"])
        if row is None:
            row = EventDocument(**owner, **values)
            session.add(row)
            await session.flush()
            await link(session, row, SOURCE, prefix + document["Id"])
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


FOLDER = Path(__file__).resolve().parent.parent / "seed_data" / "m2s-2026"


async def import_recorded_league(
    sessions: async_sessionmaker[AsyncSession],
    folder: Path = FOLDER,
    *,
    year: int = 2026,
    log=print,
) -> Report:
    """The 1. and 2. Liga's recorded Manage2Sail events onto what the TracTrac import made
    (``scripts/record-m2s.py``, ``events.json``): the season's documents onto each
    league's series, each weekend's class onto that league's act on those days, linked.

    **Documents only.** The acts' teams came from TracTrac, and Manage2Sail's entries do
    not name a club in a way to tie them by: its club code is shared (``KYC``), its sail
    number is whatever the team typed (``GER SV03``, ``HA 072``). A class nobody sailed
    that weekend (the 2. Liga on the 1. Liga's extra act) has no act and is passed over.
    """
    report = Report()
    index = json.loads((folder / "events.json").read_text("utf-8"))
    async with httpx.AsyncClient(transport=recorded_transport(folder)) as http:
        client = Manage2SailClient(http)
        for item in index:
            event_uuid = item["event"]
            page = await client.event_page(event_uuid)
            days = {_day(d) for d in page["days"]}
            for cls in page["classes"]:
                name = cls["Name"]
                slug = f"dsbl-{int(name.split('.', 1)[0])}-{year}"
                if item["kind"] == "season":
                    target = {"to_series": slug}
                else:
                    async with sessions() as session:
                        act = (
                            await session.execute(
                                select(Event.id)
                                .join(Series, Series.id == Event.series_id)
                                .where(Series.slug == slug, Event.starts_on.in_(days))
                            )
                        ).scalar_one_or_none()
                    if act is None:
                        if await client.entries(event_uuid, cls["Id"]):
                            report.warnings.append(f"{event_uuid} {name}: no act of {slug} then")
                        continue
                    target = {"to_event": act}
                part = await import_m2s(
                    sessions,
                    client,
                    event_uuid,
                    regatta=name,
                    with_entries=False,
                    log=log,
                    **target,
                )
                report.merge(part)
    return report
