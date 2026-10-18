"""Who is in a club — the roster (Story V-10).

Membership is the ``member`` tuple on the club (Story Z-5), written by the club's admin
through the tuple endpoints of Story Z-2 and deleted by the member to leave. What is left
here is the one read the club's own people need: who belongs, and what each is to the club.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app import authz
from app.auth import current_user
from app.db import get_session
from app.models import Club
from app.models.auth import ObjectType, Relation, User
from app.problems import Problem
from app.schemas.public import ClubMemberOut
from app.services import grants
from app.services.lookup import get_or_404

router = APIRouter(tags=["clubs"])


@router.get(
    "/api/clubs/{club_id}/members",
    response_model=list[ClubMemberOut],
    summary="Who belongs to this club",
)
async def list_club_members(
    club_id: int,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> list[ClubMemberOut]:
    """Everyone with a ``member`` tuple on the club, with what else they are to it, so the
    organizers are recognizable. Display name only — contact data is the club admin's
    business (the People panel). Open to the club's own members and organizers and to
    staff; a stranger, or a member of a *different* club, gets 403.
    """
    club = await get_or_404(session, Club, club_id)
    if not authz.check(acting, Relation.EDITOR) and not authz.check(
        acting, Relation.MEMBER, Relation.MANAGER, on=club
    ):
        raise Problem(
            403,
            "club-members-restricted-to-members",
            "Only members and organizers of this club, or staff, can see its member list.",
        )

    rows = await grants.grants_on(session, ObjectType.CLUB, club.id)
    by_user: dict[int, tuple[User, list[str]]] = {}
    for row in rows:
        by_user.setdefault(row.user_id, (row.user, []))[1].append(row.relation)
    # `organizer` and `admin` come off the relations collected here, never off
    # `user.grants`: an account reached through `selectinload(Grant.user)` does not get its
    # own `grants` loaded (the eager load stops where the path cycles back to `Grant`), and
    # touching it lazy-loads outside the async context — a 500 for every roster with
    # someone in it besides the caller. Direct tuples, like `authz.read`.
    members = [
        ClubMemberOut(
            user_id=user.id,
            display_name=user.display_name,
            relations=sorted(relations, key=list(Relation).index),
            organizer=Relation.MANAGER in relations or Relation.ADMIN in relations,
            admin=Relation.ADMIN in relations,
        )
        for user, relations in by_user.values()
        if Relation.MEMBER in relations
    ]
    members.sort(key=lambda member: member.display_name)
    return members
