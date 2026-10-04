"""Steps of a journey test (``docs/userstories/journeys.md``).

A journey is one long test through several stories. ``step()`` names the story the code
below it walks through — so a failure's captured output says *which step* broke, an
Allure report (``--alluredir``) shows each step as one, and ``scripts/check-docs.py`` can
check the test walks the journey's main steps in the documented order.

Deliberately a plain call, not a context manager: a journey test is long, and
re-indenting all of it to mark ten boundaries would bury its history. So a step runs until
the next one starts; the last is closed by the hook in ``tests/conftest.py``, with the
test's failure if there was one.
"""

from __future__ import annotations

from typing import Any

import allure

_open: Any = None


def step(story: str, what: str) -> None:
    """Marks the start of the journey step for ``story`` (e.g. ``"VA-7"``)."""
    global _open
    close(None)
    print(f"── step {story}: {what}")
    _open = allure.step(f"{story}: {what}")
    _open.__enter__()


def close(excinfo: tuple[Any, Any, Any] | None) -> None:
    """Ends the open step, as failed when ``excinfo`` carries the test's exception."""
    global _open
    if _open is not None:
        step_, _open = _open, None
        step_.__exit__(*(excinfo or (None, None, None)))
