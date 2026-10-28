"""Every mail the site sends is a template per language, ends with the same footer, and
is German by default (`app/mail.py`)."""

import pytest
from jinja2 import meta

from app.config import settings
from app.i18n import DEFAULT_LOCALE, LOCALES
from app.mail import TEMPLATES, _env, render_mail

MAILS = sorted(p.stem for p in (TEMPLATES / DEFAULT_LOCALE).glob("*.txt"))


def _variables(locale: str, name: str) -> set[str]:
    source = (TEMPLATES / locale / f"{name}.txt").read_text("utf-8")
    return meta.find_undeclared_variables(_env.parse(source))


def test_the_footer_says_who_sends_why_and_where_to_write():
    mail = render_mail("login_code", code="123456", minutes=10)
    assert mail.subject == "Ihr Anmeldecode für die Deutsche Segel-Liga"
    body, _, footer = mail.body.partition("\n-- \n")
    assert body.startswith("Hallo,\n") and "123456" in body
    assert body.endswith("nichts.\n"), "the signature delimiter is `-- ` on a line of its own"
    assert "Deutsche Segel-Liga e.V." in footer
    assert "Sie erhalten diese E-Mail, weil auf unserer Website ein Anmeldecode" in footer
    assert settings.mail_contact in footer
    assert f"{settings.site_url}/privacy" in footer
    assert f"{settings.site_url}/legal-notice" in footer


def test_english_when_the_caller_knows_the_reader_reads_english():
    mail = render_mail("login_code", "en", code="123456", minutes=10)
    assert "You receive this email because a login code" in mail.body
    assert "Legal notice" in mail.body


@pytest.mark.parametrize("locale", [loc for loc in LOCALES if loc != DEFAULT_LOCALE])
def test_every_mail_exists_in_every_language_with_the_same_variables(locale):
    translated = sorted(p.stem for p in (TEMPLATES / locale).glob("*.txt"))
    assert translated == MAILS
    for name in MAILS:
        assert _variables(locale, name) == _variables(DEFAULT_LOCALE, name), name


def test_a_missing_value_raises_rather_than_leaving_a_hole():
    with pytest.raises(Exception, match="link"):
        render_mail("invitation", club="ASVW", inviter="A", first_name="B", days=14)
