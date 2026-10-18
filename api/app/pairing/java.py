"""What both calls into the Java tool share: finding it, and quoting its output.

The draw (``generator.py``) and the printed list (``pdf.py``) run the same JAR from
``reference/PairingList`` through different entry points; whether it can run at all is
the same question for both.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from app.config import settings


def require_jar(jar: Path | None, error: type[Exception], needed_for: str) -> Path:
    """The JAR to run, or ``error`` saying why there is none.

    ``needed_for`` starts the sentence about Java — "The pairing generator",
    "Printing a pairing list" — so each caller's message names what is missing for it.
    """
    jar_path = Path(jar) if jar else Path(settings.pairing_jar)
    if not jar_path.is_file():
        raise error(
            f"The pairing JAR is missing at {jar_path}. "
            "Build with: mvn -DskipTests package in the reference/PairingList directory"
        )
    if shutil.which(settings.java_binary) is None:
        raise error(
            f"Java was not found ('{settings.java_binary}'). "
            f"{needed_for} needs a Java runtime version 17 or later."
        )
    return jar_path


def tail(log: str, lines: int = 15) -> str:
    """The last lines of the tool's output — where its error is, without the progress."""
    return "\n".join(log.strip().splitlines()[-lines:])
