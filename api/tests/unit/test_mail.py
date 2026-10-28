"""Every mail the site sends ends with the same footer, in German by default (`app/mail.py`)."""

from app.config import settings
from app.mail import with_footer


def test_the_footer_says_who_sends_why_and_where_to_write():
    mail = with_footer("Hallo,\n", "Sie es angefordert haben")
    body, _, footer = mail.partition("\n-- \n")
    assert body == "Hallo,\n", "the signature delimiter is `-- ` on a line of its own"
    assert "Deutsche Segel-Liga e.V." in footer
    assert "Sie erhalten diese E-Mail, weil Sie es angefordert haben." in footer
    assert settings.mail_contact in footer
    assert f"{settings.site_url}/privacy" in footer
    assert f"{settings.site_url}/legal-notice" in footer


def test_english_when_the_caller_knows_the_reader_reads_english():
    footer = with_footer("Hello,\n", "you asked for it", "en")
    assert "You receive this email because you asked for it." in footer
    assert "Legal notice" in footer
