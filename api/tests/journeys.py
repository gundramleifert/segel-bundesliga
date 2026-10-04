"""Steps of a journey test (``docs/userstories/journeys.md``).

A journey is one long test through several stories. ``step()`` names the story the code
below it walks through — so a failure's captured output says *which step* broke, and
``scripts/check-docs.py`` can check the test walks the journey's main steps in the
documented order. Deliberately a plain call, not a context manager: a journey test is
long, and re-indenting all of it to mark ten boundaries would bury its history.
"""


def step(story: str, what: str) -> None:
    """Marks the start of the journey step for ``story`` (e.g. ``"VA-7"``)."""
    print(f"── step {story}: {what}")
