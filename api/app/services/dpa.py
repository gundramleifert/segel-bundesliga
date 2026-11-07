"""The data processing agreement a club accepts before working with its people (Story V-17).

The club is controller of its members' data; the association processes it on the site —
so every club has the agreement, decided 2026-11-07 ("always"). ``ensure`` is the one
gate the club's own writes call; the league office acting for the association passes.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import authz
from app.models import ClubDpa
from app.models.auth import Relation, User
from app.problems import Problem

# shortcut: the text lives in the `legal` locale (dpa.*) beside this version, not frozen in
# a table like the waiver's; bump this with every change of that text, and move it into a
# table once the lawyer's text needs a history.
DPA_VERSION = "2026-11-07"


async def current(session: AsyncSession, club_id: int) -> ClubDpa | None:
    """The club's acceptance of the version in force, if any."""
    return await session.scalar(
        select(ClubDpa).where(ClubDpa.club_id == club_id, ClubDpa.version == DPA_VERSION)
    )


async def ensure(session: AsyncSession, user: User, club_id: int) -> None:
    """Refuses the club's side with ``dpa-required`` until the club accepted."""
    if authz.check(user, Relation.ADMIN):
        return
    if await current(session, club_id) is None:
        raise Problem(
            409,
            "dpa-required",
            "The club has not accepted the data processing agreement yet.",
            club_id=club_id,
        )


async def ensure_any(session: AsyncSession, user: User, club_ids: list[int]) -> None:
    """For a person in several clubs: one of them having accepted is enough; a person in
    no club is the league office's or anyone's to complete, and needs none."""
    if not club_ids or authz.check(user, Relation.ADMIN):
        return
    for club_id in club_ids:
        if await current(session, club_id) is not None:
            return
    await ensure(session, user, club_ids[0])
