"""Feedback (Stories S-9, A-15): stored, mailed to the site's ``feedback_receiver``s, read
in the league office."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import Select, delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.mail import MailError, send_feedback
from app.models import Feedback, FeedbackCategory
from app.models.auth import ObjectType, Relation, User
from app.services import grants
from app.services.lookup import get_or_404

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Sent:
    """What the dialog sends, and what the server adds (the browser)."""

    category: FeedbackCategory
    message: str
    path: str
    locale: str
    app_version: str
    viewport_width: int | None
    viewport_height: int | None
    user_agent: str


async def record(session: AsyncSession, user: User, sent: Sent) -> Feedback:
    """Stores the message and commits; the mail follows the commit (:func:`notify`)."""
    row = Feedback(
        user_id=user.id,
        category=sent.category,
        message=sent.message,
        path=sent.path,
        locale=sent.locale[:16],
        app_version=sent.app_version[:64],
        viewport_width=sent.viewport_width,
        viewport_height=sent.viewport_height,
        user_agent=sent.user_agent[:512],
        handled=False,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    row.user = user
    return row


async def receivers(session: AsyncSession) -> list[User]:
    """Who is mailed: the written ``feedback_receiver`` tuples on the site — an admin
    reads the list, but is mailed only when holding the tuple itself (Story A-15)."""
    held = await grants.grants_on(session, ObjectType.SITE, None, Relation.FEEDBACK_RECEIVER)
    return [g.user for g in held if g.user.is_active]


async def notify(session: AsyncSession, row: Feedback) -> int:
    """One mail per receiver; none without one — the message is stored either way. A mail
    server that refuses is logged, not answered to the sender: what they wrote is kept."""
    mailed = 0
    for receiver in await receivers(session):
        try:
            await send_feedback(
                receiver.email,
                category=row.category,
                message=row.message,
                link=f"{settings.site_url}{row.path}",
                sender=row.user.display_name,
                sender_email=row.user.email,
                sent_at=row.created_at.strftime("%Y-%m-%d %H:%M UTC"),
                locale_shown=row.locale,
                app_version=row.app_version,
                viewport=_viewport(row),
                user_agent=row.user_agent,
            )
            mailed += 1
        except MailError:
            logger.exception("Feedback %s could not be mailed to %s", row.id, receiver.email)
    return mailed


def _viewport(row: Feedback) -> str:
    if row.viewport_width is None or row.viewport_height is None:
        return ""
    return f"{row.viewport_width}×{row.viewport_height}"


def listing() -> Select:
    """Every message with its sender — the list's filter narrows and orders it."""
    return select(Feedback).options(selectinload(Feedback.user))


async def set_handled(session: AsyncSession, feedback_id: int, handled: bool) -> Feedback:
    row = await get_or_404(session, Feedback, feedback_id)
    row.handled = handled
    await session.commit()
    return (await session.execute(listing().where(Feedback.id == feedback_id))).scalar_one()


async def erase_of(session: AsyncSession, user: User) -> None:
    """Story Z-7: what someone sent goes with their account. Flushes nothing."""
    await session.execute(delete(Feedback).where(Feedback.user_id == user.id))
