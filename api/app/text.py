"""Text utilities used in multiple places."""

from __future__ import annotations

import re

_UMLAUTE = str.maketrans(
    {"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss", "Ä": "ae", "Ö": "oe", "Ü": "ue"}
)


def slugify(value: str) -> str:
    """Create a URL-safe short form.

    Umlauts are spelled out instead of removed: from ``BYCÜ`` becomes ``bycue`` not
    ``byc`` — otherwise clubs differing only in umlauts would collide.
    """
    text = value.strip().lower().translate(_UMLAUTE)
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-") or "eintrag"
