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

import asyncio
from collections import Counter
from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import authz
from app.auth import current_user, optional_user
from app.authz import ObjectRef
from app.config import settings
from app.db import get_session
from app.models import Club, Event, EventCrew, Sailor, Series, Team, TeamMembership
from app.models.auth import ObjectType, Relation, User
from app.models.org import CrewRole
from app.pagination import Page, PageInput, PageParams, apply_search, page_of, paginate
from app.problems import Problem
from app.schemas.public import MemberOut
from app.services import is_minor, pictures
from app.services.contexts import require_linked_sailor
from app.services.lookup import get_or_404

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


class SquadClubOut(BaseModel):
    """The club of one registration — enough to tell two people with one surname apart."""

    id: int
    name: str
    short_name: str


class SquadSeriesOut(BaseModel):
    """The series of one registration. Named alongside the club, because the same club can
    register the same person for two of them and the club alone would be ambiguous."""

    id: int
    name: str


class SailorRegistrationOut(BaseModel):
    """One series registration of a person — Story V-1.

    A `TeamMembership` row, as the candidate list needs it. There is one per registration
    and a person legitimately has several: sailing for more than one club is allowed, and
    only doing it twice *within a series* is not.
    """

    team_id: int
    club: SquadClubOut
    series: SquadSeriesOut
    role: CrewRole


class SailorAdminOut(BaseModel):
    """Like MemberOut, but with contact details — administration needs them, the website doesn't."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    first_name: str
    last_name: str
    email: str | None = None
    birth_date: date | None = None
    # Story S-4: management sees the sailor's choice, never sets it (`SailorUpdate` has
    # no such field).
    profile_public: bool = True
    # How many series this person is registered for. Says at a glance whether they're
    # in a squad anywhere.
    squads: int = 0
    # Where, specifically. A bare count cannot answer either question a squad screen has
    # — "is this the right Nanisberg" and "can I add them to *this* series" — because
    # eighteen people share that surname and a person may sail for several clubs at once
    # (Story V-1).
    registrations: list[SailorRegistrationOut] = Field(default_factory=list)


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
    # Story S-4: whether the profile page is public — the choice, or the age default.
    profile_public: bool = True


class SailorMeUpdate(SailorFields):
    """Self-service edit. No `email` field: identity is out of scope here — it changes
    via the account, not the sailor record, and a sailor may never grant themselves
    someone else's record by re-pointing the email that links the two."""

    first_name: str | None = Field(default=None, min_length=1, max_length=80)
    last_name: str | None = Field(default=None, min_length=1, max_length=80)
    birth_date: date | None = Field(default=None, le=date.today())
    # Story S-4 — the one field here management cannot set for someone else. Null (or
    # absent) leaves the choice as it is.
    profile_public: bool | None = None


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
    # The size the series (or the stand-alone event) asks for — Story V-1. The panel reads
    # them here, never off a constant.
    squad_min: int
    squad_max: int
    members: list[MemberOut] = Field(default_factory=list)


# ------------------------------------------------------------------------ Sailors


#: What this list may be sorted by — Story A-13. A map rather than "any column of the
#: model": a sort parameter is public API, and exposing the model's attribute names would
#: make every rename a breaking change for callers.
SAILOR_SORT = {
    "last_name": Sailor.last_name,
    "first_name": Sailor.first_name,
    "email": Sailor.email,
    "birth_date": Sailor.birth_date,
}


