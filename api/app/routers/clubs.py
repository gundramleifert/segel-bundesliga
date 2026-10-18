"""Club creation and management.

Admin and editorial roles have access. Clubs are master data: teams, accounts, and
memberships depend on them — and the choice of host for creating an event.

The crest upload (Story V-3) sits on a **second router** in this file: it is the one club
endpoint a `team_manager` may also use — for their own club — so it cannot live under this
module's router-level `require_master_data`. See `crest_router`.
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import authz
from app.auth import current_user, require_master_data
from app.authz import ObjectRef
from app.crests import delete_crest, save_crest
from app.db import get_session
from app.models import Club, Series, Team, TeamStatus
from app.models.auth import ObjectType, Relation, User
from app.pagination import Page, PageInput, PageParams, apply_search, page_of, paginate
from app.problems import Problem
from app.schemas.public import ClubOut, SeriesOut
from app.services import current_year
from app.services.lookup import get_or_404
from app.services.registrations import Registration, RegistrationHasResults, sync_registrations
from app.text import slugify

router = APIRouter(
    prefix="/api/admin/clubs",
    tags=["admin"],
    dependencies=[Depends(require_master_data)],
)

# Same prefix, different permission: a router-level dependency cannot be relaxed for a
# single route, and the crest is the one thing a club's own manager maintains here.
crest_router = APIRouter(prefix="/api/admin/clubs", tags=["admin"])


class ClubCreate(BaseModel):
    """The name alone suffices for creation; all other fields can be added later."""

    name: str = Field(min_length=3, max_length=200)
    short_name: str | None = Field(
        default=None,
        max_length=32,
        description="Abbreviation like 'NRV'. If absent, the name is used initially.",
    )
    city: str | None = Field(default=None, max_length=120)
    website: str | None = None
    logo_url: str | None = Field(default=None, description="Club crest")
    description: str | None = Field(
        default=None, max_length=2000, description="A few sentences for the club page"
    )
    slug: str | None = Field(default=None, description="If absent, it is generated from the name.")


class ClubUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=3, max_length=200)
    short_name: str | None = Field(default=None, min_length=1, max_length=32)
    city: str | None = Field(default=None, max_length=120)
    website: str | None = None
    logo_url: str | None = None
    description: str | None = Field(default=None, max_length=2000)


class SeriesAssignment(BaseModel):
    series: list[int] = Field(
        description=(
            "IDs of series in which the club participates. An empty list removes all "
            "assignments. The year is embedded in the series."
        )
    )


class AssignmentOut(BaseModel):
    series: SeriesOut
    status: str
    decision_note: str | None = None


class ClubAdminOut(ClubOut):
    """Like ClubOut, plus series assignments — admin needs both together."""

    assignments: list[AssignmentOut] = Field(default_factory=list)
    visible: bool = Field(
        description="Whether the club appears publicly — i.e., is assigned to an active series."
    )


#: Story A-13 — the columns this list may be sorted by.
CLUB_SORT = {"name": Club.name, "short_name": Club.short_name, "city": Club.city}


@router.get("", response_model=Page[ClubAdminOut], summary="All clubs with assignments")
async def list_all_clubs(
    q: str | None = Query(default=None, description="Search in name, abbreviation and city"),
    params: PageParams = PageInput,
    session: AsyncSession = Depends(get_session),
) -> Page[ClubAdminOut]:
    """Includes those not yet assigned — otherwise they couldn't be found.

    Paged and searchable since Story A-13: the association runs several series of 18 clubs
    and offers the site to clubs organising their own events, so this is the list that
    grows fastest of all of them.
    """
    stmt = apply_search(select(Club), q, Club.name, Club.short_name, Club.city)
    clubs, total = await paginate(
        session, stmt, params, sortable=CLUB_SORT, default_order=[Club.name, Club.id]
    )
    return page_of(await _compose(session, list(clubs)), total, params)


async def _compose(session: AsyncSession, clubs: list[Club]) -> list[ClubAdminOut]:
    """Adds each club's series assignments and whether it is publicly visible.

    Split out from the route by Story A-13: the route answers with one page now, so
    `_club_out` can no longer compose the whole list and pick its club out of it.
    """
    if not clubs:
        return []
    year = await current_year(session)

    assignments = (
        await session.execute(
            select(Team, Series)
            .join(Series, Team.series_id == Series.id)
            # Only series registrations; entries in individual events are not a separate
            # club assignment.
            .where(Team.event_id.is_(None), Team.club_id.in_([c.id for c in clubs]))
            .order_by(Series.year.desc().nulls_last(), Series.level.nulls_last())
        )
    ).all()

    by_club: dict[int, list[AssignmentOut]] = {}
    for team, series in assignments:
        by_club.setdefault(team.club_id, []).append(
            AssignmentOut(
                series=SeriesOut.model_validate(series),
                status=team.status,
                decision_note=team.decision_note,
            )
        )

    return [
        ClubAdminOut(
            **ClubOut.model_validate(club).model_dump(),
            assignments=by_club.get(club.id, []),
            visible=any(
                assignment.series.year == year and assignment.status == TeamStatus.ACCEPTED
                for assignment in by_club.get(club.id, [])
            ),
        )
        for club in clubs
    ]


@router.put(
    "/{club_id}/series",
    response_model=ClubAdminOut,
    summary="Assign series",
)
async def set_series(
    club_id: int,
    request: SeriesAssignment,
    session: AsyncSession = Depends(get_session),
) -> ClubAdminOut:
    """Sets the series in which the club participates.

    The year is embedded in the series: an assignment to "DSBL 2026" does not apply to
    "DSBL 2027" — a new assignment is needed there. An assignment under which racing has
    already occurred cannot be removed; results depend on it.
    """
    club = await get_or_404(session, Club, club_id)

    desired: dict[int, Series] = {}
    for series_id in dict.fromkeys(request.series):
        series = await get_or_404(session, Series, series_id)
        desired[series.id] = series

    existing = (
        await session.execute(select(Team).where(Team.club_id == club.id, Team.event_id.is_(None)))
    ).scalars()
    try:
        await sync_registrations(
            session,
            existing,
            (Registration(club.id, series_id, club.short_name) for series_id in desired),
        )
    except RegistrationHasResults:
        raise Problem(
            409,
            "registration-has-results",
            "The assignment cannot be removed: this series already has race results for the club.",
        ) from None
    await session.commit()
    club = (await session.execute(select(Club).where(Club.id == club_id))).scalar_one()
    return (await _compose(session, [club]))[0]


@router.post("", response_model=ClubAdminOut, status_code=status.HTTP_201_CREATED)
async def create_club(
    request: ClubCreate,
    session: AsyncSession = Depends(get_session),
) -> ClubAdminOut:
    """A new club — answered in the shape the admin list has, so a client needs one type."""
    slug = slugify(request.slug or request.short_name or request.name)
    if await _slug_taken(session, slug):
        raise Problem(
            409,
            "slug-taken",
            f"The URL '{slug}' is already taken. Please provide your own slug.",
            slug=slug,
        )

    club = Club(
        slug=slug,
        name=request.name.strip(),
        # Don't normalize abbreviation on purpose: 'BYC (BA)' and 'BYC (BE)' are different
        # clubs, and the suffix in parentheses is the only distinction.
        # Without its own abbreviation, the name is used initially — better than a guessed one.
        short_name=(request.short_name or request.name).strip()[:32],
        city=request.city.strip() if request.city else None,
        website=request.website,
        logo_url=request.logo_url,
        description=request.description.strip() if request.description else None,
    )
    session.add(club)
    await session.commit()
    return (await _compose(session, [club]))[0]


@router.patch("/{club_id}", response_model=ClubAdminOut)
async def update_club(
    club_id: int,
    request: ClubUpdate,
    session: AsyncSession = Depends(get_session),
) -> ClubAdminOut:
    club = await get_or_404(session, Club, club_id)

    for field, value in request.model_dump(exclude_unset=True).items():
        setattr(club, field, value.strip() if isinstance(value, str) else value)

    await session.commit()
    return (await _compose(session, [club]))[0]


# ------------------------------------------------------------------- Crest (V-3)


@crest_router.post("/{club_id}/logo", response_model=ClubOut, summary="Upload club crest")
async def upload_club_logo(
    club_id: int,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> ClubOut:
    """Story V-3: the club's crest ("Stander") as an actual file, not a pasted URL.

    Uploading again simply replaces it — there is one crest per club, and a second upload
    is the way to correct a bad one. The response is the club as the public API renders it,
    so the caller immediately sees the resolved `logo_url` (see
    `ClubOut._prefer_uploaded_crest`) and does not have to guess the URL.
    """
    _can_manage_crest(acting, club_id)
    club = await _club(session, club_id)
    raw = await file.read()
    # Decoding and resizing is CPU work: off the event loop, with no session in the thread.
    await asyncio.to_thread(save_crest, club.id, raw, content_type=file.content_type)
    return ClubOut.model_validate(club)


@crest_router.delete(
    "/{club_id}/logo",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove club crest",
)
async def delete_club_logo(
    club_id: int,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> Response:
    """Removes the uploaded file. Doing this to a club that has none is a no-op, not an
    error — the desired state is "no uploaded crest" either way.

    `Club.logo_url` is deliberately left alone: it means "externally hosted emblem", and a
    club that had one before the upload gets it back rather than losing it here.
    """
    _can_manage_crest(acting, club_id)
    await _club(session, club_id)
    delete_crest(club_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _can_manage_crest(acting: User, club_id: int) -> None:
    """Administration and editorial for any club, the club's own admin for theirs
    (Story V-3): the admin decides who is in the club and what it looks like."""
    if authz.check(acting, Relation.EDITOR):
        return
    if authz.check(acting, Relation.ADMIN, on=ObjectRef(ObjectType.CLUB, club_id)):
        return
    raise Problem(
        403,
        "club-crest-not-yours",
        "The crest is maintained by administration, editorial staff, or the club's own leadership.",
    )


async def _club(session: AsyncSession, club_id: int) -> Club:
    club = (await session.execute(select(Club).where(Club.id == club_id))).scalar_one_or_none()
    if club is None:
        raise Problem(404, "club-not-found", f"Club {club_id} not found.")
    return club


async def _slug_taken(session: AsyncSession, slug: str) -> bool:
    """Check if a slug is already taken."""
    hit = (await session.execute(select(Club.id).where(Club.slug == slug))).scalar_one_or_none()
    return hit is not None
