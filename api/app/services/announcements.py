"""Who may speak for an event on its notice board — Story VA-11.

An announcement carries its issuer, and each issuer is a relation on the event: the race
committee is ``race_officer``, the jury ``jury``, the organizer ``manager``. Answered
through the model (``app/authz.py``), so a race officer appointed on the series or the
host club, or the site's race committee, may announce here too.
"""

from __future__ import annotations

from app import authz
from app.models import AnnouncementIssuer, Event, Relation, User

ISSUER_RELATION: dict[AnnouncementIssuer, Relation] = {
    AnnouncementIssuer.RACE_COMMITTEE: Relation.RACE_OFFICER,
    AnnouncementIssuer.JURY: Relation.JURY,
    AnnouncementIssuer.ORGANIZER: Relation.MANAGER,
}


def may_announce_as(user: User, issuer: AnnouncementIssuer, event: Event) -> bool:
    return authz.check(user, ISSUER_RELATION[issuer], on=event)


def issuers_for(user: User | None, event: Event) -> list[AnnouncementIssuer]:
    """The issuers this person may publish as on this event — empty for a guest."""
    if user is None:
        return []
    return [issuer for issuer in AnnouncementIssuer if may_announce_as(user, issuer, event)]