@router.get("/sailors", response_model=Page[SailorAdminOut], summary="Search sailors")
async def list_sailors(
    q: str | None = Query(default=None, description="Search in first name, last name, and email"),
    params: PageParams = PageInput,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> Page[SailorAdminOut]:
    """One page of people, filtered by `q` and sorted by `sort` (Story A-13).

    This used to answer with up to 500 rows and offer no way to ask for the 501st, so the
    screen showed whatever the first 500 happened to be and the rest of the register was
    reachable only by guessing a search term.
    """
    _can_manage_master_data(acting)

    stmt = apply_search(select(Sailor), q, Sailor.first_name, Sailor.last_name, Sailor.email)
    sailors, total = await paginate(
        session,
        stmt,
        params,
        sortable=SAILOR_SORT,
        default_order=[Sailor.last_name, Sailor.first_name, Sailor.id],
    )
    registrations = await _registrations_by_sailor(session, [s.id for s in sailors])

    return page_of(
        [
            SailorAdminOut.model_validate(sailor).model_copy(
                update={
                    "squads": len(registrations.get(sailor.id, [])),
                    "registrations": registrations.get(sailor.id, []),
                }
            )
            for sailor in sailors
        ],
        total,
        params,
    )


async def _registrations_by_sailor(
    session: AsyncSession, sailor_ids: list[int]
) -> dict[int, list[SailorRegistrationOut]]:
    """Every series registration of these people, grouped by person.

    **Series registrations only** (`Team.event_id is None`). The other kind of `Team` row
    is an entry in one event, carries no squad, and naming it here would tell a club
    manager the person is registered somewhere they are not (Story V-1).

    One query rather than one per person: this feeds a candidate list of up to 500.
    """
    if not sailor_ids:
        return {}

    rows = (
        await session.execute(
            select(TeamMembership.sailor_id, Team.id, TeamMembership.role, Club, Series)
            .join(Team, TeamMembership.team_id == Team.id)
            .join(Club, Team.club_id == Club.id)
            .join(Series, Team.series_id == Series.id)
            .where(
                TeamMembership.sailor_id.in_(sailor_ids),
                Team.event_id.is_(None),
            )
            .order_by(Series.year.desc(), Series.name, Club.name)
        )
    ).all()

    grouped: dict[int, list[SailorRegistrationOut]] = {}
    for sailor_id, team_id, role, club, series in rows:
        grouped.setdefault(sailor_id, []).append(
            SailorRegistrationOut(
                team_id=team_id,
                club=SquadClubOut(id=club.id, name=club.name, short_name=club.short_name),
                series=SquadSeriesOut(id=series.id, name=series.name),
                role=role,
            )
        )
    return grouped


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
) -> SailorAdminOut:
    """Create a person.

    They don't belong to any competition yet — that comes with squad registration.
    """
    _can_manage_master_data(acting)

    if request.email and await _email_taken(session, request.email):
        raise Problem(
            409,
            "email-taken",
            f"Email {request.email} is already taken. Emails are unique.",
            email=request.email,
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
) -> SailorAdminOut:
    _can_manage_master_data(acting)
    sailor = await _sailor(session, sailor_id)
    await _may_change_sailor(session, acting, sailor)

    changes = request.model_dump(exclude_unset=True)
    email = changes.get("email")
    if email and await _email_taken(session, email, except_id=sailor.id):
        raise Problem(
            409, "email-taken", f"Email {email} is already taken. Emails are unique.", email=email
        )

    for field, value in changes.items():
        setattr(sailor, field, value)

    await session.commit()
    return SailorAdminOut.model_validate(sailor)


# ------------------------------------------------------------------------- Squad


@router.get(
    "/teams/{team_id}/members",
    response_model=SquadOut,
    dependencies=[Depends(current_user)],
    summary="View squad",
)
async def get_squad(
    team_id: int,
    session: AsyncSession = Depends(get_session),
) -> SquadOut:
    """Any signed-in account may read a squad: participation is public (the club page
    lists every squad, CLAUDE.md), so the only thing the old `_can_manage_squad` check
    here achieved was to break `/club` for a club's plain member, who is promised the
    read-only view (Story V-12). Writing still needs the club's leadership."""
    team = await _team(session, team_id)
    return await _squad_out(session, team)


