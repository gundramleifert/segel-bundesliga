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
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AuditLog,
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
    PaymentState,
    PaymentStatus,
)
from app.models.auth import Relation, User
from app.problems import Problem

#: The site's default, for a club that has set none — and the fallback for every key a
#: club's policy leaves out or gets wrong (``Club.expense_policy``).
DEFAULT_POLICY: dict[str, Any] = {
    "km_rate_cents": 30,
    "eligible": ["race_officer", "jury", "manager", "helper"],
    "document_required": ["travel_public", "accommodation", "other"],
}

#: Relations a series can hand down to its events' claims. ``helper`` is per event only.
_SERIES_RELATIONS = {Relation.RACE_OFFICER, Relation.JURY, Relation.MANAGER}

#: The claimant may change a claim in these states, and only these.
EDITABLE = (ClaimStatus.DRAFT, ClaimStatus.RETURNED)


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
    for name in policy.eligible:
        relation = Relation(name) if name in Relation._value2member_map_ else None
        if relation is None:
            continue
        if user.holds(relation, event_id=event.id):
            return True
        if (
            relation in _SERIES_RELATIONS
            and event.series_id is not None
            and user.holds(relation, series_id=event.series_id)
        ):
            return True
    return False


def may_decide(user: User, claim: ExpenseClaim) -> bool:
    """The manager or treasurer of what the claim is on (Story F-3). On an event: its
    treasurer by the model (the host club's included), its own manager by the tuple, and
    the host club's manager. On a club: its manager or treasurer. Never asks whether the
    person is the claimant — :func:`require_decider` does."""
    if claim.event is not None:
        event = claim.event
        if user.can(Relation.TREASURER, on=event) or user.holds(
            Relation.MANAGER, event_id=event.id
        ):
            return True
        return event.host_club_id is not None and user.can(
            Relation.MANAGER, on=Club(id=event.host_club_id)
        )
    assert claim.club_id is not None
    return user.can(Relation.MANAGER, Relation.TREASURER, on=Club(id=claim.club_id))


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
            "A claim can be changed only while it is a draft or returned.",
            detail=f"The claim is {claim.status}.",
        )


def require_decider(user: User, claim: ExpenseClaim) -> None:
    if claim.claimant_user_id == user.id:
        # Four eyes (Story F-3): whatever else this person holds.
        raise Problem(403, "claim-own-decision", "Nobody decides or pays their own claim.")
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


async def targets(session: AsyncSession, user: User) -> list[tuple[str, Event | Club]]:
    """Every event and club this person may file a claim on (Story F-2), events first."""
    direct = {g.event_id for g in user.grants if g.event_id is not None}
    series = {g.series_id for g in user.grants if g.series_id is not None}
    events: list[Event] = []
    if direct or series:
        found = (
            (
                await session.execute(
                    select(Event)
                    .where(
                        Event.host_club_id.is_not(None),
                        Event.id.in_(direct) | Event.series_id.in_(series),
                    )
                    .order_by(Event.starts_on.desc().nulls_last(), Event.id)
                )
            )
            .scalars()
            .all()
        )
        hosts = await _clubs(session, {e.host_club_id for e in found if e.host_club_id})
        events = [
            e for e in found if may_file_on_event(user, e, policy_for(hosts.get(e.host_club_id)))
        ]
    members = sorted(user.member_club_ids)
    member_clubs = await _clubs(session, set(members))
    return [("event", e) for e in events] + [
        ("club", member_clubs[c]) for c in members if c in member_clubs
    ]


async def _clubs(session: AsyncSession, ids: set[int]) -> dict[int, Club]:
    if not ids:
        return {}
    rows = (await session.execute(select(Club).where(Club.id.in_(ids)))).scalars()
    return {club.id: club for club in rows}


async def pending(session: AsyncSession, user: User) -> list[ExpenseClaim]:
    """What waits for this person (Story F-6): ``submitted`` claims to decide and
    ``approved`` ones not yet paid, on whatever they hold the money of — never their own,
    never a draft."""
    candidates = (
        (
            await session.execute(
                select(ExpenseClaim)
                .where(
                    ExpenseClaim.status.in_([ClaimStatus.SUBMITTED, ClaimStatus.APPROVED]),
                    (ExpenseClaim.claimant_user_id != user.id)
                    | ExpenseClaim.claimant_user_id.is_(None),
                )
                .order_by(ExpenseClaim.submitted_at, ExpenseClaim.id)
            )
        )
        .scalars()
        .all()
    )
    return [
        claim
        for claim in candidates
        if may_decide(user, claim) and claim.payment_state is not PaymentState.PAID
    ]


