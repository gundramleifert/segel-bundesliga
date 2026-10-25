"""Expense claims, from filing to "paid" (Stories F-2 to F-6).

One service owns every transition of a claim, the way ``race_state.py`` owns a race's:
who may file it, what submitting copies onto it, who may decide it, and the short way to
pay it. Each transition writes one ``AuditLog`` row. The plan is
``docs/PLAN_DATA_MODEL.md``; the two decisions of 2026-10-07 on top of it:

* **A claim is on an event or on a club.** On an event the host club pays, and those who
  worked the event file; on a club the club pays, and its members file.
* **The manager or the treasurer decides and pays** — the event's own manager (the tuple,
  not the rewrite: a series' manager or the site's editor is not the event's purse) or
  the host club's, and the treasurer of either. Never the claimant.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Any, Literal, NamedTuple

from sqlalchemy import ColumnElement, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import authz
from app.authz import ObjectRef
from app.models import (
    BankAccount,
    ClaimStatus,
    Club,
    Event,
    ExpenseClaim,
    ExpenseItem,
    ExpenseKind,
    Payment,
    PaymentAllocation,
    PaymentMethod,
    PaymentStatus,
)
from app.models.auth import SCHEMA, ObjectType, Relation, User
from app.problems import Problem
from app.services.audit import EntityType, audit

#: The site's default, for a club that has set none — and the fallback for every key a
#: club's policy leaves out or gets wrong (``Club.expense_policy``).
DEFAULT_POLICY: dict[str, Any] = {
    "km_rate_cents": 30,
    "eligible": ["race_officer", "jury", "manager", "helper"],
    "document_required": ["travel_public", "accommodation", "other"],
}

#: Relations a series can hand down to its events' claims. ``helper`` is per event only.
_SERIES_RELATIONS = {Relation.RACE_OFFICER, Relation.JURY, Relation.MANAGER}

#: Every relation's name, to read a club's policy without trusting it.
_RELATION_NAMES = frozenset(relation.value for relation in Relation)

#: The claimant may change a claim in these states, and only these — everything until it
#: is approved (Story F-2, decided 2026-10-24). A change to a submitted or a rejected one
#: makes it a draft again (:func:`changed`).
EDITABLE = (ClaimStatus.DRAFT, ClaimStatus.SUBMITTED, ClaimStatus.REJECTED)


@dataclass(frozen=True)
class Policy:
    km_rate_cents: int
    eligible: frozenset[str]
    document_required: frozenset[str]


def policy_for(club: Club | None) -> Policy:
    """The paying club's rates and rules, falling back to the site default key by key —
    tolerant of anything unexpected, the way ``PrintSettings`` is."""
    raw = club.expense_policy if club is not None and club.expense_policy else {}
    if not isinstance(raw, dict):
        raw = {}

    def pick(key: str, valid) -> Any:
        value = raw.get(key)
        return value if valid(value) else DEFAULT_POLICY[key]

    rate = pick(
        "km_rate_cents", lambda v: isinstance(v, int) and not isinstance(v, bool) and v >= 0
    )
    as_list = lambda v: isinstance(v, list) and all(isinstance(x, str) for x in v)  # noqa: E731
    return Policy(
        km_rate_cents=rate,
        eligible=frozenset(pick("eligible", as_list)),
        document_required=frozenset(pick("document_required", as_list)),
    )


# ---------------------------------------------------------------------- who


def may_file_on_event(user: User, event: Event, policy: Policy) -> bool:
    """A relation the policy names, held **directly** on the event or its series — a
    relation inherited from the site entitles nobody to travel costs (Story F-2)."""
    for name in policy.eligible & _RELATION_NAMES:
        relation = Relation(name)
        if authz.read(user, relation, ObjectRef(ObjectType.EVENT, event.id)):
            return True
        if (
            relation in _SERIES_RELATIONS
            and event.series_id is not None
            and authz.read(user, relation, ObjectRef(ObjectType.SERIES, event.series_id))
        ):
            return True
    return False


def may_pay_for(user: User, club_id: int) -> bool:
    """The club's manager or treasurer (and their admins): the people who hold its money
    (Story F-3). The club's claims, account and payment runs are theirs alone."""
    return authz.check(
        user, Relation.MANAGER, Relation.TREASURER, on=ObjectRef(ObjectType.CLUB, club_id)
    )


