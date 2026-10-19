"""Pictures to show: a sailor's photo (S-2), a club's crest (V-3), a post's picture (R-1).

Each one is decoded, turned upright and re-encoded — never stored as uploaded, so a
phone's EXIF (its location included) never reaches the public site, and a file that only
claims to be an image is refused by Pillow itself. What differs is the shape and the
format, and that stays with each caller:

* a **photo** is cropped to a square and stored as a JPEG (`square`, `jpeg`);
* a **crest** keeps its transparency and its aspect ratio, as a PNG (`bounded`, `png`) —
  it is drawn over coloured surfaces, and a flattened alpha channel is a white box;
* a **post's picture** keeps its aspect ratio, as a JPEG (`bounded`, `jpeg`).

Private papers — a waiver scan, a receipt — are not pictures: they are stored as
uploaded, see `app/services/uploads.py`.
"""

from __future__ import annotations

import io
from datetime import date

from PIL import ExifTags, Image, ImageOps

from app.problems import Problem

JPEG_QUALITY = 85


def check(raw: bytes, content_type: str | None, *, code: str, what: str, max_bytes: int) -> None:
    """The cheap checks, before Pillow decodes anything: the declared type, then the size.

    ``code`` prefixes the problem codes (``<code>-invalid-type``, ``<code>-invalid``,
    ``<code>-too-large``), so each kind keeps the codes its frontend maps; ``what`` names
    the file in the English title ("The photo")."""
    if content_type is not None and not content_type.startswith("image/"):
        raise Problem(
            422,
            f"{code}-invalid-type",
            "The upload must be an image.",
            detail=f"Got content type '{content_type}'.",
        )
    if not raw:
        raise Problem(422, f"{code}-invalid", "The upload is empty.")
    if len(raw) > max_bytes:
        raise Problem(
            413,
            f"{code}-too-large",
            f"{what} must be at most {max_bytes // (1024 * 1024)} MB.",
        )


def upright(raw: bytes, *, code: str, edge: int | None = None, alpha: bool = False) -> Image.Image:
    """The decoded picture, rotated as the camera meant it — phones store orientation as
    metadata, not pixels, and skipping this shows a sideways photo — as RGB, or as RGBA
    when ``alpha`` is asked for and the picture has transparency. Not a picture:
    ``<code>-invalid``.

    Converted here, before any scaling: Pillow scales a palette image with nearest
    neighbour only, which leaves a crest's edges jagged.

    ``edge``: the size it will be cut down to. A large JPEG is then decoded at a fraction
    of its size straight away — a phone's 48 MP photo need never exist in memory at full
    size to end up 2000 px wide."""
    try:
        image = Image.open(io.BytesIO(raw))
        if edge is not None:
            image.draft("RGB", (edge, edge))
        image.load()
    except Exception as exc:
        raise Problem(422, f"{code}-invalid", "This file is not a readable image.") from exc
    image = ImageOps.exif_transpose(image) or image
    return image.convert("RGBA" if alpha and _has_alpha(image) else "RGB")


def _has_alpha(image: Image.Image) -> bool:
    """Transparency in any of the ways Pillow expresses it — `mode` alone is not enough:
    a palette PNG keeps its transparent colour in `info["transparency"]`, and converting
    it to RGB would silently drop that."""
    return image.mode in ("RGBA", "LA", "PA") or "transparency" in image.info


def bounded(image: Image.Image, edge: int) -> Image.Image:
    """At most ``edge`` on its longer side, the aspect ratio kept. `thumbnail`, not
    `resize`: anything already smaller is left alone rather than blown up blurry."""
    image.thumbnail((edge, edge), Image.LANCZOS)
    return image


def square(image: Image.Image, size: int) -> Image.Image:
    """Cropped to its centre square, then scaled to ``size`` — every camera's aspect ratio
    ends up the same shape."""
    width, height = image.size
    side = min(width, height)
    left, top = (width - side) // 2, (height - side) // 2
    return image.crop((left, top, left + side, top + side)).resize((size, size), Image.LANCZOS)


def jpeg(image: Image.Image) -> bytes:
    """A JPEG without metadata — for a photograph, where transparency means nothing."""
    out = io.BytesIO()
    image.convert("RGB").save(out, format="JPEG", quality=JPEG_QUALITY)
    return out.getvalue()


def png(image: Image.Image) -> bytes:
    """A PNG without metadata, its transparency kept — the one lossless format that
    carries alpha and every browser reads."""
    out = io.BytesIO()
    image.save(out, format="PNG", optimize=True)
    return out.getvalue()


def taken_on(raw: bytes) -> date | None:
    """The day the camera says it took the picture — read before the re-encoding drops
    EXIF, and the only thing kept of it (never the location). ``None`` when it does not
    say, or says nonsense."""
    try:
        exif = Image.open(io.BytesIO(raw)).getexif()
        stamp = exif.get_ifd(ExifTags.IFD.Exif).get(ExifTags.Base.DateTimeOriginal) or exif.get(
            ExifTags.Base.DateTime
        )
        year, month, day = (int(part) for part in str(stamp)[:10].split(":"))
        return date(year, month, day)
    except Exception:
        return None
