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
from email.utils import formataddr

from app.config import settings
from app.i18n import Locale, tr

logger = logging.getLogger(__name__)


class MailError(Exception):
    """The message could not be handed to the mail server — wraps the underlying
    smtplib/network error so callers don't need to know smtplib's exception zoo."""


# Mails go out in **German** unless the caller knows the reader's language (decided
# 2026-10-28): the site's readers are German clubs and sailors, and a mail — unlike a page —
# has no language switcher. English is the second variant, through `tr` as everywhere.
MAIL_LOCALE: Locale = "de"

# Every mail ends with the same footer: who sends it, why the reader gets it, where to
# write to a person, and the privacy and legal pages. The sender is the association, not a
# league — the same name as the site. The register court and number are not in it: they
# are still «folgt» in the legal notice (`legal.json`) and are not to be invented. A mail
# the site sends is transactional — something the reader or their club did — so it carries
# no unsubscribe link; it says instead what caused it. `-- ` (with its space) is the
# signature delimiter mail programs fold away in a reply.
FOOTER_EN = """
-- 
Deutsche Segel-Liga e.V.
c/o Düsseldorfer Yacht-Club · Rotterdamer Straße 30 · 40474 Düsseldorf

You receive this email because {reason}.
It was sent automatically — to reach a person, write to {contact}.

Website: {site}
Privacy: {site}/privacy · Legal notice: {site}/legal-notice
"""

FOOTER_DE = """
-- 
Deutsche Segel-Liga e.V.
c/o Düsseldorfer Yacht-Club · Rotterdamer Straße 30 · 40474 Düsseldorf

Sie erhalten diese E-Mail, weil {reason}.
Sie wurde automatisch versandt — eine Person erreichen Sie unter {contact}.

Website: {site}
Datenschutz: {site}/privacy · Impressum: {site}/legal-notice
"""


def with_footer(body: str, reason: str, locale: Locale = MAIL_LOCALE) -> str:
    """``body`` with the footer every mail of the site ends with; ``reason`` completes
    "You receive this email because …" in ``locale``'s language."""
    footer = tr(locale, en=FOOTER_EN, de=FOOTER_DE)
    return body + footer.format(
        reason=reason, contact=settings.mail_contact, site=settings.site_url
    )


async def send_login_code(email: str, code: str, locale: Locale = MAIL_LOCALE) -> None:
    minutes = settings.otp_lifetime_minutes
    subject = tr(
        locale,
        en="Your login code for Deutsche Segel-Liga",
        de="Ihr Anmeldecode für die Deutsche Segel-Liga",
    )
    text = tr(
        locale,
        en="""Hello,

Your login code is: {code}

It is valid for {minutes} minutes and can only be used once.

If you did not try to log in, you can ignore this message — nothing happens without the code.
""",
        de="""Hallo,

Ihr Anmeldecode lautet: {code}

Er gilt {minutes} Minuten und kann nur einmal verwendet werden.

Wenn Sie sich nicht anmelden wollten, können Sie diese Nachricht ignorieren —
ohne den Code geschieht nichts.
""",
    )
    body = with_footer(
        text.format(code=code, minutes=minutes),
        tr(
            locale,
            en="a login code for this address was requested on our website",
            de="auf unserer Website ein Anmeldecode für diese Adresse angefordert wurde",
        ),
        locale,
    )

    if not settings.smtp_host:
        # No mail server configured: code goes to the log instead. Intended for development
        # — in production SBL_SMTP_HOST must be set.
        logger.warning("No SMTP configured. Login code for %s is: %s", email, code)
        return

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = formataddr((settings.mail_from_name, settings.mail_from))
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
