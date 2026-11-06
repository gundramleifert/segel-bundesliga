"""The league's pool of judges and who sits on which jury (Stories JU-1–JU-5).

Being in the pool is a tuple (``user:judge:site``) and being an event's jury is one too
(``user:jury:event``) — the model's, written by `app/services/jury.py`. What is here is
what the model has no place for: the licences a judge says they hold, and the
conversation before an approval — asked, answered, approved.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.competition import Event


class JudgeLicence(StrEnum):
    """A licence for the jury, after the DSV's licence rules for race officials. The
    judge's own word (decided 2026-11-03): nobody checks it, as on the water."""

    UMPIRE = "umpire"
    """Umpires on the water — the league's races are umpired."""

    NATIONAL_JUDGE = "national_judge"
    """Nationaler Schiedsrichter."""

    REGIONAL_JUDGE = "regional_judge"
    """Regionaler Schiedsrichter."""


class JuryState(StrEnum):
    """Where a judge stands for one event — derived from the request's columns, never
    stored (:attr:`JuryRequest.state`)."""

    INVITED = "invited"
    AVAILABLE = "available"
    DECLINED = "declined"
    APPROVED = "approved"


class JudgeLicenceHolding(Base):
    """One licence a judge says they hold (Story JU-2)."""

    __tablename__ = "judge_licence"
    __table_args__ = (UniqueConstraint("user_id", "licence"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("app_user.id", ondelete="CASCADE"), index=True)
    licence: Mapped[str] = mapped_column(String(32))


class JuryRequest(Base, TimestampMixin):
    """One judge and one event: asked by the jury organizer (JU-3), answered by the judge
    (JU-4), approved by the organizer (JU-5). One row per pair; an approval without a
    request first — a judge put on the event directly — is a row with no ``invited_at``.

    ``approved`` mirrors the event's ``jury`` tuple, which is the fact the rest of the
    site reads; the service writes both together.
    """

    __tablename__ = "jury_request"
    __table_args__ = (UniqueConstraint("event_id", "user_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("event.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("app_user.id", ondelete="CASCADE"), index=True)
    invited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    # The judge's answer: True available (their application), False declined, None open.
    available: Mapped[bool | None] = mapped_column(Boolean, default=None)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    event: Mapped[Event] = relationship(lazy="raise")

    @property
    def state(self) -> JuryState:
        if self.approved:
            return JuryState.APPROVED
        if self.available is None:
            return JuryState.INVITED
        return JuryState.AVAILABLE if self.available else JuryState.DECLINED
