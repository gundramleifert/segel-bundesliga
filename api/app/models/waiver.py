"""Liability waiver — versioned text and its confirmations.

Stories S-2 (a sailor confirms the waiver for a series or an event), VA-2 and VA-5
(the organizer sees who is cleared on the check-in list).

Two rules shape the model:

* **The text is immutable once published.** A confirmation points at exactly one
  ``WaiverText`` row. A changed wording is a **new version**, never an edit — otherwise a
  later change would silently alter what someone agreed to. This is the whole reason the
  version is tracked.
* **A series confirmation covers every event of that series.** The scope of a
  ``WaiverConfirmation`` is either a series or a single event; when checking whether a
  sailor is cleared for an event, a matching series-level confirmation counts.

Minors are handled explicitly: a sailor who is under 18 on the reference date cannot
clear the waiver by their own click. Their confirmation must be ``GUARDIAN`` and carry a
reference to the guardian's signed statement.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, utcnow


class WaiverMethod(StrEnum):
    ONLINE = "online"
    """The sailor confirmed it themselves, in the app — valid only for adults."""

    GUARDIAN = "guardian"
    """A legal guardian signed a paper statement; the scan is on file."""


class WaiverText(Base, TimestampMixin):
    """One specific, frozen version of the liability waiver.

    Both languages live in the same row: they are the same legal version, shown to the
    sailor in whichever language they read. ``version`` counts up from 1; the highest one
    is the version currently in force.
    """

    __tablename__ = "waiver_text"

    id: Mapped[int] = mapped_column(primary_key=True)
    version: Mapped[int] = mapped_column(unique=True, index=True)

    title_en: Mapped[str] = mapped_column(String(200))
    body_en: Mapped[str] = mapped_column(Text)
    title_de: Mapped[str] = mapped_column(String(200))
    body_de: Mapped[str] = mapped_column(Text)

    # When it went live. Set once, never moved — the text is frozen from here on.
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    # Internal changelog: "added engine-failure clause". Not shown to sailors.
    notes: Mapped[str | None] = mapped_column(String(500), default=None)

    confirmations: Mapped[list[WaiverConfirmation]] = relationship(
        back_populates="waiver_text"
    )

    def title(self, locale: str) -> str:
        return self.title_de if locale == "de" else self.title_en

    def body(self, locale: str) -> str:
        return self.body_de if locale == "de" else self.body_en


class WaiverConfirmation(Base, TimestampMixin):
    """A single act of agreeing to a specific waiver version, for one competition.

    Append-only evidence: who, when, which version, in which language, and — for a minor —
    which guardian signed. Nothing here is updated after the fact; a new agreement (a new
    version, or the guardian's signature arriving later) is a new row.
    """

    __tablename__ = "waiver_confirmation"
    __table_args__ = (
        CheckConstraint(
            "(series_id IS NULL) <> (event_id IS NULL)",
            name="exactly_one_scope",
        ),
        # One confirmation per sailor, per scope, per version. Split in two partial
        # indexes because a plain unique over nullable columns would treat every NULL as
        # distinct (same reason as the Team model).
        Index(
            "uq_waiver_conf_series",
            "sailor_id",
            "series_id",
            "waiver_text_id",
            unique=True,
            sqlite_where=text("event_id IS NULL"),
            postgresql_where=text("event_id IS NULL"),
        ),
        Index(
            "uq_waiver_conf_event",
            "sailor_id",
            "event_id",
            "waiver_text_id",
            unique=True,
            sqlite_where=text("series_id IS NULL"),
            postgresql_where=text("series_id IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    sailor_id: Mapped[int] = mapped_column(ForeignKey("sailor.id"), index=True)
    waiver_text_id: Mapped[int] = mapped_column(ForeignKey("waiver_text.id"), index=True)

    # Exactly one of these is set — the check constraint enforces it.
    series_id: Mapped[int | None] = mapped_column(
        ForeignKey("series.id"), index=True, default=None
    )
    event_id: Mapped[int | None] = mapped_column(
        ForeignKey("event.id"), index=True, default=None
    )

    confirmed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    method: Mapped[str] = mapped_column(String(16), default=WaiverMethod.ONLINE)
    # The language of the text the sailor was actually shown.
    locale_shown: Mapped[str] = mapped_column(String(2), default="en")

    # The signed-in account that recorded this — usually the sailor's own, but an admin or
    # club manager may enter a paper form. Kept for the audit trail; the account can later
    # be deactivated, so no cascade.
    recorded_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("app_user.id"), default=None
    )
    user_agent: Mapped[str | None] = mapped_column(String(400), default=None)

    # Minors only.
    guardian_name: Mapped[str | None] = mapped_column(String(160), default=None)
    # Pointer to the scan of the signed statement. File storage is not settled yet
    # (see docs/userstories.md, "File storage — not yet decided"), so this is a free
    # string: a URL, an object key, or a note like "on file, office ref #214".
    guardian_signature_ref: Mapped[str | None] = mapped_column(String(500), default=None)

    waiver_text: Mapped[WaiverText] = relationship(back_populates="confirmations")

    @property
    def is_guardian_signed(self) -> bool:
        return (
            self.method == WaiverMethod.GUARDIAN
            and bool(self.guardian_signature_ref)
        )
