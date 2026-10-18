"""Stories S-1, VA-5: which confirmations count for a competition, and what judging reads.

``Competition.covers`` is the Python twin of the SQL filter ``sailor_waivers`` loads all of
a sailor's confirmations with in one query; the two must agree, or a status would differ
between the account page and the check-in list.
"""

from datetime import date

from app.models import Event, Series, WaiverConfirmation
from app.services.waivers import SCAN_REF_PREFIX, Competition, has_scan


def _row(*, series_id: int | None = None, event_id: int | None = None) -> WaiverConfirmation:
    return WaiverConfirmation(sailor_id=1, series_id=series_id, event_id=event_id)


def test_a_series_counts_only_its_own_confirmations():
    series = Competition.of_series(Series(id=5, name="S", year=2027, starts_on=date(2027, 5, 1)))
    assert series.reference_date == date(2027, 5, 1)
    assert series.covers(_row(series_id=5))
    assert not series.covers(_row(series_id=6))
    # An event confirmation covers that event alone, never its series.
    assert not series.covers(_row(event_id=9))


def test_an_event_counts_its_own_and_its_series_confirmations():
    event = Competition.of_event(Event(id=9, title="E", series_id=5, starts_on=None))
    assert event.covers(_row(event_id=9))
    assert event.covers(_row(series_id=5))
    assert not event.covers(_row(event_id=8))
    alone = Competition.of_event(Event(id=9, title="E", series_id=None, starts_on=None))
    assert not alone.covers(_row(series_id=5))


def test_a_scan_is_read_off_the_reference_without_touching_the_disk():
    """Judging a whole squad must not stat a file per sailor: the reference says it."""
    assert has_scan(f"{SCAN_REF_PREFIX}does-not-exist-on-disk.png")
    assert not has_scan("paper folder 3, page 12")
    assert not has_scan(None)
    assert not has_scan("")
