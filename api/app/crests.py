"""Storage for uploaded club crests ("Stander", the club burgee) — Story V-3.

Storage follows the person-photo pattern (`app/routers/people.py::_save_photo`): a
deterministic key in the upload store (`app/storage.py`), so **the file's existence is the state**
— no `has_crest` column, nothing to keep in sync, and a lost uploads directory degrades
to "no crest" instead of to a broken link.

**Processing differs from a sailor photo on purpose** — see `save_crest`. A crest is a
logo with an alpha channel, not a photograph.

Lives as its own module rather than inside a router because two layers need it: the
router that writes the file, and `app.schemas.public.ClubOut`, which resolves
`logo_url` against it on every read.
"""

from __future__ import annotations

from app.services import pictures
from app.storage import storage

# Cap applied before any decoding — the whole raw upload is read into memory once. Lower
# than the sailor photo's 5 MB: a crest is a piece of vector-ish artwork exported small,
# not a 12-megapixel phone capture.
MAX_UPLOAD_BYTES = 2 * 1024 * 1024

# Longest edge of the stored image. Unlike a sailor photo there is no fixed square: a
# burgee is a pennant, a shield or a wordmark, and forcing one aspect ratio would cut the
# artwork. Aspect ratio is preserved, only the size is bounded.
MAX_EDGE = 512

# One extension for every upload, whatever came in. Keeps "does a crest exist?" a single
# look-up instead of a scan across candidate suffixes.
_SUFFIX = ".png"


def crest_key(club_id: int) -> str:
    """Where this club's crest lives in the upload store."""
    return f"clubs/{club_id}{_SUFFIX}"


def crest_url(club_id: int) -> str | None:
    """The public URL of the uploaded crest — or ``None`` if this club has none.

    The `?v=` stamp is when the file was written: the path itself is stable across
    replacements, so without it a browser (or CDN) would keep showing the old crest after
    an upload. It is a cache key, never an identifier — clients must treat the whole
    string as opaque, and the serving endpoint ignores the parameter.
    """
    stamp = storage().stamp(crest_key(club_id))
    if stamp is None:
        return None
    return f"/api/clubs/{club_id}/logo?v={stamp}"


def delete_crest(club_id: int) -> None:
    """Removing a crest that isn't there is a no-op, not an error."""
    storage().delete(crest_key(club_id))


def save_crest(club_id: int, raw: bytes) -> None:
    """Validates, downscales and stores an uploaded crest — Story V-3.

    **Deliberately not a sailor photo's JPEG square** (`app/services/pictures.py`). Do not
    "fix" this into consistency with it: converting to RGB and re-encoding as JPEG is
    right for a photograph and wrong here. A crest is drawn *over* colored surfaces — the home-page
    hero and the event cards sit on brand blue — so flattening its alpha channel onto a
    solid background produces a visible white (or black) box around the emblem. Hence:

    * **Alpha survives.** An image that arrives with transparency (PNG, transparent WebP,
      palette images with a transparency index) is stored as RGBA PNG; only a genuinely
      opaque source is stored as RGB PNG. PNG for everything, because it is the one
      lossless format that carries alpha and every browser reads.
    * **No center-crop to a square.** Only the longest edge is bounded, the aspect ratio
      is preserved, and a crest exported at 180 px stays 180 px; a pennant cropped square
      is a mutilated pennant.

    Shared with every picture (`pictures.check`, `pictures.upright`): cheap checks first,
    Pillow as the final arbiter of "is this really an image", and upright orientation.
    """
    pictures.check(raw, code="club-crest", what="The crest", max_bytes=MAX_UPLOAD_BYTES)
    image = pictures.bounded(pictures.upright(raw, code="club-crest", alpha=True), MAX_EDGE)
    storage().put(crest_key(club_id), pictures.png(image))
