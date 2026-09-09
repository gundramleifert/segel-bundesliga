"""Create sailors and register squad — Stories V-1 and V-4; self-service profile — Story S-2.

Two levels that belong together:

* The **Sailor** (`Sailor`) is a person. They exist independently of any competition
  and can sail for multiple clubs.
* The **Squad** (`TeamMembership`) is the registration of this person for a series. From this,
  the club later selects the lineup for a matchday (`EventCrew`, Story V-2).

The rule enforced here: **Within a series, a person competes only once.**
Sailing for multiple clubs is allowed — competing against oneself is not.

This file also carries the self-service half of Story S-2 (`me_router`, mounted at
`/api/sailors`, separate from the `/api/admin` router above because a signed-in sailor is
not administration): viewing/editing one's own name and birthdate, and a profile photo.
See the docstring on `_save_photo` for the storage and minors-visibility design.
"""

from __future__ import annotations

import io
from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse, Response
from PIL import Image, ImageOps
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import current_user, optional_user
from app.config import settings
from app.db import get_session
from app.i18n import Locale, resolve_locale, tr
from app.models import Event, EventCrew, Sailor, Team, TeamMembership
from app.models.auth import Role, User
from app.models.org import CrewRole
from app.problems import Problem
from app.schemas.public import MemberOut
from app.services import is_minor

router = APIRouter(prefix="/api/admin", tags=["administration"])
me_router = APIRouter(prefix="/api/sailors", tags=["sailors"])


class SailorFields(BaseModel):
    """Common validation for creation and updates.

    Both normalize in the same place: names without leading/trailing whitespace, emails
    lowercased. If the endpoint did this, the rule would exist twice — and eventually
    twice differently.
    """

    # check_fields=False: fields are defined in inheriting models.
    @field_validator("first_name", "last_name", mode="after", check_fields=False)
    @classmethod
    def _strip_whitespace(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Name cannot be empty.")
        return trimmed

    @field_validator("email", mode="after", check_fields=False)
    @classmethod
    def _lowercase(cls, value: str | None) -> str | None:
        # Otherwise "Jan@…" and "jan@…" would create two people and later two accounts.
        return value.strip().lower() if value else None


class SailorCreate(SailorFields):
    """First and last name are sufficient for creation."""

    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(min_length=1, max_length=80)
    # Connection to account: the person signs in and submits their waiver via this
    # address. Required here — someone created through this form must be reachable.
    # (A future import path, e.g. from manage2sail, can still write a sailor without one
    # directly, bypassing this schema; that's a separate concern from manual creation.)
    email: EmailStr
    # The full date, not just a year — needed to check age-category eligibility
    # (e.g. a youth series) precisely, not just to the nearest twelve months.
    birth_date: date | None = Field(default=None, le=date.today())


class SailorUpdate(SailorFields):
    """All fields are optional — only provided values are updated."""

    first_name: str | None = Field(default=None, min_length=1, max_length=80)
    last_name: str | None = Field(default=None, min_length=1, max_length=80)
    email: EmailStr | None = None
    birth_date: date | None = Field(default=None, le=date.today())


class SailorAdminOut(BaseModel):
    """Like MemberOut, but with contact details — administration needs them, the website doesn't."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    first_name: str
    last_name: str
    email: str | None = None
    birth_date: date | None = None
    # How many series this person is registered for. Says at a glance whether they're
    # in a squad anywhere.
    squads: int = 0


class SailorMeOut(BaseModel):
    """A sailor's own view of their record — no email (that's account identity, handled
    by the sign-in flow, not this endpoint)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    first_name: str
    last_name: str
    birth_date: date | None = None
    # Whether a photo file exists — never the binary itself, see `get_sailor_photo`.
    has_photo: bool = False


class SailorMeUpdate(SailorFields):
    """Self-service edit. No `email` field: identity is out of scope here — it changes
    via the account, not the sailor record, and a sailor may never grant themselves
    someone else's record by re-pointing the email that links the two."""

    first_name: str | None = Field(default=None, min_length=1, max_length=80)
    last_name: str | None = Field(default=None, min_length=1, max_length=80)
    birth_date: date | None = Field(default=None, le=date.today())


