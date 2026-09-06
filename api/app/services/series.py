"""Which year is currently in effect.

A series carries its year in its name ("DSBL 2026"). The *current* year is the most
recent one that isn't in the future — deliberately not simply the highest: "DSBL 2027" is
created back in 2026 already, so clubs can be assigned to it, and that mustn't switch the
public site over to a year nobody has registered for yet.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Series


async def aktueller_jahrgang(session: AsyncSession) -> int | None:
    """The year currently in effect."""
    jahr = datetime.now(UTC).year

    laufend = (
        await session.execute(
            select(Series.year)
            .where(Series.year.is_not(None), Series.year <= jahr)
            .order_by(Series.year.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if laufend is not None:
        return laufend

    # If only future years exist, the earliest one applies — better than none at all.
    return (
        await session.execute(
            select(Series.year)
            .where(Series.year.is_not(None))
            .order_by(Series.year)
            .limit(1)
        )
    ).scalar_one_or_none()


async def serien_des_jahrgangs(session: AsyncSession, jahr: int | None) -> list[Series]:
    """All series of a given year, ordered by level."""
    if jahr is None:
        return []
    return list(
        (
            await session.execute(
                select(Series)
                .where(Series.year == jahr)
                .order_by(Series.level.nulls_last(), Series.name)
            )
        ).scalars()
    )
