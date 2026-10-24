"""Who writes about what — editorial on three levels (Stories R-1, R-2, decided 2026-10-24).

The site's ``editor`` writes the association's posts and every league's, and keeps the
whole picture library. An ``editor`` of a series or an event writes about *that regatta*:
posts and pictures whose ``event_id`` or ``series_id`` it is — a series' editor its events'
too, through the model (``editor from series``). Nothing else: editorial organizes nothing.

A post or a picture is about at most one regatta (``media.check_context``); one about none
is the site's editor's alone.
"""

from __future__ import annotations

from sqlalchemy import ColumnElement, false, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import authz
from app.auth import forbidden
from app.models import Event, Series
from app.models.auth import ObjectType, Relation, User


def site_editor(user: User) -> bool:
    """The association's editorial: every post and picture, with or without a regatta."""
    return authz.check(user, Relation.EDITOR)


async def ensure_about(
    session: AsyncSession, user: User, event_id: int | None, series_id: int | None
) -> None:
    """403 unless this person may write about this regatta — or about none, the site's
    editor alone. Call after ``media.check_context``, which answers an unknown one."""
    if site_editor(user):
        return
    if event_id is not None:
        event = await session.get(Event, event_id)
        if event is not None and authz.check(user, Relation.EDITOR, on=event):
            return
        raise forbidden("writing about this event", [Relation.EDITOR])
    if series_id is not None:
        series = await session.get(Series, series_id)
        if series is not None and authz.check(user, Relation.EDITOR, on=series):
            return
        raise forbidden("writing about this series", [Relation.EDITOR])
    raise forbidden("writing without a regatta", [Relation.EDITOR])


def within_reach(
    user: User, event_id: ColumnElement[int | None], series_id: ColumnElement[int | None]
) -> ColumnElement[bool] | None:
    """The WHERE clause for the posts or pictures this person may see in editorial — None
    for the site's editor, who sees all. A series' editor reaches its own and its events'."""
    if site_editor(user):
        return None
    series = authz.list_objects(user, Relation.EDITOR, ObjectType.SERIES)
    events = authz.list_objects(user, Relation.EDITOR, ObjectType.EVENT)
    clauses = []
    if events:
        clauses.append(event_id.in_(events))
    if series:
        clauses.append(series_id.in_(series))
        clauses.append(event_id.in_(select(Event.id).where(Event.series_id.in_(series))))
    return or_(*clauses) if clauses else false()


async def league_of(
    session: AsyncSession, event_id: int | None, series_id: int | None
) -> int | None:
    """The league a regatta belongs to — where a series' or an event's editor's post
    appears. None for a regatta in no league."""
    if event_id is not None:
        event = await session.get(Event, event_id)
        series_id = event.series_id if event is not None else None
    if series_id is None:
        return None
    series = await session.get(Series, series_id)
    return series.league_id if series is not None else None
