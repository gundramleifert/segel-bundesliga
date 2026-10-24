"""User accounts, identities and roles.

Whoever signs in proves themselves via an identity provider (Google, Microsoft), a
one-time code to their email address, or a password (Story Z-9). Passwords were long
kept out — no hashes, no reset flow, no liability — and came in on 2026-10-05 because not
every sailor has a Google or Microsoft account and a code on every sign-in is slow on a
pontoon. The code stays the reset, so there is still no reset flow of its own.

An account (``User``) can have several ``Identity`` entries: the same person signs in
with Google one day and by email code the next, landing in the same account. Linked via
the **verified** email address.

**Permissions are relation tuples** (Story Z-2): ``user:relation:object`` — this person
is ``manager`` of club A, ``race_officer`` of event C, ``admin`` of the site. That is the
Zanzibar/OpenFGA model at the size this site needs: the model in OpenFGA's DSL
(:data:`MODEL`, parsed into :data:`SCHEMA`) says which relations each object type has and
what implies what, and the tuples themselves are :class:`Grant` rows. One person holds as
many tuples as they have responsibilities: manager of two clubs and race officer of two
events is four rows. Club **membership** is the ``member`` tuple on the club (Story Z-5).
This module is the data; the questions are asked through `app/authz.py`, the one facade.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, NamedTuple

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship, selectinload

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.competition import Event, Series
    from app.models.org import Club, Sailor


class Relation(StrEnum):
    """What a person can *be* to an object — the relation of a tuple (Story Z-2)."""

    ADMIN = "admin"
    """Everything within the object — the site, or one club, series or event — including
    who else holds what on it. The site's admin is admin of every object."""

    EDITOR = "editor"
    """Site, series or event: editorial — news, press releases and pictures, and nothing
    else (decided 2026-10-24). The site's for the association and every league; a
    series' or an event's for posts and pictures about that regatta."""

    MANAGER = "manager"
    """Club, series or event: the organizer. Runs the thing, names its people."""

    RACE_OFFICER = "race_officer"
    """Site, series or event: the race committee — results, race control, trackers. A
    club has none of its own: the events it hosts get theirs from the event, the series
    or the site."""

    JURY = "jury"
    """Series or event: the protest committee. Publishes announcements, hears protests."""

    MEMBER = "member"
    """Club: belongs to it. Implies nothing else, and nothing implies it."""

    GUARDIAN = "guardian"
    """Sailor: a parent or legal guardian, linked by the child's club (Story V-13) — may
    accept the liability waiver for the child while the child is a minor (Story S-8)."""

    HELPER = "helper"
    """Event: works the day — RIB driver, pontoon, boat handling (Story VA-12). Grants no
    power on the event; it entitles the person to an expense claim on it (Story F-2) and
    lets the event's organizers see their documents (Story S-5)."""

    TREASURER = "treasurer"
    """Club or event: holds the money — checks and pays the expense claims of an event
    (Story F-1). The host club pays its events' costs, so the host club's treasurer is
    the treasurer of every event it hosts. Neither a series nor the site pays."""


class ObjectType(StrEnum):
    SITE = "site"
    CLUB = "club"
    SERIES = "series"
    EVENT = "event"
    SAILOR = "sailor"


class ObjectRef(NamedTuple):
    """An object a relation is held on: ``club:3``, or the ``site``. FGA's object
    notation, never an ORM instance's class name. Defined with the tuples it names and
    re-exported by `app/authz.py`, where callers take it from."""

    type: ObjectType
    id: int | None = None

    def __str__(self) -> str:
        return "site" if self.type is ObjectType.SITE else f"{self.type.value}:{self.id}"

    @classmethod
    def parse(cls, text: str) -> ObjectRef:
        """``"event:3"`` → ``ObjectRef(EVENT, 3)``; ``"site"`` → :data:`SITE`."""
        if text == "site":
            return SITE
        kind, _, ident = text.partition(":")
        if not ident.isdigit() or kind not in {t.value for t in ObjectType} or kind == "site":
            raise ValueError(f"not an object: {text!r} (expected type:id, e.g. event:3, or site)")
        return cls(ObjectType(kind), int(ident))


SITE = ObjectRef(ObjectType.SITE)


