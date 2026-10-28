"""Sending the site's emails — login codes and club invitations.

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
from email.utils import formataddr
from pathlib import Path
from typing import NamedTuple

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from app.config import settings
from app.i18n import Locale

logger = logging.getLogger(__name__)


class MailError(Exception):
    """The message could not be handed to the mail server — wraps the underlying
    smtplib/network error so callers don't need to know smtplib's exception zoo."""


# Mails go out in **German** unless the caller knows the reader's language (decided
# 2026-10-28): the site's readers are German clubs and sailors, and a mail — unlike a page —
# has no language switcher. English is the second variant, from the same catalog.
MAIL_LOCALE: Locale = "de"

# A mail is a Jinja2 template per language, `app/templates/mail/<lang>/<name>.txt`
# (decided 2026-10-28 — what Python mail code commonly does; short sentences stay in the
# `app/locales/` catalogs). Each extends its language's `_base.txt`, which is the footer
# every mail ends with, and fills the blocks `subject`, `reason` (completing "You receive
# this email because …") and `body`. Plain text, so nothing is escaped; an undefined
# value raises rather than leaving a hole in a mail. `tests/unit/test_mail.py` holds both
# languages to the same templates and the same variables.
TEMPLATES = Path(__file__).parent / "templates" / "mail"
_env = Environment(
    loader=FileSystemLoader(TEMPLATES),
    undefined=StrictUndefined,
    autoescape=False,
    trim_blocks=True,
    keep_trailing_newline=True,
)


class Mail(NamedTuple):
    subject: str
    body: str


def render_mail(name: str, locale: Locale = MAIL_LOCALE, /, **values: object) -> Mail:
    """Mail ``name`` in ``locale``, filled with ``values`` and the footer's own (the
    contact address, the site)."""
    template = _env.get_template(f"{locale}/{name}.txt")
    context = template.new_context(
        {"contact": settings.mail_contact, "site": settings.site_url, **values}
    )
    subject = "".join(template.blocks["subject"](context)).strip()
    return Mail(subject=subject, body=template.render(context.get_all()))


async def send_login_code(email: str, code: str, locale: Locale = MAIL_LOCALE) -> None:
    mail = render_mail("login_code", locale, code=code, minutes=settings.otp_lifetime_minutes)
    await _deliver(email, mail, what="login code", secret=code)


async def send_invitation(
    email: str,
    *,
    club: str,
    inviter: str,
    first_name: str,
    link: str,
    locale: Locale = MAIL_LOCALE,
) -> None:
    """Story V-16: the club's invitation to an account — the link creates it and makes
    the reader a member of ``club``. Names the club and who invited, as the story asks."""
    mail = render_mail(
        "invitation",
        locale,
        club=club,
        inviter=inviter,
        first_name=first_name,
        link=link,
        days=settings.invitation_lifetime_days,
    )
    await _deliver(email, mail, what="invitation link", secret=link)


async def _deliver(email: str, mail: Mail, *, what: str, secret: str) -> None:
    """Hands one mail to SBL_SMTP_HOST — or, without one, logs ``secret`` (the code, the
    link) instead, so the site works locally without a mail server. The secret is the
    log record's last argument: that is what the tests read."""
    if not settings.smtp_host:
        # No mail server configured: the secret goes to the log instead. Intended for
        # development — in production SBL_SMTP_HOST must be set.
        logger.warning("No SMTP configured. The %s for %s is: %s", what, email, secret)
        return

    message = EmailMessage()
    message["Subject"] = mail.subject
    message["From"] = formataddr((settings.mail_from_name, settings.mail_from))
    message["To"] = email
    message.set_content(mail.body)

    # Silent on success and on failure alike before this: there was no way to tell, short
    # of reading someone's inbox, whether SBL_SMTP_* actually works. Log both outcomes —
    # this is what "did the mail go out?" is checked against (`compose.sh logs api`).
    try:
        # smtplib is blocking; run in a thread to keep the event loop free.
        await asyncio.to_thread(_send, message)
    except Exception as exc:
        logger.error(
            "Sending the %s email to %s via %s:%s failed: %s",
            what,
            email,
            settings.smtp_host,
            settings.smtp_port,
            exc,
        )
        raise MailError(str(exc)) from exc
    logger.info(
        "The %s email was sent to %s via %s:%s", what, email, settings.smtp_host, settings.smtp_port
    )


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
