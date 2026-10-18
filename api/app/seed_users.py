"""Create the test accounts — a small cast: one club, one series, one event.

    uv run python -m app.seed_users

All 18 clubs, their sailors, the series and their events stay as data (`app.seed`): the
league, its pairing lists and its standings need them. The people who sign in are
concentrated on **one of each**:

* the **club** NRV: its board (the club's ``admin`` — who is in the club), its team
  manager (``manager`` — who sails), its treasurer, and every sailor of its squads — all
  of them ``member`` of it. A sailor needs an account to sign their waiver (Story S-1),
  and the specs pick their adults and juniors from this squad;
* the **series** 1. Segel-Bundesliga 2026: its manager;
* the **event** act 3 of that series, still planned: its organizer, race officer, jury
  and helper.

Beyond these: the league office (``admin``, ``editor``, ``race_officer`` on the site) and
a guest with no relation.
Tuples are written through `app/services/grants.py`, like every other tuple, so the run
is repeatable: an existing account is updated and a tuple it holds is not written twice.
"""

from __future__ import annotations

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import authz
from app.auth import create_access_token
from app.authz import ObjectRef
from app.db import SessionLocal
from app.models import Club, Event, Sailor, Series, Team, TeamMembership
from app.models.auth import ObjectType, Relation, User
from app.problems import Problem
from app.services import grants

#: The one club, series and event the cast is about.
TEST_CLUB = "nrv"
TEST_SERIES = "dsbl-1-2026"
TEST_EVENT = "dsbl-1-2026-act-3"

#: The league office and a guest: (email, name, site relations).
SITE_ACCOUNTS: list[tuple[str, str, list[Relation]]] = [
    ("admin@sbl.example.com", "Alina Admin", [Relation.ADMIN]),
    ("redaktion@sbl.example.com", "Rudi Editor", [Relation.EDITOR]),
    ("wl@sbl.example.com", "Wanda Racecommittee", [Relation.RACE_OFFICER]),
    ("gast@sbl.example.com", "Gero Guest", []),
]
#: The test series' manager (Story Z-2).
SERIES_ACCOUNTS: list[tuple[str, str, Relation]] = [
    ("serie@sbl.example.com", "Sven Series", Relation.MANAGER),
]
#: One tuple each on the test event (Story Z-2).
EVENT_ACCOUNTS: list[tuple[str, str, Relation]] = [
    ("regatta@sbl.example.com", "Regina Regatta", Relation.RACE_OFFICER),
    ("orga@sbl.example.com", "Otto Organizer", Relation.MANAGER),
    ("jury@sbl.example.com", "Jutta Jury", Relation.JURY),
    ("helfer@sbl.example.com", "Hanna Helper", Relation.HELPER),
]
#: The test club's officials: (address before the @, what they are, relation).
CLUB_OFFICIALS: list[tuple[str, str, Relation]] = [
    ("board", "Club admin", Relation.ADMIN),
    ("teams", "Team manager", Relation.MANAGER),
    ("treasurer", "Treasurer", Relation.TREASURER),
]


async def _account(session: AsyncSession, email: str, name: str) -> User:
    """The account under this address — created verified (test accounts redeem no code),
    or brought back to active."""
    user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if user is None:
        user = User(email=email, display_name=name, email_verified=True)
        # Empty, not unloaded: writing a tuple reads the collection, and a lazy load fails
        # in the async session.
        user.grants = []
        session.add(user)
        await session.flush()
        return user
    user.display_name = name
    user.is_active = True
    user.email_verified = True
    return user


async def _tuple(session: AsyncSession, user: User, relation: Relation, obj: ObjectRef) -> None:
    if not authz.read(user, relation, obj):
        await grants.grant(session, user, relation, obj.type, obj.id, actor=None)


