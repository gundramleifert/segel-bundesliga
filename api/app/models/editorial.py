from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.competition import Event, League, Series


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
    __table_args__ = (
        CheckConstraint("event_id IS NULL OR series_id IS NULL", name="post_event_or_series"),
    )

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
    # A picture from the library (`/api/media/<name>.jpg`, Story R-2) or one of the site's
    # own — linked, never copied (docs/site-structure.md § Content sources).
    photo_url: Mapped[str | None] = mapped_column(String(500), default=None)
    photo_credit: Mapped[str | None] = mapped_column(String(160), default=None)
    published: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    # Written to fill the page, not real news: the page says so (Story B-14).
    example: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")

    # The regatta the post is about — an event, or a whole series — whose public pictures
    # end its page (Story R-1). Neither is required, never both.
    event_id: Mapped[int | None] = mapped_column(
        ForeignKey("event.id", ondelete="SET NULL"), index=True, default=None
    )
    series_id: Mapped[int | None] = mapped_column(
        ForeignKey("series.id", ondelete="SET NULL"), index=True, default=None
    )

    league: Mapped[League | None] = relationship()
    event: Mapped[Event | None] = relationship()
    series: Mapped[Series | None] = relationship()

    @property
    def league_slug(self) -> str | None:
        """Where the public site shows it — ``PostOut.league``; load ``league`` first."""
        return self.league.slug if self.league else None


class MediaSource(StrEnum):
    """How a picture reached the library — Story R-2."""

    UPLOAD = "upload"  # editorial, from the editor or the Media tab
    IMPORT = "import"  # a source with an import key: the upload page, later a bridge


class ImportKey(Base, TimestampMixin):
    """What lets a source deliver pictures without a person's sign-in — Story R-2.

    Editorial makes one per source ("Photos Kiel, act 3") and sees it **once**; only its
    SHA-256 is stored. A revoked key keeps its row, so the pictures it delivered still say
    where they came from. How many it delivered, and when last, is counted from
    `MediaItem.import_key_id`, never stored.
    """

    __tablename__ = "import_key"
    __table_args__ = (
        CheckConstraint("event_id IS NULL OR series_id IS NULL", name="event_or_series"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(String(120))
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    # The key's first characters, so editorial can tell two keys apart in the list.
    prefix: Mapped[str] = mapped_column(String(16))
    # Put on every picture that arrives without a credit of its own.
    credit: Mapped[str | None] = mapped_column(String(160), default=None)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    # What its pictures are of — an event or a series, never both, and neither required
    # (Story R-2). An event implies its series; a series' pictures are its events' too.
    event_id: Mapped[int | None] = mapped_column(
        ForeignKey("event.id", ondelete="SET NULL"), index=True, default=None
    )
    series_id: Mapped[int | None] = mapped_column(
        ForeignKey("series.id", ondelete="SET NULL"), index=True, default=None
    )
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("app_user.id", ondelete="SET NULL"), default=None
    )

    event: Mapped[Event | None] = relationship()
    series: Mapped[Series | None] = relationship()


class MediaItem(Base, TimestampMixin):
    """One picture in the library — Story R-2, `docs/PLAN_MEDIA.md`.

    The upload is kept as it came, privately; the site serves WebP made from it at a few
    widths (`app/services/media.py`). ``width``/``height`` are the largest one's, at most
    2400 px. ``name`` is random, so a picture nobody has used yet cannot be found by
    counting.
    ``sha256`` is of the bytes as uploaded: the same file twice is one entry.
    """

    __tablename__ = "media_item"
    __table_args__ = (
        UniqueConstraint("import_key_id", "external_id", name="import_external_id"),
        CheckConstraint("event_id IS NULL OR series_id IS NULL", name="event_or_series"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    source: Mapped[str] = mapped_column(String(16), default=MediaSource.UPLOAD)
    sha256: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    original_name: Mapped[str] = mapped_column(String(255), default="")
    alt: Mapped[str] = mapped_column(String(300), default="")
    # False while ``alt`` is still the file's name: the library marks it, a screen
    # reader would read "DSC 0471" (Story R-2). Set once someone writes one.
    alt_confirmed: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    credit: Mapped[str | None] = mapped_column(String(160), default=None)
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    # The camera's date, read before EXIF is dropped; the location never is kept.
    taken_on: Mapped[date | None] = mapped_column(Date, default=None)
    import_key_id: Mapped[int | None] = mapped_column(
        ForeignKey("import_key.id", ondelete="SET NULL"), index=True, default=None
    )
    # The source's own id for the picture: sent twice with one key, it is one entry.
    external_id: Mapped[str | None] = mapped_column(String(200), default=None)
    uploaded_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("app_user.id", ondelete="SET NULL"), default=None
    )
    # What the picture is of — an event or a series, never both, and neither required
    # (Story R-2). An event implies its series; a series' pictures are its events' too.
    event_id: Mapped[int | None] = mapped_column(
        ForeignKey("event.id", ondelete="SET NULL"), index=True, default=None
    )
    series_id: Mapped[int | None] = mapped_column(
        ForeignKey("series.id", ondelete="SET NULL"), index=True, default=None
    )

    event: Mapped[Event | None] = relationship()
    series: Mapped[Series | None] = relationship()

    @property
    def url(self) -> str:
        """The largest variant — what a post's text and cover point at."""
        return f"/api/media/{self.name}.webp"

    @property
    def thumb_url(self) -> str:
        return f"/api/media/{self.name}-480.webp"


def context_of(row: ImportKey | MediaItem | Post) -> str | None:
    """What a key's or a picture's pictures are of, as a name — load ``event`` and
    ``series`` first."""
    if row.event is not None:
        return row.event.title
    return row.series.name if row.series is not None else None
