"""Create test accounts — one for each role and for each participant.

    uv run python -m app.seed_users

Each registered sailor gets an account, because without logging in they cannot submit
their waiver (Stories V-1 and S-1). One person per club additionally gets the
``club_manager`` role so roster management and club assignment can be tested.

In addition, a set of named accounts for roles that do not belong to a club — administration,
editorial, race officer — plus an account with no role to see what a logged-in guest can do.

The run is repeatable: existing accounts are updated, not duplicated.
"""

from __future__ import annotations

import asyncio

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import create_access_token
from app.db import SessionLocal
from app.models import Club, ClubMember, ClubMemberStatus, Event, Sailor, Team, TeamMembership
from app.models.auth import Grant, Relation, Role, User

# Accounts not linked to a club: (email, name, site relations)
FUNCTIONAL_ACCOUNTS: list[tuple[str, str, list[str]]] = [
    ("admin@sbl.example.com", "Alina Admin", [Relation.ADMIN]),
    ("redaktion@sbl.example.com", "Rudi Editor", [Relation.EDITOR]),
    ("wl@sbl.example.com", "Wanda Racecommittee", [Relation.RACE_OFFICER]),
    ("beides@sbl.example.com", "Bea Bothroles", [Relation.EDITOR, Relation.RACE_OFFICER]),
    ("gast@sbl.example.com", "Gero Guest", []),
]
# Tuples on one event (Story Z-2) — written after the loop, because they name an event:
# the person a club names to run its regatta, and the organizer of that event.
EVENT_ACCOUNTS: list[tuple[str, str, str]] = [
    ("regatta@sbl.example.com", "Regina Regatta", Relation.RACE_OFFICER),
    ("orga@sbl.example.com", "Otto Organizer", Relation.MANAGER),
    ("jury@sbl.example.com", "Jutta Jury", Relation.JURY),
]


async def _account(
    session: AsyncSession,
    *,
    email: str,
    name: str,
    roles: list[str],
    club_id: int | None = None,
) -> User:
    user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()

    if user is None:
        # Set roles before the flush: afterward the assignment would first want to reload the
        # collection, and a lazy load fails in async context.
        # Test accounts are considered verified — otherwise each would first need to redeem a code.
        user = User(email=email, display_name=name, club_id=club_id, email_verified=True)
        # `Role.CLUB_MANAGER` here means "manager of this club"; everything else is a
        # site relation.
        user.grants = [_tuple(role, club_id) for role in roles]
        session.add(user)
        await session.flush()
        return user

    user.display_name = name
    user.is_active = True
    user.email_verified = True
    user.club_id = club_id
    # Replace existing tuples via SQL instead of via the collection — for the same reason.
    await session.execute(delete(Grant).where(Grant.user_id == user.id))
    for role in roles:
        row = _tuple(role, club_id)
        row.user_id = user.id
        session.add(row)
    await session.flush()
    return user


def _tuple(role: str, club_id: int | None) -> Grant:
    if role == Role.CLUB_MANAGER:
        return Grant(relation=Relation.MANAGER, club_id=club_id)
    return Grant(relation=Relation(role))


async def _membership(session: AsyncSession, club_id: int, user_id: int) -> None:
    existing = (
        await session.execute(
            select(ClubMember).where(ClubMember.club_id == club_id, ClubMember.user_id == user_id)
        )
    ).scalar_one_or_none()
    if existing is None:
        session.add(ClubMember(club_id=club_id, user_id=user_id, status=ClubMemberStatus.ACTIVE))
    else:
        existing.status = ClubMemberStatus.ACTIVE


