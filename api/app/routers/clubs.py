"""Club creation and management.

Admin and editorial roles have access. Clubs are master data: teams, accounts, and
memberships depend on them — and the choice of host for creating an event.

The crest upload (Story V-3) sits on a **second router** in this file: it is the one club
endpoint a `club_manager` may also use — for their own club — so it cannot live under this
module's router-level `require_master_data`. See `crest_router`.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import current_user, require_master_data
from app.crests import delete_crest, save_crest
from app.db import get_session
from app.i18n import Locale, resolve_locale, tr
from app.models import Club, Series, Team, TeamStatus
from app.models.auth import Role, User
from app.problems import Problem
from app.schemas.public import ClubOut, SeriesOut
from app.services import (
    adopt_series_registrations,
    current_year,
    delete_event_entries,
    has_results,
)
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


@router.get("", response_model=list[ClubAdminOut], summary="All clubs with assignments")
async def list_all_clubs(session: AsyncSession = Depends(get_session)) -> list[ClubAdminOut]:
    """Includes those not yet assigned — otherwise they couldn't be found."""
    clubs = (await session.execute(select(Club).order_by(Club.name))).scalars().all()
    year = await current_year(session)

    assignments = (
        await session.execute(
            select(Team, Series)
            .join(Series, Team.series_id == Series.id)
            # Only series registrations; entries in individual events are not a separate
            # club assignment.
            .where(Team.event_id.is_(None))
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
    locale: Locale = Depends(resolve_locale),
) -> ClubAdminOut:
    """Sets the series in which the club participates.

    The year is embedded in the series: an assignment to "DSBL 2026" does not apply to
    "DSBL 2027" — a new assignment is needed there. An assignment under which racing has
    already occurred cannot be removed; results depend on it.
    """
    club = (await session.execute(select(Club).where(Club.id == club_id))).scalar_one_or_none()
    if club is None:
        raise HTTPException(
            status_code=404,
            detail=tr(
                locale, f"Club {club_id} not found", f"Verein {club_id} nicht gefunden"
            ),
        )

    desired: dict[int, Series] = {}
    for series_id in dict.fromkeys(request.series):
        series = (
            await session.execute(select(Series).where(Series.id == series_id))
        ).scalar_one_or_none()
        if series is None:
            raise HTTPException(
                status_code=404,
                detail=tr(
                    locale,
                    f"Series {series_id} not found",
                    f"Serie {series_id} nicht gefunden",
                ),
            )
        desired[series.id] = series

    existing = {
        team.series_id: team
        for team in (
            await session.execute(
                select(Team).where(Team.club_id == club.id, Team.event_id.is_(None))
            )
        ).scalars()
    }

    for series_id, team in existing.items():
        if series_id in desired:
            continue
        if await has_results(session, team):
            raise HTTPException(
                status_code=409,
                detail=tr(
                    locale,
                    (
                        "The assignment cannot be removed: this series already has"
                        " race results for the club."
                    ),
                    (
                        "Die Zuordnung lässt sich nicht aufheben: in dieser Serie"
                        " liegen für den Verein bereits Wettfahrtergebnisse vor."
                    ),
                ),
            )
        # Without series registration, no entry in its events.
        await delete_event_entries(session, series_id, club.id)
        await session.delete(team)

    for series_id in desired:
        if series_id not in existing:
            # Admin assigns directly — that's immediate participation.
            session.add(
                Team(
                    name=club.short_name,
                    club_id=club.id,
                    series_id=series_id,
                    status=TeamStatus.ACCEPTED,
                )
            )

    await session.flush()
    await _backfill_event_entries(session, desired.keys())
    await session.commit()
    return next(c for c in await list_all_clubs(session) if c.id == club_id)


@router.post("", response_model=ClubOut, status_code=status.HTTP_201_CREATED)
async def create_club(
    request: ClubCreate,
    session: AsyncSession = Depends(get_session),
    locale: Locale = Depends(resolve_locale),
) -> Club:
    slug = slugify(request.slug or request.short_name or request.name)
    if await _slug_taken(session, slug):
        raise HTTPException(
            status_code=409,
            detail=tr(
                locale,
                f"The URL '{slug}' is already taken. Please provide your own slug.",
                f"Die Adresse '{slug}' ist schon vergeben. Bitte einen eigenen Slug angeben.",
            ),
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
    return club


@router.patch("/{club_id}", response_model=ClubOut)
async def update_club(
    club_id: int,
    request: ClubUpdate,
    session: AsyncSession = Depends(get_session),
    locale: Locale = Depends(resolve_locale),
) -> Club:
    club = (
        await session.execute(select(Club).where(Club.id == club_id))
    ).scalar_one_or_none()
    if club is None:
        raise HTTPException(
            status_code=404,
            detail=tr(
                locale, f"Club {club_id} not found", f"Verein {club_id} nicht gefunden"
            ),
        )

    for field, value in request.model_dump(exclude_unset=True).items():
        setattr(club, field, value.strip() if isinstance(value, str) else value)

    await session.commit()
    return club


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
    save_crest(club.id, await file.read(), content_type=file.content_type)
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
    """Administration and editorial for any club, a `club_manager` for their own.

    `club_manager` is granted per club (`UserRole.club_id`), so the check is
    `manages_club(...)` — never `acting.club_id == club_id`, which is the separate
    "represents" field and would let a member of one club edit it while missing a manager
    who organizes several.
    """
    if acting.has_any(Role.ADMIN, Role.EDITOR):
        return
    if acting.manages_club(club_id):
        return
    raise Problem(
        403,
        "club-crest-not-yours",
        "The crest is maintained by administration, editorial staff, or the club's own "
        "leadership.",
    )


async def _club(session: AsyncSession, club_id: int) -> Club:
    club = (
        await session.execute(select(Club).where(Club.id == club_id))
    ).scalar_one_or_none()
    if club is None:
        raise Problem(404, "club-not-found", f"Club {club_id} not found.")
    return club


async def _slug_taken(session: AsyncSession, slug: str) -> bool:
    """Check if a slug is already taken."""
    hit = (
        await session.execute(select(Club.id).where(Club.slug == slug))
    ).scalar_one_or_none()
    return hit is not None


async def _backfill_event_entries(session: AsyncSession, series_ids) -> None:
    """Register newly assigned clubs in unraced events of their series.

    Normally, the same clubs enter every event of a series. If a club joins later,
    it shouldn't need to be added individually to upcoming events — adding it to an
    already-raced event would falsify the results.
    """
    from app.models import Event, EventStatus

    for series_id in series_ids:
        events = (
            await session.execute(
                select(Event).where(
                    Event.series_id == series_id, Event.status == EventStatus.PLANNED
                )
            )
        ).scalars().all()
        for event in events:
            await adopt_series_registrations(session, event)
