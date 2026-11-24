"""What people tell the league office from the page they are on (Stories S-9, A-15).

One row per message. Who sent it is the account; its name and address are read from
there, never copied in. The rest is what the browser knew when the dialog was sent.
"""

from __future__ import annotations

from enum import StrEnum

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.auth import User
from app.models.base import Base, TimestampMixin

#: The longest message accepted (Story S-9).
FEEDBACK_MAX_LENGTH = 5000


class FeedbackCategory(StrEnum):
    """What kind of message — the sender's own word for it."""

    BUG = "bug"
    FEATURE = "feature"
    QUESTION = "question"
    OTHER = "other"


class Feedback(Base, TimestampMixin):
    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Erased with the account's person (Story Z-7, `people.end_account`); the cascade is
    # for an account row deleted outright, which the app itself never does.
    user_id: Mapped[int] = mapped_column(ForeignKey("app_user.id", ondelete="CASCADE"), index=True)
    category: Mapped[str] = mapped_column(String(16))
    message: Mapped[str] = mapped_column(Text)
    # Path and query of the page the dialog was opened on — an address inside the site.
    path: Mapped[str] = mapped_column(String(2000))
    locale: Mapped[str] = mapped_column(String(16), default="")
    app_version: Mapped[str] = mapped_column(String(64), default="")
    viewport_width: Mapped[int | None] = mapped_column(Integer, default=None)
    viewport_height: Mapped[int | None] = mapped_column(Integer, default=None)
    user_agent: Mapped[str] = mapped_column(String(512), default="")
    handled: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    user: Mapped[User] = relationship(lazy="raise")
