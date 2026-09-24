"""User accounts, identities and roles.

**We don't manage passwords.** Whoever signs in proves themselves via an identity
provider (Google, Microsoft) or a one-time code to their email address. That saves us
password hashes, reset flows, password rules, and liability for stolen credentials — for
a league site with a few dozen accounts total, that's clearly the better trade.

An account (``User``) can have several ``Identity`` entries: the same person signs in
with Google one day and by email code the next, landing in the same account. Linked via
the **verified** email address.

Roles are their own rows, not a column: a person can have several (the league office is
often also the editorial team), and they need to be grantable and revocable without
changing the schema.

**Permissions are relation tuples** (Story Z-2): ``user:relation:object`` — this person
is ``manager`` of club A, ``race_officer`` of event C, ``admin`` of the site. That is the
Zanzibar/OpenFGA model at the size this site needs: a schema of which relations each
object type has (:data:`SCHEMA`), rewrite rules for what implies what (:data:`IMPLIED`),
and the tuples themselves (:class:`Grant`) in three foreign-key columns. One person holds
as many tuples as they have responsibilities: manager of two clubs and race officer of two
events is four rows. Club **membership** is not a tuple — it needs both sides' consent
(``ClubMember``).
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.competition import Event, Series
    from app.models.org import Club


class Relation(StrEnum):
    """What a person can *be* to an object — the relation of a tuple (Story Z-2)."""

    ADMIN = "admin"
    """Site: master data, series, accounts and every tuple."""

    EDITOR = "editor"
    """Site: editorial — posts, club contributions, master data."""

    MANAGER = "manager"
    """Club, series or event: the organizer. Runs the thing, names its people."""

    RACE_OFFICER = "race_officer"
    """Site, club, series or event: the race committee — results, race control, trackers."""

    JURY = "jury"
    """Series or event: the protest committee. Publishes announcements, hears protests."""


class ObjectType(StrEnum):
    SITE = "site"
    CLUB = "club"
    SERIES = "series"
    EVENT = "event"


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
#: Read: the league's site-wide race committee keeps the setup rights it always had
#: (``manager: … or race_officer from site``); a race officer appointed for one event
#: only runs its races. Club membership is not here — it needs both sides' consent.
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
    define manager: [user] or admin from site
    define race_officer: [user] or race_officer from site

type series
  relations
    define manager: [user] or admin from site
    define race_officer: [user] or race_officer from site
    define jury: [user] or admin from site

type event
  relations
    define manager: [user] or manager from series or manager from host_club
      or editor from site or race_officer from site
    define race_officer: [user] or race_officer from series or race_officer from host_club
      or race_officer from site
    define jury: [user] or jury from series or admin from site
"""

#: One term of a ``define``: ``direct`` for ``[user]``, else the relation to check on
#: ``self`` or on the object behind ``edge``.
Term = tuple[str, str | None]  # (relation or "direct", edge or None)


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
                    terms.append(("direct", None))
                elif " from " in part:
                    relation, edge = part.split(" from ")
                    terms.append((relation.strip(), edge.strip()))
                else:
                    terms.append((part, None))
            schema[current][Relation(head.strip())] = tuple(terms)
    return schema


#: ``SCHEMA[object_type][relation]`` — the parsed model. Also the table that decides
#: whether a tuple may be written at all: a relation missing here does not exist there.
SCHEMA = _parse_model(MODEL)


def parse_object(text: str) -> tuple[ObjectType, int | None]:
    """``"event:3"`` → ``(EVENT, 3)``; ``"site"`` → ``(SITE, None)``. FGA's object notation."""
    if text == "site":
        return ObjectType.SITE, None
    kind, _, ident = text.partition(":")
    if not ident.isdigit() or kind not in {t.value for t in ObjectType} or kind == "site":
        raise ValueError(f"not an object: {text!r} (expected type:id, e.g. event:3, or site)")
    return ObjectType(kind), int(ident)


class Role(StrEnum):
    """The **summary** roles — what the navigation and the help page call a person.

    Derived from the tuples, never stored: ``club_manager`` means "manager of some club",
    ``event_manager`` "manager of some series or event", ``race_officer`` and ``jury``
    "held on anything". The site relations keep their names.
    """

    ADMIN = "admin"
    EDITOR = "editor"
    RACE_OFFICER = "race_officer"
    CLUB_MANAGER = "club_manager"
    EVENT_MANAGER = "event_manager"
    JURY = "jury"