async def seed_users() -> None:
    async with SessionLocal() as session:
        club = (
            await session.execute(select(Club).where(Club.slug == TEST_CLUB))
        ).scalar_one_or_none()
        if club is None:
            raise SystemExit("No clubs yet. Run 'uv run python -m app.seed' first.")

        for email, name, relations in SITE_ACCOUNTS:
            user = await _account(session, email, name)
            for relation in relations:
                await _tuple(session, user, relation, authz.SITE)

        series = (
            await session.execute(select(Series).where(Series.slug == TEST_SERIES))
        ).scalar_one_or_none()
        if series is not None:
            for email, name, relation in SERIES_ACCOUNTS:
                user = await _account(session, email, name)
                await _tuple(session, user, relation, ObjectRef(ObjectType.SERIES, series.id))

        event = (
            await session.execute(select(Event).where(Event.slug == TEST_EVENT))
        ).scalar_one_or_none()
        if event is not None:
            for email, name, relation in EVENT_ACCOUNTS:
                user = await _account(session, email, name)
                await _tuple(session, user, relation, ObjectRef(ObjectType.EVENT, event.id))

        here = ObjectRef(ObjectType.CLUB, club.id)
        for local, what, relation in CLUB_OFFICIALS:
            user = await _account(
                session, f"{local}@{club.slug}.example.com", f"{what} {club.short_name}"
            )
            await _tuple(session, user, relation, here)
            # Officials belong to their club, like everyone in it.
            await _tuple(session, user, Relation.MEMBER, here)
        # Every sailor of the club's squads and entries, as a member of it.
        rows = (
            await session.execute(
                select(Sailor)
                .join(TeamMembership, TeamMembership.sailor_id == Sailor.id)
                .join(Team, TeamMembership.team_id == Team.id)
                .where(Team.club_id == club.id, Sailor.email.is_not(None))
                .distinct()
                .order_by(Sailor.id)
            )
        ).scalars()
        sailors = 0
        for sailor in rows:
            assert sailor.email is not None
            user = await _account(session, sailor.email, sailor.full_name)
            await _tuple(session, user, Relation.MEMBER, here)
            sailors += 1

        await session.commit()
        admin = (
            await session.execute(select(User).where(User.email == SITE_ACCOUNTS[0][0]))
        ).scalar_one()
        _report(club, sailors, admin)


def _report(club: Club, sailors: int, admin: User) -> None:
    print("League office and guest:")
    for email, name, relations in SITE_ACCOUNTS:
        print(f"  {email:30s} {', '.join(relations) or 'no relation':22s} {name}")
    print(f"On the series {TEST_SERIES}:")
    for email, name, relation in SERIES_ACCOUNTS:
        print(f"  {email:30s} {relation:22s} {name}")
    print(f"On the event {TEST_EVENT}:")
    for email, name, relation in EVENT_ACCOUNTS:
        print(f"  {email:30s} {relation:22s} {name}")
    print(f"{club.name}:")
    for local, what, relation in CLUB_OFFICIALS:
        print(f"  {local + '@' + club.slug + '.example.com':30s} {relation:22s} {what}")
    print(f"…and {sailors} sailors of the club, each a member.")
    # A convenience line, and nothing the seed depends on — so a missing signing secret
    # must not take the whole seeding down with it. It used to: `create_access_token`
    # raises 503 without `SBL_JWT_SECRET`, which made `seed_test_setup` exit 1 *after*
    # writing every row correctly, and `scripts/dev-stack.sh` then refused to start
    # servers against a database that was in fact complete.
    try:
        token, _ = create_access_token(admin)
    except Problem:
        print("\nNo SBL_JWT_SECRET is configured, so no example token is printed here.")
        print("Set one to sign in — the seeded data itself is complete either way.")
    else:
        print("\nAccess via curl (administration):")
        print(f'  curl -s http://127.0.0.1:8000/api/auth/me -H "Authorization: Bearer {token}"')
    print("\nIn the interface: the role switcher at the bottom right (dev only).")


if __name__ == "__main__":
    asyncio.run(seed_users())
