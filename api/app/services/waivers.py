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

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Event, Sailor, Series, WaiverConfirmation, WaiverText

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
        await session.execute(
            select(WaiverText).order_by(WaiverText.version.desc()).limit(1)
        )
    ).scalar_one_or_none()


# ---------------------------------------------------------------- Coverage


# Why a sailor is not cleared — a stable token the UI can translate and style.
STATUS_CLEARED = "cleared"
STATUS_NOT_REQUIRED = "not_required"
STATUS_MISSING = "missing"
STATUS_OUTDATED = "version_outdated"
STATUS_GUARDIAN_UNSIGNED = "guardian_signature_missing"
STATUS_BIRTH_DATE_UNKNOWN = "birth_date_unknown"


@dataclass
class SailorWaiver:
    sailor_id: int
    status: str
    required_version: int | None
    minor: bool | None
    confirmed_version: int | None = None
    confirmed_at: datetime | None = None
    method: str | None = None


def _judge(
    *,
    sailor_id: int,
    minor: bool | None,
    required: WaiverText | None,
    confirmations: list[WaiverConfirmation],
) -> SailorWaiver:
    if required is None:
        return SailorWaiver(sailor_id, STATUS_NOT_REQUIRED, None, minor)

    base = dict(sailor_id=sailor_id, required_version=required.version, minor=minor)

    # The most recent confirmation of *any* version wins as "what they last did", but only
    # one of the current version can clear them.
    latest = max(confirmations, key=lambda c: c.confirmed_at, default=None)
    for_current = [c for c in confirmations if c.waiver_text_id == required.id]

    if not for_current:
        if latest is not None:
            return SailorWaiver(
                **base,
                status=STATUS_OUTDATED,
                confirmed_version=latest.waiver_text.version,
                confirmed_at=latest.confirmed_at,
                method=latest.method,
            )
        return SailorWaiver(**base, status=STATUS_MISSING)

    chosen = max(for_current, key=lambda c: c.confirmed_at)
    seen = dict(
        confirmed_version=required.version,
        confirmed_at=chosen.confirmed_at,
        method=chosen.method,
    )

    if minor is None:
        return SailorWaiver(**base, **seen, status=STATUS_BIRTH_DATE_UNKNOWN)
    if minor and not any(c.is_guardian_signed for c in for_current):
        return SailorWaiver(**base, **seen, status=STATUS_GUARDIAN_UNSIGNED)
    return SailorWaiver(**base, **seen, status=STATUS_CLEARED)


async def event_waiver_status(
    session: AsyncSession, event: Event, sailor_ids: list[int]
) -> dict[int, SailorWaiver]:
    """Clearance for each of ``sailor_ids`` for one event.

    A confirmation counts if it is scoped to this event, or to the event's series.
    """
    required = await current_waiver_text(session)
    if not sailor_ids:
        return {}

    ref = event_reference_date(event)
    ages = dict(
        (
            await session.execute(
                select(Sailor.id, Sailor.birth_date).where(Sailor.id.in_(sailor_ids))
            )
        ).all()
    )

    scope = WaiverConfirmation.event_id == event.id
    if event.series_id is not None:
        scope = scope | (WaiverConfirmation.series_id == event.series_id)

    rows = (
        await session.execute(
            select(WaiverConfirmation)
            .options(selectinload(WaiverConfirmation.waiver_text))
            .where(WaiverConfirmation.sailor_id.in_(sailor_ids), scope)
        )
    ).scalars().all()
    by_sailor: dict[int, list[WaiverConfirmation]] = {}
    for row in rows:
        by_sailor.setdefault(row.sailor_id, []).append(row)

    return {
        sid: _judge(
            sailor_id=sid,
            minor=is_minor(ages.get(sid), ref),
            required=required,
            confirmations=by_sailor.get(sid, []),
        )
        for sid in sailor_ids
    }
