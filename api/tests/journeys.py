"""Steps of a journey test (``docs/journeys/``).

A journey is one long test through several stories. ``step()`` names the journey step
(``"J-5.4"``) the code below it walks through. The step's story comes from
``docs/stories.json``, where ``scripts/check-docs.py --fix`` puts every step of every
journey's table — so a failure's captured output says *which step* broke, an Allure report
(``--alluredir``) shows each step as one, titled ``J-5.4 · V-2: …``, labels the test with
that story too, and ``scripts/check-docs.py`` can check the test walks the journey's steps
in the table's order.

Deliberately a plain call, not a context manager: a journey test is long, and
re-indenting all of it to mark ten boundaries would bury its history. So a step runs until
the next one starts; the last is closed by the hook in ``tests/conftest.py``, with the
test's failure if there was one.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import allure

_STORIES: dict[str, dict[str, str]] = json.loads(
    (Path(__file__).parents[2] / "docs" / "stories.json").read_text("utf-8")
)
_REPOSITORY = "https://github.com/gundramleifert/segel-bundesliga/blob/main"
_open: Any = None


def step(step_id: str, what: str) -> None:
    """Marks the start of journey step ``step_id`` (e.g. ``"J-5.4"``)."""
    global _open
    if not re.fullmatch(r"J-\d+\.\d+", step_id):
        raise ValueError(f'step: "{step_id}" is not a journey step, e.g. "J-5.4"')
    close(None)
    # A step added to the table but not yet in stories.json (no --fix since) still runs;
    # check-docs.py is what refuses a step that is in no journey.
    story = _STORIES.get(step_id, {}).get("story")
    title = f"{step_id} · {story}: {what}" if story else f"{step_id}: {what}"
    print(f"── step {title}")
    if story in _STORIES:
        entry = _STORIES[story]
        allure.dynamic.story(f"{story} · {entry['title']}")
        allure.dynamic.tag(story)
        allure.dynamic.link(f"{_REPOSITORY}/{entry['file']}#{entry['anchor']}", name=story)
    _open = allure.step(title)
    _open.__enter__()


def close(excinfo: tuple[Any, Any, Any] | None) -> None:
    """Ends the open step, as failed when ``excinfo`` carries the test's exception."""
    global _open
    if _open is not None:
        step_, _open = _open, None
        step_.__exit__(*(excinfo or (None, None, None)))
