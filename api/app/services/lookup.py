"""Load one row by its primary key, or answer 404 with a typed problem.

Every router used to carry its own ``_event``/``_series``/``_club`` that did this — with a
different status text each, some of them localized, none of them a code a client could
map. One helper gives every "no such thing" the same shape: ``/errors/<thing>-not-found``,
where ``<thing>`` is the model's name in kebab-case (``Event`` → ``event-not-found``) —
the codes ``public.py`` and ``tracking.py`` already answered with.

``session.get``, not a select: a route guard (``require_on_event``) has often loaded the
row into this session already, and ``get`` answers from the identity map.
"""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.problems import Problem
from app.text import slugify


def not_found_code(model: type) -> str:
    """``Event`` → ``event-not-found``, ``PaymentRun`` → ``payment-run-not-found``."""
    return re.sub(r"(?<!^)(?=[A-Z])", "-", model.__name__).lower() + "-not-found"


async def get_or_404[Row](
    session: AsyncSession, model: type[Row], row_id: int, *, code: str | None = None
) -> Row:
    """The row of ``model`` with this id, or ``Problem(404, "<model>-not-found")``.

    ``code`` overrides the derived one where an existing contract says otherwise.
    """
    row = await session.get(model, row_id)
    if row is None:
        raise Problem(
            404,
            code or not_found_code(model),
            f"{model.__name__} {row_id} not found.",
            id=row_id,
        )
    return row


async def unique_slug(session: AsyncSession, model: type, base: str) -> str:
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
