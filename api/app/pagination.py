"""One way to ask for part of a list, and one shape to answer with — Story A-13.

Every list endpoint that grows with the database takes the same three parameters and
answers with the same envelope, so that a screen can page, sort and count without knowing
which endpoint it is talking to. Lists bounded by their own subject — an event's
participants, its boats, a club's members — stay plain arrays: they have no page two, and
an envelope would only cost every caller an ``.items``.

A list someone would *search* takes a fourth, ``q``, applied with :func:`apply_search`
before the statement is counted.

**Sorting and filtering** are the list's :class:`app.listing.ListFilter` (decided
2026-10-25, on `fastapi-filter`): ``sort``, ``q`` and one typed query parameter per
filter, applied to the statement before it reaches :func:`paginate`, which only counts
and cuts. A screen that lists "the events of this series" asks the server for them; it
never fetches a page of everything and filters in the browser, which silently stops at
the page's end.

The three rules that are easy to get wrong, and are therefore decided here once:

* **``total`` counts what the filter matched**, not what the table holds. The count runs
  over the *same* statement as the page, with its ordering and its ``limit`` stripped —
  which is why ``paginate`` takes the built statement rather than a table.
* **An offset past the end is an empty page, not a 404.** Someone on page 8 of a list that
  just lost half its rows has not made an error.
* **A sort column that does not exist is refused**, never ignored (`app.listing`). A sort
  that silently does nothing is indistinguishable from one that did not fire at all.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

# 25 fills a screen without filling a scrollbar; the cap keeps one client from asking for
# the whole table by way of a query parameter.
DEFAULT_LIMIT = 25
MAX_LIMIT = 100


class Page[T](BaseModel):
    """One page of a list, and how much there is of it.

    ``total`` is in the body rather than in a header because the generated frontend client
    types the body: a count in ``X-Total-Count`` would arrive as a string nobody checks,
    and the screen that says "26-50 of 180" would need a second request to learn the 180.
    """

    items: list[T]
    total: int = Field(description="Rows matching the filter, not rows on this page")
    limit: int
    offset: int


@dataclass(slots=True, frozen=True)
class PageParams:
    """Which part of the list the caller asked for. Built by :func:`page_params`, never by
    hand; the order is the list's filter's (`app.listing.ListFilter.sort`)."""

    limit: int
    offset: int


def page_params(
    limit: int = Query(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT, description="Rows per page"),
    offset: int = Query(default=0, ge=0, description="Rows to skip"),
) -> PageParams:
    return PageParams(limit=limit, offset=offset)


#: Use as ``params: PageParams = PageInput`` in a route signature.
PageInput = Depends(page_params)


def apply_search(stmt: Select, q: str | None, *columns: Any) -> Select:
    """Narrows ``stmt`` to rows where any of ``columns`` contains ``q``.

    Apply it to the statement **before** handing it to :func:`paginate`, so that ``total``
    counts what the search matched rather than what the table holds.

    One function rather than the same eight lines in every router, because each of its
    three decisions is one a copy got wrong at least once:

    * **Case-insensitive, matching anywhere in the field.** Someone searching for a club
      types the half of the name they remember, in whatever case the keyboard was in.
    * **A blank search is no search.** An empty or whitespace-only ``q`` returns the
      statement untouched. The tempting shortcut — letting it become a ``%%`` pattern —
      looks like "match everything" but silently drops every row whose searched columns
      are all NULL.
    * **A NULL column simply does not match**, which SQL gives us for free: a club with no
      city stays findable by its name.
    """
    term = (q or "").strip().lower()
    if not term:
        return stmt
    pattern = f"%{term}%"
    return stmt.where(or_(*(func.lower(column).like(pattern) for column in columns)))


async def paginate(
    session: AsyncSession, stmt: Select, params: PageParams
) -> tuple[list[Any], int]:
    """Runs ``stmt`` — narrowed and ordered by the list's filter — as one page, and counts
    what it matched.

    Returns the rows and the total, rather than a :class:`Page`, because most routes still
    have to turn their ORM objects into schemas in between. Build the page with
    :func:`page_of`.
    """
    # `order_by(None)` clears the order for the count — it does not need it, and SQL
    # Server-style backends refuse ORDER BY inside a subquery without TOP.
    total = await session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    rows = (await session.execute(stmt.limit(params.limit).offset(params.offset))).scalars()
    return list(rows), int(total or 0)


def page_of[T](items: list[T], total: int, params: PageParams) -> Page[T]:
    """The envelope, filled in from the request that produced it."""
    return Page[T](items=items, total=total, limit=params.limit, offset=params.offset)