class IdentityProvider(StrEnum):
    GOOGLE = "google"
    MICROSOFT = "microsoft"
    EMAIL = "email"
    """One-time code to the email address — for anyone without a Google or Microsoft account."""


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
    # The club this account represents — for a club account, their own.
    # **Memberships** of a person are instead in ``ClubMember``: someone can be in
    # several clubs but always acts for only one.
    club_id: Mapped[int | None] = mapped_column(ForeignKey("club.id"), default=None, index=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    grants: Mapped[list[Grant]] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )
    identities: Mapped[list[Identity]] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )

    # ---- the check ------------------------------------------------------------------

    def holds(
        self,
        relation: Relation | str,
        *,
        club_id: int | None = None,
        series_id: int | None = None,
        event_id: int | None = None,
    ) -> bool:
        """A **direct** tuple: this relation on exactly this object (no ids: the site).
        No rewrite — an admin does not "hold" manager on a club, they merely may act as
        one. Use this where the tuple itself is the fact, e.g. "is listed as organizer"."""
        return any(
            g.relation == relation
            and g.club_id == club_id
            and g.series_id == series_id
            and g.event_id == event_id
            for g in self.grants
        )

    def can(self, *relations: Relation | str, on: object = ObjectType.SITE) -> bool:
        """The one permission check — FGA's ``check``: does any of ``relations`` hold on
        ``on``, directly or through the model's rewrite rules?

        ``on`` is a ``Club``, ``Series`` or ``Event`` instance, or ``ObjectType.SITE``.
        An event brings its containers along (``series_id``, ``host_club_id``), which is
        all the rewrite needs — no query.
        """
        ref, edges = _ref(on)
        return any(self._check(Relation(relation), ref, edges) for relation in relations)

    def _check(
        self,
        relation: Relation,
        ref: tuple[ObjectType, int | None],
        edges: dict[str, tuple[ObjectType, int | None]],
    ) -> bool:
        object_type, object_id = ref
        for term, edge in SCHEMA[object_type].get(relation, ()):
            if term == "direct":
                if self.holds(relation, **_ids(ref)):
                    return True
            elif edge is None:
                if self._check(Relation(term), ref, edges):
                    return True
            elif edge in edges:
                parent = edges[edge]
                # A parent has only the site above it.
                if self._check(Relation(term), parent, {"site": (ObjectType.SITE, None)}):
                    return True
        return False

    def holds_any(self, relation: Relation | str, object_type: ObjectType | None = None) -> bool:
        """Holds this relation on *something* (of this type) — for "is a club manager
        somewhere" pre-checks and the navigation. Direct tuples only."""
        return any(
            g.relation == relation and (object_type is None or g.object_type is object_type)
            for g in self.grants
        )

    def objects_of(self, relation: Relation | str, object_type: ObjectType) -> set[int]:
        """Every object of this type the person directly holds this relation on."""
        return {
            g.object_id
            for g in self.grants
            if g.relation == relation and g.object_type is object_type and g.object_id is not None
        }

    # ---- sugar the routers read well ------------------------------------------------

    @property
    def roles(self) -> set[str]:
        """The summary roles (:class:`Role`) — derived, for the navigation and the help."""
        out: set[str] = set()
        for g in self.grants:
            if g.object_type is ObjectType.SITE:
                out.add(g.relation)
            elif g.relation == Relation.MANAGER:
                out.add(
                    Role.CLUB_MANAGER if g.object_type is ObjectType.CLUB else Role.EVENT_MANAGER
                )
            else:
                out.add(g.relation)
        return out

    def has_any(self, *roles: str) -> bool:
        """Holds one of these **summary** roles — a navigation-level question. Never a
        permission check on an object: that is :meth:`can`."""
        return bool(self.roles & set(roles))

    def is_admin(self) -> bool:
        return self.holds(Relation.ADMIN)

    def manages_club(self, club_id: int) -> bool:
        """Directly holds ``manager`` on this club — the organizer listing (Story A-8).
        For "may act as its manager" (which an admin may) use ``can(MANAGER, on=club)``."""
        return self.holds(Relation.MANAGER, club_id=club_id)

    @property
    def managed_club_ids(self) -> set[int]:
        """Every club this account organizes — for "show me everything I manage" listings."""
        return self.objects_of(Relation.MANAGER, ObjectType.CLUB)


