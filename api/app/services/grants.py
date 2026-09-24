"""Writing and deleting relation tuples — Story Z-2.

A tuple says ``user:relation:object``: this person is ``manager`` of club A,
``race_officer`` of event C, ``admin`` of the site. Everything that writes or deletes one
goes through here — the Accounts tab, the event panel's access list and the club screen's
"make organizer" alike — so the rules live once: the schema (which relations an object
type has), that the object exists, that a tuple is not written twice, that a person cannot
lock themselves out, that a club keeps at least one organizer, and that every change
lands in the audit log.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import AuditLog, Club, Event, Series
from app.models.auth import SCHEMA, Grant, ObjectType, Relation, User
from app.problems import Problem

_TABLES = {ObjectType.CLUB: Club, ObjectType.SERIES: Series, ObjectType.EVENT: Event}
_COLUMNS = {
    ObjectType.CLUB: "club_id",
    ObjectType.SERIES: "series_id",
    ObjectType.EVENT: "event_id",
}


def check_schema(relation: Relation, object_type: ObjectType) -> None:
    """A relation only exists on the object types the schema lists — ``manager`` has no
    meaning on the site, ``admin`` none on a club."""
    if relation not in SCHEMA[object_type]:
        raise Problem(
            422,
            "tuple-relation-invalid",
            "This relation does not exist on that kind of object.",
            detail=(
                f"{object_type.value} has: "
                + ", ".join(sorted(r.value for r in SCHEMA[object_type]))
                + "."
            ),
            relation=str(relation),
            object_type=object_type.value,
        )


async def resolve(
    session: AsyncSession, object_type: ObjectType, object_id: int | None
) -> Club | Series | Event | None:
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
    actor: User,
) -> Grant:
    """Writes the tuple onto ``target`` (not yet committed) and logs it."""
    check_schema(relation, object_type)
    obj = await resolve(session, object_type, object_id)
    ids = {_COLUMNS[object_type]: object_id} if object_type is not ObjectType.SITE else {}

    if target.holds(relation, **ids):
        raise Problem(
            409,
            "tuple-exists",
            "This person already holds this relation on this object.",
            detail="Already granted.",
        )

    row = Grant(relation=relation, **ids)
    # Hand the loaded object to the row, so naming the tuple in the response right after
    # the commit needs no lazy load — which would fail outside the async context
    # (docs/gotchas: a relationship on a row you just appended is not loaded).
    if object_type is ObjectType.CLUB:
        row.club = obj
    elif object_type is ObjectType.SERIES:
        row.series = obj
    elif object_type is ObjectType.EVENT:
        row.event = obj
    # Change the collection, not a bare INSERT — otherwise the in-memory user still
    # looks role-less to the response built afterwards (expire_on_commit is off).
    target.grants.append(row)
    if object_type is ObjectType.CLUB and relation == Relation.MANAGER and target.club_id is None:
        # Populate the "represents" convention on someone's first club — but it must
        # never again be the thing that blocks or defines a (further) tuple.
        target.club_id = object_id
    session.add(_audit("grant", target, relation, object_type, object_id, actor))
    return row


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
    if row.relation == Relation.MANAGER and row.object_type is ObjectType.CLUB:
        assert row.club_id is not None
        if await organizer_count(session, row.club_id, excluding_user_id=target.id) < 1:
            # Story A-8: a club with no organizer left could no longer manage itself.
            raise Problem(
                409,
                "last-organizer",
                "At least one organizer must remain for this club.",
                detail="At least one organizer must remain for this club.",
                club_id=row.club_id,
            )

    # Reassign the collection so the in-memory user is consistent for the response;
    # delete-orphan cascade removes the dropped row on flush.
    target.grants = [g for g in target.grants if g is not row]
    session.add(_audit("revoke", target, row.relation, row.object_type, row.object_id, actor))


async def grants_on(
    session: AsyncSession, object_type: ObjectType, object_id: int | None
) -> list[Grant]:
    """Every tuple written on this object — the "who has access here" list."""
    stmt = select(Grant).options(selectinload(Grant.user)).order_by(Grant.relation, Grant.id)
    if object_type is ObjectType.SITE:
        stmt = stmt.where(
            Grant.club_id.is_(None), Grant.series_id.is_(None), Grant.event_id.is_(None)
        )
    else:
        stmt = stmt.where(getattr(Grant, _COLUMNS[object_type]) == object_id)
    return list((await session.execute(stmt)).scalars().all())


async def organizer_count(
    session: AsyncSession, club_id: int, *, excluding_user_id: int | None = None
) -> int:
    """How many accounts organize this club — i.e. hold ``manager`` on it."""
    stmt = select(func.count(func.distinct(Grant.user_id))).where(
        Grant.relation == Relation.MANAGER, Grant.club_id == club_id
    )
    if excluding_user_id is not None:
        stmt = stmt.where(Grant.user_id != excluding_user_id)
    return int((await session.execute(stmt)).scalar_one())


def may_administer(
    acting: User, object_type: ObjectType, obj: Club | Series | Event | None
) -> bool:
    """Who may write tuples on this object: the site's admin, and the object's own
    manager — an organizer names the people of their club, series or event (Story Z-2).
    Site tuples are the admin's alone."""
    if acting.can(Relation.ADMIN):
        return True
    if object_type is ObjectType.SITE or obj is None:
        return False
    return acting.can(Relation.MANAGER, on=obj)


def _audit(
    action: str,
    target: User,
    relation: str,
    object_type: ObjectType,
    object_id: int | None,
    actor: User,
) -> AuditLog:
    return AuditLog(
        entity_type="user",
        entity_id=target.id,
        action=action,
        actor=actor.email,
        payload={
            "relation": str(relation),
            "object_type": object_type.value,
            "object_id": object_id,
        },
    )
