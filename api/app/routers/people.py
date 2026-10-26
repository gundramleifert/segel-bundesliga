"""Create people and register squad — Stories V-1 and V-4; self-service profile — Story S-2.

Two levels that belong together:

* The **Person** (`Person`). They exist independently of any competition
  and can sail for multiple clubs.
* The **Squad** (`TeamMembership`) is the registration of this person for a series. From this,
  the club later selects the lineup for a matchday (`EventCrew`, Story V-2).

The rule enforced here: **Within a series, a person competes only once.**
Sailing for multiple clubs is allowed — competing against oneself is not.

This file also carries the self-service half of Story S-2 (`me_router`, mounted at
`/api/people`, separate from the `/api/admin` router above because a signed-in sailor is
not administration): viewing/editing one's own name and birthdate, and a profile photo.
See the docstring on `_save_photo` for the storage and minors-visibility design.
"""

from __future__ import annotations

import asyncio
from collections import Counter
from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, File, UploadFile, status
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import authz
from app.auth import current_user, optional_user
from app.authz import ObjectRef
from app.config import settings
from app.db import get_session
from app.filters import PersonFilter
from app.listing import ListDepends
from app.models import (
    Club,
    Event,
    EventCrew,
    Person,
    Series,
    Team,
    TeamMembership,
    TeamStatus,
)
from app.models.auth import ObjectType, Relation, User
from app.models.org import CrewRole
from app.pagination import (
    Page,
    PageInput,
    PageParams,
    page_of,
    paginate,
)
from app.problems import Problem
from app.schemas.public import MemberOut
from app.services import is_minor, pictures
from app.services.contexts import require_linked_person
from app.services.lookup import get_or_404
from app.services.participation import connect_person

router = APIRouter(prefix="/api/admin", tags=["administration"])
me_router = APIRouter(prefix="/api/people", tags=["people"])


class PersonFields(BaseModel):
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


class PersonCreate(PersonFields):
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
    # The club the person sails for (Story V-4). A club's organizer creates people for
    # their own club, so it is required of them; the league office may leave it empty.
    club_id: int | None = None


class PersonUpdate(PersonFields):
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


class PersonRegistrationOut(BaseModel):
    """One series registration of a person — Story V-1.

    A `TeamMembership` row, as the candidate list needs it. There is one per registration
    and a person legitimately has several: sailing for more than one club is allowed, and
    only doing it twice *within a series* is not.
    """

    team_id: int
    club: SquadClubOut
    series: SquadSeriesOut
    role: CrewRole


class PersonAdminOut(BaseModel):
    """Like MemberOut, but with contact details — administration needs them, the website doesn't."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    first_name: str
    last_name: str
    email: str | None = None
    birth_date: date | None = None
    # Story S-4: management sees the sailor's choice, never sets it (`PersonUpdate` has
    # no such field).
    profile_public: bool = True
    # How many series this person is registered for. Says at a glance whether they're
    # in a squad anywhere.
    squads: int = 0
    # Where, specifically. A bare count cannot answer either question a squad screen has
    # — "is this the right Nanisberg" and "can I add them to *this* series" — because
    # eighteen people share that surname and a person may sail for several clubs at once
    # (Story V-1).
    registrations: list[PersonRegistrationOut] = Field(default_factory=list)
    # The clubs the person sails for (Story V-4): a squad takes only its own club's people,
    # or someone who sails for nobody yet. The squad screen greys out the rest.
    club_ids: list[int] = Field(default_factory=list)


class PersonMeOut(BaseModel):
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


class PersonMeUpdate(PersonFields):
    """Self-service edit. No `email` field: identity is out of scope here — it changes
    via the account, not the person record, and a sailor may never grant themselves
    someone else's record by re-pointing the email that links the two."""

    first_name: str | None = Field(default=None, min_length=1, max_length=80)
    last_name: str | None = Field(default=None, min_length=1, max_length=80)
    birth_date: date | None = Field(default=None, le=date.today())
    # Story S-4 — the one field here management cannot set for someone else. Null (or
    # absent) leaves the choice as it is.
    profile_public: bool | None = None


