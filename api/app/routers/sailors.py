"""Create sailors and register squad — Stories V-1 and V-4.

Two levels that belong together:

* The **Sailor** (`Sailor`) is a person. They exist independently of any competition
  and can sail for multiple clubs.
* The **Squad** (`TeamMembership`) is the registration of this person for a series. From this,
  the club later selects the lineup for a matchday (`EventCrew`, Story V-2).

The rule enforced here: **Within a series, a person competes only once.**
Sailing for multiple clubs is allowed — competing against oneself is not.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import current_user
from app.db import get_session
from app.i18n import Locale, resolve_locale, tr
from app.models import Event, EventCrew, Sailor, Team, TeamMembership
from app.models.auth import Role, User
from app.models.org import CrewRole
from app.schemas.public import MemberOut

router = APIRouter(prefix="/api/admin", tags=["administration"])


class SailorFelder(BaseModel):
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


class SailorCreate(SailorFelder):
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


class SailorUpdate(SailorFelder):
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


class KaderEintrag(BaseModel):
    sailor_id: int
    role: CrewRole = CrewRole.CREW


class KaderSetzen(BaseModel):
    members: list[KaderEintrag] = Field(
        description="The complete squad. An empty list removes it."
    )


class KaderOut(BaseModel):
    team_id: int
    club_id: int
    series_id: int | None
    members: list[MemberOut] = Field(default_factory=list)


# ------------------------------------------------------------------------ Segler


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
    _darf_stammdaten(acting)

    stmt = select(Sailor).order_by(Sailor.last_name, Sailor.first_name).limit(limit)
    if q:
        muster = f"%{q.strip().lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(Sailor.first_name).like(muster),
                func.lower(Sailor.last_name).like(muster),
                func.lower(Sailor.email).like(muster),
            )
        )
    sailors = list((await session.execute(stmt)).scalars())

    meldungen = dict(
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
            update={"squads": meldungen.get(sailor.id, 0)}
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
    _darf_stammdaten(acting)

    if request.email and await _adresse_belegt(session, request.email):
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
    _darf_stammdaten(acting)
    sailor = await _sailor(session, sailor_id)

    changes = request.model_dump(exclude_unset=True)
    email = changes.get("email")
    if email and await _adresse_belegt(session, email, except_id=sailor.id):
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


# ------------------------------------------------------------------------- Kader


@router.get("/teams/{team_id}/members", response_model=KaderOut, summary="View squad")
async def get_squad(
    team_id: int,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> KaderOut:
    team = await _team(session, team_id)
    _darf_den_kader_pflegen(acting, team)
    return await _kader_out(session, team)


@router.put("/teams/{team_id}/members", response_model=KaderOut, summary="Register squad")
async def set_squad(
    team_id: int,
    request: KaderSetzen,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
    locale: Locale = Depends(resolve_locale),
) -> KaderOut:
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
    _darf_den_kader_pflegen(acting, team)

    if not team.ist_serienmeldung:
        raise HTTPException(
            status_code=422,
            detail=tr(
                locale,
                en="Squad is tied to series registration, not to competition at a single event.",
                de="Der Kader hängt an der Meldung für die Serie, nicht am Antritt zu einer "
                "einzelnen Veranstaltung.",
            ),
        )

    gewuenscht = {eintrag.sailor_id: eintrag.role for eintrag in request.members}
    if len(gewuenscht) != len(request.members):
        raise HTTPException(
            status_code=422,
            detail=tr(
                locale,
                en="A person appears twice in the squad.",
                de="Eine Person steht doppelt im Kader.",
            ),
        )

    if gewuenscht:
        await _alle_vorhanden(session, set(gewuenscht))
        await _nicht_schon_in_der_serie(session, team, set(gewuenscht), locale)

    await _nicht_aufgestellt_entfernen(session, team, set(gewuenscht), locale)

    await session.execute(
        delete(TeamMembership).where(TeamMembership.team_id == team.id)
    )
    session.add_all(
        TeamMembership(team_id=team.id, sailor_id=sailor_id, role=role)
        for sailor_id, role in gewuenscht.items()
    )
    await session.commit()
    return await _kader_out(session, team)


# ------------------------------------------------------------------ Hilfsfunktionen


def _darf_stammdaten(acting: User) -> None:
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


def _darf_den_kader_pflegen(acting: User, team: Team) -> None:
    if acting.has_any(Role.ADMIN):
        return
    if acting.has_any(Role.CLUB_MANAGER) and acting.club_id == team.club_id:
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


async def _adresse_belegt(
    session: AsyncSession, email: str, *, except_id: int | None = None
) -> bool:
    stmt = select(Sailor.id).where(Sailor.email == email)
    if except_id is not None:
        stmt = stmt.where(Sailor.id != except_id)
    return (await session.execute(stmt.limit(1))).scalar_one_or_none() is not None


async def _alle_vorhanden(session: AsyncSession, sailor_ids: set[int]) -> None:
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


async def _nicht_schon_in_der_serie(
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


async def _nicht_aufgestellt_entfernen(
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


async def _kader_out(session: AsyncSession, team: Team) -> KaderOut:
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
    return KaderOut(
        team_id=team.id,
        club_id=team.club_id,
        series_id=team.series_id,
        members=members,
    )