#: The authorization model, in OpenFGA's DSL — and this string *is* the definition:
#: :func:`_parse_model` reads it at import and :meth:`User.can` interprets it. What the
#: syntax means here:
#:
#: * ``[user]`` — the relation can be written directly as a tuple (all of ours can).
#: * ``or <relation>`` — another relation on the same object satisfies it.
#: * ``or <relation> from <edge>`` — the relation on the object at the end of ``edge``:
#:   ``site`` (every object hangs off the one site), and for an event ``series`` and
#:   ``host_club`` — its two containers, both foreign keys on the row.
#: * A line starting with ``or`` continues the ``define`` above it (our one addition to
#:   the DSL, so a long rule stays under the line length).
#:
#: Read: almost every relation is scoped by a club, a series or an event. ``admin`` of an
#: object is everything within it — including who else holds what on it — and a series'
#: admin is admin of its events, the host club's admin of the events it hosts, the site's
#: admin of all. ``manager`` is the setup work (clubs, events, schedules) without the
#: people. On a club the split reads: the ``admin`` decides who is *in* the club —
#: members, organizers, the club's tuples (among its members, Story A-8) — the ``manager``
#: decides who *sails* — squads, lineups, registrations. The league's site-wide race
#: committee keeps the setup rights it always had (``manager: … or race_officer from
#: site``); a race officer appointed for one event only runs its races. Membership is the
#: ``member`` tuple on a club — written by the club's admin, deleted by the member to
#: leave — and implies nothing else. ``treasurer`` holds the money: the host club pays its
#: events' costs, so the club's treasurer is that of every event it hosts (Story F-1).
#: ``helper`` works one event's day and holds no power on it (Story VA-12).
MODEL = """
model
  schema 1.1

type user

type site
  relations
    define admin: [user]
    define editor: [user] or admin
    define race_officer: [user] or admin

type club
  relations
    define admin: [user] or admin from site
    define manager: [user] or admin
    define member: [user]
    define treasurer: [user] or admin

type series
  relations
    define admin: [user] or admin from site
    define manager: [user] or admin
    define race_officer: [user] or admin or race_officer from site
    define jury: [user] or admin
    define editor: [user] or admin or editor from site

type event
  relations
    define admin: [user] or admin from series or admin from host_club or admin from site
    define manager: [user] or admin or manager from series or manager from host_club
      or race_officer from site
    define race_officer: [user] or admin or race_officer from series
      or race_officer from site
    define jury: [user] or admin or jury from series
    define helper: [user] or admin
    define treasurer: [user] or admin or treasurer from host_club
    define editor: [user] or admin or editor from series or editor from site

type sailor
  relations
    define admin: admin from site
    define guardian: [user]
"""


class Term(NamedTuple):
    """One term of a ``define``: ``direct`` for ``[user]``, else the relation to check on
    ``self`` or on the object behind ``edge``."""

    relation: str
    edge: str | None = None


def _parse_model(text: str) -> dict[ObjectType, dict[Relation, tuple[Term, ...]]]:
    schema: dict[ObjectType, dict[Relation, tuple[Term, ...]]] = {}
    current: ObjectType | None = None
    lines: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("or ") and lines:
            lines[-1] += " " + line
        else:
            lines.append(line)
    for line in lines:
        if line.startswith("type "):
            name = line.split()[1]
            current = None if name == "user" else ObjectType(name)
            if current is not None:
                schema[current] = {}
        elif line.startswith("define ") and current is not None:
            head, expr = line[len("define ") :].split(":", 1)
            terms: list[Term] = []
            for part in expr.split(" or "):
                part = part.strip()
                if part == "[user]":
                    terms.append(Term("direct"))
                elif " from " in part:
                    relation, edge = part.split(" from ")
                    terms.append(Term(relation.strip(), edge.strip()))
                else:
                    terms.append(Term(part))
            schema[current][Relation(head.strip())] = tuple(terms)
    return schema


#: ``SCHEMA[object_type][relation]`` — the parsed model.
SCHEMA = _parse_model(MODEL)


def writable(object_type: ObjectType) -> list[Relation]:
    """The relations a tuple can name on this object type: those with a ``[user]`` term.
    A relation that is only derived (a sailor's ``admin``) is not among them."""
    return [
        relation
        for relation, terms in SCHEMA[object_type].items()
        if any(term == "direct" for term, _ in terms)
    ]


