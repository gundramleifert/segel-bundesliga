"""Storage for uploaded club crests ("Stander", the club burgee) — Story V-3.

Storage follows the sailor-photo pattern (`app/routers/sailors.py::_save_photo`): a
deterministic path under `settings.uploads_dir`, so **the file's existence is the state**
— no `has_crest` column, nothing to keep in sync, and a lost uploads directory degrades
to "no crest" instead of to a broken link.

**Processing differs from a sailor photo on purpose** — see `save_crest`. A crest is a
logo with an alpha channel, not a photograph.

Lives as its own module rather than inside a router because two layers need it: the
router that writes the file, and `app.schemas.public.ClubOut`, which resolves
`logo_url` against it on every read.
"""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageOps

from app.config import settings
from app.problems import Problem

# Cap applied before any decoding — the whole raw upload is read into memory once. Lower
# than the sailor photo's 5 MB: a crest is a piece of vector-ish artwork exported small,
# not a 12-megapixel phone capture.
MAX_UPLOAD_BYTES = 2 * 1024 * 1024

# Longest edge of the stored image. Unlike a sailor photo there is no fixed square: a
# burgee is a pennant, a shield or a wordmark, and forcing one aspect ratio would cut the
# artwork. Aspect ratio is preserved, only the size is bounded.
MAX_EDGE = 512

# One extension for every upload, whatever came in. Keeps "does a crest exist?" a single
# `Path.exists()` instead of a directory scan across candidate suffixes.
_SUFFIX = ".png"


def crest_path(club_id: int) -> Path:
    """Where this club's crest lives. Pure path arithmetic — no directory is created,
    because this runs on every club that gets serialized (see `ClubOut`); only the
    upload path needs the directory to exist."""
    return Path(settings.uploads_dir) / "clubs" / f"{club_id}{_SUFFIX}"


def crest_url(club_id: int) -> str | None:
    """The public URL of the uploaded crest — or ``None`` if this club has none.

    The `?v=` stamp is the file's modification time: the path itself is stable across
    replacements, so without it a browser (or CDN) would keep showing the old crest after
    an upload. It is a cache key, never an identifier — clients must treat the whole
    string as opaque, and the serving endpoint ignores the parameter.
    """
    path = crest_path(club_id)
    if not path.exists():
        return None
    return f"/api/clubs/{club_id}/logo?v={int(path.stat().st_mtime)}"


def delete_crest(club_id: int) -> None:
    """Removing a crest that isn't there is a no-op, not an error."""
    crest_path(club_id).unlink(missing_ok=True)


def save_crest(club_id: int, raw: bytes, *, content_type: str | None) -> None:
    """Validates, downscales and stores an uploaded crest — Story V-3.

    **Deliberately not `_save_photo`.** Do not "fix" this into consistency with the sailor
    photo path: that one converts to RGB and re-encodes as JPEG, which is right for a
    photograph and wrong here. A crest is drawn *over* colored surfaces — the home-page
    hero and the event cards sit on brand blue — so flattening its alpha channel onto a
    solid background produces a visible white (or black) box around the emblem. Hence:

    * **Alpha survives.** An image that arrives with transparency (PNG, transparent WebP,
      palette images with a transparency index) is stored as RGBA PNG; only a genuinely
      opaque source is stored as RGB PNG. PNG for everything, because it is the one
      lossless format that carries alpha and every browser reads.
    * **No center-crop to a square.** Only the longest edge is bounded, the aspect ratio
      is preserved; a pennant cropped square is a mutilated pennant.

    What is kept from the sailor path: cheap checks first (declared content type, then
    size, both before Pillow decodes anything), Pillow itself as the final arbiter of
    "is this really an image", EXIF-upright orientation, and a bounded stored size.
    """
    if content_type is not None and not content_type.startswith("image/"):
        raise Problem(
            422,
            "club-crest-invalid-type",
            "The upload must be an image.",
            detail=f"Got content type '{content_type}'.",
        )
    if not raw:
        raise Problem(422, "club-crest-invalid", "The upload is empty.")
    if len(raw) > MAX_UPLOAD_BYTES:
        raise Problem(
            413,
            "club-crest-too-large",
            f"The crest must be at most {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.",
        )

    try:
        image = Image.open(io.BytesIO(raw))
        image.load()
    except Exception as exc:
        raise Problem(
            422, "club-crest-invalid", "This file is not a readable image."
        ) from exc

    image = ImageOps.exif_transpose(image) or image
    image = image.convert("RGBA" if _has_alpha(image) else "RGB")
    # `thumbnail`, not `resize`/`contain`: it shrinks to fit the box and leaves anything
    # already smaller alone, so a crest exported at 180 px is stored at 180 px instead of
    # being blown up into a blurry 512.
    image.thumbnail((MAX_EDGE, MAX_EDGE), Image.LANCZOS)

    path = crest_path(club_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="PNG", optimize=True)


def _has_alpha(image: Image.Image) -> bool:
    """Whether this image carries transparency in any of the ways Pillow expresses it.

    `mode` alone is not enough: a palette PNG ("P") keeps its transparent color in
    `info["transparency"]`, and converting it to RGB would silently drop that.
    """
    return image.mode in ("RGBA", "LA", "PA") or "transparency" in image.info