async def seed_users() -> None:
    async with SessionLocal() as session:
        clubs = (await session.execute(select(Club).order_by(Club.name))).scalars().all()
        if not clubs:
            raise SystemExit("No clubs yet. Run 'uv run python -m app.seed' first.")

        for email, name, roles in FUNCTIONAL_ACCOUNTS:
            await _account(session, email=email, name=name, roles=roles)

        # The planned matchday, so results can still be entered and the setup changed.
        planned = (
            await session.execute(select(Event).where(Event.slug == "dsbl-1-2026-act-3"))
        ).scalar_one_or_none()
        if planned is not None:
            for email, name, relation in EVENT_ACCOUNTS:
                person = await _account(session, email=email, name=name, roles=[])
                session.add(Grant(user_id=person.id, relation=relation, event_id=planned.id))
            await session.flush()

        # All registered sailors with their club: via the team, not by name.
        rows = (
            await session.execute(
                select(Sailor, Team.club_id)
                .join(TeamMembership, TeamMembership.sailor_id == Sailor.id)
                .join(Team, TeamMembership.team_id == Team.id)
                .where(Sailor.email.is_not(None))
                .order_by(Team.club_id, Sailor.id)
            )
        ).all()

        seen: set[str] = set()
        first_per_club: set[int] = set()
        participants = 0
        club_managers = 0

        for sailor, club_id in rows:
            assert sailor.email is not None
            if sailor.email in seen:
                continue
            seen.add(sailor.email)

            # The first person of a club also manages it — otherwise club
            # assignment (Z-3) couldn't be tested.
            leads = club_id not in first_per_club
            if leads:
                first_per_club.add(club_id)
                club_managers += 1

            account = await _account(
                session,
                email=sailor.email,
                name=f"{sailor.first_name} {sailor.last_name}",
                roles=[Role.CLUB_MANAGER] if leads else [],
                club_id=club_id,
            )
            # Membership is mutually confirmed: registered sailors belong to the club.
            await _membership(session, club_id, account.id)
            participants += 1

        await session.commit()
        await _report(session, participants, club_managers, len(clubs))


async def _report(
    session: AsyncSession, participants: int, club_managers: int, clubs_count: int
) -> None:
    clubs = {c.id: c for c in (await session.execute(select(Club))).scalars()}

    print(f"Test accounts ready: {participants} participants from {clubs_count} clubs,")
    print(f"of which {club_managers} with the role club_manager.\n")

    print("Functional accounts:")
    for email, name, roles in FUNCTIONAL_ACCOUNTS:
        print(f"  {email:24s} {', '.join(roles) or 'no role':28s} {name}")
    for email, name, relation in EVENT_ACCOUNTS:
        print(f"  {email:24s} {relation + ' (one event)':28s} {name}")

    samples = (
        (
            await session.execute(
                select(User)
                .join(Grant, Grant.user_id == User.id)
                .where(Grant.relation == Relation.MANAGER, Grant.club_id.is_not(None))
                .order_by(User.id)
                .limit(3)
            )
        )
        .scalars()
        .all()
    )

    print("\nClub managers (sample):")
    for user in samples:
        club = clubs.get(user.club_id) if user.club_id else None
        abbr = club.short_name if club else "—"
        print(f"  {user.email:34s} club_manager  {user.display_name} [{abbr}]")

    no_role = (
        (
            await session.execute(
                select(User)
                .where(User.club_id.is_not(None), ~User.grants.any())
                .order_by(User.id)
                .limit(2)
            )
        )
        .scalars()
        .all()
    )

    print("\nParticipants with no role (sample):")
    for user in no_role:
        club = clubs.get(user.club_id) if user.club_id else None
        abbr = club.short_name if club else "—"
        print(f"  {user.email:34s} —             {user.display_name} [{abbr}]")

    admin = (
        await session.execute(select(User).where(User.email == "admin@sbl.example.com"))
    ).scalar_one()
    # A convenience line, and nothing the seed depends on — so a missing signing secret
    # must not take the whole seeding down with it. It used to: `create_access_token`
    # raises 503 without `SBL_JWT_SECRET`, which made `seed_test_setup` exit 1 *after*
    # writing every row correctly, and `scripts/dev-stack.sh` then refused to start
    # servers against a database that was in fact complete.
    try:
        token, _ = create_access_token(admin)
    except HTTPException:
        print("\nNo SBL_JWT_SECRET is configured, so no example token is printed here.")
        print("Set one to sign in — the seeded data itself is complete either way.")
    else:
        print("\nAccess via curl (administration):")
        print(f'  curl -s http://127.0.0.1:8000/api/auth/me -H "Authorization: Bearer {token}"')
    print("\nIn the interface: the role switcher at the bottom right (dev only).")


if __name__ == "__main__":
    asyncio.run(seed_users())