def action(claim: ExpenseClaim) -> str | None:
    """What the decider is to do with it: ``decide``, ``pay``, or nothing."""
    if claim.status == ClaimStatus.SUBMITTED:
        return "decide"
    if claim.status == ClaimStatus.APPROVED and claim.payment_state is not PaymentState.PAID:
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
        if not user.is_member_of(club_id):
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
    description: str,
    distance_km: int | None,
    amount_cents: int | None,
) -> None:
    require_claimant(user, claim)
    require_editable(claim)
    if kind == ExpenseKind.TRAVEL_CAR:
        if distance_km is None:
            raise Problem(422, "expense-distance-required", "A car journey needs its distance.")
        rate = policy_for(await paying_club(session, claim)).km_rate_cents
        item = ExpenseItem(
            kind=kind,
            incurred_on=incurred_on,
            description=description,
            distance_km=distance_km,
            rate_cents=rate,
            amount_cents=distance_km * rate,
        )
    else:
        if amount_cents is None:
            raise Problem(422, "expense-amount-required", "This item needs an amount.")
        item = ExpenseItem(
            kind=kind, incurred_on=incurred_on, description=description, amount_cents=amount_cents
        )
    claim.items.append(item)


async def submit(session: AsyncSession, user: User, claim: ExpenseClaim) -> None:
    """``draft``/``returned`` → ``submitted``. Copies payer, rate and bank details onto
    the claim — what is submitted is what will be decided and paid."""
    require_claimant(user, claim)
    require_editable(claim)
    if not claim.items:
        raise Problem(422, "claim-empty", "A claim needs at least one item.")

    payer = await paying_club(session, claim)
    if payer is None:
        raise Problem(
            409, "event-has-no-host-club", "This event has no host club, so nobody pays it."
        )
    policy = policy_for(payer)
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
        item.approved_cents = None

    claim.payer_club_id = payer.id
    claim.payee_name = account.holder
    claim.iban = account.iban
    claim.status = ClaimStatus.SUBMITTED
    claim.submitted_at = datetime.now(UTC)
    _audit(session, claim, "submitted", user)


def withdraw(session: AsyncSession, user: User, claim: ExpenseClaim) -> None:
    require_claimant(user, claim)
    if claim.status not in (ClaimStatus.DRAFT, ClaimStatus.SUBMITTED, ClaimStatus.RETURNED):
        raise Problem(
            409,
            "claim-not-editable",
            "A decided claim cannot be withdrawn.",
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


def approve(
    session: AsyncSession,
    user: User,
    claim: ExpenseClaim,
    *,
    cuts: dict[int, int],
    note: str | None,
) -> None:
    """Approves, optionally lowering single items — never raising one."""
    require_decider(user, claim)
    _require_submitted(claim)
    items = {item.id: item for item in claim.items}
    for item_id, cents in cuts.items():
        item = items.get(item_id)
        if item is None:
            raise Problem(422, "expense-item-unknown", "That item is not on this claim.")
        if not 0 <= cents <= item.amount_cents:
            raise Problem(
                422,
                "expense-approval-above-claim",
                "An item can be approved for at most what was claimed.",
                item_id=item_id,
            )
    for item_id, cents in cuts.items():
        items[item_id].approved_cents = None if cents == items[item_id].amount_cents else cents
    _decide(session, user, claim, ClaimStatus.APPROVED, note)


def send_back(
    session: AsyncSession, user: User, claim: ExpenseClaim, status: ClaimStatus, note: str
) -> None:
    """``returned`` or ``rejected`` — both with a note saying why."""
    require_decider(user, claim)
    _require_submitted(claim)
    _decide(session, user, claim, status, note)


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
    committed = sum(
        a.amount_cents
        for a in claim.allocations
        if a.payment.status in (PaymentStatus.ISSUED, PaymentStatus.SETTLED)
    )
    open_cents = claim.approved_cents - committed
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
    session.add(
        AuditLog(
            entity_type="expense_claim",
            entity_id=claim.id,
            action=action,
            actor=user.email,
            payload={k: v for k, v in payload.items() if v is not None},
        )
    )
