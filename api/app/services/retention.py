"""Deleting what the privacy policy promises to delete (Story B-9).

The periods are the privacy page's "Speicherdauer und Löschung", decided 2026-11-07: a
one-time code goes 7 days after it expired, the audit log after 3 years. The request log
is not the application's — Docker hands it to journald, whose 14 days are set on the host
(docs/deploy-server.md). Waivers (3 years after the season) and receipts (10 years) have no
routine yet: the first of them falls due in 2029.
"""

import asyncio
import logging
from datetime import timedelta

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings
from app.models import AuditLog
from app.models.auth import LoginCode
from app.models.base import utcnow

logger = logging.getLogger(__name__)

LOGIN_CODE_DAYS = 7
AUDIT_LOG_YEARS = 3


async def purge(session: AsyncSession) -> None:
    """Delete expired login codes and old audit-log rows; the caller commits."""
    now = utcnow()
    await session.execute(
        delete(LoginCode).where(LoginCode.expires_at < now - timedelta(days=LOGIN_CODE_DAYS))
    )
    await session.execute(
        delete(AuditLog).where(AuditLog.created_at < now - timedelta(days=365 * AUDIT_LOG_YEARS))
    )


async def run(sessions: async_sessionmaker[AsyncSession]) -> None:
    """Runs while the server does: once at start, then every ``retention_purge_hours``."""
    while True:
        try:
            async with sessions() as session:
                await purge(session)
                await session.commit()
        except Exception:  # one bad round must not end the loop
            logger.exception("Retention purge")
        await asyncio.sleep(settings.retention_purge_hours * 3600)
