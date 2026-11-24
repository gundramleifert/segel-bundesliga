"""Defects the concept review found in behaviour, each held by the test it must pass.

Every test here states what the site **should** do and is marked
``xfail(strict=True)`` with its item in ``docs/REVIEW_2026-11.md``: it shows in every run
as a known defect, and the day the fix lands it passes — which ``strict`` turns into a
failure until the marker is deleted. So a fix cannot go unnoticed, and the marker cannot
outlive it. A test that changes shared data puts it back.
"""

# None open (2026-11-24): 2.2, 2.4 and 5.5 were fixed and their tests moved to their stories.
