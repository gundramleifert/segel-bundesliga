"""Accounts for tests, with the person every account has (#40, `docs/PLAN_PEOPLE.md`).

A club's ``member`` is not a tuple: it is the account's person's active
``ClubMembership``. A test that wants "a member of club 3" still says
``Grant(relation=Relation.MEMBER, club_id=3)`` — :func:`account` turns it into the
membership, so the tests read as before and the database holds what the app writes.
"""

from __future__ import annotations

from sqlalchemy import select

from app.db import SessionLocal
from app.models import ClubMembership, MembershipStatus, Person
from app.models.auth import Grant, Relation, User


async def forget(email: str) -> None:
    """The account under this address goes (its tuples with it), and the person on record
    there is unlinked, as when an account is deleted — its clubs stay: the address may be
    a seeded sailor's, whose club the next test relies on. SQLite reuses ids: a row left
    behind would belong to the next account."""
    async with SessionLocal() as session:
        old = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if old is not None:
            await session.delete(old)
        person = (
            await session.execute(select(Person).where(Person.email == email))
        ).scalar_one_or_none()
        if person is not None:
            person.user_id = None
        await session.commit()


async def account(email: str, *grants: Grant, **fields) -> int:
    """An account holding exactly these tuples, and its person — a club's ``member``
    among them becomes an active membership. An old account under the address goes
    first. Returns the account's id."""
    await forget(email)
    clubs = [g.club_id for g in grants if g.relation == Relation.MEMBER]
    async with SessionLocal() as session:
        user = User(
            email=email,
            display_name=fields.pop("display_name", email.split("@")[0]),
            grants=[g for g in grants if g.relation != Relation.MEMBER],
            **fields,
        )
        session.add(user)
        await session.flush()
        person = (
            await session.execute(select(Person).where(Person.email == email))
        ).scalar_one_or_none()
        if person is None:
            person = Person(
                first_name="", last_name=user.display_name, email=email, club_memberships=[]
            )
            session.add(person)
        person.user_id = user.id
        for club in clubs:
            if club not in person.club_ids:
                person.club_memberships.append(
                    ClubMembership(club_id=club, status=MembershipStatus.ACTIVE)
                )
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
        if club_id not in person.club_ids:
            person.club_memberships.append(
                ClubMembership(club_id=club_id, status=MembershipStatus.ACTIVE)
            )
        await session.commit()
