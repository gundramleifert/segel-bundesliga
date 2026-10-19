"""Private uploads: a waiver scan (S-1), a receipt on a claim (F-5), a personal document
(S-5). One set of rules for all three, because they are the same kind of file — a paper
someone scanned, with a person's data on it:

* **PDF, JPEG or PNG, told by content.** The type is sniffed from the bytes (libmagic) and
  never taken from the file's name or the type the browser declares for it; an image must
  then decode in Pillow as that format.
* **At most 10 MB.** Stored as uploaded, never re-encoded — a receipt must stay legible.
* **A random name** under one directory per kind, which only the row knows; the uploaded
  name is shown, never used as a path. There is no static route to any of them: each kind
  has one serving endpoint that checks who asks.
"""

from __future__ import annotations

import asyncio
import io
import uuid
from pathlib import Path

from app.config import settings
from app.problems import Problem

MEDIA_TYPES = {
    "application/pdf": "pdf",
    "image/jpeg": "jpg",
    "image/png": "png",
}
#: A picture to show (a post's, Story R-1) rather than a paper to keep: no PDF, and WebP
#: too — it is re-encoded as a JPEG before it is stored, so only the check needs to know it.
IMAGE_TYPES = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
_NAMES = {
    "application/pdf": "a PDF",
    "image/jpeg": "a JPEG",
    "image/png": "a PNG",
    "image/webp": "a WebP",
}
MAX_BYTES = 10 * 1024 * 1024
#: Enough of the start of a file for libmagic to tell every type accepted here.
_SNIFF_BYTES = 8192


def sniffed(raw: bytes) -> str:
    """The MIME type the bytes are, by their content alone (libmagic, the library behind
    `file`). Never the file's name, and never the type a browser declares — which it takes
    from the name (`docs/gotchas`): a JPEG saved as `chart.png` is a JPEG."""
    import magic

    return magic.from_buffer(raw[:_SNIFF_BYTES], mime=True)


async def validated(
    raw: bytes,
    *,
    code: str,
    what: str,
    accept: dict[str, str] = MEDIA_TYPES,
    max_bytes: int = MAX_BYTES,
) -> str:
    """The media type the bytes are — or a typed refusal.

    The type is **sniffed from the content** (:func:`sniffed`), and the declared type is
    not asked at all: it comes from the file's name, and a name is not evidence. A picture
    must then also decode in Pillow as that format, so a file with the right first bytes
    and nothing behind them is refused too.

    ``code`` prefixes the problem codes (``<code>-invalid-type``, ``<code>-too-large``,
    ``<code>-invalid``), so each kind keeps the codes its frontend already maps; ``what``
    names the file in the English title ("The signed form"); ``accept`` narrows the types
    (:data:`IMAGE_TYPES` for a picture); ``max_bytes`` raises the limit for a phone's photo,
    which is re-encoded anyway.

    Async because sniffing and Pillow's decode are CPU work: they run in a thread, so a
    large scan does not stall every other request while it is checked.
    """
    if not raw:
        raise Problem(422, f"{code}-invalid", "The upload is empty.")
    if len(raw) > max_bytes:
        raise Problem(
            422,
            f"{code}-too-large",
            f"{what} is too large.",
            detail=f"At most {max_bytes // (1024 * 1024)} MB.",
        )
    found = await asyncio.to_thread(sniffed, raw)
    if found not in accept:
        names = [_NAMES[media_type] for media_type in accept]
        raise Problem(
            422,
            f"{code}-invalid-type",
            f"{what} must be {', '.join(names[:-1])} or {names[-1]}.",
            detail=f"The file is {found}.",
        )
    if found == "application/pdf":
        return found
    try:
        decoded = await asyncio.to_thread(_image_format, raw)
    except ValueError as error:
        raise Problem(422, f"{code}-invalid", "This file is not a readable image.") from error
    if {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}.get(decoded or "") != found:
        raise Problem(422, f"{code}-invalid", "This file is not a readable image.")
    return found


def _image_format(raw: bytes) -> str | None:
    """Pillow's name for the format the bytes decode as; ``ValueError`` if they do not."""
    from PIL import Image, UnidentifiedImageError

    try:
        with Image.open(io.BytesIO(raw)) as image:
            image.verify()
            return image.format
    except (UnidentifiedImageError, OSError, SyntaxError) as error:
        raise ValueError(str(error)) from error


def _directory(kind: str) -> Path:
    directory = Path(settings.uploads_dir) / kind
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def store(kind: str, raw: bytes, media_type: str) -> str:
    """Writes validated bytes under a random name in ``uploads/<kind>/`` and returns the
    name — the only handle to the file, kept on the row."""
    name = f"{uuid.uuid4().hex}.{MEDIA_TYPES[media_type]}"
    (_directory(kind) / name).write_bytes(raw)
    return name


def path(kind: str, name: str | None) -> Path | None:
    """The stored file, or ``None`` when the name is absent, malformed or its file gone —
    so a row whose file was cleaned up reads as "no file" instead of a 500."""
    if not name or "/" in name or "\\" in name or name.startswith("."):
        return None
    found = _directory(kind) / name
    return found if found.is_file() else None


def discard(kind: str, name: str | None) -> None:
    found = path(kind, name)
    if found is not None:
        found.unlink(missing_ok=True)
