"""Internationalisation of what the backend itself says. Errors are not here: they are
typed Problems the frontend words (`app/problems.py`). Mails are not here either: each is
a Jinja2 template per language (`app/mail.py`). What is left is the few sentences a route
answers in its own words.

**Catalogs, one file per namespace and language**, like the frontend's
(`web/src/i18n/locales/`): ``app/locales/<lang>/<namespace>.toml``, a key's path being
``<namespace>.<table>.<key>`` — ``t(locale, "auth.register.sent", minutes=10)``. TOML
because it is in the standard library and reads well. English is the source; German is a
full second language.

**Placeholders are ``{name}``** — the same as an ICU simple argument in the frontend, so a
translator sees one syntax. Nothing else of ICU yet: no plural, no select; the day one is
needed it comes here, not as a second key per form. A literal brace is ``{{``/``}}``.

``tests/unit/test_i18n.py`` is the gate, as ``pnpm check:i18n`` is the frontend's: every
language has the same keys with the same placeholders, and every key the code names exists.

Locale is resolved once per request from the ``Accept-Language`` header via the
``Locale``/``resolve_locale`` dependency and threaded through explicitly. Nothing here is
implicit or global — a request without the dependency simply gets English, which is the
correct default for a public API; a mail without a known reader is German
(`app/mail.py::MAIL_LOCALE`).
"""

from __future__ import annotations

import string
import tomllib
from functools import cache
from pathlib import Path
from typing import Literal, get_args

from fastapi import Header

Locale = Literal["en", "de"]

DEFAULT_LOCALE: Locale = "en"
LOCALES: tuple[Locale, ...] = get_args(Locale)
CATALOG_DIR = Path(__file__).parent / "locales"


def resolve_locale(accept_language: str | None = Header(default=None)) -> Locale:
    """Picks German only if it's explicitly preferred; English is the default.

    A bare `Accept-Language: de` or `de-DE,de;q=0.9,en;q=0.8` selects German. Anything
    else — missing header, `en`, `*`, an unrelated language — falls back to English.
    """
    if not accept_language:
        return DEFAULT_LOCALE
    primary = accept_language.split(",")[0].strip().lower()
    return "de" if primary.startswith("de") else DEFAULT_LOCALE


def _flatten(table: dict, prefix: str) -> dict[str, str]:
    flat: dict[str, str] = {}
    for key, value in table.items():
        path = f"{prefix}.{key}"
        if isinstance(value, dict):
            flat.update(_flatten(value, path))
        else:
            flat[path] = value
    return flat


@cache
def catalog(locale: Locale) -> dict[str, str]:
    """Every message of ``locale``, by its dotted key."""
    messages: dict[str, str] = {}
    for path in sorted((CATALOG_DIR / locale).glob("*.toml")):
        messages.update(_flatten(tomllib.loads(path.read_text("utf-8")), path.stem))
    return messages


def placeholders(message: str) -> set[str]:
    """The ``{name}``s of a message."""
    return {name for _, name, _, _ in string.Formatter().parse(message) if name is not None}


def t(locale: Locale, key: str, /, **values: object) -> str:
    """The message ``key`` in ``locale``, its placeholders filled from ``values``.

    An unknown key or a missing value raises — a mail with ``{club}`` in it is worse than
    an error, and the test suite exercises every message.
    """
    return catalog(locale)[key].format_map(values)