class SquadMemberIn(BaseModel):
    sailor_id: int
    role: CrewRole = CrewRole.CREW


class SquadSetRequest(BaseModel):
    members: list[SquadMemberIn] = Field(
        description="The complete squad. An empty list removes it."
    )


class SquadOut(BaseModel):
    team_id: int
    club_id: int
    series_id: int | None
    members: list[MemberOut] = Field(default_factory=list)


# ------------------------------------------------------------------------ Sailors


@router.get("/sailors", response_model=list[SailorAdminOut], summary="Search sailors")
async def list_sailors(
    q: str | None = Query(default=None, description="Search in first name, last name, and email"),
    limit: int = Query(default=50, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> list[SailorAdminOut]:
    """Without a search term, returns the first names.

    With 360 people, a full list would be unusable.
    """
    _can_manage_master_data(acting)

    stmt = select(Sailor).order_by(Sailor.last_name, Sailor.first_name).limit(limit)
    if q:
        pattern = f"%{q.strip().lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(Sailor.first_name).like(pattern),
                func.lower(Sailor.last_name).like(pattern),
                func.lower(Sailor.email).like(pattern),
            )
        )
    sailors = list((await session.execute(stmt)).scalars())

    membership_counts = dict(
        (
            await session.execute(
                select(TeamMembership.sailor_id, func.count())
                .where(TeamMembership.sailor_id.in_([s.id for s in sailors]))
                .group_by(TeamMembership.sailor_id)
            )
        ).all()
    )

    return [
        SailorAdminOut.model_validate(sailor).model_copy(
            update={"squads": membership_counts.get(sailor.id, 0)}
        )
        for sailor in sailors
    ]


@router.post(
    "/sailors",
    response_model=SailorAdminOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create sailor",
)
async def create_sailor(
    request: SailorCreate,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
    locale: Locale = Depends(resolve_locale),
) -> SailorAdminOut:
    """Create a person.

    They don't belong to any competition yet — that comes with squad registration.
    """
    _can_manage_master_data(acting)

    if request.email and await _email_taken(session, request.email):
        raise HTTPException(
            status_code=409,
            detail=tr(
                locale,
                en=f"Email {request.email} is already taken. Emails are unique.",
                de=f"Zu {request.email} ist schon jemand angelegt. Adressen sind eindeutig.",
            ),
        )

    sailor = Sailor(**request.model_dump())
    session.add(sailor)
    await session.commit()
    return SailorAdminOut.model_validate(sailor)


@router.patch("/sailors/{sailor_id}", response_model=SailorAdminOut, summary="Update sailor")
async def update_sailor(
    sailor_id: int,
    request: SailorUpdate,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
    locale: Locale = Depends(resolve_locale),
) -> SailorAdminOut:
    _can_manage_master_data(acting)
    sailor = await _sailor(session, sailor_id)

    changes = request.model_dump(exclude_unset=True)
    email = changes.get("email")
    if email and await _email_taken(session, email, except_id=sailor.id):
        raise HTTPException(
            status_code=409,
            detail=tr(
                locale,
                en=f"Email {email} is already taken. Emails are unique.",
                de=f"Zu {email} ist schon jemand angelegt. Adressen sind eindeutig.",
            ),
        )

    for field, value in changes.items():
        setattr(sailor, field, value)

    await session.commit()
    return SailorAdminOut.model_validate(sailor)


# ------------------------------------------------------------------------- Squad