class SquadMemberIn(BaseModel):
    person_id: int
    role: CrewRole = CrewRole.CREW


class SquadSetRequest(BaseModel):
    members: list[SquadMemberIn] = Field(
        description="The complete squad. An empty list removes it."
    )


class SquadLineupOut(BaseModel):
    """One matchday a squad member is lined up for — the squad panel names them beside the
    person, so it is plain who cannot leave the squad before that lineup changes."""

    person_id: int
    event_id: int
    title: str
    starts_on: date | None = None


class SquadOut(BaseModel):
    team_id: int
    club_id: int
    series_id: int | None
    # The size the series (or the stand-alone event) asks for — Story V-1. The panel reads
    # them here, never off a constant.
    squad_min: int
    squad_max: int
    members: list[MemberOut] = Field(default_factory=list)
    #: The members' lineups at this competition's matchdays, earliest first.
    lineups: list[SquadLineupOut] = Field(default_factory=list)


# ------------------------------------------------------------------------ Sailors


#: What this list may be sorted by — Story A-13. A map rather than "any column of the
#: model": a sort parameter is public API, and exposing the model's attribute names would
@router.get("/people", response_model=Page[PersonAdminOut], summary="Search people")
async def list_people(
    filters: PersonFilter = ListDepends(PersonFilter),
    params: PageParams = PageInput,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> Page[PersonAdminOut]:
    """One page of people, filtered by `q` and sorted by `sort` (Story A-13).

    This used to answer with up to 500 rows and offer no way to ask for the 501st, so the
    screen showed whatever the first 500 happened to be and the rest of the register was
    reachable only by guessing a search term.
    """
    _can_manage_master_data(acting)

    people, total = await paginate(session, filters.sort(filters.filter(select(Person))), params)
    registrations = await _registrations_by_person(session, [s.id for s in people])

    return page_of(
        [
            PersonAdminOut.model_validate(person).model_copy(
                update={
                    "squads": len(registrations.get(person.id, [])),
                    "registrations": registrations.get(person.id, []),
                }
            )
            for person in people
        ],
        total,
        params,
    )


async def _registrations_by_person(
    session: AsyncSession, person_ids: list[int]
) -> dict[int, list[PersonRegistrationOut]]:
    """Every series registration of these people, grouped by person.

    **Series registrations only** (`Team.event_id is None`). The other kind of `Team` row
    is an entry in one event, carries no squad, and naming it here would tell a club
    manager the person is registered somewhere they are not (Story V-1).

    One query rather than one per person: this feeds a candidate list of up to 500.
    """
    if not person_ids:
        return {}

    rows = (
        await session.execute(
            select(TeamMembership.person_id, Team.id, TeamMembership.role, Club, Series)
            .join(Team, TeamMembership.team_id == Team.id)
            .join(Club, Team.club_id == Club.id)
            .join(Series, Team.series_id == Series.id)
            .where(
                TeamMembership.person_id.in_(person_ids),
                Team.event_id.is_(None),
            )
            .order_by(Series.year.desc(), Series.name, Club.name)
        )
    ).all()

    grouped: dict[int, list[PersonRegistrationOut]] = {}
    for person_id, team_id, role, club, series in rows:
        grouped.setdefault(person_id, []).append(
            PersonRegistrationOut(
                team_id=team_id,
                club=SquadClubOut(id=club.id, name=club.name, short_name=club.short_name),
                series=SquadSeriesOut(id=series.id, name=series.name),
                role=role,
            )
        )
    return grouped


@router.post(
    "/people",
    response_model=PersonAdminOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create person",
)
async def create_person(
    request: PersonCreate,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> PersonAdminOut:
    """Create a person, sailing for `club_id` (Story V-4).

    They don't belong to any competition yet — that comes with squad registration. A
    club's organizer creates people for a club they organize; only the league office
    creates someone who sails for no club yet.
    """
    _can_manage_master_data(acting)
    if request.club_id is None:
        if not authz.check(acting, Relation.ADMIN):
            raise Problem(
                422, "person-needs-club", "Say which of your clubs this person sails for."
            )
    else:
        if await session.get(Club, request.club_id) is None:
            raise Problem(404, "club-not-found", "No such club.")
        if not authz.check(
            acting, Relation.MANAGER, on=ObjectRef(ObjectType.CLUB, request.club_id)
        ):
            raise Problem(
                403,
                "person-club-not-yours",
                "You create people only for a club you organize.",
                club_id=request.club_id,
            )

    if request.email and await _email_taken(session, request.email):
        raise Problem(
            409,
            "email-taken",
            f"Email {request.email} is already taken. Emails are unique.",
            email=request.email,
        )

    person = Person(**request.model_dump(exclude={"club_id"}), club_memberships=[])
    if request.club_id is not None:
        connect_person(person, request.club_id)
    session.add(person)
    await session.commit()
    return PersonAdminOut.model_validate(person)


@router.patch("/people/{person_id}", response_model=PersonAdminOut, summary="Update person")
async def update_person(
    person_id: int,
    request: PersonUpdate,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> PersonAdminOut:
    _can_manage_master_data(acting)
    person = await _person(session, person_id)
    await _may_change_person(session, acting, person)

    changes = request.model_dump(exclude_unset=True)
    email = changes.get("email")
    if (
        "email" in changes
        and person.email is not None
        and email != person.email
        and not authz.check(acting, Relation.ADMIN)
    ):
        # The address is what links the record to an account (waivers, the profile): a
        # club's organizer gives it to someone who has none, but re-pointing it would hand
        # the person's record to another account — the league office's to do.
        raise Problem(
            403,
            "person-email-locked",
            "Only the league office changes the address of a sailor who has one.",
            person_id=person.id,
        )
    if email and await _email_taken(session, email, except_id=person.id):
        raise Problem(
            409, "email-taken", f"Email {email} is already taken. Emails are unique.", email=email
        )

    for field, value in changes.items():
        setattr(person, field, value)

    await session.commit()
    return PersonAdminOut.model_validate(person)


@router.delete(
    "/people/{person_id}/clubs/{club_id}",
    response_model=PersonAdminOut,
    summary="The person no longer sails for this club",
)
async def disconnect_person_from_club(
    person_id: int,
    club_id: int,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> PersonAdminOut:
    """Story V-4: a club lets someone go — its own connection, never another club's. The
    squads they are in stay as they are; the club just stops being theirs to change."""
    person = await _person(session, person_id)
    if not authz.check(acting, Relation.MANAGER, on=ObjectRef(ObjectType.CLUB, club_id)):
        raise _not_yours(person)
    person.club_memberships = [link for link in person.club_memberships if link.club_id != club_id]
    await session.commit()
    return PersonAdminOut.model_validate(person)


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
    if team.series_id is None and team.number != 1:
        # A stand-alone event's squad hangs off the club's first team (`squad_team`).
        raise Problem(
            422,
            "squad-on-first-team",
            "The club's squad for this event belongs to its first team.",
            team_id=team.id,
        )
    if team.status == TeamStatus.REJECTED:
        raise Problem(
            409,
            "squad-registration-rejected",
            "This registration was rejected; it takes no squad.",
            team_id=team.id,
        )

    desired = {entry.person_id: entry.role for entry in request.members}
    if len(desired) != len(request.members):
        counts = Counter(entry.person_id for entry in request.members)
        twice = sorted(person_id for person_id, n in counts.items() if n > 1)
        raise Problem(
            422,
            "squad-duplicate-person",
            "A person appears twice in this squad.",
            person_ids=twice,
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
    joining = await _may_join(session, acting, team, set(desired))

    await _not_removing_lined_up(session, team, set(desired))
    for person in joining:
        connect_person(person, team.club_id)

    await session.execute(delete(TeamMembership).where(TeamMembership.team_id == team.id))
    session.add_all(
        TeamMembership(team_id=team.id, person_id=person_id, role=role)
        for person_id, role in desired.items()
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


@me_router.get("/me", response_model=PersonMeOut, summary="My own person record")
async def get_my_person(
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> PersonMeOut:
    """Story S-2: a sailor views their own name, birthdate, and photo status.

    Not every account has a linked sailor — an admin-only account, for instance. That is
    not an error, just nothing to show here (404, not a crash).
    """
    person = await require_linked_person(session, acting)
    return _me_out(person)


@me_router.patch("/me", response_model=PersonMeOut, summary="Edit my own person record")
async def update_my_person(
    request: PersonMeUpdate,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> PersonMeOut:
    """A sailor corrects their own name or birthdate — the same fields a team manager or
    admin can already set via `PATCH /api/admin/people/{id}`, just scoped to "my own
    record" instead of requiring `_can_manage_master_data`."""
    person = await require_linked_person(session, acting)
    changes = request.model_dump(exclude_unset=True)
    profile_public = changes.pop("profile_public", None)
    if profile_public is not None:
        person.profile_public_choice = profile_public
    for field, value in changes.items():
        setattr(person, field, value)
    await session.commit()
    return _me_out(person)


@me_router.post("/me/photo", response_model=PersonMeOut, summary="Upload or replace my photo")
async def upload_my_photo(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> PersonMeOut:
    person = await require_linked_person(session, acting)
    raw = await file.read()
    await asyncio.to_thread(_save_photo, person.id, raw)
    return _me_out(person)


@me_router.delete("/me/photo", status_code=status.HTTP_204_NO_CONTENT, summary="Remove my photo")
async def delete_my_photo(
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> Response:
    """Removing a photo that doesn't exist is not an error — there is simply nothing to do."""
    person = await require_linked_person(session, acting)
    _photo_path(person.id).unlink(missing_ok=True)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@me_router.get("/{person_id}/photo", summary="A person's photo")
async def get_person_photo(
    person_id: int,
    session: AsyncSession = Depends(get_session),
    acting: User | None = Depends(optional_user),
) -> FileResponse:
    """Serves the stored photo — see `_save_photo` for the minors-visibility rule this
    enforces. There is no placeholder here: the frontend already renders one when
    `has_photo` is false, so a missing file is simply a 404."""
    person = await _person(session, person_id)
    path = _photo_path(person.id)
    if not path.exists():
        raise Problem(404, "person-photo-not-found", "This person has no photo.")

    # `is_minor` is deliberately tri-state: None means the birth date is unset. None is
    # falsy, so a plain truth test here would fail *open* — and since the birth date is an
    # optional, self-reported field, leaving it blank would publish a 14-year-old's photo to
    # the world, defeating the entire gate by omission. Anything other than a definite
    # "adult" therefore requires the connected-viewer check. A sailor lifts the restriction
    # on their own photo by filling in their birth date in the same self-service form they
    # uploaded it from. `app/routers/waivers.py` treats the same unknown as blocking.
    minor = is_minor(person.birth_date, date.today()) is not False
    if (minor or not person.profile_public) and await connected_to_person(session, acting, person):
        return FileResponse(path, media_type="image/jpeg")
    if minor:
        raise Problem(
            403,
            "person-photo-protected",
            "This person is a minor, or their date of birth is not on file. Their photo is "
            "only shown to a signed-in account connected to them: the sailor themselves, "
            "administration, or their club's leadership.",
        )
    # Story S-4: a hidden profile takes its photo with it — the same 404 as a sailor
    # without one, for whoever is not connected to the person.
    if not person.profile_public:
        raise Problem(404, "person-photo-not-found", "This person has no photo.")

    return FileResponse(path, media_type="image/jpeg")


def _me_out(person: Person) -> PersonMeOut:
    return PersonMeOut(
        id=person.id,
        first_name=person.first_name,
        last_name=person.last_name,
        birth_date=person.birth_date,
        has_photo=_photo_path(person.id).exists(),
        profile_public=person.profile_public,
    )


def _photo_path(person_id: int) -> Path:
    directory = Path(settings.uploads_dir) / "sailors"
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"{person_id}.jpg"


def _save_photo(person_id: int, raw: bytes) -> None:
    """Validates, then center-crops and downsizes the upload — Story S-2.

    **Storage**: a deterministic path (`uploads/sailors/{id}.jpg`) needs no database
    column — the file's existence *is* the "has a photo" state (`PersonMeOut.has_photo`,
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
    pictures.check(raw, code="person-photo", what="The photo", max_bytes=_MAX_UPLOAD_BYTES)
    image = pictures.square(pictures.upright(raw, code="person-photo"), _PHOTO_SIZE)
    _photo_path(person_id).write_bytes(pictures.jpeg(image))


async def connected_to_person(session: AsyncSession, acting: User | None, person: Person) -> bool:
    """Who may see a photo or a profile page that is not public — Story S-2's own open
    question, resolved here, and the same circle Story S-4 opens a hidden page for.

    An **adult's** photo is public: "so that people see who sails for the club" is the whole
    point of S-2, and there is no reason to gate it. A minor's photo is sensitive in exactly
    the way the waiver story (S-1) already treats minors' data with extra care, so it is shown
    only to a signed-in account with an actual connection to that person: the sailor
    themselves, administration (who already manage this data unrestricted, see
    `_can_manage_master_data`), or a manager of a club this sailor sails for (the model's
    ``manager`` on the sailor, not just any club).

    An **unknown** birth date is treated like a minor's, not like an adult's — see the caller.
    """
    if acting is None:
        return False
    if person.user_id is not None and person.user_id == acting.id:
        return True
    return authz.check(acting, Relation.MANAGER, on=person)


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
        "person-manage-forbidden",
        "Only administration and club leadership can manage people.",
    )


async def _may_change_person(session: AsyncSession, acting: User, person: Person) -> None:
    """Story V-4: a club's organizer changes the people who sail for *their* club — or
    someone who sails for no club yet. Finding stays open to every club's organizer
    (`_can_manage_master_data`): that is how they see whom they may not add."""
    if not person.club_ids or authz.check(acting, Relation.MANAGER, on=person):
        return
    raise _not_yours(person)


def _not_yours(person: Person) -> Problem:
    return Problem(
        403,
        "person-not-yours",
        "This person sails for another club; only that club's organizers can change them.",
        person_id=person.id,
    )


def _can_manage_squad(acting: User, team: Team) -> None:
    if authz.check(acting, Relation.MANAGER, on=ObjectRef(ObjectType.CLUB, team.club_id)):
        return
    raise Problem(
        403,
        "squad-manage-forbidden",
        "Only club leadership of the same club can manage the squad.",
    )


async def _person(session: AsyncSession, person_id: int) -> Person:
    person = await get_or_404(session, Person, person_id)
    return person


async def _team(session: AsyncSession, team_id: int) -> Team:
    team = await get_or_404(session, Team, team_id)
    return team


async def _email_taken(session: AsyncSession, email: str, *, except_id: int | None = None) -> bool:
    stmt = select(Person.id).where(Person.email == email)
    if except_id is not None:
        stmt = stmt.where(Person.id != except_id)
    return (await session.execute(stmt.limit(1))).scalar_one_or_none() is not None


async def _all_exist(session: AsyncSession, person_ids: set[int]) -> None:
    found = set(
        (await session.execute(select(Person.id).where(Person.id.in_(person_ids)))).scalars()
    )
    missing = sorted(person_ids - found)
    if missing:
        raise Problem(
            404,
            "squad-unknown-person",
            "Some of these people do not exist.",
            person_ids=missing,
        )


async def _not_already_in_series(session: AsyncSession, team: Team, person_ids: set[int]) -> None:
    """The core rule: once per series, for whichever club."""
    if team.series_id is None:
        return

    rows = (
        await session.execute(
            select(Person.first_name, Person.last_name)
            .join(TeamMembership, TeamMembership.person_id == Person.id)
            .join(Team, TeamMembership.team_id == Team.id)
            .where(
                Team.series_id == team.series_id,
                Team.event_id.is_(None),
                Team.id != team.id,
                TeamMembership.person_id.in_(person_ids),
            )
        )
    ).all()
    if rows:
        # The names travel as data, not inside a sentence: the screen builds the sentence
        # in the reader's language (`errors.squad-person-in-another-club`), and a sentence
        # assembled here could only ever be in one.
        raise Problem(
            409,
            "squad-person-in-another-club",
            "Some of these people already sail for another club in this series.",
            people=[f"{first} {last}" for first, last in rows],
        )


async def _may_join(
    session: AsyncSession, acting: User, team: Team, desired: set[int]
) -> list[Person]:
    """Who joins the squad with this save — refused if they sail for another club (Story
    V-4). A club's organizer adds the people of their own club, and someone who sails for
    nobody yet, who then sails for it. The league office adds anyone — the one way a
    person comes to sail for a second club."""
    current = set(
        (
            await session.execute(
                select(TeamMembership.person_id).where(TeamMembership.team_id == team.id)
            )
        ).scalars()
    )
    joining = list(
        (
            await session.execute(
                select(Person).where(Person.id.in_(desired - current)).order_by(Person.id)
            )
        ).scalars()
    )
    if not authz.check(acting, Relation.ADMIN):
        foreign = [s for s in joining if s.club_ids and team.club_id not in s.club_ids]
        if foreign:
            raise Problem(
                403,
                "squad-person-of-another-club",
                "Some of these people sail for another club.",
                people=[s.full_name for s in foreign],
                person_ids=[s.id for s in foreign],
            )
    return joining


async def _not_removing_lined_up(session: AsyncSession, team: Team, staying: set[int]) -> None:
    """People selected for a matchday cannot be removed from the squad."""
    current = set(
        (
            await session.execute(
                select(TeamMembership.person_id).where(TeamMembership.team_id == team.id)
            )
        ).scalars()
    )
    removing = current - staying
    if not removing:
        return

    stmt = (
        select(Person.first_name, Person.last_name, Event.title)
        .join(EventCrew, EventCrew.person_id == Person.id)
        .join(Event, EventCrew.event_id == Event.id)
        .join(Team, EventCrew.team_id == Team.id)
        .where(Team.club_id == team.club_id, EventCrew.person_id.in_(removing))
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
    else:
        # A team is a series registration or an event entry — never neither (the model's
        # check constraint), so this is the stand-alone event's.
        row = (
            await session.execute(
                select(Event.squad_min, Event.squad_max).where(Event.id == team.event_id)
            )
        ).one()
    return int(row[0]), int(row[1])


async def _squad_out(session: AsyncSession, team: Team) -> SquadOut:
    squad_min, squad_max = await _squad_limits(session, team)
    rows = (
        await session.execute(
            select(TeamMembership, Person)
            .join(Person, TeamMembership.person_id == Person.id)
            .where(TeamMembership.team_id == team.id)
        )
    ).all()
    members = sorted(
        (MemberOut.of(person, membership.role) for membership, person in rows),
        key=MemberOut.announce_order,
    )
    return SquadOut(
        team_id=team.id,
        club_id=team.club_id,
        series_id=team.series_id,
        squad_min=squad_min,
        squad_max=squad_max,
        members=members,
        lineups=await _squad_lineups(session, team, {m.id for m in members}),
    )


async def _squad_lineups(
    session: AsyncSession, team: Team, people: set[int]
) -> list[SquadLineupOut]:
    """Where the squad's people are lined up for this club — the same matchdays
    :func:`_not_removing_lined_up` guards: the series' events, or the stand-alone one."""
    if not people:
        return []
    stmt = (
        select(EventCrew.person_id, Event.id, Event.title, Event.starts_on)
        .join(Event, EventCrew.event_id == Event.id)
        .join(Team, EventCrew.team_id == Team.id)
        .where(Team.club_id == team.club_id, EventCrew.person_id.in_(people))
        .order_by(Event.starts_on.asc().nulls_last(), Event.id)
    )
    if team.series_id is not None:
        stmt = stmt.where(Event.series_id == team.series_id)
    elif team.event_id is not None:
        stmt = stmt.where(Event.id == team.event_id)
    return [
        SquadLineupOut(person_id=person, event_id=event, title=title, starts_on=starts_on)
        for person, event, title, starts_on in (await session.execute(stmt)).all()
    ]
