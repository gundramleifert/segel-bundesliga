"""Writing and deleting relation tuples — Story Z-2.

A tuple says ``user:relation:object``: this person is ``manager`` of club A,
``race_officer`` of event C, ``admin`` of the site. Everything that writes or deletes one
goes through here — the Accounts tab, the event panel's access list and the club screen's
"make organizer" alike — so the rules live once: the schema (which relations an object
type has), that the object exists, that a tuple is not written twice, that a person cannot
lock themselves out, that a club keeps at least one organizer, and that every change
lands in the audit log. It is the write half of the facade `app/authz.py` (FGA's
``Write``/``Delete``/``Read``); nothing else touches the ``Grant`` table.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app import authz
from app.authz import ObjectRef
from app.models import Club, Event, Person, Series
from app.models.auth import GRANT_COLUMN, Grant, ObjectType, Relation, User, grant_names, writable
from app.problems import Problem
from app.services.audit import EntityType, audit

_TABLES = {
    ObjectType.CLUB: Club,
    ObjectType.SERIES: Series,
    ObjectType.EVENT: Event,
    ObjectType.PERSON: Person,
}


def check_schema(relation: Relation, object_type: ObjectType) -> None:
    """A relation can only be written where the model gives it a ``[user]`` term —
    ``manager`` has none on the site, ``admin`` none on a sailor (there it is derived)."""
    if relation not in writable(object_type):
        raise Problem(
            422,
            "tuple-relation-invalid",
            "This relation does not exist on that kind of object.",
            detail=(
                f"{object_type.value} has: "
                + ", ".join(sorted(r.value for r in writable(object_type)))
                + "."
            ),
            relation=str(relation),
            object_type=object_type.value,
        )


async def resolve(
    session: AsyncSession, object_type: ObjectType, object_id: int | None
) -> Club | Series | Event | Person | None:
    """The object a tuple names, loaded — or a 404/422. ``None`` for the site."""
    if object_type is ObjectType.SITE:
        if object_id is not None:
            raise Problem(
                422,
                "tuple-relation-invalid",
                "The site has no id.",
                detail="Leave object_id empty for a site relation.",
            )
        return None
    if object_id is None:
        raise Problem(
            422,
            "tuple-relation-invalid",
            "A club, series or event relation needs the object's id.",
            detail=f"object_id is required for {object_type.value}.",
        )
    found = await session.get(_TABLES[object_type], object_id)
    if found is None:
        raise Problem(
            404,
            "tuple-object-missing",
            "The club, series or event this tuple names does not exist.",
            detail=f"{object_type.value} {object_id} not found.",
        )
    return found


async def grant(
    session: AsyncSession,
    target: User,
    relation: Relation,
    object_type: ObjectType,
    object_id: int | None,
    *,
    actor: User | None,
) -> Grant:
    """Writes the tuple onto ``target`` (not yet committed) and logs it. ``actor`` is
    ``None`` for the system itself — the admin whitelist at sign-in."""
    check_schema(relation, object_type)
    obj = await resolve(session, object_type, object_id)
    column = GRANT_COLUMN.get(object_type)
    ids = {column: object_id} if column else {}

    if authz.read(target, relation, ObjectRef(object_type, object_id)):
        raise Problem(
            409,
            "tuple-exists",
            "This person already holds this relation on this object.",
            detail="Already granted.",
        )

    row = Grant(relation=relation, **ids)
    # Hand the loaded object to the row, so naming the tuple in the response right after
    # the commit needs no load (docs/gotchas: a relationship on a row you just appended
    # is not loaded).
    if column:
        setattr(row, column.removesuffix("_id"), obj)
    # Change the collection, not a bare INSERT — otherwise the in-memory user still
    # looks role-less to the response built afterwards (expire_on_commit is off).
    target.grants.append(row)
    audit(
        session, EntityType.USER, target.id, "grant", actor,
        relation=str(relation), object_type=object_type.value, object_id=object_id,
    )  # fmt: skip
    return row


async def require_not_last_organizer(session: AsyncSession, user: User) -> None:
    """Story A-8 for an account that goes as a whole — deleted or deactivated — rather than
    one tuple at a time through :func:`revoke`: refused while some club would be left
    without an admin or without an organizer."""
    for row in user.grants:
        if row.object_type is not ObjectType.CLUB or row.relation not in (
            Relation.MANAGER,
            Relation.ADMIN,
        ):
            continue
        assert row.club_id is not None
        if (
            row.relation == Relation.ADMIN
            and await admin_count(session, row.club_id, excluding_user_id=user.id) < 1
        ) or await organizer_count(session, row.club_id, excluding_user_id=user.id) < 1:
            raise Problem(
                409,
                "last-organizer",
                "At least one admin must remain for this club.",
                detail="Name another admin first — the admin decides who is in the club.",
                club_id=row.club_id,
            )


async def revoke(session: AsyncSession, target: User, row: Grant, *, actor: User) -> None:
    """Deletes exactly this tuple (not yet committed) and logs it. Every other tuple of
    the person stays — an earlier "set roles" endpoint rebuilt the rows from a list of
    names and silently dropped every per-club grant on any edit."""
    if (
        row.relation == Relation.ADMIN
        and row.object_type is ObjectType.SITE
        and target.id == actor.id
    ):
        # Someone who revokes their own admin may lock everyone out.
        raise Problem(
            409,
            "tuple-self-lockout",
            "You cannot revoke your own admin role.",
            detail="Ask another administrator to do it.",
        )
    if row.relation in (Relation.MANAGER, Relation.ADMIN) and row.object_type is ObjectType.CLUB:
        assert row.club_id is not None
        # Someone who is both admin and manager of the club stays an organizer after one
        # of the two goes, so only the last organizer *relation* of the last person counts.
        remains_organizer = any(
            g is not row
            and g.relation in (Relation.MANAGER, Relation.ADMIN)
            and g.club_id == row.club_id
            for g in target.grants
        )
        # And the admin is who decides who is *in* the club: with managers only left, it
        # could not add a member or an organizer any more (decided 2026-10-18).
        last_admin = (
            row.relation == Relation.ADMIN
            and await admin_count(session, row.club_id, excluding_user_id=target.id) < 1
        )
        if last_admin or (
            not remains_organizer
            and await organizer_count(session, row.club_id, excluding_user_id=target.id) < 1
        ):
            # Story A-8: a club with no admin or no organizer left could no longer manage itself.
            raise Problem(
                409,
                "last-organizer",
                "At least one admin must remain for this club.",
                detail="Name another admin first — the admin decides who is in the club.",
                club_id=row.club_id,
            )

    # Reassign the collection so the in-memory user is consistent for the response;
    # delete-orphan cascade removes the dropped row on flush.
    target.grants = [g for g in target.grants if g is not row]
    audit(
        session, EntityType.USER, target.id, "revoke", actor,
        relation=str(row.relation), object_type=row.object_type.value, object_id=row.object_id,
    )  # fmt: skip


async def revoke_row(session: AsyncSession, row: Grant, *, actor: User) -> None:
    """:func:`revoke` for a tuple found by itself (by its id): the person is loaded through
    their own query, so their tuples are — reached through ``row.user`` they are not."""
    target = (await session.execute(select(User).where(User.id == row.user_id))).scalar_one()
    # The row the user's collection holds is the one to drop (same identity map).
    await revoke(session, target, next(g for g in target.grants if g.id == row.id), actor=actor)


async def grants_on(
    session: AsyncSession,
    object_type: ObjectType,
    object_id: int | None,
    relation: Relation | None = None,
) -> list[Grant]:
    """Every tuple written on this object (of this relation) — FGA ``Read`` by object, the
    "who has access here" list. Named and with their accounts."""
    stmt = (
        select(Grant)
        .options(selectinload(Grant.user), *grant_names())
        .order_by(Grant.relation, Grant.id)
    )
    if object_type is ObjectType.SITE:
        stmt = stmt.where(*(getattr(Grant, c).is_(None) for c in GRANT_COLUMN.values()))
    else:
        stmt = stmt.where(getattr(Grant, GRANT_COLUMN[object_type]) == object_id)
    if relation is not None:
        stmt = stmt.where(Grant.relation == relation)
    return list((await session.execute(stmt)).scalars().all())


async def holders(
    session: AsyncSession, relation: Relation, object_type: ObjectType, object_ids: list[int]
) -> list[Grant]:
    """The tuples of this relation on any of these objects — FGA ``ListUsers`` for many
    objects at once (the guardians of a club's sailors)."""
    if not object_ids:
        return []
    column = getattr(Grant, GRANT_COLUMN[object_type])
    stmt = (
        select(Grant)
        .options(selectinload(Grant.user))
        .where(Grant.relation == relation, column.in_(object_ids))
    )
    return list((await session.execute(stmt)).scalars().all())


async def tuples_of(session: AsyncSession, user_id: int) -> list[Grant]:
    """Every tuple another person holds — FGA ``Read`` by user. One's own are on the
    ``User`` already."""
    return list((await session.execute(select(Grant).where(Grant.user_id == user_id))).scalars())


async def named(session: AsyncSession, *users: User) -> None:
    """Loads what names these people's tuples (``Grant.object_name``) — only the screens
    that list tuples need it, so a user is loaded without it."""
    ids = [g.id for user in users for g in user.grants if g.id is not None]
    if ids:
        await session.execute(
            select(Grant)
            .where(Grant.id.in_(ids))
            .options(*grant_names())
            .execution_options(populate_existing=True)
        )


async def organizer_count(
    session: AsyncSession, club_id: int, *, excluding_user_id: int | None = None
) -> int:
    """How many accounts organize this club — i.e. hold ``manager`` or ``admin`` on it."""
    stmt = select(func.count(func.distinct(Grant.user_id))).where(
        Grant.relation.in_([Relation.MANAGER, Relation.ADMIN]), Grant.club_id == club_id
    )
    if excluding_user_id is not None:
        stmt = stmt.where(Grant.user_id != excluding_user_id)
    return int((await session.execute(stmt)).scalar_one())


async def admin_count(session: AsyncSession, club_id: int, *, excluding_user_id: int) -> int:
    """How many other accounts hold ``admin`` on this club directly."""
    stmt = select(func.count(func.distinct(Grant.user_id))).where(
        Grant.relation == Relation.ADMIN,
        Grant.club_id == club_id,
        Grant.user_id != excluding_user_id,
    )
    return int((await session.execute(stmt)).scalar_one())


def may_administer(
    acting: User, object_type: ObjectType, obj: Club | Series | Event | Person | None
) -> bool:
    """Who may write tuples on this object: its ``admin`` — which the model resolves to
    the site's admin for everything, a series' admin for its events, the host club's for
    the events it hosts, and a club's admin for the club (Story Z-2). A manager sets
    things up; naming people is the admin's. A sailor's admin is the site's alone: the
    child's club links a guardian through its own endpoints (Story V-13)."""
    return acting.can(Relation.ADMIN, on=obj if obj is not None else authz.SITE)
