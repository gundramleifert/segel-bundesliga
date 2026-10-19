"""Formatted text from the site's editor — Story R-1.

Editorial writes in a rich-text editor and the browser sends HTML. The public site renders
that HTML as it is, so it is cleaned **here, on every write**, to the few elements the
editor's toolbar can make: whatever else arrives — a pasted ``<script>``, an ``onclick``,
a ``javascript:`` link, the styles of a word processor — is dropped before it is stored.
Cleaning on write rather than on read keeps the stored text the text that is shown.
"""

from __future__ import annotations

import nh3

#: What the toolbar makes (`web/src/components/RichTextEditor.tsx`): paragraphs, two levels
#: of heading, bold, italic, underline, strike, lists, a quote, a rule, a line break, a link,
#: a picture and a table. A table's column widths (`colgroup`) are kept, their styles not.
TAGS = {
    *("p", "br", "hr", "h2", "h3", "strong", "em", "u", "s", "ul", "ol", "li", "blockquote"),
    *("a", "img"),
    *("table", "colgroup", "col", "thead", "tbody", "tr", "th", "td"),
}
ATTRIBUTES = {
    "a": {"href"},
    "img": {"src", "alt"},
    "th": {"colspan", "rowspan"},
    "td": {"colspan", "rowspan"},
}
URL_SCHEMES = {"http", "https", "mailto"}


def clean_html(value: str) -> str:
    """The HTML reduced to :data:`TAGS`; an editor's empty paragraph is no text at all."""
    cleaned = nh3.clean(
        value,
        tags=TAGS,
        attributes=ATTRIBUTES,
        url_schemes=URL_SCHEMES,
        link_rel="noopener noreferrer",
    ).strip()
    return "" if cleaned in {"", "<p></p>"} else cleaned