def _ids(ref: tuple[ObjectType, int | None]) -> dict[str, int]:
    object_type, object_id = ref
    column = {
        ObjectType.CLUB: "club_id",
        ObjectType.SERIES: "series_id",
        ObjectType.EVENT: "event_id",
    }
    return (
        {column[object_type]: object_id} if object_id is not None and object_type in column else {}
    )


def _ref(
    on: object,
) -> tuple[tuple[ObjectType, int | None], dict[str, tuple[ObjectType, int | None]]]:
    """The object as ``(type, id)`` plus its edges: ``site`` always, and for an event
    ``series`` and ``host_club`` when set."""
    site = (ObjectType.SITE, None)
    if on is ObjectType.SITE or on == "site":
        return site, {"site": site}
    name = type(on).__name__
    ident: int = on.id  # type: ignore[attr-defined]
    if name == "Club":
        return (ObjectType.CLUB, ident), {"site": site}
    if name == "Series":
        return (ObjectType.SERIES, ident), {"site": site}
    if name == "Event":
        edges: dict[str, tuple[ObjectType, int | None]] = {"site": site}
        if on.series_id is not None:  # type: ignore[attr-defined]
            edges["series"] = (ObjectType.SERIES, on.series_id)  # type: ignore[attr-defined]
        if on.host_club_id is not None:  # type: ignore[attr-defined]
            edges["host_club"] = (ObjectType.CLUB, on.host_club_id)  # type: ignore[attr-defined]
        return (ObjectType.EVENT, ident), edges
    raise TypeError(f"not an object a relation can be held on: {name}")


class Grant(Base, TimestampMixin):
    """One tuple: ``user`` is ``relation`` of the site, a club, a series or an event.

    ``user:relation:object`` in the FGA notation; here the object is one of three foreign
    keys (all NULL for the site), so the database cascades and joins and the check needs
    no lookup. At most one is set. The uniqueness constraint cannot see two site tuples as
    equal (NULLs are distinct in SQL), so `app/services/grants.py` checks for a duplicate
    before inserting.
    """

    __tablename__ = "access_grant"
    __table_args__ = (
        UniqueConstraint("user_id", "relation", "club_id", "series_id", "event_id"),
        CheckConstraint(
            "(club_id IS NOT NULL) + (series_id IS NOT NULL) + (event_id IS NOT NULL) <= 1",
            name="one_object",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("app_user.id"), index=True)
    relation: Mapped[str] = mapped_column(String(32), index=True)
    club_id: Mapped[int | None] = mapped_column(ForeignKey("club.id"), default=None, index=True)
    series_id: Mapped[int | None] = mapped_column(ForeignKey("series.id"), default=None, index=True)
    event_id: Mapped[int | None] = mapped_column(ForeignKey("event.id"), default=None, index=True)

    user: Mapped[User] = relationship(back_populates="grants")
    # Loaded eagerly so a tuple can be *named* in a response ("race_officer · Act 2 Kiel")
    # without a second query per row; the lists are short.
    club: Mapped[Club | None] = relationship(lazy="selectin")
    series: Mapped[Series | None] = relationship(lazy="selectin")
    event: Mapped[Event | None] = relationship(lazy="selectin")

    @property
    def object_type(self) -> ObjectType:
        if self.club_id is not None:
            return ObjectType.CLUB
        if self.series_id is not None:
            return ObjectType.SERIES
        if self.event_id is not None:
            return ObjectType.EVENT
        return ObjectType.SITE

    @property
    def object_id(self) -> int | None:
        return self.club_id or self.series_id or self.event_id

    @property
    def object(self) -> str:
        """FGA's notation: ``event:3``, or ``site``."""
        object_type = self.object_type
        return "site" if object_type is ObjectType.SITE else f"{object_type.value}:{self.object_id}"

    @property
    def object_name(self) -> str | None:
        if self.club is not None:
            return self.club.name
        if self.series is not None:
            return self.series.name
        if self.event is not None:
            return self.event.title
        return None


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