def own_claim() -> Problem:
    """Four eyes (Story F-3): nobody decides or pays their own claim, whatever else they
    hold — the one refusal for it, wherever a claim is decided or paid."""
    return Problem(403, "claim-own-decision", "Nobody decides or pays their own claim.")


def may_decide(user: User, claim: ExpenseClaim) -> bool:
    """The manager or treasurer of what the claim is on (Story F-3). On an event: its
    treasurer by the model (the host club's included), its own manager by the tuple, and
    the host club's manager. On a club: its manager or treasurer. Never asks whether the
    person is the claimant — :func:`require_decider` does."""
    if claim.event is not None:
        event = claim.event
        if authz.check(user, Relation.TREASURER, on=event) or authz.read(
            user, Relation.MANAGER, ObjectRef(ObjectType.EVENT, event.id)
        ):
            return True
        return event.host_club_id is not None and authz.check(
            user, Relation.MANAGER, on=ObjectRef(ObjectType.CLUB, event.host_club_id)
        )
    assert claim.club_id is not None
    return may_pay_for(user, claim.club_id)


def may_see(user: User, claim: ExpenseClaim) -> bool:
    return claim.claimant_user_id == user.id or may_decide(user, claim)


def require_claimant(user: User, claim: ExpenseClaim) -> None:
    if claim.claimant_user_id != user.id:
        raise Problem(403, "claim-forbidden", "Only the claimant can change this claim.")


def require_editable(claim: ExpenseClaim) -> None:
    if claim.status not in EDITABLE:
        raise Problem(
            409,
            "claim-not-editable",
            "An approved or withdrawn claim cannot be changed.",
            detail=f"The claim is {claim.status}.",
        )


def changed(session: AsyncSession, user: User, claim: ExpenseClaim) -> None:
    """The claimant changed it: a submitted or rejected claim is a draft again, to be
    submitted again — nobody decides a claim that is changing under them (Story F-2). The
    decider's note stays readable until then."""
    if claim.status in (ClaimStatus.SUBMITTED, ClaimStatus.REJECTED):
        claim.status = ClaimStatus.DRAFT
        _audit(session, claim, "reopened", user)


def require_decider(user: User, claim: ExpenseClaim) -> None:
    if claim.claimant_user_id == user.id:
        raise own_claim()
    if not may_decide(user, claim):
        raise Problem(
            403,
            "claim-forbidden",
            "Only the manager or treasurer of the event or club decides this claim.",
        )


# ---------------------------------------------------------------------- reading


