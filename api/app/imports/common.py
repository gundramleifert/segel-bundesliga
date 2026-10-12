"""What both importers share: the run's report, the `ExternalId` lookups, the club key.

Matching is by `ExternalId`, never by name (Domain decisions): SAP Sailing, Manage2Sail and
this site spell every club differently. What a source *does* share with us is the club's
**code** — `HSC`, `NRV`, `VSaW` — so a code is how a club this site already has is found
the first time; from then on the `ExternalId` row is the link.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Club, ExternalId, ImportRun
from app.models.base import Base
from app.text import slugify

USER_AGENT = "dsl-website-import/1.0 (+https://sbl-web.onrender.com)"


@dataclass
class Report:
    """What one run did — printed at the end and kept in ``ImportRun.summary``."""

    created: Counter[str] = field(default_factory=Counter)
    updated: Counter[str] = field(default_factory=Counter)
    unchanged: Counter[str] = field(default_factory=Counter)
    # A result recorded here that the source disagrees with: kept, never overwritten.
    conflicts: list[str] = field(default_factory=list)
    # Rows the source has that could not be tied to anything here.
    unassigned: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def tally(self, kind: str, what: str, n: int = 1) -> None:
        {"created": self.created, "updated": self.updated, "unchanged": self.unchanged}[kind][
            what
        ] += n

    def as_json(self) -> dict[str, Any]:
        return {
            "created": dict(self.created),
            "updated": dict(self.updated),
            "unchanged": dict(self.unchanged),
            "conflicts": self.conflicts,
            "unassigned": self.unassigned,
            "warnings": self.warnings,
            "errors": self.errors,
        }

    def render(self) -> str:
        def counts(counter: Counter[str]) -> str:
            return ", ".join(f"{n} {what}" for what, n in sorted(counter.items())) or "nothing"

        lines = [
            f"created:   {counts(self.created)}",
            f"updated:   {counts(self.updated)}",
            f"unchanged: {counts(self.unchanged)}",
        ]
        for title, items in (
            ("conflicts (kept ours)", self.conflicts),
            ("unassigned", self.unassigned),
            ("warnings", self.warnings),
            ("errors", self.errors),
        ):
            if items:
                lines.append(f"{title}: {len(items)}")
                lines.extend(f"  - {item}" for item in items)
        return "\n".join(lines)


async def start_run(session: AsyncSession, source: str, reference: str) -> ImportRun:
    run = ImportRun(source=source, reference=reference[:200], started_at=datetime.now(UTC))
    session.add(run)
    await session.flush()
    return run


def finish_run(run: ImportRun, report: Report) -> None:
    run.finished_at = datetime.now(UTC)
    run.ok = not report.errors
    run.summary = report.as_json()


async def linked[M: Base](session: AsyncSession, model: type[M], source: str, key: str) -> M | None:
    """The row the source's ``key`` is linked to, if any."""
    entity_id = (
        await session.execute(
            select(ExternalId.entity_id).where(
                ExternalId.source == source,
                ExternalId.entity_type == model.__tablename__,
                ExternalId.external_key == key,
            )
        )
    ).scalar_one_or_none()
    return None if entity_id is None else await session.get(model, entity_id)


async def link_key(
    session: AsyncSession, model: type[Base], source: str, entity_id: int
) -> str | None:
    """The source's key for one of our rows — the reverse of ``linked``."""
    return (
        await session.execute(
            select(ExternalId.external_key).where(
                ExternalId.source == source,
                ExternalId.entity_type == model.__tablename__,
                ExternalId.entity_id == entity_id,
            )
        )
    ).scalar_one_or_none()


async def link(session: AsyncSession, row: Base, source: str, key: str) -> None:
    session.add(
        ExternalId(
            source=source,
            entity_type=row.__tablename__,
            entity_id=row.id,  # type: ignore[attr-defined]
            external_key=key,
        )
    )
    await session.flush()


async def unique_slug(session: AsyncSession, model: type[Base], base: str) -> str:
    """``base``, or ``base-2``, ``base-3`` … — whichever no row of ``model`` has yet."""
    slug_column = model.slug  # type: ignore[attr-defined]
    base = slugify(base)
    taken = set(
        (await session.execute(select(slug_column).where(slug_column.like(f"{base}%")))).scalars()
    )
    if base not in taken:
        return base
    n = 2
    while f"{base}-{n}" in taken:
        n += 1
    return f"{base}-{n}"


async def club_by_code(session: AsyncSession, code: str, source: str) -> Club | None:
    """The one club here whose short name **is** this code and that no other key of this
    source claims yet — the first-run bridge to a club this site already has.

    Case-insensitive (`VSaW` here, `VSAW` at Manage2Sail) — compared in Python, because
    SQLite's `lower()` folds ASCII only and would never find `BYCÜ` from `BYCü`, where
    Postgres would. Two clubs with the same code here means nothing is guessed.
    """
    wanted = code.strip().casefold()
    candidates = [
        club
        for club in (await session.execute(select(Club))).scalars()
        if club.short_name.strip().casefold() == wanted
    ]
    if len(candidates) != 1:
        return None
    club = candidates[0]
    if await link_key(session, Club, source, club.id) is not None:
        return None
    return club


async def resolve_club(
    session: AsyncSession,
    report: Report,
    *,
    source: str,
    key: str,
    code: str,
    name: str,
    match_by_code: bool = True,
) -> Club:
    """The club for this source key: linked before, else found by its code, else new."""
    club = await linked(session, Club, source, key)
    if club is not None:
        report.tally("unchanged", "clubs")
        return club
    club = await club_by_code(session, code, source) if match_by_code else None
    if club is not None:
        await link(session, club, source, key)
        report.tally("updated", "clubs (linked)")
        return club
    club = Club(
        slug=await unique_slug(session, Club, code),
        name=name.strip() or code,
        short_name=code.strip()[:32],
    )
    session.add(club)
    await session.flush()
    await link(session, club, source, key)
    report.tally("created", "clubs")
    return club
