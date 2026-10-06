"""Passwords — Story Z-9.

One more way into an account, beside Google, Microsoft and the one-time code. The rules
that matter, each for a reason:

* **Argon2id** through ``argon2-cffi``'s ``PasswordHasher``; ``check_needs_rehash`` lets
  stronger parameters reach every hash at its owner's next successful sign-in.
* **Only a verified address** gets a password, so a never-proven address cannot become a
  way in. Setting one never creates an account.
* **Length is the only rule**, after NFKC normalization — "ü" typed on a Mac and on a
  phone are different code points and must be the same password.
* **Every failure looks the same** to the caller (:class:`LoginFailed`), and an unknown
  address still pays for one ``verify``, so neither body nor timing tells who has an
  account.
* **Guessing is slowed per account:** every fifth failure locks it, growing (1, 5, 15
  min). A successful sign-in — by password or by code — clears the count.

The one-time code is the reset: whoever forgot their password signs in by code and sets
a new one. Hashing is CPU-bound for tens of milliseconds, so it runs off the event loop.
"""

from __future__ import annotations

import asyncio
import unicodedata
from datetime import UTC, datetime, timedelta
from functools import cache

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog
from app.models.auth import Identity, IdentityProvider, PasswordCredential, User

MIN_LENGTH = 12
MAX_LENGTH = 128

#: Every fifth failure locks the account, for the next of these in turn.
FAILURES_PER_LOCK = 5
LOCK_STEPS = (timedelta(minutes=1), timedelta(minutes=5), timedelta(minutes=15))

_hasher = PasswordHasher()


class LoginFailed(Exception):
    """Wrong address, no password, wrong password, locked, suspended — deliberately one."""


class PasswordRejected(Exception):
    """The new password breaks the length rule."""


class EmailUnverified(Exception):
    """The account's address was never proven, so it may not carry a password."""


class CurrentPasswordWrong(Exception):
    """Changing a password needs the current one, and this was not it."""


def _normalize(password: str) -> str:
    return unicodedata.normalize("NFKC", password)


def check_length(password: str) -> None:
    if not MIN_LENGTH <= len(_normalize(password)) <= MAX_LENGTH:
        raise PasswordRejected


@cache
def _dummy_hash() -> str:
    """What an unknown address is verified against, so it costs the same as a known one."""
    return _hasher.hash("no account has this password")


async def _verify(stored: str, password: str) -> bool:
    try:
        return await asyncio.to_thread(_hasher.verify, stored, _normalize(password))
    except (VerificationError, InvalidHashError):
        return False


async def _hash(password: str) -> str:
    return await asyncio.to_thread(_hasher.hash, _normalize(password))


def _utc(value: datetime | None) -> datetime | None:
    # SQLite hands back naive datetimes even for a timezone-aware column.
    return value if value is None or value.tzinfo else value.replace(tzinfo=UTC)


async def credential_of(session: AsyncSession, user_id: int) -> PasswordCredential | None:
    return (
        await session.execute(
            select(PasswordCredential).where(PasswordCredential.user_id == user_id)
        )
    ).scalar_one_or_none()


def _audit(user: User, action: str, actor: User | None = None) -> AuditLog:
    """Who did what to whose password — never the password, never the hash."""
    return AuditLog(
        entity_type="user",
        entity_id=user.id,
        action=action,
        actor=(actor or user).email,
        payload={},
    )


async def _check(session: AsyncSession, user: User, row: PasswordCredential, password: str) -> bool:
    """Verify against one account's credential, counting a failure and locking on every
    fifth. While locked, even the right password fails — and still pays for a verify."""
    now = datetime.now(UTC)
    locked = (_utc(row.locked_until) or now) > now
    if not await _verify(row.hash, password) or locked:
        if not locked:
            row.failed_attempts += 1
            if row.failed_attempts % FAILURES_PER_LOCK == 0:
                step = min(row.failed_attempts // FAILURES_PER_LOCK, len(LOCK_STEPS)) - 1
                row.locked_until = now + LOCK_STEPS[step]
                session.add(_audit(user, "password_locked"))
        return False
    clear_failures(row)
    if _hasher.check_needs_rehash(row.hash):
        row.hash = await _hash(password)
    return True


def clear_failures(row: PasswordCredential) -> None:
    row.failed_attempts = 0
    row.locked_until = None


async def login(session: AsyncSession, email: str, password: str) -> User:
    """The account behind this address and password, or :class:`LoginFailed`. The caller
    commits — a failure too, since it counted."""
    email = email.strip().lower()
    user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
    row = await credential_of(session, user.id) if user is not None else None
    if user is None or row is None:
        await _verify(_dummy_hash(), password)
        raise LoginFailed
    if not await _check(session, user, row, password) or not user.is_active:
        raise LoginFailed
    return user


async def set_password(
    session: AsyncSession, user: User, new_password: str, current_password: str | None
) -> None:
    """Set a first password, or change one — then the current one is required, and a
    wrong one counts like a failed sign-in, so a stolen session cannot guess through here."""
    if not user.email_verified:
        raise EmailUnverified
    check_length(new_password)
    row = await credential_of(session, user.id)
    now = datetime.now(UTC)
    if row is None:
        session.add(
            PasswordCredential(user_id=user.id, hash=await _hash(new_password), changed_at=now)
        )
        if not any(i.provider == IdentityProvider.PASSWORD for i in user.identities):
            user.identities.append(
                Identity(user_id=user.id, provider=IdentityProvider.PASSWORD, subject=user.email)
            )
        session.add(_audit(user, "password_set"))
        return
    if current_password is None or not await _check(session, user, row, current_password):
        raise CurrentPasswordWrong
    row.hash = await _hash(new_password)
    row.changed_at = now
    session.add(_audit(user, "password_changed"))


async def remove_password(session: AsyncSession, user: User, actor: User | None = None) -> bool:
    """Remove the password — by its owner, or cleared by the admin (``actor``). Never
    refused as "the last way in": the one-time code always is one. False if there was
    none."""
    row = await credential_of(session, user.id)
    if row is None:
        return False
    await session.delete(row)
    for identity in [i for i in user.identities if i.provider == IdentityProvider.PASSWORD]:
        user.identities.remove(identity)
    session.add(_audit(user, "password_cleared" if actor else "password_removed", actor))
    return True
