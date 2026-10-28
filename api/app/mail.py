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


class MailError(Exception):
    """The message could not be handed to the mail server — wraps the underlying
    smtplib/network error so callers don't need to know smtplib's exception zoo."""


SUBJECT = "Your login code for Deutsche Segelliga"

BODY = """Hello,

Your login code is: {code}

It is valid for {minutes} minutes and can only be used once.

If you did not try to log in, you can ignore this message — nothing happens without the code.
"""


async def send_login_code(email: str, code: str) -> None:
    minutes = settings.otp_lifetime_minutes
    body = BODY.format(code=code, minutes=minutes)

    if not settings.smtp_host:
        # No mail server configured: code goes to the log instead. Intended for development
        # — in production SBL_SMTP_HOST must be set.
        logger.warning("No SMTP configured. Login code for %s is: %s", email, code)
        return

    message = EmailMessage()
    message["Subject"] = SUBJECT
    message["From"] = settings.mail_from
    message["To"] = email
    message.set_content(body)

    # Silent on success and on failure alike before this: there was no way to tell, short
    # of reading someone's inbox, whether SBL_SMTP_* actually works. Log both outcomes —
    # this is what "did the mail go out?" is checked against (`compose.sh logs api`).
    try:
        # smtplib is blocking; run in a thread to keep the event loop free.
        await asyncio.to_thread(_send, message)
    except Exception as exc:
        logger.error(
            "Sending the login email to %s via %s:%s failed: %s",
            email,
            settings.smtp_host,
            settings.smtp_port,
            exc,
        )
        raise MailError(str(exc)) from exc
    logger.info("Login email sent to %s via %s:%s", email, settings.smtp_host, settings.smtp_port)


def _connect() -> smtplib.SMTP:
    """A connection to SBL_SMTP_HOST, encrypted and signed in — what a send starts with."""
    # Implicit TLS (smtp_ssl, typically port 465) encrypts from the first byte and needs
    # its own connection class; STARTTLS (typically port 587) upgrades a plaintext one.
    # Passing an explicit `ssl.create_default_context()` rather than smtplib's own default
    # ensures certificate and hostname verification actually happen.
    if settings.smtp_ssl:
        context = ssl.create_default_context()
        smtp: smtplib.SMTP = smtplib.SMTP_SSL(
            settings.smtp_host, settings.smtp_port, timeout=15, context=context
        )
    else:
        smtp = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15)
    try:
        if settings.smtp_starttls and not settings.smtp_ssl:
            smtp.starttls(context=ssl.create_default_context())
        if settings.smtp_user:
            smtp.login(settings.smtp_user, settings.smtp_password)
    except Exception:
        smtp.close()
        raise
    return smtp


def _send(message: EmailMessage) -> None:
    with _connect() as smtp:
        smtp.send_message(message)


def main() -> None:
    """Test the mail settings: connect, encrypt and sign in, then stop — or, with
    `--send`, also send a login mail with the code 000000.

        python -m app.mail                       # connection test, sends nothing
        python -m app.mail --send you@example.com
        deploy/compose/compose.sh exec api python -m app.mail
    """
    import argparse

    parser = argparse.ArgumentParser(description=main.__doc__)
    parser.add_argument("--send", metavar="ADDRESS", help="also send a test login mail there")
    args = parser.parse_args()
    if not settings.smtp_host:
        raise SystemExit("SBL_SMTP_HOST is not set: login codes go to the log.")
    where = f"{settings.smtp_host}:{settings.smtp_port} as {settings.smtp_user or '(no login)'}"
    try:
        _connect().quit()
    except Exception as exc:
        raise SystemExit(f"Connection to {where} failed: {exc}") from exc
    print(f"Connected to {where}: encrypted and signed in.")
    if args.send:
        asyncio.run(send_login_code(args.send, "000000"))
        print(f"Test mail sent from {settings.mail_from} to {args.send}.")


if __name__ == "__main__":
    main()
