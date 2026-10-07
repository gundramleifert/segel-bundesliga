"""A person's own space (Stories S-5, S-6): their documents and their bank account.

Both hang off the **account**, not the sailor record: a helper or a jury member may never
have sailed in a result, and still has a boat licence and costs to be paid back.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum

from sqlalchemy import CheckConstraint, Date, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin

#: The largest document a person keeps — the same limit as a waiver scan or a receipt.
PERSONAL_DOCUMENT_MAX_BYTES = 10 * 1024 * 1024


class DocumentKind(StrEnum):
    """The label of a personal document — a fixed list, so an organizer can look for
    "boat licence" across people instead of reading free text."""

    BOAT_LICENCE_SEA = "boat_licence_sea"
    """Sportbootführerschein See."""

    BOAT_LICENCE_INLAND = "boat_licence_inland"
    """Sportbootführerschein Binnen."""

    RADIO_CERTIFICATE = "radio_certificate"
    """SRC, UBI or another radio operator's certificate."""

    FIRST_AID = "first_aid"

    OFFICIAL_LICENCE = "official_licence"
    """An umpire's, judge's or race officer's licence."""

    OTHER = "other"
    """Anything else — then the title says what it is."""


class PersonalDocument(Base, TimestampMixin):
    """A licence or certificate a person keeps on the site (Story S-5).

    Stored under a random name like a waiver scan; the uploaded file name is only shown.
    Seen by the owner and the person's organizers (``app/services/personal.py``), and
    every look by anyone but the owner goes to the audit log.
    """

    __tablename__ = "personal_document"
    __table_args__ = (
        CheckConstraint(
            f"size_bytes > 0 AND size_bytes <= {PERSONAL_DOCUMENT_MAX_BYTES}",
            name="size_within_limit",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("app_user.id"), index=True)
    kind: Mapped[str] = mapped_column(String(32))
    # Required for ``other``; for a listed kind a free addition ("SRC, issued in Kiel").
    title: Mapped[str | None] = mapped_column(String(200), default=None)
    # Empty: does not expire. Past: shown as expired, never hidden.
    valid_until: Mapped[date | None] = mapped_column(Date, default=None)
    stored_name: Mapped[str] = mapped_column(String(64), unique=True)
    original_name: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(64))
    size_bytes: Mapped[int] = mapped_column()

    @property
    def expired(self) -> bool:
        return self.valid_until is not None and self.valid_until < date.today()


class BankAccount(Base, TimestampMixin):
    """Where a person's costs are paid back to (Story S-6) — one per account.

    Its own table rather than columns on ``User``, for the reason ``PasswordCredential``
    is: every serializer that lists an account reads ``User``, and none of them can carry
    an IBAN it never sees. A claim copies holder and IBAN at submission (Story F-2), so
    changing this later changes no claim already filed.
    """

    __tablename__ = "bank_account"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("app_user.id"), unique=True)
    holder: Mapped[str] = mapped_column(String(160))
    # Normalised: no spaces, upper case, check digits verified (ISO 13616).
    iban: Mapped[str] = mapped_column(String(34))
    bic: Mapped[str | None] = mapped_column(String(11), default=None)
