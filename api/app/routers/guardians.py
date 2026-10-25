"""A parent linked to a young sailor — Story V-13; what the parent then does is Story S-8.

Guardianship is a relation tuple, ``user:guardian:sailor`` (Story Z-2), written through
`app/services/grants.py` like every other — so it is checked against the model, never
written twice, and logged. What is particular is **who** may write it: the manager or
admin of a club the child belongs to, decided 2026-10-17. Never the parent (anyone could
claim any child) and never the child. A sailor has no admin of its own in the model, so
these endpoints carry that rule rather than the generic tuple endpoint, which leaves
sailor tuples to the site's admin.

A child "belongs to" a club when they sail for it — the ``club`` edge of a sailor in the
model (`SailorClub`, Story V-4), written when the club creates them or takes them into its
squad, and only by a club they already sail for. Until 2026-10-25 a squad was enough, so
any club could put a child in its squad and then link a parent to them.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import authz
from app.auth import current_user
from app.authz import ObjectRef
from app.db import get_session
from app.models import Club, Sailor, SailorClub
from app.models.auth import Grant, ObjectType, Relation, User
from app.problems import Problem
from app.services import grants
from app.services.waivers import is_minor

router = APIRouter(tags=["guardians"])


class GuardianOut(BaseModel):
    #: The tuple's id — what unlinking deletes.
    id: int
    email: str
    display_name: str | None


class GuardianSailorOut(BaseModel):
    id: int
    first_name: str
    last_name: str


class SailorGuardiansOut(BaseModel):
    """One of the club's sailors and the guardians linked to them."""

    sailor: GuardianSailorOut
    #: Under 18 today — `None` without a date of birth. A guardian accepts the waiver only
    #: while the child is a minor on the competition's reference date (Story S-8).
    minor: bool | None
    guardians: list[GuardianOut]


class LinkGuardian(BaseModel):
    email: str = Field(description="The parent's account, by its address (Story V-9).")


@router.get(
    "/api/clubs/{club_id}/guardians",
    response_model=list[SailorGuardiansOut],
    summary="The club's sailors and their guardians",
)
async def list_club_guardians(
    club_id: int,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> list[SailorGuardiansOut]:
    """Story V-13: for the club's manager or admin — every sailor who sails for the club,
    with the guardians linked to them."""
    if await session.get(Club, club_id) is None:
        raise Problem(404, "club-not-found", "No such club.")
    if not authz.check(acting, Relation.MANAGER, on=ObjectRef(ObjectType.CLUB, club_id)):
        raise _forbidden()
    sailors = await _club_sailors(session, club_id)
    links = await grants.holders(
        session, Relation.GUARDIAN, ObjectType.SAILOR, [s.id for s in sailors]
    )
    accounts = {g.user_id: g.user for g in links}
    return [
        SailorGuardiansOut(
            sailor=GuardianSailorOut(id=s.id, first_name=s.first_name, last_name=s.last_name),
            minor=is_minor(s.birth_date, date.today()),
            guardians=[_out(g, accounts[g.user_id]) for g in links if g.sailor_id == s.id],
        )
        for s in sailors
    ]


@router.post(
    "/api/sailors/{sailor_id}/guardians",
    response_model=GuardianOut,
    status_code=status.HTTP_201_CREATED,
    summary="Link a parent to a sailor",
)
async def link_guardian(
    sailor_id: int,
    request: LinkGuardian,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> GuardianOut:
    """Story V-13: writes `user:guardian:sailor` for an existing account, by email."""
    sailor = await _sailor(session, sailor_id)
    await _may_link(session, acting, sailor)
    email = request.email.strip().lower()
    parent = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if parent is None:
        raise Problem(
            404,
            "guardian-account-missing",
            "No account with this address — the parent registers first.",
        )
    if sailor.email is not None and sailor.email.lower() == email:
        raise Problem(
            422,
            "guardian-is-the-sailor",
            "A sailor cannot be their own guardian.",
        )
    row = await grants.grant(
        session, parent, Relation.GUARDIAN, ObjectType.SAILOR, sailor.id, actor=acting
    )
    await session.commit()
    return _out(row, parent)


@router.delete(
    "/api/sailors/{sailor_id}/guardians/{tuple_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Unlink a parent from a sailor",
)
async def unlink_guardian(
    sailor_id: int,
    tuple_id: int,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> Response:
    sailor = await _sailor(session, sailor_id)
    await _may_link(session, acting, sailor)
    row = await session.get(Grant, tuple_id)
    if row is None or row.sailor_id != sailor.id or row.relation != Relation.GUARDIAN:
        raise Problem(404, "guardian-link-missing", "This sailor has no such guardian.")
    await grants.revoke_row(session, row, actor=acting)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ------------------------------------------------------------------ Helper functions


async def _may_link(session: AsyncSession, acting: User, sailor: Sailor) -> None:
    """The manager of a club the child sails for — the model's ``manager`` on the sailor
    (``manager from club``) — or the league office."""
    if not authz.check(acting, Relation.MANAGER, on=sailor):
        raise _forbidden()


async def _club_sailors(session: AsyncSession, club_id: int) -> list[Sailor]:
    return list(
        (
            await session.execute(
                select(Sailor)
                .join(SailorClub, SailorClub.sailor_id == Sailor.id)
                .where(SailorClub.club_id == club_id)
                .order_by(Sailor.last_name, Sailor.first_name, Sailor.id)
            )
        ).scalars()
    )


async def _sailor(session: AsyncSession, sailor_id: int) -> Sailor:
    sailor = await session.get(Sailor, sailor_id)
    if sailor is None:
        raise Problem(404, "sailor-not-found", "No such sailor.")
    return sailor


def _forbidden() -> Problem:
    return Problem(
        403,
        "guardian-link-forbidden",
        "Only the manager or admin of the sailor's club links a guardian.",
    )


def _out(row: Grant, parent: User) -> GuardianOut:
    return GuardianOut(id=row.id, email=parent.email, display_name=parent.display_name)
