"""Sending login emails.

Intentionally behind a narrow interface: in development the code goes to the log, in
production it goes via SMTP. Anyone trying the application locally should be able to log in
without setting up a mail server.
"""

from __future__ import annotations

import asyncio
import logging
import smtplib
import ssl
from email.message import EmailMessage

from app.config import settings

logger = logging.getLogger(__name__)

SUBJECT = "Your login code for Sailing Bundesliga"

BODY = """Hello,

Your login code is: {code}

It is valid for {minutes} minutes and can only be used once.

If you did not try to log in, you can ignore this message — nothing happens without the code.
"""


async def send_login_code(email: str, code: str) -> None:
    minutes = settings.otp_lifetime_minutes
    if not settings.smtp_host:
        # No mail server configured: code goes to the log instead. Intended for development
        # — in production SBL_SMTP_HOST must be set.
        logger.warning("No SMTP configured. Login code for %s is: %s", email, code)
        return

    message = EmailMessage()
    message["Subject"] = SUBJECT
    message["From"] = settings.mail_from
    message["To"] = email
    message.set_content(BODY.format(code=code, minutes=minutes))

    # smtplib is blocking; run in a thread to keep the event loop free.
    await asyncio.to_thread(_send, message)


def _send(message: EmailMessage) -> None:
    # Implicit TLS (smtp_ssl, typically port 465) encrypts from the first byte and needs
    # its own connection class; STARTTLS (typically port 587) upgrades a plaintext one.
    # Passing an explicit `ssl.create_default_context()` rather than smtplib's own default
    # ensures certificate and hostname verification actually happen.
    if settings.smtp_ssl:
        smtp_cls = smtplib.SMTP_SSL
        context = ssl.create_default_context()
        smtp: smtplib.SMTP = smtp_cls(
            settings.smtp_host, settings.smtp_port, timeout=15, context=context
        )
    else:
        smtp = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15)

    with smtp:
        if settings.smtp_starttls and not settings.smtp_ssl:
            smtp.starttls(context=ssl.create_default_context())
        if settings.smtp_user:
            smtp.login(settings.smtp_user, settings.smtp_password)
        smtp.send_message(message)
