"""A person and the account they sign in with (#40, #52, `docs/PLAN_PEOPLE.md` §2).

**Every person has an account, and every account has exactly one person** (#52, decided
2026-10-28). The two are made together: a club or the league office creating someone
creates their account too (:func:`new_person`) — unverified, so it cannot sign in until
its address is proven by a code or a club's invitation link; and someone registering or
signing in for the first time gets their person (:func:`person_for`). Linked by
``Person.user_id``; from then on nothing compares addresses. An account is never deleted:
deleting it deactivates it (`app/routers/auth.py`), so the person keeps one.
"""

from __future__ import annotations

from sqlalchemy import inspect, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Person
from app.models.auth import User
from app.services import passwords


def _names(display_name: str) -> tuple[str, str]:
    """``"Anna Maria Eigen"`` → ``("Anna Maria", "Eigen")``; one word is the last name."""
    first, _, last = display_name.strip().rpartition(" ")
    return first, last or display_name.strip()


async def new_person(
    session: AsyncSession, *, first_name: str, last_name: str, email: str, **fields: object
) -> Person:
    """A person with their account — unverified, no sign-in until the address is proven.
    The caller makes sure no account has the address. Flushes, never commits."""
    email = email.strip().lower()
    user = User(
        email=email,
        display_name=Person(first_name=first_name, last_name=last_name).full_name,
        email_verified=False,
        identities=[],
        grants=[],
    )
    session.add(user)
    await session.flush()
    person = Person(
        first_name=first_name,
        last_name=last_name,
        user=user,
        club_memberships=[],
        **fields,
    )
    session.add(person)
    await session.flush()
    return person


async def person_for(session: AsyncSession, user: User) -> Person:
    """The account's person — or, for an account made by registering or signing in, a new
    one. Idempotent; flushes, never commits."""
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
    first, last = _names(user.display_name)
    person = Person(first_name=first, last_name=last, user=user, club_memberships=[])
    session.add(person)
    await session.flush()
    # Loaded now, so the permission checks later in this request see the person.
    await session.refresh(user, ["person"])
    return person


async def account_of(session: AsyncSession, person: Person) -> User:
    """The person's account — from the session when it is loaded already."""
    account = await session.get(User, person.user_id)
    assert account is not None  # every person has one (#52)
    return account


async def signs_in(session: AsyncSession, person: Person) -> bool:
    """Whether the person's account can sign in (``User.signs_in``) — what "has an
    account" meant before every person had one (#52)."""
    return (await account_of(session, person)).signs_in


async def by_address(session: AsyncSession, email: str) -> Person | None:
    """The person under this address — their account's, the only one there is."""
    email = email.strip().lower()
    return (
        await session.execute(
            select(Person).join(User, User.id == Person.user_id).where(User.email == email)
        )
    ).scalar_one_or_none()


async def end_account(session: AsyncSession, user: User) -> None:
    """The account stops signing in and the person behind it is erased (Story Z-7, review
    5.5, GDPR Art. 17): sign-in methods, password, every role and every club membership
    go; the address becomes a placeholder, freeing the real one; birth date and federation
    id are cleared and the profile page is switched off. The **name** stays — results carry
    it — and so do the account and person rows, which squads, results and waivers point
    at. Flushes nothing, commits nothing."""
    from app.services.participation import end  # participation imports grants, not us

    person = await person_for(session, user)
    for link in list(person.club_memberships):
        await end(session, person, link.club_id)
    await passwords.remove_password(session, user)
    user.identities = []
    user.grants = []
    user.is_active = False
    user.email = f"erased-{user.id}@invalid"
    user.email_verified = False
    person.birth_date = None
    person.federation_id = None
    person.profile_public_choice = False