@router.put("/teams/{team_id}/members", response_model=SquadOut, summary="Register squad")
async def set_squad(
    team_id: int,
    request: SquadSetRequest,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> SquadOut:
    """Registers the people who are allowed to compete for this team — Story V-1.

    Two rules apply:

    * The squad is tied to **series registration**, not to competing at a single event
    of the series. From it, the lineup is selected for each matchday (Story V-2). An
    event that belongs to no series has no registration above it, so there the club's
    **entry** carries the squad (Story V-12) — the team `participation.squad_team` names.
    * **Within a series, a person competes only once.** Registering for a second club
    in the same series would mean competing against oneself.

    Those who are already selected for a matchday cannot be removed from the squad —
    otherwise a lineup would exist that has no registration anymore.
    """
    team = await _team(session, team_id)
    _can_manage_squad(acting, team)

    if not team.is_series_registration and team.series_id is not None:
        raise Problem(
            422,
            "squad-needs-series-registration",
            "A squad belongs to the series registration, not to the entry in one of its events.",
            team_id=team.id,
        )

    desired = {entry.sailor_id: entry.role for entry in request.members}
    if len(desired) != len(request.members):
        counts = Counter(entry.sailor_id for entry in request.members)
        twice = sorted(sailor_id for sailor_id, n in counts.items() if n > 1)
        raise Problem(
            422,
            "squad-duplicate-sailor",
            "A person appears twice in this squad.",
            sailor_ids=twice,
        )

    _, squad_max = await _squad_limits(session, team)
    if len(desired) > squad_max:
        raise Problem(
            422,
            "squad-too-large",
            "More people than this competition allows in a squad.",
            squad_max=squad_max,
            registered=len(desired),
        )

    if desired:
        await _all_exist(session, set(desired))
        await _not_already_in_series(session, team, set(desired))

    await _not_removing_lined_up(session, team, set(desired))

    await session.execute(delete(TeamMembership).where(TeamMembership.team_id == team.id))
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


@me_router.get("/me", response_model=SailorMeOut, summary="My own sailor record")
async def get_my_sailor(
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> SailorMeOut:
    """Story S-2: a sailor views their own name, birthdate, and photo status.

    Not every account has a linked sailor — an admin-only account, for instance. That is
    not an error, just nothing to show here (404, not a crash).
    """
    sailor = await require_linked_sailor(session, acting)
    return _me_out(sailor)


@me_router.patch("/me", response_model=SailorMeOut, summary="Edit my own sailor record")
async def update_my_sailor(
    request: SailorMeUpdate,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> SailorMeOut:
    """A sailor corrects their own name or birthdate — the same fields a team manager or
    admin can already set via `PATCH /api/admin/sailors/{id}`, just scoped to "my own
    record" instead of requiring `_can_manage_master_data`."""
    sailor = await require_linked_sailor(session, acting)
    changes = request.model_dump(exclude_unset=True)
    profile_public = changes.pop("profile_public", None)
    if profile_public is not None:
        sailor.profile_public_choice = profile_public
    for field, value in changes.items():
        setattr(sailor, field, value)
    await session.commit()
    return _me_out(sailor)


@me_router.post("/me/photo", response_model=SailorMeOut, summary="Upload or replace my photo")
async def upload_my_photo(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> SailorMeOut:
    sailor = await require_linked_sailor(session, acting)
    raw = await file.read()
    await asyncio.to_thread(_save_photo, sailor.id, raw)
    return _me_out(sailor)


@me_router.delete("/me/photo", status_code=status.HTTP_204_NO_CONTENT, summary="Remove my photo")
async def delete_my_photo(
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> Response:
    """Removing a photo that doesn't exist is not an error — there is simply nothing to do."""
    sailor = await require_linked_sailor(session, acting)
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
    minor = is_minor(sailor.birth_date, date.today()) is not False
    if (minor or not sailor.profile_public) and await connected_to_sailor(session, acting, sailor):
        return FileResponse(path, media_type="image/jpeg")
    if minor:
        raise Problem(
            403,
            "sailor-photo-protected",
            "This sailor is a minor, or their date of birth is not on file. Their photo is "
            "only shown to a signed-in account connected to them: the sailor themselves, "
            "administration/editorial staff, or their club's leadership.",
        )
    # Story S-4: a hidden profile takes its photo with it — the same 404 as a sailor
    # without one, for whoever is not connected to the person.
    if not sailor.profile_public:
        raise Problem(404, "sailor-photo-not-found", "This sailor has no photo.")

    return FileResponse(path, media_type="image/jpeg")


def _me_out(sailor: Sailor) -> SailorMeOut:
    return SailorMeOut(
        id=sailor.id,
        first_name=sailor.first_name,
        last_name=sailor.last_name,
        birth_date=sailor.birth_date,
        has_photo=_photo_path(sailor.id).exists(),
        profile_public=sailor.profile_public,
    )


def _photo_path(sailor_id: int) -> Path:
    directory = Path(settings.uploads_dir) / "sailors"
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"{sailor_id}.jpg"


def _save_photo(sailor_id: int, raw: bytes) -> None:
    """Validates, then center-crops and downsizes the upload — Story S-2.

    **Storage**: a deterministic path (`uploads/sailors/{id}.jpg`) needs no database
    column — the file's existence *is* the "has a photo" state (`SailorMeOut.has_photo`,
    `_me_out`). Not versioned (see `.gitignore`); Postgres/S3-backed storage remains a
    later option once this goes into production, see `docs/userstories/README.md`, "Still to Write".

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
    pictures.check(raw, code="sailor-photo", what="The photo", max_bytes=_MAX_UPLOAD_BYTES)
    image = pictures.square(pictures.upright(raw, code="sailor-photo"), _PHOTO_SIZE)
    _photo_path(sailor_id).write_bytes(pictures.jpeg(image))


async def connected_to_sailor(session: AsyncSession, acting: User | None, sailor: Sailor) -> bool:
    """Who may see a photo or a profile page that is not public — Story S-2's own open
    question, resolved here, and the same circle Story S-4 opens a hidden page for.

    An **adult's** photo is public: "so that people see who sails for the club" is the whole
    point of S-2, and there is no reason to gate it. A minor's photo is sensitive in exactly
    the way the waiver story (S-1) already treats minors' data with extra care, so it is shown
    only to a signed-in account with an actual connection to that person: the sailor
    themselves, administration (who already manage this data unrestricted, see
    `_can_manage_master_data`), or a manager of a club this sailor is registered with (their
    squad club, not just any club).

    An **unknown** birth date is treated like a minor's, not like an adult's — see the caller.
    """
    if acting is None:
        return False
    if authz.check(acting, Relation.ADMIN):
        return True
    if sailor.email is not None and sailor.email.lower() == acting.email.lower():
        return True
    managed = authz.list_objects(acting, Relation.MANAGER, ObjectType.CLUB)
    if managed:
        club_ids = (
            await session.execute(
                select(Team.club_id)
                .join(TeamMembership, TeamMembership.team_id == Team.id)
                .where(TeamMembership.sailor_id == sailor.id)
                .distinct()
            )
        ).scalars()
        if managed & set(club_ids):
            return True
    return False


# ------------------------------------------------------------------ Helper functions


def _can_manage_master_data(acting: User) -> None:
    """People are managed by administration and club leadership.

    Club leadership is included because they register their own sailors — they know the
    spelling of names, not the head office.
    """
    if authz.check(acting, Relation.ADMIN) or authz.list_objects(
        acting, Relation.MANAGER, ObjectType.CLUB
    ):
        return
    raise Problem(
        403,
        "sailor-manage-forbidden",
        "Only administration and club leadership can manage sailors.",
    )


async def _may_change_sailor(session: AsyncSession, acting: User, sailor: Sailor) -> None:
    """Story V-4: a club's organizer changes the people *their* club's squads or entries
    hold — or anyone nobody's squad holds yet, who belongs to no club. Creating and
    finding stay open to every club's organizer (`_can_manage_master_data`): a new
    person has no club to scope by."""
    if authz.check(acting, Relation.ADMIN):
        return
    clubs = set(
        (
            await session.execute(
                select(Team.club_id)
                .join(TeamMembership, TeamMembership.team_id == Team.id)
                .where(TeamMembership.sailor_id == sailor.id)
            )
        ).scalars()
    )
    if not clubs or clubs & authz.list_objects(acting, Relation.MANAGER, ObjectType.CLUB):
        return
    raise Problem(
        403,
        "sailor-not-yours",
        "This person sails for another club; only that club's organizers can change them.",
        sailor_id=sailor.id,
    )


def _can_manage_squad(acting: User, team: Team) -> None:
    if authz.check(acting, Relation.MANAGER, on=ObjectRef(ObjectType.CLUB, team.club_id)):
        return
    raise Problem(
        403,
        "squad-manage-forbidden",
        "Only club leadership of the same club can manage the squad.",
    )


async def _sailor(session: AsyncSession, sailor_id: int) -> Sailor:
    sailor = await get_or_404(session, Sailor, sailor_id)
    return sailor


async def _team(session: AsyncSession, team_id: int) -> Team:
    team = await get_or_404(session, Team, team_id)
    return team


async def _email_taken(session: AsyncSession, email: str, *, except_id: int | None = None) -> bool:
    stmt = select(Sailor.id).where(Sailor.email == email)
    if except_id is not None:
        stmt = stmt.where(Sailor.id != except_id)
    return (await session.execute(stmt.limit(1))).scalar_one_or_none() is not None


async def _all_exist(session: AsyncSession, sailor_ids: set[int]) -> None:
    found = set(
        (await session.execute(select(Sailor.id).where(Sailor.id.in_(sailor_ids)))).scalars()
    )
    missing = sorted(sailor_ids - found)
    if missing:
        raise Problem(
            404,
            "squad-unknown-sailor",
            "Some of these people do not exist.",
            sailor_ids=missing,
        )


async def _not_already_in_series(session: AsyncSession, team: Team, sailor_ids: set[int]) -> None:
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
        # The names travel as data, not inside a sentence: the screen builds the sentence
        # in the reader's language (`errors.squad-sailor-in-another-club`), and a sentence
        # assembled here could only ever be in one.
        raise Problem(
            409,
            "squad-sailor-in-another-club",
            "Some of these people already sail for another club in this series.",
            sailors=[f"{first} {last}" for first, last in rows],
        )


async def _not_removing_lined_up(session: AsyncSession, team: Team, staying: set[int]) -> None:
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
    elif team.event_id is not None:
        # A stand-alone event's squad only feeds that event's crew.
        stmt = stmt.where(Event.id == team.event_id)

    selected = (await session.execute(stmt)).all()
    if selected:
        # Sailor *and* matchday, because the fix is "go and change that lineup first" and
        # the organizer needs to know which one.
        raise Problem(
            409,
            "squad-member-is-lined-up",
            "Some of these people are lined up for a matchday.",
            selections=[
                {"sailor": f"{first} {last}", "event": title} for first, last, title in selected
            ],
        )


async def _squad_limits(session: AsyncSession, team: Team) -> tuple[int, int]:
    """The squad size the competition asks for: the series', or the stand-alone event's."""
    if team.series_id is not None:
        row = (
            await session.execute(
                select(Series.squad_min, Series.squad_max).where(Series.id == team.series_id)
            )
        ).one()
    elif team.event_id is not None:
        row = (
            await session.execute(
                select(Event.squad_min, Event.squad_max).where(Event.id == team.event_id)
            )
        ).one()
    else:
        return 4, 10
    return int(row[0]), int(row[1])


async def _squad_out(session: AsyncSession, team: Team) -> SquadOut:
    squad_min, squad_max = await _squad_limits(session, team)
    rows = (
        await session.execute(
            select(TeamMembership, Sailor)
            .join(Sailor, TeamMembership.sailor_id == Sailor.id)
            .where(TeamMembership.team_id == team.id)
        )
    ).all()
    members = sorted(
        (MemberOut.of(sailor, membership.role) for membership, sailor in rows),
        key=MemberOut.announce_order,
    )
    return SquadOut(
        team_id=team.id,
        club_id=team.club_id,
        series_id=team.series_id,
        squad_min=squad_min,
        squad_max=squad_max,
        members=members,
    )
