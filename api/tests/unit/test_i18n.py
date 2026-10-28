"""The backend's catalogs (`app/i18n.py`) — what ``pnpm check:i18n`` is to the frontend's:
every language says every message, with the same placeholders, and every key the code
names is in them."""

import re
from pathlib import Path

import pytest

from app.i18n import DEFAULT_LOCALE, LOCALES, catalog, placeholders, t

APP = Path(__file__).parents[2] / "app"
# `t(locale, "mail.invitation.subject", …)` — a key spelled out at the call.
CALL = re.compile(r"""\bt\(\s*[\w.]+\s*,\s*"([a-z_][\w.]*)"\s*[,)]""")


def _keys_in_code() -> set[str]:
    return {key for path in APP.rglob("*.py") for key in CALL.findall(path.read_text("utf-8"))}


@pytest.mark.parametrize("locale", [loc for loc in LOCALES if loc != DEFAULT_LOCALE])
def test_every_language_has_every_message_with_the_same_placeholders(locale):
    source, translated = catalog(DEFAULT_LOCALE), catalog(locale)
    assert set(translated) == set(source), "a key is missing or left over"
    for key, message in source.items():
        assert placeholders(translated[key]) == placeholders(message), key


def test_every_key_the_code_names_exists():
    named = _keys_in_code()
    assert "auth.register.sent" in named, "the scan finds the calls"
    assert named - set(catalog(DEFAULT_LOCALE)) == set()


def test_placeholders_are_filled_and_a_missing_one_raises():
    assert "10 Minuten" in t("de", "auth.register.sent", minutes=10)
    with pytest.raises(KeyError):
        t("en", "auth.register.sent")
