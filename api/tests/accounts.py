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
from app.models import Person
from app.models.auth import Grant, PasswordCredential, Relation, User
from app.services import people
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


async def account(email: str, *grants: Grant, **fields) -> int:
    """An account holding exactly these tuples, and its person — a club's ``member``
    among them becomes an active membership. An old account under the address starts
    over first. Returns the account's id."""
    await forget(email)
    clubs = [g.club_id for g in grants if g.relation == Relation.MEMBER]
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
