"""The one way an ``AuditLog`` row is written.

Twelve hand-built rows had drifted on who the actor is — a ``User``, an e-mail string,
``"system"`` — and on which strings name what was touched. Here the actor is resolved
once (an account is its e-mail, ``None`` is the system) and the entity type is an enum,
so a reader such as ``event_readiness`` counting race starts names the same value the
writer stored.
"""

from __future__ import annotations

from enum import StrEnum

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, User

#: Who wrote a row when no person did — a bootstrap, an import, a login's own grant.
SYSTEM_ACTOR = "system"


class EntityType(StrEnum):
    """``AuditLog.entity_type``: what kind of row ``entity_id`` points at."""

    USER = "user"
    TEAM = "team"
    RACE = "race"
    EXPENSE_CLAIM = "expense_claim"
    EXPENSE_DOCUMENT = "expense_document"
    PAYMENT_RUN = "payment_run"
    PAYMENT = "payment"
    WAIVER_SCAN = "waiver_scan"
    PERSONAL_DOCUMENT = "personal_document"
    PERSON = "person"


def audit(
    session: AsyncSession,
    entity_type: EntityType,
    entity_id: int,
    action: str,
    actor: User | str | None,
    /,
    **payload: object,
) -> AuditLog:
    """Adds one row to the session — written with the caller's commit, never on its own.

    ``actor`` is the account that acted, an already-named actor (the emulator), or
    ``None`` for the system. ``payload`` is stored as given.
    """
    if isinstance(actor, User):
        name = actor.email
    elif actor is None:
        name = SYSTEM_ACTOR
    else:
        name = actor
    row = AuditLog(
        entity_type=entity_type.value,
        entity_id=entity_id,
        action=action,
        actor=name,
        payload=payload,
    )
    session.add(row)
    return row
