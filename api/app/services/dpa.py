"""The data processing agreement a club accepts before working with its people (Story V-17).

The club is controller of its members' data; the association processes it on the site —
so every club has the agreement, decided 2026-11-07 ("always"). ``ensure`` is the one
gate the club's own writes call; the league office acting for the association passes.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import authz
from app.authz import ObjectRef
from app.models import ClubDpa, Person
from app.models.auth import ObjectType, Relation, User
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


def acting_clubs(user: User, person: Person) -> list[int]:
    """The clubs through which ``user`` acts on ``person``: those of the person's clubs
    the user organizes (``manager``, which a club's ``admin`` is too). Empty when the
    user acts as the person, their guardian, or the league office."""
    return [
        club_id
        for club_id in person.club_ids
        if authz.check(user, Relation.MANAGER, on=ObjectRef(ObjectType.CLUB, club_id))
    ]


async def accepted_any(session: AsyncSession, club_ids: list[int]) -> bool:
    for club_id in club_ids:
        if await current(session, club_id) is not None:
            return True
    return False


async def ensure_for_person(session: AsyncSession, user: User, person: Person) -> None:
    """The gate for a club's side acting on one of its people — changing them, linking a
    parent, signing or scanning a waiver for them, reading their documents. Checked on
    the club the user **acts through** (review 5.6): another of the person's clubs having
    accepted does not make this one's work lawful. Someone acting not through a club —
    the person, a guardian, the league office — passes."""
    if authz.check(user, Relation.ADMIN):
        return
    clubs = acting_clubs(user, person)
    if clubs and not await accepted_any(session, clubs):
        await ensure(session, user, clubs[0])