@router.get("/teams/{team_id}/members", response_model=SquadOut, summary="View squad")
async def get_squad(
    team_id: int,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> SquadOut:
    team = await _team(session, team_id)
    _can_manage_squad(acting, team)
    return await _squad_out(session, team)


@router.put("/teams/{team_id}/members", response_model=SquadOut, summary="Register squad")
async def set_squad(
    team_id: int,
    request: SquadSetRequest,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
    locale: Locale = Depends(resolve_locale),
) -> SquadOut:
    """Registers the people who are allowed to compete for this team — Story V-1.

    Two rules apply:

    * The squad is tied to **series registration**, not to competing at a single event.
    From it, the lineup is selected for each matchday (Story V-2).
    * **Within a series, a person competes only once.** Registering for a second club
    in the same series would mean competing against oneself.

    Those who are already selected for a matchday cannot be removed from the squad —
    otherwise a lineup would exist that has no registration anymore.
    """
    team = await _team(session, team_id)
    _can_manage_squad(acting, team)

    if not team.is_series_registration:
        raise HTTPException(
            status_code=422,
            detail=tr(
                locale,
                en="Squad is tied to series registration, not to competition at a single event.",
                de="Der Kader hängt an der Meldung für die Serie, nicht am Antritt zu einer "
                "einzelnen Veranstaltung.",
            ),
        )

    desired = {entry.sailor_id: entry.role for entry in request.members}
    if len(desired) != len(request.members):
        raise HTTPException(
            status_code=422,
            detail=tr(
                locale,
                en="A person appears twice in the squad.",
                de="Eine Person steht doppelt im Kader.",
            ),
        )

    if desired:
        await _all_exist(session, set(desired))
        await _not_already_in_series(session, team, set(desired), locale)

    await _not_removing_lined_up(session, team, set(desired), locale)

    await session.execute(
        delete(TeamMembership).where(TeamMembership.team_id == team.id)
    )
    session.add_all(
        TeamMembership(team_id=team.id, sailor_id=sailor_id, role=role)
        for sailor_id, role in desired.items()
    )
    await session.commit()
    return await _squad_out(session, team)


# ------------------------------------------------------------------- Self-service (S-2)

# Cap applied before any processing — the whole raw upload is read into memory once.
_MAX_UPLOAD_BYTES = 5 * 1024 * 1024
# Fixed square output size — "mobile format works" (S-2 acceptance criterion): every
# camera aspect ratio ends up the same shape, and the file stays small regardless of
# what was uploaded.
_PHOTO_SIZE = 512
_JPEG_QUALITY = 85


@me_router.get("/me", response_model=SailorMeOut, summary="My own sailor record")
async def get_my_sailor(
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> SailorMeOut:
    """Story S-2: a sailor views their own name, birthdate, and photo status.

    Not every account has a linked sailor — an admin-only account, for instance. That is
    not an error, just nothing to show here (404, not a crash).
    """
    sailor = await _my_sailor(session, acting)
    return _me_out(sailor)


@me_router.patch("/me", response_model=SailorMeOut, summary="Edit my own sailor record")
async def update_my_sailor(
    request: SailorMeUpdate,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> SailorMeOut:
    """A sailor corrects their own name or birthdate — the same fields a club manager or
    admin can already set via `PATCH /api/admin/sailors/{id}`, just scoped to "my own
    record" instead of requiring `_can_manage_master_data`."""
    sailor = await _my_sailor(session, acting)
    for field, value in request.model_dump(exclude_unset=True).items():
        setattr(sailor, field, value)
    await session.commit()
    return _me_out(sailor)


@me_router.post("/me/photo", response_model=SailorMeOut, summary="Upload or replace my photo")
async def upload_my_photo(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> SailorMeOut:
    sailor = await _my_sailor(session, acting)
    raw = await file.read()
    _save_photo(sailor.id, raw, content_type=file.content_type)
    return _me_out(sailor)


@me_router.delete(
    "/me/photo", status_code=status.HTTP_204_NO_CONTENT, summary="Remove my photo"
)
async def delete_my_photo(
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> Response:
    """Removing a photo that doesn't exist is not an error — there is simply nothing to do."""
    sailor = await _my_sailor(session, acting)
    _photo_path(sailor.id).unlink(missing_ok=True)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@me_router.get("/{sailor_id}/photo", summary="A sailor's photo")
async def get_sailor_photo(
    sailor_id: int,
    session: AsyncSession = Depends(get_session),
    acting: User | None = Depends(optional_user),
) -> FileResponse:
    """Serves the stored photo — see `_save_photo` for the minors-visibility rule this
    enforces. There is no placeholder here: the frontend already renders one when
    `has_photo` is false, so a missing file is simply a 404."""
    sailor = await _sailor(session, sailor_id)
    path = _photo_path(sailor.id)
    if not path.exists():
        raise Problem(404, "sailor-photo-not-found", "This sailor has no photo.")

    # `is_minor` is deliberately tri-state: None means the birth date is unset. None is
    # falsy, so a plain truth test here would fail *open* — and since the birth date is an
    # optional, self-reported field, leaving it blank would publish a 14-year-old's photo to
    # the world, defeating the entire gate by omission. Anything other than a definite
    # "adult" therefore requires the connected-viewer check. A sailor lifts the restriction
    # on their own photo by filling in their birth date in the same self-service form they
    # uploaded it from. `app/routers/waivers.py` treats the same unknown as blocking.
    if is_minor(sailor.birth_date, date.today()) is not False and not await _may_view_minor_photo(
        session, acting, sailor
    ):
        raise Problem(
            403,
            "sailor-photo-protected",
            "This sailor is a minor, or their date of birth is not on file. Their photo is "
            "only shown to a signed-in account connected to them: the sailor themselves, "
            "administration/editorial staff, or their club's leadership.",
        )

    return FileResponse(path, media_type="image/jpeg")


def _me_out(sailor: Sailor) -> SailorMeOut:
    return SailorMeOut(
        id=sailor.id,
        first_name=sailor.first_name,
        last_name=sailor.last_name,
        birth_date=sailor.birth_date,
        has_photo=_photo_path(sailor.id).exists(),
    )


async def _my_sailor(session: AsyncSession, acting: User) -> Sailor:
    """The `Sailor` row linked to the signed-in account's email — never someone else's.

    Requires the address to be **verified**: an account that merely claims an email (not
    yet redeemed via a one-time code or provider token) proves nothing, and matching on
    it would let anyone view or edit any sailor's record just by typing their address at
    sign-up. The 404 is worded the same whether the reason is "no verified email at all"
    or "no sailor row uses this email" — a caller has no legitimate use for telling those
    apart, and the frontend shows one plain "nothing to edit yet" message either way.
    """
    sailor = None
    if acting.email_verified:
        sailor = (
            await session.execute(select(Sailor).where(Sailor.email == acting.email.lower()))
        ).scalar_one_or_none()
    if sailor is None:
        raise Problem(
            404,
            "no-linked-sailor-record",
            "No sailor record is linked to this account yet.",
            detail=(
                "An administrator or your club's leadership can create your sailor "
                "record and link it to this email address."
            ),
        )
    return sailor


def _photo_path(sailor_id: int) -> Path:
    directory = Path(settings.uploads_dir) / "sailors"
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"{sailor_id}.jpg"


def _save_photo(sailor_id: int, raw: bytes, *, content_type: str | None) -> None:
    """Validates, then center-crops and downsizes the upload — Story S-2.

    **Storage**: a deterministic path (`uploads/sailors/{id}.jpg`) needs no database
    column — the file's existence *is* the "has a photo" state (`SailorMeOut.has_photo`,
    `_me_out`). Not versioned (see `.gitignore`); Postgres/S3-backed storage remains a
    later option once this goes into production, see `docs/userstories.md`.

    **Processing**: re-encoded as JPEG, EXIF-rotated upright first (phone cameras store
    orientation as metadata, not pixels — skipping this would show sideways photos),
    center-cropped to a square, then downsized to a fixed `_PHOTO_SIZE` — "cropped and
    scaled down; mobile format works" is the acceptance criterion, and a fixed small size
    keeps every stored photo roughly the same, small footprint regardless of what a phone
    camera produced.

    **Validation**: content-type is checked first (cheap, before touching the bytes) and
    size next (before Pillow ever decodes anything) — both are the "reject anything
    absurdly large" and "reject non-image uploads" requirements. What's left is handed to
    Pillow itself: if it can't decode it, it wasn't a real image regardless of what the
    upload claimed to be.
    """
    if content_type is not None and not content_type.startswith("image/"):
        raise Problem(
            422,
            "sailor-photo-invalid-type",
            "The upload must be an image.",
            detail=f"Got content type '{content_type}'.",
        )
    if not raw:
        raise Problem(422, "sailor-photo-invalid", "The upload is empty.")
    if len(raw) > _MAX_UPLOAD_BYTES:
        raise Problem(
            413,
            "sailor-photo-too-large",
            f"The photo must be at most {_MAX_UPLOAD_BYTES // (1024 * 1024)} MB.",
        )

    try:
        image = Image.open(io.BytesIO(raw))
        image.load()
    except Exception as exc:
        raise Problem(
            422, "sailor-photo-invalid", "This file is not a readable image."
        ) from exc

    image = ImageOps.exif_transpose(image) or image
    image = image.convert("RGB")

    width, height = image.size
    side = min(width, height)
    left = (width - side) // 2
    top = (height - side) // 2
    image = image.crop((left, top, left + side, top + side))
    image = image.resize((_PHOTO_SIZE, _PHOTO_SIZE), Image.LANCZOS)

    image.save(_photo_path(sailor_id), format="JPEG", quality=_JPEG_QUALITY)


async def _may_view_minor_photo(
    session: AsyncSession, acting: User | None, sailor: Sailor
) -> bool:
    """Who may see a photo that is not public — Story S-2's own open question, resolved here.

    An **adult's** photo is public: "so that people see who sails for the club" is the whole
    point of S-2, and there is no reason to gate it. A minor's photo is sensitive in exactly
    the way the waiver story (S-1) already treats minors' data with extra care, so it is shown
    only to a signed-in account with an actual connection to that person: the sailor
    themselves, administration/editorial staff (who already manage this data unrestricted, see
    `_can_manage_master_data`), or a manager of a club this sailor is registered with (their
    squad club, not just any club).

    An **unknown** birth date is treated like a minor's, not like an adult's — see the caller.
    """
    if acting is None:
        return False
    if acting.has_any(Role.ADMIN, Role.EDITOR):
        return True
    if sailor.email is not None and sailor.email.lower() == acting.email.lower():
        return True
    if acting.has_any(Role.CLUB_MANAGER):
        club_ids = (
            await session.execute(
                select(Team.club_id)
                .join(TeamMembership, TeamMembership.team_id == Team.id)
                .where(TeamMembership.sailor_id == sailor.id)
                .distinct()
            )
        ).scalars()
        if any(acting.manages_club(club_id) for club_id in club_ids):
            return True
    return False


# ------------------------------------------------------------------ Helper functions


def _can_manage_master_data(acting: User) -> None:
    """People are managed by administration, editorial staff, and club leadership.

    Club leadership is included because they register their own sailors — they know the
    spelling of names, not the head office.
    """
    if acting.has_any(Role.ADMIN, Role.EDITOR, Role.CLUB_MANAGER):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Only administration, editorial staff, and club leadership can manage sailors.",
    )


def _can_manage_squad(acting: User, team: Team) -> None:
    if acting.has_any(Role.ADMIN):
        return
    if acting.has_any(Role.CLUB_MANAGER) and acting.manages_club(team.club_id):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Only club leadership of the same club can manage the squad.",
    )


async def _sailor(session: AsyncSession, sailor_id: int) -> Sailor:
    sailor = (
        await session.execute(select(Sailor).where(Sailor.id == sailor_id))
    ).scalar_one_or_none()
    if sailor is None:
        raise HTTPException(status_code=404, detail=f"Sailor {sailor_id} not found")
    return sailor


async def _team(session: AsyncSession, team_id: int) -> Team:
    team = (
        await session.execute(select(Team).where(Team.id == team_id))
    ).scalar_one_or_none()
    if team is None:
        raise HTTPException(status_code=404, detail=f"Team {team_id} not found")
    return team


async def _email_taken(
    session: AsyncSession, email: str, *, except_id: int | None = None
) -> bool:
    stmt = select(Sailor.id).where(Sailor.email == email)
    if except_id is not None:
        stmt = stmt.where(Sailor.id != except_id)
    return (await session.execute(stmt.limit(1))).scalar_one_or_none() is not None


async def _all_exist(session: AsyncSession, sailor_ids: set[int]) -> None:
    found = set(
        (
            await session.execute(select(Sailor.id).where(Sailor.id.in_(sailor_ids)))
        ).scalars()
    )
    missing = sorted(sailor_ids - found)
    if missing:
        raise HTTPException(
            status_code=404, detail=f"These people don't exist: {missing}"
        )


async def _not_already_in_series(
    session: AsyncSession, team: Team, sailor_ids: set[int], locale: Locale
) -> None:
    """The core rule: once per series, for whichever club."""
    if team.series_id is None:
        return

    rows = (
        await session.execute(
            select(Sailor.first_name, Sailor.last_name)
            .join(TeamMembership, TeamMembership.sailor_id == Sailor.id)
            .join(Team, TeamMembership.team_id == Team.id)
            .where(
                Team.series_id == team.series_id,
                Team.event_id.is_(None),
                Team.id != team.id,
                TeamMembership.sailor_id.in_(sailor_ids),
            )
        )
    ).all()
    if rows:
        names = ", ".join(f"{first} {last}" for first, last in rows)
        raise HTTPException(
            status_code=409,
            detail=tr(
                locale,
                en=f"Already registered for another club in this series: {names}. "
                "A person competes only once per series.",
                de=f"In dieser Serie schon für einen anderen Verein gemeldet: {names}. "
                "Eine Person tritt je Serie nur einmal an.",
            ),
        )


async def _not_removing_lined_up(
    session: AsyncSession, team: Team, staying: set[int], locale: Locale
) -> None:
    """People selected for a matchday cannot be removed from the squad."""
    current = set(
        (
            await session.execute(
                select(TeamMembership.sailor_id).where(TeamMembership.team_id == team.id)
            )
        ).scalars()
    )
    removing = current - staying
    if not removing:
        return

    stmt = (
        select(Sailor.first_name, Sailor.last_name, Event.title)
        .join(EventCrew, EventCrew.sailor_id == Sailor.id)
        .join(Event, EventCrew.event_id == Event.id)
        .join(Team, EventCrew.team_id == Team.id)
        .where(Team.club_id == team.club_id, EventCrew.sailor_id.in_(removing))
    )
    if team.series_id is not None:
        stmt = stmt.where(Event.series_id == team.series_id)

    selected = (await session.execute(stmt)).all()
    if selected:
        description = ", ".join(f"{first} {last} ({title})" for first, last, title in selected)
        raise HTTPException(
            status_code=409,
            detail=tr(
                locale,
                en=f"These people are already selected: {description}. "
                "Change the lineup first, then the squad.",
                de=f"Diese Personen sind bereits aufgestellt: {description}. "
                "Erst die Aufstellung ändern, dann den Kader.",
            ),
        )


async def _squad_out(session: AsyncSession, team: Team) -> SquadOut:
    rows = (
        await session.execute(
            select(TeamMembership, Sailor)
            .join(Sailor, TeamMembership.sailor_id == Sailor.id)
            .where(TeamMembership.team_id == team.id)
        )
    ).all()
    order = {CrewRole.HELM: 0, CrewRole.CREW: 1, CrewRole.SUBSTITUTE: 2}
    members = sorted(
        (
            MemberOut(
                id=sailor.id,
                first_name=sailor.first_name,
                last_name=sailor.last_name,
                role=membership.role,
            )
            for membership, sailor in rows
        ),
        key=lambda m: (order.get(m.role, 9), m.last_name, m.first_name),
    )
    return SquadOut(
        team_id=team.id,
        club_id=team.club_id,
        series_id=team.series_id,
        members=members,
    )
