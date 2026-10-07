"""Private uploads: a waiver scan (S-1), a receipt on a claim (F-5), a personal document
(S-5). One set of rules for all three, because they are the same kind of file — a paper
someone scanned, with a person's data on it:

* **PDF, JPEG or PNG, checked by content.** The declared type is checked first (cheap),
  then the bytes: a PDF starts with its magic, an image must decode in Pillow and be the
  format it claims. A file that lies about its type is refused, not renamed.
* **At most 10 MB.** Stored as uploaded, never re-encoded — a receipt must stay legible.
* **A random name** under one directory per kind, which only the row knows; the uploaded
  name is shown, never used as a path. There is no static route to any of them: each kind
  has one serving endpoint that checks who asks.
"""

from __future__ import annotations

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
MAX_BYTES = 10 * 1024 * 1024


def validated(raw: bytes, content_type: str | None, *, code: str, what: str) -> str:
    """The media type the bytes really are — or a typed refusal.

    ``code`` prefixes the problem codes (``<code>-invalid-type``, ``<code>-too-large``,
    ``<code>-invalid``), so each kind keeps the codes its frontend already maps; ``what``
    names the file in the English title ("The signed form").
    """
    if content_type not in MEDIA_TYPES:
        raise Problem(
            422,
            f"{code}-invalid-type",
            f"{what} must be a PDF, a JPEG or a PNG.",
            detail=f"Got content type '{content_type}'.",
        )
    if not raw:
        raise Problem(422, f"{code}-invalid", "The upload is empty.")
    if len(raw) > MAX_BYTES:
        raise Problem(
            422,
            f"{code}-too-large",
            f"{what} is too large.",
            detail=f"At most {MAX_BYTES // (1024 * 1024)} MB.",
        )
    if content_type == "application/pdf":
        if not raw.startswith(b"%PDF"):
            raise Problem(422, f"{code}-invalid", "This file is not a readable PDF.")
        return content_type
    from PIL import Image, UnidentifiedImageError

    try:
        with Image.open(io.BytesIO(raw)) as image:
            image.verify()
            detected = image.format
    except (UnidentifiedImageError, OSError, SyntaxError) as error:
        raise Problem(422, f"{code}-invalid", "This file is not a readable image.") from error
    real = {"PNG": "image/png", "JPEG": "image/jpeg"}.get(detected or "")
    if real != content_type:
        raise Problem(
            422,
            f"{code}-invalid",
            "This file is not the kind of image it claims to be.",
            detail=f"Declared {content_type}, found {detected or 'nothing readable'}.",
        )
    return content_type


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
