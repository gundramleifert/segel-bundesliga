"""A person and the account they sign in with (#40, `docs/PLAN_PEOPLE.md` §2).

**Every account has exactly one person**, and a person need not have an account. The
person comes with the account — registration, enrollment by the league office, the first
sign-in — or is the one already on record under the account's address, once that address
is **verified**: a club may have created the person years before the account existed, and
an address merely typed at registration proves nothing, so an unverified account is never
handed someone else's record. Linking is ``Person.user_id``; from then on nothing compares
addresses.
"""

from __future__ import annotations

from sqlalchemy import inspect, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Person
from app.models.auth import User


def _names(display_name: str) -> tuple[str, str]:
    """``"Anna Maria Eigen"`` → ``("Anna Maria", "Eigen")``; one word is the last name."""
    first, _, last = display_name.strip().rpartition(" ")
    return first, last or display_name.strip()


async def person_for(session: AsyncSession, user: User) -> Person | None:
    """The account's person — linked, found under its verified address, or created.

    ``None`` only while the address is unverified and a person already uses it: theirs
    once the code is redeemed (this runs again on every sign-in). Idempotent; flushes,
    never commits.
    """
    # An account created in this request has no `person` loaded, and touching it would
    # lazy-load outside the async context: ask the table instead.
    if "person" in inspect(user).unloaded:
        linked = (
            await session.execute(select(Person).where(Person.user_id == user.id))
        ).scalar_one_or_none()
        if linked is not None:
            return linked
    elif user.person is not None:
        return user.person
    email = user.email.lower()
    person = (
        await session.execute(select(Person).where(Person.email == email))
    ).scalar_one_or_none()
    if person is not None:
        if not user.email_verified or person.user_id is not None:
            return None
    else:
        first, last = _names(user.display_name)
        person = Person(first_name=first, last_name=last, email=email, club_memberships=[])
        session.add(person)
    person.user_id = user.id
    await session.flush()
    # Loaded now, so the permission checks later in this request see the person.
    await session.refresh(user, ["person"])
    return person


def unlink(user: User) -> None:
    """The account goes, the person stays (decided 2026-10-25, #43): results, squads and
    waivers point at the person, and the person may sign up again. SQLite enforces no
    foreign keys, so the ``SET NULL`` is done here, not left to the database."""
    if user.person is not None:
        user.person.user_id = None