async def load(session: AsyncSession, claim_id: int) -> ExpenseClaim:
    claim = (
        await session.execute(
            select(ExpenseClaim)
            .where(ExpenseClaim.id == claim_id)
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    if claim is None:
        raise Problem(404, "claim-not-found", "No such claim.")
    return claim


class ClaimTarget(NamedTuple):
    """Something a claim can be filed on."""

    kind: Literal["event", "club"]
    target: Event | Club


class UnclaimableReason(StrEnum):
    """Why someone who works at an event cannot claim on it (Story F-2)."""

    NO_HOST_CLUB = "no_host_club"  # nobody to pay yet
    NOT_COVERED = "not_covered"  # the host club's rules do not pay this work


class Unclaimable(NamedTuple):
    """An event someone works at but cannot claim on — what they are there, and why."""

    event: Event
    relations: list[Relation]
    reason: UnclaimableReason


class ClaimOptions(NamedTuple):
    targets: list[ClaimTarget]
    unavailable: list[Unclaimable]


#: The work at an event a claim can be for — the site default's ``eligible``, the widest
#: any policy is read against.
_WORK = tuple(Relation(name) for name in DEFAULT_POLICY["eligible"])


def _work_at(user: User, event: Event) -> list[Relation]:
    """The work this person holds **directly** on the event, or on its series."""
    return [
        relation
        for relation in _WORK
        if authz.read(user, relation, ObjectRef(ObjectType.EVENT, event.id))
        or (
            relation in _SERIES_RELATIONS
            and event.series_id is not None
            and authz.read(user, relation, ObjectRef(ObjectType.SERIES, event.series_id))
        )
    ]


async def claim_options(session: AsyncSession, user: User) -> ClaimOptions:
    """Every event and club this person may file a claim on (Story F-2), events first —
    and the events they work at but cannot, each with the reason, so the page can say
    so instead of claiming they hold nothing."""
    # Any relation held there; which ones entitle to a claim is the host's policy, below.
    direct = authz.list_objects(user, tuple(SCHEMA[ObjectType.EVENT]), ObjectType.EVENT)
    series = authz.list_objects(user, tuple(SCHEMA[ObjectType.SERIES]), ObjectType.SERIES)
    events: list[Event] = []
    unavailable: list[Unclaimable] = []
    if direct or series:
        found = (
            (
                await session.execute(
                    select(Event)
                    .where(Event.id.in_(direct) | Event.series_id.in_(series))
                    .order_by(Event.starts_on.desc().nulls_last(), Event.id)
                )
            )
            .scalars()
            .all()
        )
        hosts = await _clubs(session, {e.host_club_id for e in found if e.host_club_id})
        for event in found:
            if event.host_club_id is not None and may_file_on_event(
                user, event, policy_for(hosts.get(event.host_club_id))
            ):
                events.append(event)
            elif work := _work_at(user, event):
                reason = (
                    UnclaimableReason.NO_HOST_CLUB
                    if event.host_club_id is None
                    else UnclaimableReason.NOT_COVERED
                )
                unavailable.append(Unclaimable(event, work, reason))
    members = sorted(authz.list_objects(user, Relation.MEMBER, ObjectType.CLUB))
    member_clubs = await _clubs(session, set(members))
    return ClaimOptions(
        [ClaimTarget("event", e) for e in events]
        + [ClaimTarget("club", member_clubs[c]) for c in members if c in member_clubs],
        unavailable,
    )


async def _clubs(session: AsyncSession, ids: set[int]) -> dict[int, Club]:
    if not ids:
        return {}
    rows = (await session.execute(select(Club).where(Club.id.in_(ids)))).scalars()
    return {club.id: club for club in rows}


async def pending(session: AsyncSession, user: User) -> list[ExpenseClaim]:
    """What waits for this person (Story F-6): ``submitted`` claims to decide and
    ``approved`` ones with something still open, on whatever they hold the money of —
    never their own, never a draft."""
    stmt = select(ExpenseClaim).where(
        ExpenseClaim.status.in_([ClaimStatus.SUBMITTED, ClaimStatus.APPROVED]),
        (ExpenseClaim.claimant_user_id != user.id) | ExpenseClaim.claimant_user_id.is_(None),
    )
    if not authz.check(user, Relation.ADMIN):
        # Only where this person holds a tuple that can make them a decider — a superset
        # of :func:`may_decide`, which still has the last word below. The site's admin
        # decides everywhere, so for them every claim is a candidate.
        within = _decider_scope(user)
        if within is None:
            return []
        stmt = stmt.where(within)
    candidates = (
        (await session.execute(stmt.order_by(ExpenseClaim.submitted_at, ExpenseClaim.id)))
        .scalars()
        .all()
    )
    return [claim for claim in candidates if may_decide(user, claim) and action(claim)]


def _decider_scope(user: User) -> ColumnElement[bool] | None:
    """The claims :func:`may_decide` can say yes to for someone who is not the site's
    admin, as a condition — ``None`` when there are none. Read off the model: an event's
    treasurer or manager is its own tuple, its admin's (the event's, its series', its host
    club's) or its host club's manager's or treasurer's; a club's are its manager's,
    treasurer's or admin's."""
    clubs = authz.list_objects(user, (Relation.MANAGER, Relation.TREASURER), ObjectType.CLUB)
    events = authz.list_objects(user, (Relation.MANAGER, Relation.TREASURER), ObjectType.EVENT)
    series = authz.list_objects(user, Relation.ADMIN, ObjectType.SERIES)
    if not (clubs or events or series):
        return None
    hosted = select(Event.id).where(Event.host_club_id.in_(clubs) | Event.series_id.in_(series))
    return (
        ExpenseClaim.club_id.in_(clubs)
        | ExpenseClaim.event_id.in_(events)
        | ExpenseClaim.event_id.in_(hosted)
    )


async def rejected_of(session: AsyncSession, user: User) -> list[ExpenseClaim]:
    """My claims that were rejected and wait for me to change or withdraw them (Story F-2)."""
    return list(
        (
            await session.execute(
                select(ExpenseClaim).where(
                    ExpenseClaim.claimant_user_id == user.id,
                    ExpenseClaim.status == ClaimStatus.REJECTED,
                )
            )
        ).scalars()
    )


def action(claim: ExpenseClaim) -> str | None:
    """What the decider is to do with it: ``decide``, ``pay``, or nothing."""
    if claim.status == ClaimStatus.SUBMITTED:
        return "decide"
    if claim.open_cents > 0:
        # Approved, and not covered by a payment already issued — one in an exported
        # SEPA run is waiting for the bank, not for the decider (Story F-7).
        return "pay"
    return None


# ---------------------------------------------------------------------- the claimant


async def create(
    session: AsyncSession,
    user: User,
    *,
    title: str,
    event_id: int | None,
    club_id: int | None,
) -> ExpenseClaim:
    if (event_id is None) == (club_id is None):
        raise Problem(
            422, "claim-target-invalid", "A claim is on one event or on one club, not both."
        )
    if event_id is not None:
        event = await session.get(Event, event_id)
        if event is None:
            raise Problem(404, "event-not-found", "No such event.")
        if event.host_club_id is None:
            raise Problem(
                409,
                "event-has-no-host-club",
                "This event has no host club, so nobody pays its costs yet.",
            )
        host = await session.get(Club, event.host_club_id)
        if not may_file_on_event(user, event, policy_for(host)):
            raise _not_eligible()
    else:
        assert club_id is not None
        if await session.get(Club, club_id) is None:
            raise Problem(404, "club-not-found", "No such club.")
        if not authz.check(user, Relation.MEMBER, on=ObjectRef(ObjectType.CLUB, club_id)):
            raise _not_eligible()

    claim = ExpenseClaim(
        title=title,
        event_id=event_id,
        club_id=club_id,
        claimant_user_id=user.id,
        claimant_name=user.display_name,
        status=ClaimStatus.DRAFT,
    )
    session.add(claim)
    await session.flush()
    _audit(session, claim, "created", user)
    return claim


def _not_eligible() -> Problem:
    return Problem(
        403,
        "claim-not-eligible",
        "You can claim costs only for an event you worked at or a club you belong to.",
    )


async def paying_club(session: AsyncSession, claim: ExpenseClaim) -> Club | None:
    club_id = claim.event.host_club_id if claim.event is not None else claim.club_id
    return await session.get(Club, club_id) if club_id is not None else None


async def add_item(
    session: AsyncSession,
    user: User,
    claim: ExpenseClaim,
    *,
    kind: ExpenseKind,
    incurred_on: date,
    incurred_until: date | None,
    description: str,
    distance_km: int | None,
    amount_cents: int | None,
) -> None:
    require_claimant(user, claim)
    require_editable(claim)
    price = await _priced(session, claim, kind, distance_km, amount_cents)
    days = _range(incurred_on, incurred_until)
    claim.items.append(
        ExpenseItem(
            kind=kind,
            incurred_on=days.first,
            incurred_until=days.last,
            description=description,
            distance_km=distance_km if kind == ExpenseKind.TRAVEL_CAR else None,
            rate_cents=price.rate_cents,
            amount_cents=price.amount_cents,
        )
    )
    changed(session, user, claim)


async def update_item(
    session: AsyncSession,
    user: User,
    claim: ExpenseClaim,
    item: ExpenseItem,
    *,
    kind: ExpenseKind,
    incurred_on: date,
    incurred_until: date | None,
    description: str,
    distance_km: int | None,
    amount_cents: int | None,
) -> None:
    """The item as the claimant now says it — the same rules as adding one."""
    require_claimant(user, claim)
    require_editable(claim)
    price = await _priced(session, claim, kind, distance_km, amount_cents)
    days = _range(incurred_on, incurred_until)
    item.kind = kind
    item.incurred_on, item.incurred_until = days.first, days.last
    item.description = description
    item.distance_km = distance_km if kind == ExpenseKind.TRAVEL_CAR else None
    item.rate_cents = price.rate_cents
    item.amount_cents = price.amount_cents
    changed(session, user, claim)


class Price(NamedTuple):
    amount_cents: int
    #: A car's: the paying club's per km, which the amount is distance × of.
    rate_cents: int | None


class Days(NamedTuple):
    first: date
    #: The last day of a range; empty for one day.
    last: date | None


async def _priced(
    session: AsyncSession,
    claim: ExpenseClaim,
    kind: ExpenseKind,
    distance_km: int | None,
    amount_cents: int | None,
) -> Price:
    """The amount and, for a car, the paying club's rate it is distance × rate of."""
    if kind == ExpenseKind.TRAVEL_CAR:
        if distance_km is None:
            raise Problem(422, "expense-distance-required", "A car journey needs its distance.")
        rate = policy_for(await paying_club(session, claim)).km_rate_cents
        return Price(distance_km * rate, rate)
    if amount_cents is None:
        raise Problem(422, "expense-amount-required", "This item needs an amount.")
    return Price(amount_cents, None)


def _range(first: date, last: date | None) -> Days:
    """One day, or a range that ends later — a range of one day is that day."""
    if last is None or last == first:
        return Days(first, None)
    if last < first:
        raise Problem(422, "expense-range-backwards", "A range of dates ends after it begins.")
    return Days(first, last)


async def submit(session: AsyncSession, user: User, claim: ExpenseClaim) -> None:
    """``draft`` → ``submitted`` — a rejected claim too, as it stands. Copies payer, rate
    and bank details onto the claim — what is submitted is what will be decided and paid."""
    require_claimant(user, claim)
    if claim.status not in (ClaimStatus.DRAFT, ClaimStatus.REJECTED):
        raise Problem(
            409,
            "claim-not-editable",
            "Only a draft or a rejected claim is submitted.",
            detail=f"The claim is {claim.status}.",
        )
    if not claim.items:
        raise Problem(422, "claim-empty", "A claim needs at least one item.")

    payer = await paying_club(session, claim)
    if payer is None:
        raise Problem(
            409, "event-has-no-host-club", "This event has no host club, so nobody pays it."
        )
    policy = policy_for(payer)
    _require_receipts(claim, policy)

    account = (
        await session.execute(select(BankAccount).where(BankAccount.user_id == user.id))
    ).scalar_one_or_none()
    if account is None:
        raise Problem(
            422,
            "bank-account-missing",
            "Save the bank account to pay this back to first.",
        )

    # The rate is the paying club's at submission, frozen on the item (plan §3.2).
    for item in claim.items:
        if item.kind == ExpenseKind.TRAVEL_CAR and item.distance_km is not None:
            item.rate_cents = policy.km_rate_cents
            item.amount_cents = item.distance_km * policy.km_rate_cents

    claim.payer_club_id = payer.id
    claim.payee_name = account.holder
    claim.iban = account.iban
    claim.status = ClaimStatus.SUBMITTED
    claim.submitted_at = datetime.now(UTC)
    # A new decision is asked for: the last one's note is in the audit log.
    claim.decided_by_user_id = claim.decided_at = claim.decision_note = None
    _audit(session, claim, "submitted", user)


def _require_receipts(claim: ExpenseClaim, policy: Policy) -> None:
    """Every item of a kind the paying club wants a receipt for has one — its own, or one
    on the whole claim (Story F-5)."""
    covered_by_claim = any(d.item_id is None for d in claim.documents)
    with_document = {d.item_id for d in claim.documents}
    missing = [
        item.id
        for item in claim.items
        if item.kind in policy.document_required
        and not covered_by_claim
        and item.id not in with_document
    ]
    if missing:
        raise Problem(
            422,
            "expense-document-missing",
            "Some items need a receipt before the claim can be submitted.",
            item_ids=missing,
        )


def withdraw(session: AsyncSession, user: User, claim: ExpenseClaim) -> None:
    require_claimant(user, claim)
    if claim.status not in EDITABLE:
        raise Problem(
            409,
            "claim-not-editable",
            "An approved claim cannot be withdrawn.",
            detail=f"The claim is {claim.status}.",
        )
    claim.status = ClaimStatus.WITHDRAWN
    _audit(session, claim, "withdrawn", user)


# ---------------------------------------------------------------------- the decider


def _require_submitted(claim: ExpenseClaim) -> None:
    if claim.status != ClaimStatus.SUBMITTED:
        raise Problem(
            409,
            "claim-not-submitted",
            "Only a submitted claim is decided.",
            detail=f"The claim is {claim.status}.",
        )


async def approve(
    session: AsyncSession, user: User, claim: ExpenseClaim, *, note: str | None
) -> None:
    """Approves the claim as it stands — the decider changes no amount (Story F-3). The
    receipts are checked again: the claim may have changed since it was first submitted."""
    require_decider(user, claim)
    _require_submitted(claim)
    _require_receipts(claim, policy_for(await paying_club(session, claim)))
    _decide(session, user, claim, ClaimStatus.APPROVED, note)


def reject(session: AsyncSession, user: User, claim: ExpenseClaim, note: str) -> None:
    """With a message saying why — the claimant changes the claim and submits it again."""
    require_decider(user, claim)
    _require_submitted(claim)
    _decide(session, user, claim, ClaimStatus.REJECTED, note)


def _decide(
    session: AsyncSession,
    user: User,
    claim: ExpenseClaim,
    status: ClaimStatus,
    note: str | None,
) -> None:
    claim.status = status
    claim.decided_by_user_id = user.id
    claim.decided_at = datetime.now(UTC)
    claim.decision_note = note
    _audit(session, claim, status.value, user, note=note)


def pay(
    session: AsyncSession,
    user: User,
    claim: ExpenseClaim,
    *,
    paid_on: date | None,
    reference: str | None,
    method: PaymentMethod,
) -> Payment:
    """ "Mark as paid" (Story F-4): one settled payment over what is still open — for the
    transfer the decider has just made in their own banking."""
    require_decider(user, claim)
    if claim.status != ClaimStatus.APPROVED:
        raise Problem(409, "claim-not-approved", "Only an approved claim is paid.")
    open_cents = claim.open_cents
    if open_cents <= 0:
        raise Problem(409, "claim-already-paid", "Nothing is left to pay on this claim.")
    assert claim.payer_club_id is not None
    day = paid_on or date.today()
    payment = Payment(
        payer_club_id=claim.payer_club_id,
        payee_user_id=claim.claimant_user_id,
        payee_name=claim.payee_name or claim.claimant_name,
        iban=claim.iban,
        status=PaymentStatus.SETTLED,
        method=method,
        reference=reference or claim.title[:140],
        issued_by_user_id=user.id,
        issued_on=day,
        settled_on=day,
    )
    payment.allocations.append(PaymentAllocation(claim=claim, amount_cents=open_cents))
    session.add(payment)
    _audit(session, claim, "paid", user, amount_cents=open_cents)
    return payment


def _audit(
    session: AsyncSession, claim: ExpenseClaim, action: str, user: User, **payload: Any
) -> None:
    present = {k: v for k, v in payload.items() if v is not None}
    audit(session, EntityType.EXPENSE_CLAIM, claim.id, action, user, **present)
