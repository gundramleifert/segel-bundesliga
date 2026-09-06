from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import JSON, DateTime, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Source(StrEnum):
    SAP_SAILING = "sapsailing"
    MANAGE2SAIL = "m2s"
    CSV = "csv"


class ExternalId(Base, TimestampMixin):
    """Linking local records to external systems.

    Deliberately a separate table instead of name matching: club and team names are
    spelled differently in SAP Sailing and manage2sail; fuzzy-matching names produces
    silent false mappings.
    """

    __tablename__ = "external_id"
    __table_args__ = (
        UniqueConstraint("source", "entity_type", "external_key"),
        UniqueConstraint("source", "entity_type", "entity_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(32), index=True)
    entity_type: Mapped[str] = mapped_column(String(32))
    entity_id: Mapped[int] = mapped_column(index=True)
    external_key: Mapped[str] = mapped_column(String(200))


class ImportRun(Base, TimestampMixin):
    __tablename__ = "import_run"

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(32), index=True)
    reference: Mapped[str] = mapped_column(String(200))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    ok: Mapped[bool] = mapped_column(default=False)
    # {"created": n, "updated": n, "skipped": n, "errors": [...]}
    summary: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class AuditLog(Base, TimestampMixin):
    """Who overwrote what — particularly discarded standings from offline sync."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(32), index=True)
    entity_id: Mapped[int] = mapped_column(index=True)
    action: Mapped[str] = mapped_column(String(32))
    actor: Mapped[str | None] = mapped_column(String(120), default=None)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
