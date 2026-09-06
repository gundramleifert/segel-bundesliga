"""User accounts, identities and roles.

**We don't manage passwords.** Whoever signs in proves themselves via an identity
provider (Google, Microsoft) or a one-time code to their email address. That saves us
password hashes, reset flows, password rules, and liability for stolen credentials — for
a league site with a few dozen accounts total, that's clearly the better trade.

An account (``User``) can have several ``Identity`` entries: the same person signs in
with Google one day and by email code the next, landing in the same account. Linked via
the **verified** email address.

Roles are their own rows, not a column: a person can have several (the league office is
often also the editorial team), and they need to be grantable and revocable without
changing the schema.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Role(StrEnum):
    ADMIN = "admin"
    """Admin: master data, series, matchdays, accounts and roles."""

    EDITOR = "editor"
    """Editorial team: write news, approve club contributions."""

    RACE_OFFICER = "race_officer"
    """Race committee: record and correct results."""

    CLUB_MANAGER = "club_manager"
    """Club account: manage own team, submit contributions, check-in."""


class IdentityProvider(StrEnum):
    GOOGLE = "google"
    MICROSOFT = "microsoft"
    EMAIL = "email"
    """One-time code to the email address — for anyone without a Google or Microsoft account."""


class User(Base, TimestampMixin):
    __tablename__ = "app_user"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Stored lowercase; identity providers link via this.
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(120))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Whether the address is verified. If someone self-registers, they've only claimed
    # it initially; only a redeemed one-time code (or a provider token) proves it.
    # Without this verification, the account cannot request membership.
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    # The club this account represents — for a club account, their own.
    # **Memberships** of a person are instead in ``ClubMember``: someone can be in
    # several clubs but always acts for only one.
    club_id: Mapped[int | None] = mapped_column(
        ForeignKey("club.id"), default=None, index=True
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )

    role_rows: Mapped[list[UserRole]] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )
    identities: Mapped[list[Identity]] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )

    @property
    def roles(self) -> set[str]:
        return {row.role for row in self.role_rows}

    def has_any(self, *roles: str) -> bool:
        return bool(self.roles & set(roles))


class UserRole(Base, TimestampMixin):
    __tablename__ = "user_role"
    __table_args__ = (UniqueConstraint("user_id", "role"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("app_user.id"), index=True)
    role: Mapped[str] = mapped_column(String(32), index=True)

    user: Mapped[User] = relationship(back_populates="role_rows")


class Identity(Base, TimestampMixin):
    """A way an account proves itself."""

    __tablename__ = "identity"
    __table_args__ = (UniqueConstraint("provider", "subject"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("app_user.id"), index=True)
    provider: Mapped[str] = mapped_column(String(32), index=True)
    # The immutable identifier with the provider ("sub" in the ID token); for EMAIL, the address.
    subject: Mapped[str] = mapped_column(String(254))

    user: Mapped[User] = relationship(back_populates="identities")


class LoginCode(Base, TimestampMixin):
    """One-time code for email login.

    The code exists **only as a hash** in the database: someone reading the database
    should not be able to sign in with it. ``attempts`` limits brute-forcing, ``consumed_at``
    makes each code single-use.
    """

    __tablename__ = "login_code"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), index=True)
    code_hash: Mapped[str] = mapped_column(String(255))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    attempts: Mapped[int] = mapped_column(default=0)
    consumed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