#: Which column of a :class:`Grant` holds the object of each type — the site has none.
GRANT_COLUMN = {
    ObjectType.CLUB: "club_id",
    ObjectType.SERIES: "series_id",
    ObjectType.EVENT: "event_id",
    ObjectType.SAILOR: "sailor_id",
}


class Role(StrEnum):
    """The **summary** roles — what the navigation and the help page call a person.

    Derived from the tuples, never stored: ``club_admin`` means "admin of some club",
    ``team_manager`` "manager or admin of some club" (the model makes an admin a manager),
    ``series_manager`` and ``event_manager`` the same for a series or an event,
    ``race_officer``, ``jury``, ``treasurer`` and ``helper`` "held on anything". The site
    relations keep their names.
    """

    ADMIN = "admin"
    EDITOR = "editor"
    RACE_OFFICER = "race_officer"
    CLUB_ADMIN = "club_admin"
    TEAM_MANAGER = "team_manager"
    SERIES_MANAGER = "series_manager"
    EVENT_MANAGER = "event_manager"
    JURY = "jury"
    TREASURER = "treasurer"
    HELPER = "helper"


class IdentityProvider(StrEnum):
    GOOGLE = "google"
    MICROSOFT = "microsoft"
    EMAIL = "email"
    """One-time code to the email address — for anyone without a Google or Microsoft account."""
    PASSWORD = "password"
    """A password the person set themselves (Story Z-9); the hash is a ``PasswordCredential``."""


class User(Base, TimestampMixin):
    __tablename__ = "app_user"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Stored lowercase; identity providers link via this.
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(120))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Whether the address is verified. If someone self-registers, they've only claimed
    # it initially; only a redeemed one-time code (or a provider token) proves it.
    # Without this verification, the account cannot request membership.
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    grants: Mapped[list[Grant]] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )
    identities: Mapped[list[Identity]] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )
    # Only so the credential goes with a deleted account: SQLite enforces no foreign keys
    # and reuses ids, so a row left behind would belong to the next account. Plain lazy
    # loading on purpose — the delete cascade loads it inside the flush, and nothing else
    # ever reads it through here (`app/services/passwords.py` queries it by `user_id`).
    password_credential: Mapped[PasswordCredential | None] = relationship(
        cascade="all, delete-orphan"
    )

    def can(self, *relations: Relation | str, on: object = ObjectType.SITE) -> bool:
        """``authz.check(self, …)`` — the one permission check, in the form the routers
        read best. Everything else about permissions is `app/authz.py`."""
        # Imported here: `app.authz` interprets this module's model, so it imports this
        # module, and a top-level import back would be a cycle.
        from app import authz

        return authz.check(self, *relations, on=on)

    @property
    def roles(self) -> set[str]:
        """The summary roles (:class:`Role`) — derived, for the navigation and the help.
        Never a permission: that is ``can``."""
        out: set[str] = set()
        organizer = {
            ObjectType.CLUB: Role.TEAM_MANAGER,
            ObjectType.SERIES: Role.SERIES_MANAGER,
            ObjectType.EVENT: Role.EVENT_MANAGER,
        }
        for g in self.grants:
            if g.relation in (Relation.MEMBER, Relation.GUARDIAN):
                continue
            if g.object_type is ObjectType.SITE:
                out.add(g.relation)
            elif g.relation in (Relation.MANAGER, Relation.ADMIN):
                out.add(organizer[g.object_type])
                if g.relation == Relation.ADMIN and g.object_type is ObjectType.CLUB:
                    out.add(Role.CLUB_ADMIN)
            else:
                out.add(g.relation)
        return out


