from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.competition import League


class PostKind(StrEnum):
    """Which page a post appears on: a league's news, or its press centre."""

    NEWS = "news"
    PRESS = "press"


class Post(Base, TimestampMixin):
    """A news article or a press release, written by editorial — Story R-1.

    Belongs to **one league or to the association** (``league_id`` empty): the
    association's posts appear on every league's page and on the home page.

    ``published`` works like an event's (Story VA-8): a draft is invisible on the public
    site, and publishing locks nothing. ``slug`` is made once from the title and kept
    when the title is corrected, so a shared link keeps working.
    """

    __tablename__ = "post"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(16), default=PostKind.NEWS, index=True)
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    league_id: Mapped[int | None] = mapped_column(
        ForeignKey("league.id", ondelete="SET NULL"), index=True, default=None
    )
    title: Mapped[str] = mapped_column(String(200))
    # The date shown — editorial's, not the row's creation time.
    published_on: Mapped[date] = mapped_column(Date)
    # The lead of an article, the teaser on its card. A release has none.
    teaser: Mapped[str | None] = mapped_column(String(500), default=None)
    # HTML from the editor, cleaned on write (`app/services/rich_text.py`, Story R-1).
    body: Mapped[str] = mapped_column(Text, default="")
    author: Mapped[str | None] = mapped_column(String(120), default=None)
    quote: Mapped[str | None] = mapped_column(String(500), default=None)
    quote_by: Mapped[str | None] = mapped_column(String(120), default=None)
    # An uploaded picture (`/api/posts/photos/<name>`) or one of the site's own — linked,
    # never copied (docs/site-structure.md § Content sources).
    photo_url: Mapped[str | None] = mapped_column(String(500), default=None)
    photo_credit: Mapped[str | None] = mapped_column(String(160), default=None)
    published: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    # Written to fill the page, not real news: the page says so (Story B-14).
    example: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")

    league: Mapped[League | None] = relationship()
