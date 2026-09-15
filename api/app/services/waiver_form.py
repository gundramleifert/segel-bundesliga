"""The printable liability-waiver form — Story S-1.

A minor's guardian signs on paper, so the site has to hand out the paper: the wording in
force, the sailor's name and date of birth, the competition it is for, and lines for the
signature. Built from the **versioned** `WaiverText`, so what is signed always matches the
version the upload will be recorded against — a form printed from a stale PDF on someone's
desk is exactly the mismatch the versioning exists to prevent.

reportlab, with the built-in Helvetica: it covers German (WinAnsi has ä, ö, ü, ß) with no
font file to ship, and the page is text and rules only. The content stream is left
uncompressed so the story test can see the sailor's name in the bytes.
"""

from __future__ import annotations

import io
from datetime import date

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import simpleSplit
from reportlab.pdfgen import canvas

from app.models import Sailor, WaiverText

_PAGE_W, _PAGE_H = A4
_MARGIN = 20 * mm
_WIDTH = _PAGE_W - 2 * _MARGIN
_BODY = ("Helvetica", 10.5)
_BOLD = ("Helvetica-Bold", 10.5)
_TITLE = ("Helvetica-Bold", 15)
_SMALL = ("Helvetica", 8.5)
_LEADING = 14

# The wording around the signature. Two languages, like the text itself; the form is
# printed in the language the guardian reads, not the sailor's interface language.
_LABELS = {
    "en": dict(
        for_="For",
        sailor="Sailor",
        born="Date of birth",
        version="Version {version}, in force since {published}",
        guardian_heading="Declaration of the parent or legal guardian",
        guardian_text=(
            "I am a parent or legal guardian of the sailor named above. I have read the "
            "statement and agree to it on their behalf; I consent to their taking part in "
            "the competition named above on these terms."
        ),
        adult_heading="Declaration of the sailor",
        adult_text="I have read the statement above and agree to it.",
        name="Name in block letters",
        place_date="Place, date",
        signature="Signature",
        upload=(
            "Hand the signed form to your club, or photograph or scan it and upload it on "
            "your account page of the site under “Liability waiver”."
        ),
    ),
    "de": dict(
        for_="Für",
        sailor="Seglerin / Segler",
        born="Geburtsdatum",
        version="Fassung {version}, gültig seit {published}",
        guardian_heading="Erklärung der Erziehungsberechtigten",
        guardian_text=(
            "Ich bin erziehungsberechtigt für die oben genannte Seglerin / den oben "
            "genannten Segler. Ich habe die Erklärung gelesen und stimme ihr in ihrem / "
            "seinem Namen zu; ich bin mit der Teilnahme an der oben genannten Veranstaltung "
            "zu diesen Bedingungen einverstanden."
        ),
        adult_heading="Erklärung der Seglerin / des Seglers",
        adult_text="Ich habe die obige Erklärung gelesen und stimme ihr zu.",
        name="Name in Druckbuchstaben",
        place_date="Ort, Datum",
        signature="Unterschrift",
        upload=(
            "Geben Sie das unterschriebene Formular beim Verein ab, oder fotografieren "
            "bzw. scannen Sie es und laden Sie es auf der Kontoseite der Website unter "
            "„Haftungsausschluss“ hoch."
        ),
    ),
}


def _date(value: date | None, locale: str) -> str:
    if value is None:
        return "____________"
    return value.strftime("%d.%m.%Y" if locale == "de" else "%Y-%m-%d")


class _Page:
    """A cursor down the page that starts a new one when the text runs out of room."""

    def __init__(self, pdf: canvas.Canvas) -> None:
        self.pdf = pdf
        self.y = _PAGE_H - _MARGIN

    def need(self, height: float) -> None:
        if self.y - height < _MARGIN:
            self.pdf.showPage()
            self.y = _PAGE_H - _MARGIN

    def text(self, value: str, font=_BODY, *, leading: float = _LEADING) -> None:
        name, size = font
        for line in simpleSplit(value, name, size, _WIDTH):
            self.need(leading)
            self.pdf.setFont(name, size)
            self.pdf.drawString(_MARGIN, self.y - size, line)
            self.y -= leading

    def gap(self, height: float) -> None:
        self.y -= height

    def rule(self, label: str) -> None:
        self.need(12 * mm)
        self.y -= 9 * mm
        self.pdf.line(_MARGIN, self.y, _PAGE_W - _MARGIN, self.y)
        self.pdf.setFont(*_SMALL)
        self.pdf.drawString(_MARGIN, self.y - 10, label)
        self.y -= 14


def render_waiver_form(
    *,
    text: WaiverText,
    sailor: Sailor,
    competition: str,
    locale: str,
    minor: bool,
) -> bytes:
    """The PDF, as bytes. ``minor`` picks the guardian's or the sailor's own declaration."""
    lang = "de" if locale == "de" else "en"
    labels = _LABELS[lang]
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4, pageCompression=0)
    pdf.setTitle(text.title(lang))
    page = _Page(pdf)

    page.text(text.title(lang), _TITLE, leading=20)
    page.text(
        labels["version"].format(
            version=text.version, published=_date(text.published_at.date(), lang)
        ),
        _SMALL,
        leading=12,
    )
    page.gap(6 * mm)

    page.text(f"{labels['for_']}: {competition}", _BOLD)
    page.text(f"{labels['sailor']}: {sailor.first_name} {sailor.last_name}", _BOLD)
    page.text(f"{labels['born']}: {_date(sailor.birth_date, lang)}", _BOLD)
    page.gap(6 * mm)

    for paragraph in text.body(lang).split("\n"):
        if paragraph.strip():
            page.text(paragraph.strip())
            page.gap(4)
    page.gap(8 * mm)

    page.text(labels["guardian_heading" if minor else "adult_heading"], _BOLD)
    page.gap(2)
    page.text(labels["guardian_text" if minor else "adult_text"])
    page.rule(labels["name"])
    page.rule(labels["place_date"])
    page.rule(labels["signature"])
    page.gap(6 * mm)
    page.text(labels["upload"], _SMALL, leading=11)

    pdf.showPage()
    pdf.save()
    return buffer.getvalue()