class Grant(Base, TimestampMixin):
    """One tuple: ``user`` is ``relation`` of the site, a club, a series, an event or a
    sailor (a guardian, Story V-13).

    ``user:relation:object`` in the FGA notation; here the object is one of four foreign
    keys (all NULL for the site, :data:`GRANT_COLUMN`), so the database cascades and joins.
    At most one is set. The uniqueness constraint cannot see two site tuples as
    equal (NULLs are distinct in SQL), so `app/services/grants.py` checks for a duplicate
    before inserting.
    """

    __tablename__ = "access_grant"
    __table_args__ = (
        UniqueConstraint("user_id", "relation", "club_id", "series_id", "event_id", "sailor_id"),
        CheckConstraint(
            "(club_id IS NOT NULL) + (series_id IS NOT NULL) + (event_id IS NOT NULL)"
            " + (sailor_id IS NOT NULL) <= 1",
            name="one_object",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("app_user.id"), index=True)
    relation: Mapped[str] = mapped_column(String(32), index=True)
    club_id: Mapped[int | None] = mapped_column(ForeignKey("club.id"), default=None, index=True)
    series_id: Mapped[int | None] = mapped_column(ForeignKey("series.id"), default=None, index=True)
    event_id: Mapped[int | None] = mapped_column(ForeignKey("event.id"), default=None, index=True)
    sailor_id: Mapped[int | None] = mapped_column(
        ForeignKey("sailor.id", ondelete="CASCADE"), default=None, index=True
    )

    user: Mapped[User] = relationship(back_populates="grants")
    # Only to *name* a tuple in a response ("race_officer · Act 2 Kiel"). Not loaded with
    # the user: a permission check needs the ids alone, and every request loads the user.
    # Whoever names tuples loads these (`grant_names()`).
    club: Mapped[Club | None] = relationship(lazy="raise")
    series: Mapped[Series | None] = relationship(lazy="raise")
    event: Mapped[Event | None] = relationship(lazy="raise")
    sailor: Mapped[Sailor | None] = relationship(lazy="raise")

    @property
    def object_type(self) -> ObjectType:
        for object_type, column in GRANT_COLUMN.items():
            if getattr(self, column) is not None:
                return object_type
        return ObjectType.SITE

    @property
    def object_id(self) -> int | None:
        return self.club_id or self.series_id or self.event_id or self.sailor_id

    @property
    def ref(self) -> ObjectRef:
        """The tuple's object as an :class:`ObjectRef`."""
        return ObjectRef(self.object_type, self.object_id)

    @property
    def object(self) -> str:
        """FGA's notation: ``event:3``, or ``site``."""
        return str(self.ref)

    @property
    def object_name(self) -> str | None:
        """The object's name — needs :func:`grant_names` loaded."""
        if self.object_type is ObjectType.SITE:
            return None
        obj = getattr(self, GRANT_COLUMN[self.object_type].removesuffix("_id"))
        return getattr(obj, _NAME_FIELD[self.object_type]) if obj is not None else None


#: What a tuple's object is called by.
_NAME_FIELD = {
    ObjectType.CLUB: "name",
    ObjectType.SERIES: "name",
    ObjectType.EVENT: "title",
    ObjectType.SAILOR: "full_name",
}


def grant_names() -> tuple:
    """Loader options for a query that *names* tuples (``Grant.object_name``) — a function,
    because the mappers are not configured yet while this module is imported."""
    return (
        selectinload(Grant.club),
        selectinload(Grant.series),
        selectinload(Grant.event),
        selectinload(Grant.sailor),
    )


class Identity(Base, TimestampMixin):
    """A way an account proves itself."""

    __tablename__ = "identity"
    __table_args__ = (UniqueConstraint("provider", "subject"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("app_user.id"), index=True)
    provider: Mapped[str] = mapped_column(String(32), index=True)
    # The immutable identifier with the provider ("sub" in the ID token); for EMAIL, the address.
    subject: Mapped[str] = mapped_column(String(254))

    user: Mapped[User] = relationship(back_populates="identities")


class LoginCode(Base, TimestampMixin):
    """One-time code for email login.

    The code exists **only as a hash** in the database: someone reading the database
    should not be able to sign in with it. ``attempts`` limits brute-forcing, ``consumed_at``
    makes each code single-use.
    """

    __tablename__ = "login_code"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), index=True)
    code_hash: Mapped[str] = mapped_column(String(255))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    attempts: Mapped[int] = mapped_column(default=0)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class PasswordCredential(Base, TimestampMixin):
    """The password of one account (Story Z-9) — an Argon2id hash, never the password.

    Its own table rather than a column on ``User`` or ``Identity``: every serializer that
    lists an account or its identities reads those, and none of them can carry a hash it
    never sees. ``failed_attempts`` and ``locked_until`` slow guessing per account
    (`app/services/passwords.py`).
    """

    __tablename__ = "password_credential"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("app_user.id"), unique=True)
    hash: Mapped[str] = mapped_column(String(255))
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    failed_attempts: Mapped[int] = mapped_column(default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
