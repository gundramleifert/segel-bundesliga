"""Liability-waiver logic — Stories S-2, VA-2, VA-5.

Kept out of the router because two questions need answering in more than one place:

* **Which version is in force?** The highest ``WaiverText.version``.
* **Is a sailor cleared for an event?** They have a confirmation of that version, scoped
  to the event *or* to its series — and if they are a minor on the reference date, that
  confirmation must be signed by a guardian.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from typing import NamedTuple

from sqlalchemy import ColumnElement, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    Event,
    Person,
    Series,
    Team,
    TeamMembership,
    TeamStatus,
    WaiverConfirmation,
    WaiverMethod,
    WaiverText,
)
from app.services import uploads

MAJORITY_AGE = 18


def age_on(birth_date: date | None, on: date) -> int | None:
    """Full years old on a given date, or ``None`` if the birth date is unknown."""
    if birth_date is None:
        return None
    had_birthday = (on.month, on.day) >= (birth_date.month, birth_date.day)
    return on.year - birth_date.year - (0 if had_birthday else 1)


def is_minor(birth_date: date | None, on: date) -> bool | None:
    years = age_on(birth_date, on)
    return None if years is None else years < MAJORITY_AGE


def series_reference_date(series: Series) -> date:
    """The date a sailor's age is judged against for a series confirmation.

    The series start if known; failing that 1 January of its year; failing that today —
    a series with neither a date nor a year is barely a real competition anyway.
    """
    if series.starts_on is not None:
        return series.starts_on
    if series.year is not None:
        return date(series.year, 1, 1)
    return date.today()


def event_reference_date(event: Event) -> date:
    """The date an age is judged against for an event confirmation.

    The event's start if it has one — an event may be saved before its date is settled
    (Story VA-8) — otherwise today, the same fallback a dateless series gets. Deliberately
    not the series' date: the relationship isn't loaded here, and an age judged a few
    weeks off is a better answer than a lazy load in an async session.
    """
    return event.starts_on if event.starts_on is not None else date.today()


async def current_waiver_text(session: AsyncSession) -> WaiverText | None:
    """The version in force — the highest one. ``None`` if none has been published."""
    return (
        await session.execute(select(WaiverText).order_by(WaiverText.version.desc()).limit(1))
    ).scalar_one_or_none()


# ---------------------------------------------------------------- Coverage


class WaiverStatus(StrEnum):
    """Where a sailor stands with the waiver — and, when not cleared, why: a stable token
    the UI can translate and style."""

    CLEARED = "cleared"
    NOT_REQUIRED = "not_required"
    MISSING = "missing"
    OUTDATED = "version_outdated"
    GUARDIAN_UNSIGNED = "guardian_signature_missing"
    BIRTH_DATE_UNKNOWN = "birth_date_unknown"


@dataclass
class PersonWaiver:
    person_id: int
    status: WaiverStatus
    required_version: int | None
    minor: bool | None
    confirmed_version: int | None = None
    confirmed_at: datetime | None = None
    method: WaiverMethod | None = None
    # The row the status was read from — what a scan upload completes, and what the
    # scan endpoint is addressed by. ``None`` when nothing was ever confirmed.
    confirmation_id: int | None = None
    guardian_name: str | None = None
    scan_available: bool = False


def _judge(
    *,
    person_id: int,
    minor: bool | None,
    required: WaiverText | None,
    confirmations: list[WaiverConfirmation],
) -> PersonWaiver:
    if required is None:
        return PersonWaiver(person_id, WaiverStatus.NOT_REQUIRED, None, minor)

    base = dict(person_id=person_id, required_version=required.version, minor=minor)

    # The most recent confirmation of *any* version wins as "what they last did", but only
    # one of the current version can clear them.
    latest = max(confirmations, key=lambda c: c.confirmed_at, default=None)
    for_current = [c for c in confirmations if c.waiver_text_id == required.id]

    if not for_current:
        if latest is not None:
            return PersonWaiver(
                **base,
                status=WaiverStatus.OUTDATED,
                confirmed_version=latest.waiver_text.version,
                confirmed_at=latest.confirmed_at,
                method=latest.method,
                confirmation_id=latest.id,
                guardian_name=latest.guardian_name,
                scan_available=has_scan(latest.guardian_signature_ref),
            )
        return PersonWaiver(**base, status=WaiverStatus.MISSING)

    chosen = max(for_current, key=lambda c: c.confirmed_at)
    seen = dict(
        confirmed_version=required.version,
        confirmed_at=chosen.confirmed_at,
        method=chosen.method,
        confirmation_id=chosen.id,
        guardian_name=chosen.guardian_name,
        scan_available=has_scan(chosen.guardian_signature_ref),
    )

    if minor is None:
        return PersonWaiver(**base, **seen, status=WaiverStatus.BIRTH_DATE_UNKNOWN)
    if minor and not any(c.is_guardian_signed for c in for_current):
        return PersonWaiver(**base, **seen, status=WaiverStatus.GUARDIAN_UNSIGNED)
    return PersonWaiver(**base, **seen, status=WaiverStatus.CLEARED)


class _Unread:
    """The default of ``required``: distinct from ``None``, which means "none published"."""


UNREAD = _Unread()


async def event_waiver_status(
    session: AsyncSession,
    event: Event,
    person_ids: list[int],
    required: WaiverText | None | _Unread = UNREAD,
) -> dict[int, PersonWaiver]:
    """Clearance for each of ``person_ids`` for one event.

    A confirmation counts if it is scoped to this event, or to the event's series. Pass
    ``required`` when the caller has already read the waiver text in force — ``None``
    included, so a site with no text published is not asked again per event.
    """
    if isinstance(required, _Unread):
        required = await current_waiver_text(session)
    if not person_ids:
        return {}

    ref = event_reference_date(event)
    ages = dict(
        (
            await session.execute(
                select(Person.id, Person.birth_date).where(Person.id.in_(person_ids))
            )
        ).all()
    )

    by_person = await _confirmations(
        session, person_ids, Competition.of_event(event).confirmation_filter()
    )

    return {
        sid: _judge(
            person_id=sid,
            minor=is_minor(ages.get(sid), ref),
            required=required,
            confirmations=by_person.get(sid, []),
        )
        for sid in person_ids
    }


# ---------------------------------------------------------------- What must I sign?


@dataclass
class Competition:
    """One thing a sailor has to sign for: a series, or an event that belongs to none."""

    scope: str
    scope_id: int
    name: str
    reference_date: date
    series: Series | None = None
    event: Event | None = None

    @classmethod
    def of_series(cls, series: Series) -> Competition:
        return cls("series", series.id, series.name, series_reference_date(series), series=series)

    @classmethod
    def of_event(cls, event: Event) -> Competition:
        return cls("event", event.id, event.title, event_reference_date(event), event=event)

    def confirmation_filter(self) -> ColumnElement[bool]:
        """The confirmations that count here, as SQL: a series' own, or an event's own
        and its series' (an event confirmation never clears a series)."""
        if self.series is not None:
            return WaiverConfirmation.series_id == self.series.id
        assert self.event is not None
        scope = WaiverConfirmation.event_id == self.event.id
        if self.event.series_id is not None:
            scope = scope | (WaiverConfirmation.series_id == self.event.series_id)
        return scope

    def covers(self, row: WaiverConfirmation) -> bool:
        """:meth:`confirmation_filter` in Python, for confirmations already loaded."""
        if self.series is not None:
            return row.series_id == self.series.id
        assert self.event is not None
        return row.event_id == self.event.id or (
            self.event.series_id is not None and row.series_id == self.event.series_id
        )


