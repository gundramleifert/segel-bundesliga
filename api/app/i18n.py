"""Minimal internationalisation for API responses.

Every user-facing string — error details, and field descriptions that surface in the
generated OpenAPI docs — exists in English and German side by side, English first. There
is no separate catalog file: the two strings live together at the call site, so a
translator (or a future third language) always sees them in context.

Locale is resolved once per request from the `Accept-Language` header via the
`Locale`/`resolve_locale` dependency and threaded through explicitly. Nothing here is
implicit or global — a request without the dependency simply gets English, which is the
correct default for a public API.
"""

from __future__ import annotations

from typing import Literal

from fastapi import Header

Locale = Literal["en", "de"]

DEFAULT_LOCALE: Locale = "en"


def resolve_locale(accept_language: str | None = Header(default=None)) -> Locale:
    """Picks German only if it's explicitly preferred; English is the default.

    A bare `Accept-Language: de` or `de-DE,de;q=0.9,en;q=0.8` selects German. Anything
    else — missing header, `en`, `*`, an unrelated language — falls back to English.
    """
    if not accept_language:
        return DEFAULT_LOCALE
    primary = accept_language.split(",")[0].strip().lower()
    return "de" if primary.startswith("de") else DEFAULT_LOCALE


def tr(locale: Locale, en: str, de: str) -> str:
    """Returns the string for the given locale. English is the source of truth."""
    return de if locale == "de" else en
