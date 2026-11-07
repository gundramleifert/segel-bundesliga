"""The club's data processing agreement — Story V-17, `app/services/dpa.py`."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app import authz
from app.auth import current_user
from app.db import get_session
from app.models import Club, ClubDpa
from app.models.auth import Relation, User
from app.models.base import utcnow
from app.problems import Problem
from app.services import dpa
from app.services.audit import EntityType, audit
from app.services.lookup import get_or_404

router = APIRouter(prefix="/api/clubs/{club_id}/dpa", tags=["clubs"])


class DpaOut(BaseModel):
    """Which version is in force, and whether and when the club accepted it."""

    version: str
    accepted: bool
    accepted_at: datetime | None = None
    accepted_by_name: str | None = None


class DpaIn(BaseModel):
    """The version read, and the confirmation of the authority to sign for the club."""

    version: str = Field(description="The version shown when accepting.")
    authorized: bool = Field(
        description="I may represent the club, or act on behalf of its board (§ 26 BGB)."
    )


def _out(row: ClubDpa | None) -> DpaOut:
    return DpaOut(
        version=dpa.DPA_VERSION,
        accepted=row is not None,
        accepted_at=row.accepted_at if row else None,
        accepted_by_name=row.accepted_by_name if row else None,
    )


@router.get("", response_model=DpaOut, summary="Club's data processing agreement")
async def get_club_dpa(
    club_id: int,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> DpaOut:
    """Story V-17: the version in force and the club's acceptance, for its organizers."""
    club = await get_or_404(session, Club, club_id)
    authz.ensure(
        acting,
        Relation.ADMIN,
        Relation.MANAGER,
        Relation.TREASURER,
        on=club,
        code="dpa-forbidden",
        title="Only the club's organizers see its data processing agreement.",
    )
    return _out(await dpa.current(session, club.id))


@router.post(
    "",
    response_model=DpaOut,
    status_code=status.HTTP_201_CREATED,
    summary="Accept the data processing agreement",
)
async def accept_club_dpa(
    club_id: int,
    request: DpaIn,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> DpaOut:
    """Story V-17: the club's admin accepts the version in force, confirming they may sign
    for the club. Accepting it a second time changes nothing."""
    club = await get_or_404(session, Club, club_id)
    authz.ensure(
        acting,
        Relation.ADMIN,
        on=club,
        code="dpa-forbidden",
        title="Only the club's admin accepts the data processing agreement.",
    )
    if not request.authorized:
        raise Problem(
            422,
            "dpa-authority-unconfirmed",
            "Confirm that you may represent the club or act on behalf of its board.",
        )
    if request.version != dpa.DPA_VERSION:
        raise Problem(
            409,
            "dpa-version-outdated",
            "A newer version of the agreement is in force; read it first.",
            version=dpa.DPA_VERSION,
        )
    row = await dpa.current(session, club.id)
    if row is None:
        row = ClubDpa(
            club_id=club.id,
            version=dpa.DPA_VERSION,
            accepted_by_user_id=acting.id,
            accepted_by_name=acting.display_name or acting.email,
            accepted_at=utcnow(),
        )
        session.add(row)
        audit(session, EntityType.CLUB, club.id, "accept_dpa", acting, version=dpa.DPA_VERSION)
        await session.commit()
    return _out(row)
