"""The authorization facade — every permission question goes through here (Story Z-2).

The model is OpenFGA's: relation tuples ``user:relation:object`` and the rewrite rules in
:data:`app.models.auth.MODEL`. This module is its API, named after OpenFGA's own, so that
the in-process interpreter behind it could one day be an OpenFGA server and the callers
would not notice:

* :class:`ObjectRef` — an object as ``type:id`` (``club:3``; the site has no id). FGA's
  object notation, never an ORM instance's class name. Defined in `app/models/auth.py`
  (a ``Grant`` names its object with it) and taken from here.
* :func:`check` — FGA ``Check``: does any of these relations hold on the object, directly
  or through the rewrite rules? The one answer to "may this person …".
* :func:`read` — FGA ``Read``: is this exact tuple written? For the few places where the
  tuple itself is the fact (an expense claim is filed by those *named* on the event, not by
  everyone the model lets act there — Stories F-2, F-3).
* :func:`list_objects` — FGA ``ListObjects``, for "everything I organize" listings.
* :func:`ensure` — :func:`check`, or the typed 403.
* Writing and deleting tuples — FGA ``Write``/``Delete`` — is `app/services/grants.py`,
  which also owns the schema check, the audit log and the last-organizer rule.

What the in-process backend needs from its callers: the person's tuples are loaded with
the ``User`` (one query), and an event is passed as the ``Event`` itself, because its two
containers (``series``, ``host_club``) are foreign keys on the row — on an FGA server they
would be tuples of their own — and a sailor as the ``Sailor``, which brings the clubs they
sail for (``SailorClub``). Summary roles (``User.roles``) are for the navigation and
never answer a permission question.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, NamedTuple

from app.models.auth import SCHEMA, SITE, ObjectRef, ObjectType, Relation
from app.problems import Problem

if TYPE_CHECKING:
    from app.models.auth import User


class RelationTuple(NamedTuple):
    """A tuple as FGA's ``Read`` returns it, the user left implicit."""

    relation: str
    object: ObjectRef


#: What may name an object: a ref, ``"club:3"``, ``ObjectType.SITE``, or a loaded
#: ``Club``/``Series``/``Event``/``Sailor`` (an event this way brings its containers).
On = object

_KIND = {
    "Club": ObjectType.CLUB,
    "Series": ObjectType.SERIES,
    "Event": ObjectType.EVENT,
    "Sailor": ObjectType.SAILOR,
}


def ref(on: On) -> ObjectRef:
    """The object, as a ref."""
    if isinstance(on, ObjectRef):
        return on
    if on is ObjectType.SITE or on == "site":
        return SITE
    if isinstance(on, str):
        return ObjectRef.parse(on)
    kind = _KIND.get(type(on).__name__)
    if kind is None:
        raise TypeError(f"not an object a relation can be held on: {type(on).__name__}")
    return ObjectRef(kind, on.id)  # type: ignore[attr-defined]


#: The objects a rule's ``from <edge>`` reaches — an edge may reach several (a sailor
#: sails for every club they are connected to).
Edges = dict[str, tuple[ObjectRef, ...]]


def _edges(on: On) -> Edges:
    """The site always; for a loaded event its series and host club; for a loaded sailor
    the clubs they sail for."""
    edges: Edges = {"site": (SITE,)}
    kind = type(on).__name__
    if kind == "Event":
        if on.series_id is not None:  # type: ignore[attr-defined]
            edges["series"] = (ObjectRef(ObjectType.SERIES, on.series_id),)  # type: ignore[attr-defined]
        if on.host_club_id is not None:  # type: ignore[attr-defined]
            edges["host_club"] = (ObjectRef(ObjectType.CLUB, on.host_club_id),)  # type: ignore[attr-defined]
    elif kind == "Sailor":
        edges["club"] = tuple(ObjectRef(ObjectType.CLUB, c) for c in on.club_ids)  # type: ignore[attr-defined]
    return edges


def read(user: User, relation: Relation | str, on: On = SITE) -> bool:
    """Is exactly this tuple written — this relation, on this object, no rewrite? An admin
    does not *hold* ``manager`` on a club, they may merely act as one (:func:`check`)."""
    target = ref(on)
    return any(g.relation == relation and g.ref == target for g in user.grants)


def tuples(user: User) -> list[RelationTuple]:
    """FGA ``Read`` by user: every tuple this person holds, as ``(relation, object)``."""
    return [RelationTuple(g.relation, g.ref) for g in user.grants]


def check(user: User, *relations: Relation | str, on: On = SITE) -> bool:
    """Does any of ``relations`` hold on ``on`` — directly, or through the model's rewrite
    rules (an admin is a manager, a series' manager manages its events, the site's admin
    is admin of everything)?"""
    target, edges = ref(on), _edges(on)
    return any(_check(user, Relation(r), target, edges) for r in relations)


def _check(user: User, relation: Relation, target: ObjectRef, edges: Edges) -> bool:
    for term, edge in SCHEMA[target.type].get(relation, ()):
        if term == "direct":
            if read(user, relation, target):
                return True
        elif edge is None:
            if _check(user, Relation(term), target, edges):
                return True
        else:
            # A container has only the site above it.
            for container in edges.get(edge, ()):
                if _check(user, Relation(term), container, {"site": (SITE,)}):
                    return True
    return False


def list_objects(
    user: User, relations: Relation | str | tuple, object_type: ObjectType
) -> set[int]:
    """The objects of this type on which one of ``relations`` holds through a tuple on the
    object itself — a club's ``manager`` includes its ``admin`` (the model's ``or admin``).
    What comes from *above* is not listed: the site's admin may act on every club, but
    "every club" is a query of its own, not a list of tuples; ask :func:`check` for it."""
    wanted = {Relation(r) for r in ((relations,) if isinstance(relations, str) else relations)}
    implied = set()
    while wanted - implied:
        relation = (wanted - implied).pop()
        implied.add(relation)
        for term, edge in SCHEMA.get(object_type, {}).get(relation, ()):
            if term != "direct" and edge is None:
                wanted.add(Relation(term))
    return {
        g.object_id
        for g in user.grants
        if g.relation in implied and g.object_type is object_type and g.object_id is not None
    }


def ensure(
    user: User,
    *relations: Relation | str,
    on: On = SITE,
    code: str = "forbidden",
    title: str = "You lack the permission for this.",
) -> None:
    """:func:`check`, or a typed 403 (`app/problems.py`) naming what was required."""
    if not check(user, *relations, on=on):
        required = sorted(str(r) for r in relations)
        raise Problem(
            403,
            code,
            title,
            detail="Required: " + ", ".join(required) + f" on {ref(on)}.",
            required=required,
        )
