"""Formatted text from the site's editor — Story R-1.

Editorial writes in a rich-text editor and the browser sends HTML. The public site renders
that HTML as it is, so it is cleaned **here, on every write**, to the few elements the
editor's toolbar can make: whatever else arrives — a pasted ``<script>``, an ``onclick``,
a ``javascript:`` link, the styles of a word processor — is dropped before it is stored.
Cleaning on write rather than on read keeps the stored text the text that is shown.
"""

from __future__ import annotations

import re

import nh3

#: What the toolbar makes (`web/src/components/RichTextEditor.tsx`): paragraphs, **one**
#: kind of heading, bold, italic, underline, strike, lists, a quote, a rule, a line break, a
#: link, a picture and a table. A table's column widths (`colgroup`) are kept, their styles
#: not. The heading is `h2`: the page's `h1` is the post's title, set in the form and never
#: in the text (Story R-1) — every other level is made this one, see `_HEADING`.
TAGS = {
    *("p", "br", "hr", "h2", "strong", "em", "u", "s", "ul", "ol", "li", "blockquote"),
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


#: A heading of any level, opening or closing — made the text's one heading before
#: cleaning, so a title pasted from Word (`h1`) or a subheading (`h3`) keeps its words as a
#: heading instead of running into the next paragraph once the cleaner drops its tag.
_HEADING = re.compile(r"<(/?)h[1-6]\b[^>]*>", re.I)


def clean_html(value: str) -> str:
    """The HTML reduced to :data:`TAGS`; an editor's empty paragraph is no text at all."""
    cleaned = nh3.clean(
        _HEADING.sub(r"<\1h2>", value),
        tags=TAGS,
        attributes=ATTRIBUTES,
        url_schemes=URL_SCHEMES,
        link_rel="noopener noreferrer",
    ).strip()
    return "" if cleaned in {"", "<p></p>"} else cleaned


_FIRST_BLOCK = re.compile(r"^\s*<(h2|p)>(.*?)</\1>\s*", re.S)


def _words(html: str) -> str:
    return " ".join(re.sub(r"<[^>]+>", " ", html).split()).casefold()


def repeats_title(body: str, title: str) -> bool:
    """Whether the text starts with the title again (Story R-1). The title is a field of
    its own, set above the text, so a first line that says it and nothing else would show
    it twice — and it is refused, never cut away: the writer decides what goes instead.
    The same words further down are text."""
    first = _FIRST_BLOCK.match(body)
    return first is not None and _words(first.group(2)) == _words(title)
