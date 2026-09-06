"""Stored standings.

These tables are **derived**: they arise exclusively from ``RaceEntry`` via
``app.services.standings.recompute_event``. Nothing is allowed to write them by hand. A
full rebuild is possible at any time and must produce the same result — that's the
property that makes them harmless.

Why store anything at all, if it can all be computed: the league table, exports, and the
live view query the same numbers very often, and stored values allow sorting and
filtering on them without recalculating 48 races every time.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class EventStanding(Base, TimestampMixin):
    """A row in the matchday standings."""

    __tablename__ = "event_standing"
    __table_args__ = (UniqueConstraint("event_id", "team_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("event.id"), index=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("team.id"), index=True)

    rank: Mapped[int]
    total_points: Mapped[float]
    net_points: Mapped[float]
    races_scored: Mapped[int]
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SeriesStanding(Base, TimestampMixin):
    """A row in the series standings."""

    __tablename__ = "series_standing"
    __table_args__ = (UniqueConstraint("series_id", "team_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    series_id: Mapped[int] = mapped_column(ForeignKey("series.id"), index=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("team.id"), index=True)

    rank: Mapped[int]
    points: Mapped[float]
    # Matchdays where the team actually sailed.
    events_sailed: Mapped[int]
    # Matchdays where the team received the substitute rating (participant count + 1).
    events_missed: Mapped[int]
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
