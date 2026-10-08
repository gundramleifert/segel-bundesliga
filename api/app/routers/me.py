"""Story Z-8: my space — the clubs, series and events I am part of (`/me`)."""

from __future__ import annotations

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import current_user
from app.db import get_session
from app.models.auth import User
from app.services.contexts import my_space

router = APIRouter(tags=["personal"])

NeedCode = Literal["waiver", "claims", "squad_below_min", "crew_missing", "documents_expired"]


class NeedOut(BaseModel):
    """Something waiting for me there — a code the page words, and how many."""

    code: NeedCode
    count: int


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
    relations: list[str]
    needs: list[NeedOut]
    #: Only when I sail there.
    teams: list[SailingTeamOut]
    starts_on: date | None = None
    ends_on: date | None = None
    #: Events only.
    status: str | None = None
    #: A draft is listed for the people already named on it.
    published: bool = True
    #: An event's series, for the link from its page.
    series_id: int | None = None
    year: int | None = None


class MeOut(BaseModel):
    """The *Me* card: always there, whatever else is."""

    name: str
    needs: list[NeedOut]


class MySpaceOut(BaseModel):
    me: MeOut
    contexts: list[MyContextOut]


@router.get("/api/me/contexts", response_model=MySpaceOut, summary="Everything I am part of")
async def my_contexts(
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> MySpaceOut:
    """Every club, series and event I hold a relation on or sail in, with what waits for
    me there (Story Z-8). Site relations are not "mine" — the league office's reach is
    `/admin`."""
    space = await my_space(session, acting)
    return MySpaceOut(
        me=MeOut(
            name=space.name,
            needs=[NeedOut(code=n.code, count=n.count) for n in space.needs],  # type: ignore[arg-type]
        ),
        contexts=[
            MyContextOut(
                kind=c.kind,  # type: ignore[arg-type]
                id=c.id,
                name=c.name,
                short_name=c.short_name,
                relations=c.ordered_relations,
                needs=[NeedOut(code=n.code, count=n.count) for n in c.ordered_needs],  # type: ignore[arg-type]
                teams=[SailingTeamOut(**vars(t)) for t in c.teams],
                starts_on=c.starts_on,
                ends_on=c.ends_on,
                status=c.status,
                published=c.published,
                series_id=c.series_id,
                year=c.year,
            )
            for c in space.contexts
        ],
    )
