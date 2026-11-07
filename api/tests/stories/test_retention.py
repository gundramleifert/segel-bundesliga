"""User story B-9: the privacy policy's deletion periods are kept.

A one-time code is deleted 7 days after it expired, an audit-log row after 3 years —
what the privacy page states under "Speicherdauer und Löschung".
"""

from datetime import timedelta

from sqlalchemy import func, select

from app.db import SessionLocal
from app.models import AuditLog
from app.models.auth import LoginCode
from app.models.base import utcnow
from app.services import retention


async def test_old_login_codes_and_audit_rows_are_deleted_recent_ones_kept(seeded):
    """B-9: the purge deletes what is past its period and nothing younger."""
    now = utcnow()
    async with SessionLocal() as session:
        old_code = LoginCode(
            email="old@example.com", code_hash="x", expires_at=now - timedelta(days=8)
        )
        new_code = LoginCode(
            email="new@example.com", code_hash="x", expires_at=now - timedelta(days=6)
        )
        old_row = AuditLog(
            entity_type="test-retention",
            entity_id=1,
            action="old",
            created_at=now - timedelta(days=3 * 365 + 1),
        )
        new_row = AuditLog(
            entity_type="test-retention",
            entity_id=2,
            action="new",
            created_at=now - timedelta(days=3 * 365 - 1),
        )
        session.add_all([old_code, new_code, old_row, new_row])
        await session.commit()

        await retention.purge(session)
        await session.commit()

        codes = set(
            (
                await session.execute(
                    select(LoginCode.email).where(
                        LoginCode.email.in_(["old@example.com", "new@example.com"])
                    )
                )
            ).scalars()
        )
        actions = set(
            (
                await session.execute(
                    select(AuditLog.action).where(AuditLog.entity_type == "test-retention")
                )
            ).scalars()
        )
    assert codes == {"new@example.com"}
    assert actions == {"new"}
    assert (await _count_older_than_three_years()) == 0


async def _count_older_than_three_years() -> int:
    async with SessionLocal() as session:
        return await session.scalar(
            select(func.count())
            .select_from(AuditLog)
            .where(AuditLog.created_at < utcnow() - timedelta(days=3 * 365))
        )
