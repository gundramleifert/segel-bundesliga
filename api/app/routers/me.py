"""Stories Z-8, Z-10: my space — the clubs, series and events I am part of (`/me`), and
every to-do waiting for me there."""

from __future__ import annotations

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import current_user
from app.db import get_session
from app.models import EventStatus
from app.models.auth import User
from app.problems import Problem
from app.services import contexts as contexts_service
from app.services.contexts import (
    Context,
    ContextRelation,
    Need,
    NeedCode,
    Section,
    Severity,
    my_space,
)

router = APIRouter(tags=["personal"])


class NeedOut(BaseModel):
    """Something waiting for me there — a code the page words, how many, the section
    that clears it and how soon (Story Z-10)."""

    code: NeedCode
    count: int
    section: Section
    severity: Severity
    #: The race day it is tied to, if any.
    due: date | None = None


def _need(need: Need) -> NeedOut:
    return NeedOut(
        code=need.code,
        count=need.count,
        section=need.section,
        severity=need.severity,
        due=need.due,
    )


class SailingTeamOut(BaseModel):
    """A team I sail in there: the series' squad, or the event's crew."""

    team_id: int
    club_id: int
    club_name: str


class MyContextOut(BaseModel):
    kind: Literal["club", "series", "event"]
    id: int
    name: str
    short_name: str | None = None
    #: What I am there, in reading order — tuples, plus ``sailor`` for a squad or crew.
    relations: list[ContextRelation]
    needs: list[NeedOut]
    #: Only when I sail there.
    teams: list[SailingTeamOut]
    starts_on: date | None = None
    ends_on: date | None = None
    #: Events only.
    status: EventStatus | None = None
    #: A draft is listed for the people already named on it.
    published: bool = True
    #: An event's series, for the link from its page.
    series_id: int | None = None
    year: int | None = None


class MeOut(BaseModel):
    """The *Me* card: always there, whatever else is."""

    name: str
    needs: list[NeedOut]


class OfficeOut(BaseModel):
    """The league office (Story Z-10): my site relations and what waits there. Not one of
    "my" contexts — the site's reach is not a list of objects."""

    relations: list[ContextRelation]
    needs: list[NeedOut]


class TodoContextOut(BaseModel):
    """The card a to-do sits on; *Me* and the office have no id."""

    kind: Literal["me", "office", "club", "series", "event"]
    id: int | None = None


class TodoOut(NeedOut):
    """One row of the to-do list (the plan's §4): a need and where it is."""

    context: TodoContextOut


class MySpaceOut(BaseModel):
    me: MeOut
    contexts: list[MyContextOut]
    #: Only with a site relation.
    office: OfficeOut | None = None
    #: Every need of every card, most urgent first — severity, then date.
    todos: list[TodoOut]
    #: Everything that needs me, each thing once: a series' waiver asked again on each of
    #: its events is one signature. The account button's badge (Story Z-8).
    total: int


def _context_out(c: Context) -> MyContextOut:
    return MyContextOut(
        kind=c.kind,  # type: ignore[arg-type]
        id=c.id,
        name=c.name,
        short_name=c.short_name,
        relations=c.ordered_relations,
        needs=[_need(n) for n in c.ordered_needs],
        teams=[SailingTeamOut(**vars(t)) for t in c.teams],
        starts_on=c.starts_on,
        ends_on=c.ends_on,
        status=c.status,
        published=c.published,
        series_id=c.series_id,
        year=c.year,
    )


@router.get("/api/me/contexts", response_model=MySpaceOut, summary="Everything I am part of")
async def my_contexts(
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> MySpaceOut:
    """Every club, series and event I hold a relation on or sail in, with what waits for
    me there (Stories Z-8, Z-10). Site relations are not "mine" — they are the league
    ``office``, beside the contexts."""
    space = await my_space(session, acting)
    return MySpaceOut(
        me=MeOut(name=space.name, needs=[_need(n) for n in space.needs]),
        contexts=[_context_out(c) for c in space.contexts],
        office=(
            OfficeOut(
                relations=space.office.relations,
                needs=[_need(n) for n in space.office.needs.ordered],
            )
            if space.office is not None
            else None
        ),
        todos=[
            TodoOut(
                **_need(t.need).model_dump(),
                context=TodoContextOut(kind=t.context.kind, id=t.context.id),  # type: ignore[arg-type]
            )
            for t in space.todos
        ],
        total=space.total,
    )


@router.get(
    "/api/me/contexts/{kind}/{object_id}",
    response_model=MyContextOut,
    summary="One club, series or event as a context of mine",
)
async def reached_context(
    kind: Literal["club", "series", "event"],
    object_id: int,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> MyContextOut:
    """A context reached through another — a series manager's event, anything the league
    office opens (Story Z-10). Its relations are the effective ones the model answers, so
    the workspace shows what I may do there. A context in my list comes back as listed.
    404 when I hold nothing there: not mine to see, as in the list."""
    context = await contexts_service.reached_context(session, acting, kind, object_id)
    if context is None:
        raise Problem(404, "context-not-found", "Not part of your space")
    return _context_out(context)
