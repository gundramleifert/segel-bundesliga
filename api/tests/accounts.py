"""Accounts for tests, with the person every account has — and every person has an
account (#40, #52, `docs/PLAN_PEOPLE.md`).

A club's ``member`` is a tuple written only by the membership (`participation.activate`).
A test that wants "a member of club 3" still says ``Grant(relation=Relation.MEMBER,
club_id=3)`` — :func:`account` turns it into the active membership and its tuple, so the
tests read as before and the database holds what the app writes.
"""

from __future__ import annotations

from sqlalchemy import delete, select

from app.db import SessionLocal
from app.models import ClubDpa, Person
from app.models.auth import Grant, PasswordCredential, Relation, User
from app.models.base import utcnow
from app.services import dpa, people
from app.services.participation import activate


async def forget(email: str) -> None:
    """The account under this address starts over — no roles, no sign-in, no password —
    as an account nobody has used. Its person and their clubs stay: the address may be a
    seeded sailor's, whose club the next test relies on. Accounts are never deleted
    (#52), so this resets in place."""
    async with SessionLocal() as session:
        user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if user is None:
            return
        await session.execute(
            delete(PasswordCredential).where(PasswordCredential.user_id == user.id)
        )
        user.identities = []
        user.grants = [g for g in user.grants if g.relation == Relation.MEMBER]
        user.is_active = True
        user.email_verified = False
        user.last_login_at = None
        await session.commit()


async def account(email: str, *grants: Grant, dpa_accepted: bool = True, **fields) -> int:
    """An account holding exactly these tuples, and its person — a club's ``member``
    among them becomes an active membership. An old account under the address starts
    over first. Returns the account's id.

    A club it organizes has accepted the data processing agreement (Story V-17) unless
    ``dpa_accepted=False`` — the one story about that agreement says so; every other one
    is about what the club does once it has."""
    await forget(email)
    clubs = [g.club_id for g in grants if g.relation == Relation.MEMBER]
    if dpa_accepted:
        for club_id in {g.club_id for g in grants if g.club_id and g.relation != Relation.MEMBER}:
            await accept_dpa(club_id)
    display_name = fields.pop("display_name", email.split("@")[0])
    async with SessionLocal() as session:
        user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if user is None:
            person = await people.new_person(
                session, first_name="", last_name=display_name, email=email
            )
            user = (
                await session.execute(select(User).where(User.id == person.user_id))
            ).scalar_one()
        else:
            person = (
                await session.execute(select(Person).where(Person.user_id == user.id))
            ).scalar_one()
        user.display_name = display_name
        for field, value in fields.items():
            setattr(user, field, value)
        user.grants.extend(g for g in grants if g.relation != Relation.MEMBER)
        for club in clubs:
            await activate(session, person, club)
        await session.commit()
        return user.id


async def join(email: str, club_id: int) -> None:
    """The account under this address becomes an active member of the club."""
    async with SessionLocal() as session:
        person = (
            await session.execute(
                select(Person).join(User, User.id == Person.user_id).where(User.email == email)
            )
        ).scalar_one()
        await activate(session, person, club_id)
        await session.commit()


async def accept_dpa(club_id: int) -> None:
    """The club accepted the agreement in force (Story V-17), if it had not."""
    async with SessionLocal() as session:
        if await dpa.current(session, club_id) is None:
            session.add(
                ClubDpa(
                    club_id=club_id,
                    version=dpa.DPA_VERSION,
                    accepted_by_name="Test",
                    accepted_at=utcnow(),
                )
            )
            await session.commit()