class CompetitionWaiver(NamedTuple):
    competition: Competition
    status: PersonWaiver


async def _confirmations(
    session: AsyncSession, person_ids: list[int], scope: ColumnElement[bool]
) -> dict[int, list[WaiverConfirmation]]:
    rows = (
        (
            await session.execute(
                select(WaiverConfirmation)
                .options(selectinload(WaiverConfirmation.waiver_text))
                .where(WaiverConfirmation.person_id.in_(person_ids), scope)
            )
        )
        .scalars()
        .all()
    )
    by_person: dict[int, list[WaiverConfirmation]] = {}
    for row in rows:
        by_person.setdefault(row.person_id, []).append(row)
    return by_person


async def competition_status(
    session: AsyncSession,
    competition: Competition,
    people: list[Person],
    required: WaiverText | None,
) -> dict[int, PersonWaiver]:
    """Clearance of many sailors for one competition, in one query.

    ``required`` is the waiver text in force, read once by the caller for the whole
    request (``None``: nothing published, nobody needs to sign). A series counts only its
    own confirmations; an event its own and its series'.
    """
    if not people:
        return {}
    by_person = await _confirmations(
        session, [s.id for s in people], competition.confirmation_filter()
    )
    return {
        person.id: _judge(
            person_id=person.id,
            minor=is_minor(person.birth_date, competition.reference_date),
            required=required,
            confirmations=by_person.get(person.id, []),
        )
        for person in people
    }


