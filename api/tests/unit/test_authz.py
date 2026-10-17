"""Story Z-2: the authorization facade (`app/authz.py`) answers from the model alone.

No database: a person is a ``User`` with its tuples in memory, which is all the in-process
backend reads — and what an OpenFGA server would hold instead.
"""

import pytest

from app import authz
from app.authz import SITE, ObjectRef
from app.models import Club, Event
from app.models.auth import Grant, ObjectType, Relation, User, writable

CLUB = ObjectRef(ObjectType.CLUB, 3)


def person(*tuples: Grant) -> User:
    return User(email="p@example.com", display_name="P", grants=list(tuples))


def test_objects_are_written_and_read_in_fga_notation():
    assert str(CLUB) == "club:3" and str(SITE) == "site"
    assert ObjectRef.parse("event:7") == ObjectRef(ObjectType.EVENT, 7)
    assert ObjectRef.parse("site") is SITE
    for bad in ("club", "club:x", "site:1", "boat:2"):
        with pytest.raises(ValueError):
            ObjectRef.parse(bad)
    # A loaded object, a ref and its notation name the same thing.
    assert authz.ref(Club(id=3)) == authz.ref("club:3") == CLUB


def test_a_clubs_admin_is_its_manager_but_holds_no_manager_tuple():
    admin = person(Grant(relation=Relation.ADMIN, club_id=3))
    assert authz.check(admin, Relation.MANAGER, on=CLUB)
    assert not authz.read(admin, Relation.MANAGER, CLUB)
    assert not authz.check(admin, Relation.MANAGER, on=ObjectRef(ObjectType.CLUB, 4))
    # Listing follows the same rule on the object itself …
    assert authz.list_objects(admin, Relation.MANAGER, ObjectType.CLUB) == {3}
    # … and a member is no manager.
    member = person(Grant(relation=Relation.MEMBER, club_id=3))
    assert not authz.check(member, Relation.MANAGER, on=CLUB)
    assert authz.list_objects(member, Relation.MANAGER, ObjectType.CLUB) == set()


def test_the_sites_admin_reaches_everything_but_lists_nothing():
    site_admin = person(Grant(relation=Relation.ADMIN))
    assert authz.check(site_admin, Relation.MANAGER, on=CLUB)
    assert authz.check(site_admin, Relation.ADMIN, on=ObjectRef(ObjectType.SAILOR, 9))
    # "Every club" is a query, not a list of tuples.
    assert authz.list_objects(site_admin, Relation.MANAGER, ObjectType.CLUB) == set()


def test_an_event_reaches_its_series_and_host_club():
    event = Event(id=5, title="Act", series_id=2, host_club_id=3)
    host_manager = person(Grant(relation=Relation.MANAGER, club_id=3))
    series_officer = person(Grant(relation=Relation.RACE_OFFICER, series_id=2))
    assert authz.check(host_manager, Relation.MANAGER, on=event)
    assert authz.check(series_officer, Relation.RACE_OFFICER, on=event)
    assert not authz.check(series_officer, Relation.MANAGER, on=event)
    # Named only by its ref, an event brings no containers: pass the event itself.
    assert not authz.check(host_manager, Relation.MANAGER, on=ObjectRef(ObjectType.EVENT, 5))


def test_a_sailors_admin_is_derived_and_cannot_be_written():
    assert Relation.ADMIN not in writable(ObjectType.SAILOR)
    assert writable(ObjectType.SAILOR) == [Relation.GUARDIAN]


def test_ensure_refuses_with_a_typed_problem():
    from app.problems import Problem

    with pytest.raises(Problem) as refused:
        authz.ensure(person(), Relation.MANAGER, on=CLUB, code="club-not-yours")
    assert (refused.value.status, refused.value.code) == (403, "club-not-yours")
    authz.ensure(person(Grant(relation=Relation.MANAGER, club_id=3)), Relation.MANAGER, on=CLUB)
