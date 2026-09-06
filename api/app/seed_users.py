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

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import create_access_token
from app.db import SessionLocal
from app.models import Club, ClubMember, ClubMemberStatus, Sailor, Team, TeamMembership
from app.models.auth import Role, User, UserRole

# Accounts not linked to a club: (email, name, roles)
FUNKTIONSKONTEN: list[tuple[str, str, list[str]]] = [
    ("admin@sbl.example.com", "Alina Verwaltung", [Role.ADMIN]),
    ("redaktion@sbl.example.com", "Rudi Redaktion", [Role.EDITOR]),
    ("wl@sbl.example.com", "Wanda Wettfahrtleitung", [Role.RACE_OFFICER]),
    ("beides@sbl.example.com", "Bea Doppelrolle", [Role.EDITOR, Role.RACE_OFFICER]),
    ("gast@sbl.example.com", "Gero Gast", []),
]


async def _konto(
    session: AsyncSession,
    *,
    email: str,
    name: str,
    rollen: list[str],
    club_id: int | None = None,
) -> User:
    user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()

    if user is None:
        # Set roles before the flush: afterward the assignment would first want to reload the
        # collection, and a lazy load fails in async context.
        # Test accounts are considered verified — otherwise each would first need to redeem a code.
        user = User(
            email=email, display_name=name, club_id=club_id, email_verified=True
        )
        user.role_rows = [UserRole(role=rolle) for rolle in rollen]
        session.add(user)
        await session.flush()
        return user

    user.display_name = name
    user.is_active = True
    user.email_verified = True
    user.club_id = club_id
    # Replace existing roles via SQL instead of via the collection — for the same reason.
    await session.execute(delete(UserRole).where(UserRole.user_id == user.id))
    session.add_all(UserRole(user_id=user.id, role=rolle) for rolle in rollen)
    await session.flush()
    return user


async def _mitgliedschaft(session: AsyncSession, club_id: int, user_id: int) -> None:
    vorhanden = (
        await session.execute(
            select(ClubMember).where(
                ClubMember.club_id == club_id, ClubMember.user_id == user_id
            )
        )
    ).scalar_one_or_none()
    if vorhanden is None:
        session.add(
            ClubMember(
                club_id=club_id, user_id=user_id, status=ClubMemberStatus.ACTIVE
            )
        )
    else:
        vorhanden.status = ClubMemberStatus.ACTIVE


async def seed_users() -> None:
    async with SessionLocal() as session:
        clubs = (await session.execute(select(Club).order_by(Club.name))).scalars().all()
        if not clubs:
            raise SystemExit(
                "No clubs yet. Run 'uv run python -m app.seed' first."
            )

        for email, name, rollen in FUNKTIONSKONTEN:
            await _konto(session, email=email, name=name, rollen=rollen)

        # All registered sailors with their club: via the team, not by name.
        zeilen = (
            await session.execute(
                select(Sailor, Team.club_id)
                .join(TeamMembership, TeamMembership.sailor_id == Sailor.id)
                .join(Team, TeamMembership.team_id == Team.id)
                .where(Sailor.email.is_not(None))
                .order_by(Team.club_id, Sailor.id)
            )
        ).all()

        gesehen: set[str] = set()
        erste_je_club: set[int] = set()
        teilnehmer = 0
        vereinsleitungen = 0

        for sailor, club_id in zeilen:
            assert sailor.email is not None
            if sailor.email in gesehen:
                continue
            gesehen.add(sailor.email)

            # The first person of a club also manages it — otherwise club
            # assignment (Z-3) couldn't be tested.
            fuehrt = club_id not in erste_je_club
            if fuehrt:
                erste_je_club.add(club_id)
                vereinsleitungen += 1

            konto = await _konto(
                session,
                email=sailor.email,
                name=f"{sailor.first_name} {sailor.last_name}",
                rollen=[Role.CLUB_MANAGER] if fuehrt else [],
                club_id=club_id,
            )
            # Membership is mutually confirmed: registered sailors belong to the club.
            await _mitgliedschaft(session, club_id, konto.id)
            teilnehmer += 1

        await session.commit()
        await _bericht(session, teilnehmer, vereinsleitungen, len(clubs))


async def _bericht(
    session: AsyncSession, teilnehmer: int, vereinsleitungen: int, vereine: int
) -> None:
    clubs = {c.id: c for c in (await session.execute(select(Club))).scalars()}

    print(f"Test accounts ready: {teilnehmer} participants from {vereine} clubs,")
    print(f"of which {vereinsleitungen} with the role club_manager.\n")

    print("Functional accounts:")
    for email, name, rollen in FUNKTIONSKONTEN:
        print(f"  {email:24s} {', '.join(rollen) or 'keine Rolle':28s} {name}")

    beispiele = (
        await session.execute(
            select(User)
            .join(UserRole, UserRole.user_id == User.id)
            .where(UserRole.role == Role.CLUB_MANAGER)
            .order_by(User.id)
            .limit(3)
        )
    ).scalars().all()

    print("\nClub managers (sample):")
    for user in beispiele:
        verein = clubs.get(user.club_id) if user.club_id else None
        kuerzel = verein.short_name if verein else "—"
        print(f"  {user.email:34s} club_manager  {user.display_name} [{kuerzel}]")

    ohne_rolle = (
        await session.execute(
            select(User)
            .where(User.club_id.is_not(None), ~User.role_rows.any())
            .order_by(User.id)
            .limit(2)
        )
    ).scalars().all()

    print("\nParticipants with no role (sample):")
    for user in ohne_rolle:
        verein = clubs.get(user.club_id) if user.club_id else None
        kuerzel = verein.short_name if verein else "—"
        print(f"  {user.email:34s} —             {user.display_name} [{kuerzel}]")

    admin = (
        await session.execute(select(User).where(User.email == "admin@sbl.example.com"))
    ).scalar_one()
    token, _ = create_access_token(admin)
    print("\nAccess via curl (administration):")
    print(f'  curl -s http://127.0.0.1:8000/api/auth/me -H "Authorization: Bearer {token}"')
    print("\nIn the interface: the role switcher at the bottom right (dev only).")


if __name__ == "__main__":
    asyncio.run(seed_users())