async def person_waivers(
    session: AsyncSession, person: Person, required: WaiverText | None
) -> list[CompetitionWaiver]:
    """Every competition the sailor must sign for, with its status — the account page
    (S-1), a guardian's page (S-8) and "mine" (Z-8). One query for the competitions' rows
    and one for all of the sailor's confirmations, however many competitions."""
    competitions = await person_competitions(session, person)
    if not competitions:
        return []
    rows = (
        await _confirmations(
            session, [person.id], or_(*(c.confirmation_filter() for c in competitions))
        )
    ).get(person.id, [])
    return [
        CompetitionWaiver(
            competition,
            _judge(
                person_id=person.id,
                minor=is_minor(person.birth_date, competition.reference_date),
                required=required,
                confirmations=[r for r in rows if competition.covers(r)],
            ),
        )
        for competition in competitions
    ]


async def person_competitions(session: AsyncSession, person: Person) -> list[Competition]:
    """Every competition this sailor is entered in — the list on their account page.

    Series squads first (``Team.event_id`` empty, Story V-1), newest year first, then
    stand-alone events they are entered in directly. An event *within* a series is never
    listed on its own: the series confirmation covers it, and listing both would ask the
    same person for the same signature twice.
    """
    memberships = (
        select(Team)
        .join(TeamMembership, TeamMembership.team_id == Team.id)
        .where(TeamMembership.person_id == person.id, Team.status == TeamStatus.ACCEPTED)
    )
    series_rows = (
        (
            await session.execute(
                select(Series)
                .where(
                    Series.id.in_(
                        memberships.with_only_columns(Team.series_id).where(Team.event_id.is_(None))
                    )
                )
                .order_by(Series.year.desc(), Series.name)
            )
        )
        .scalars()
        .all()
    )
    event_rows = (
        (
            await session.execute(
                select(Event)
                .where(
                    Event.id.in_(
                        memberships.with_only_columns(Team.event_id).where(Team.series_id.is_(None))
                    )
                )
                .order_by(Event.starts_on.desc(), Event.title)
            )
        )
        .scalars()
        .all()
    )
    return [Competition.of_series(s) for s in series_rows] + [
        Competition.of_event(e) for e in event_rows
    ]


# ---------------------------------------------------------------- The scan on file

# A `guardian_signature_ref` that names an uploaded file rather than a paper folder.
SCAN_REF_PREFIX = "upload:"
# The scans' prefix in the private upload store, `waivers/`.
SCANS = "waivers"


def scan_name(ref: str | None) -> str | None:
    """The uploaded scan's stored name, or ``None`` when the reference is a note or absent.

    The name is a UUID the confirmation row alone knows — a client never learns it, and
    the only way to the bytes is `GET /api/waiver/confirmations/{id}/scan`, which checks
    who is asking and logs the look (Story S-1).
    """
    if not ref or not ref.startswith(SCAN_REF_PREFIX):
        return None
    return ref[len(SCAN_REF_PREFIX) :]


def scan_exists(ref: str | None) -> bool:
    """Whether the scan is on file — ``False`` for a row whose file was cleaned up, so it
    reads as "no scan" instead of a 500."""
    return uploads.exists(SCANS, scan_name(ref))


def has_scan(ref: str | None) -> bool:
    """Whether the reference names an uploaded scan — read off the row, no disk access,
    so judging a club's whole squad touches no file. A file lost since reads as
    available here and answers 404 where it is served (``scan_exists``)."""
    return bool(ref) and ref.startswith(SCAN_REF_PREFIX)


def scan_media_type(ref: str) -> str:
    suffix = ref.rsplit(".", 1)[-1]
    return next(
        (m for m, ext in uploads.MEDIA_TYPES.items() if ext == suffix), "application/octet-stream"
    )


def store_scan(raw: bytes, media_type: str) -> str:
    """Writes a validated scan and returns its ``guardian_signature_ref``."""
    return SCAN_REF_PREFIX + uploads.store(SCANS, raw, media_type)


def discard_scan(ref: str | None) -> None:
    uploads.discard(SCANS, scan_name(ref))
