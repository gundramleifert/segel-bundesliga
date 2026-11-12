"""Who may call which route on *this* club — the second layer under ``test_access.py``.

``test_access.py`` keeps the door count honest: every route without sign-in is listed.
Being signed in says nothing about *which* club, though. Here each route is one row of a
table — the people around one club, and which of them the route serves — and the test
plays every row against the running app:

- everyone **not** in the row is refused (401, 403 or 404) — and since a refusal changes
  nothing, every route is tried, writes included;
- everyone in the row gets an answer to a read (2xx). A write they may make is the story
  tests' to hold (``test_reimbursements.py``, ``test_payment_runs.py``, …): running it here
  would change the world the next row is played in.

The table is a ratchet like ``test_rules.py``'s lists: every route of a module not in
``NOT_YET`` must have its row, so a new route in ``expenses`` or ``payments`` cannot land
without someone writing down who it serves. Shrink ``NOT_YET``; never grow it.

A refusal is checked before any state: a route that answers a stranger "already paid"
(409) instead of 403 tells them the claim exists and what became of it.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from uuid import uuid4

import pytest
from fastapi.routing import iter_route_contexts
from PIL import Image
from sqlalchemy import select

from app.db import SessionLocal
from app.main import app
from app.models import Payment
from app.models.auth import Grant, Relation
from tests.stories.test_payment_runs import CLUB_IBAN
from tests.stories.test_reimbursements import login, submitted, world

# --------------------------------------------------------------------------- people

GUEST = "guest"  # not signed in
NOBODY = "nobody"  # signed in, nothing to do with the club
MEMBER = "member"  # sails for the club
CLAIMANT = "claimant"  # a member who filed the claim
TEAM_MANAGER = "team_manager"  # the club's manager — who sails, never its money
CLUB_ADMIN = "club_admin"
TREASURER = "treasurer"
OTHER_TREASURER = "other_treasurer"  # another club's treasurer
SITE_ADMIN = "site_admin"

EVERYONE = frozenset(
    {
        GUEST,
        NOBODY,
        MEMBER,
        CLAIMANT,
        TEAM_MANAGER,
        CLUB_ADMIN,
        TREASURER,
        OTHER_TREASURER,
        SITE_ADMIN,
    }
)
SIGNED_IN = EVERYONE - {GUEST}
#: Who decides and pays the club's claims and holds its purse (CLAUDE.md, F-2, F-7).
PURSE = frozenset({TREASURER, CLUB_ADMIN, SITE_ADMIN})
#: Who writes the club's tuples: its admin, and the site's (Z-2).
CLUB_TUPLES = frozenset({CLUB_ADMIN, SITE_ADMIN})


@dataclass(frozen=True)
class Row:
    """One route: who it serves, and what a call carries."""

    may: frozenset[str]
    json: dict | None = None
    upload: bool = False
    #: A GET that changes something — the GiroCode issues a payment (F-8) — is played
    #: like a write: refusals only.
    changes: bool = False


def _png() -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (8, 8), "white").save(out, format="PNG")
    return out.getvalue()


#: Method and path → the row. Path parameters are filled from :class:`World`.
POLICY: dict[str, Row] = {
    # Everyone's own: answered from the account asking, so every signed-in person.
    "GET /api/me/claims": Row(SIGNED_IN),
    "GET /api/me/claim-targets": Row(SIGNED_IN),
    "GET /api/claims/pending": Row(SIGNED_IN),  # the claims *I* decide — empty for most
    "GET /api/payment-runs": Row(SIGNED_IN),  # the runs *I* may book
    "POST /api/claims": Row(SIGNED_IN, json={"title": "x", "club_id": "{club}"}),
    # One claim: the claimant's while it is theirs, the purse's to decide.
    "GET /api/claims/{claim_id}": Row(PURSE | {CLAIMANT}),
    "PATCH /api/claims/{claim_id}": Row(frozenset({CLAIMANT}), json={"title": "y"}),
    "DELETE /api/claims/{claim_id}": Row(frozenset({CLAIMANT})),
    "POST /api/claims/{claim_id}/items": Row(
        frozenset({CLAIMANT}),
        json={"kind": "meals", "incurred_on": "2026-06-01", "description": "x", "amount_cents": 1},
    ),
    "PUT /api/claims/{claim_id}/items/{item_id}": Row(
        frozenset({CLAIMANT}),
        json={"kind": "meals", "incurred_on": "2026-06-01", "description": "x", "amount_cents": 1},
    ),
    "DELETE /api/claims/{claim_id}/items/{item_id}": Row(frozenset({CLAIMANT})),
    "POST /api/claims/{claim_id}/documents": Row(frozenset({CLAIMANT}), upload=True),
    "GET /api/claims/{claim_id}/documents/{document_id}": Row(PURSE | {CLAIMANT}),
    "DELETE /api/claims/{claim_id}/documents/{document_id}": Row(frozenset({CLAIMANT})),
    "POST /api/claims/{claim_id}/submit": Row(frozenset({CLAIMANT})),
    "POST /api/claims/{claim_id}/withdraw": Row(frozenset({CLAIMANT})),
    "POST /api/claims/{claim_id}/approve": Row(PURSE, json={"items": []}),
    "POST /api/claims/{claim_id}/reject": Row(PURSE, json={"note": "x"}),
    "POST /api/claims/{claim_id}/pay": Row(PURSE, json={}),
    "POST /api/claims/{claim_id}/unpay": Row(PURSE, json={"reason": "x"}),
    "GET /api/claims/{claim_id}/girocode": Row(PURSE, changes=True),
    # The club's purse.
    "GET /api/clubs/{club_id}/bank-account": Row(PURSE),
    "PUT /api/clubs/{club_id}/bank-account": Row(PURSE, json={"holder": "x", "iban": CLUB_IBAN}),
    "GET /api/clubs/{club_id}/claims.xlsx": Row(PURSE),
    "POST /api/clubs/{club_id}/payment-runs": Row(PURSE, json={"execution_date": "2026-10-09"}),
    "GET /api/payment-runs/{run_id}/sepa": Row(PURSE),
    "GET /api/payment-runs/{run_id}/xlsx": Row(PURSE),
    "POST /api/payment-runs/{run_id}/settle": Row(PURSE),
    "POST /api/payments/{payment_id}/fail": Row(PURSE, json={"reason": "x"}),
    # Who holds what on the club (Z-2, review 4.3).
    "GET /api/auth/tuples?object=club:{club_id}": Row(CLUB_TUPLES),
    "POST /api/auth/tuples": Row(
        CLUB_TUPLES,
        json={"user": "{member_email}", "relation": "treasurer", "object": "club:{club_id}"},
    ),
    "DELETE /api/auth/tuples/{tuple_id}": Row(CLUB_TUPLES),
}

#: Modules whose routes have no row yet — the ratchet. A module leaves when every one of
#: its signed-in routes is in ``POLICY``.
NOT_YET: frozenset[str] = frozenset(
    {
        "admin",
        "announcements",
        "applications",
        "auth",
        "club_members",
        "clubs",
        "crew",
        "dpa",
        "events",
        "guardians",
        "invitations",
        "jury",
        "me",
        "media",
        "people",
        "personal",
        "posts",
        "public",
        "sap",
        "series",
        "tracking",
        "waivers",
    }
)


# --------------------------------------------------------------------------- the world


@dataclass
class World:
    headers: dict[str, dict[str, str]]
    ids: dict[str, int | str]


async def _world(client, caplog) -> World:
    """One club with its people, one claim of each kind the routes need, one run."""
    w = await world()
    tag = uuid4().hex[:6]

    async def person(role: str, *grants: Grant) -> dict[str, str]:
        return await login(client, caplog, f"az-{role}-{tag}@example.org", *grants)

    on_club = {"club_id": w.club}
    headers = {
        GUEST: {},
        NOBODY: await person(NOBODY),
        MEMBER: await person(MEMBER, Grant(relation=Relation.MEMBER, **on_club)),
        CLAIMANT: await person(CLAIMANT, Grant(relation=Relation.MEMBER, **on_club)),
        TEAM_MANAGER: await person(TEAM_MANAGER, Grant(relation=Relation.MANAGER, **on_club)),
        CLUB_ADMIN: await person(CLUB_ADMIN, Grant(relation=Relation.ADMIN, **on_club)),
        TREASURER: await person(TREASURER, Grant(relation=Relation.TREASURER, **on_club)),
        OTHER_TREASURER: await person(
            OTHER_TREASURER, Grant(relation=Relation.TREASURER, club_id=w.other_club)
        ),
        SITE_ADMIN: await person(SITE_ADMIN, Grant(relation=Relation.ADMIN)),
    }
    treasurer, claimant = headers[TREASURER], headers[CLAIMANT]

    saved = await client.put(
        f"/api/clubs/{w.club}/bank-account",
        headers=treasurer,
        json={"holder": "Host SC", "iban": CLUB_IBAN},
    )
    assert saved.status_code == 200, saved.text

    # A submitted claim with an item and a receipt — the one most routes are about.
    claim = await submitted(client, claimant, club=w.club)
    uploaded = await client.post(
        f"/api/claims/{claim['id']}/documents",
        headers=claimant,
        files={"file": ("r.png", _png(), "image/png")},
    )
    assert uploaded.status_code == 200, uploaded.text

    # An approved one in a run, so the run and its payment exist.
    paid = await submitted(client, claimant, club=w.club)
    approved = await client.post(
        f"/api/claims/{paid['id']}/approve", headers=treasurer, json={"items": []}
    )
    assert approved.status_code == 200, approved.text
    run = await client.post(
        f"/api/clubs/{w.club}/payment-runs",
        headers=treasurer,
        json={"execution_date": "2026-10-09"},
    )
    assert run.status_code == 201, run.text
    async with SessionLocal() as session:
        payment = (
            await session.execute(select(Payment.id).where(Payment.run_id == run.json()["id"]))
        ).scalar_one()

    tuples = await client.get(
        "/api/auth/tuples", params={"object": f"club:{w.club}"}, headers=headers[CLUB_ADMIN]
    )
    assert tuples.status_code == 200, tuples.text
    manager_tuple = next(t for t in tuples.json() if t["relation"] == "manager")

    return World(
        headers=headers,
        ids={
            "club": w.club,
            "club_id": w.club,
            "claim_id": claim["id"],
            "item_id": claim["items"][0]["id"],
            "document_id": uploaded.json()["documents"][0]["id"],
            "run_id": run.json()["id"],
            "payment_id": payment,
            "tuple_id": manager_tuple["id"],
            "member_email": f"az-{MEMBER}-{tag}@example.org",
        },
    )


def _fill(value, ids: dict[str, int | str]):
    if isinstance(value, str):
        filled = value.format(**ids)
        return int(filled) if value in ("{club}", "{club_id}") else filled
    if isinstance(value, dict):
        return {k: _fill(v, ids) for k, v in value.items()}
    return value


async def _call(client, key: str, row: Row, world: World, who: str):
    method, target = key.split(" ", 1)
    kwargs: dict = {"headers": world.headers[who]}
    if row.json is not None:
        kwargs["json"] = _fill(row.json, world.ids)
    if row.upload:
        kwargs["files"] = {"file": ("r.png", _png(), "image/png")}
    return await client.request(method, _fill(target, world.ids), **kwargs)


# --------------------------------------------------------------------------- the tests


async def test_everyone_outside_a_row_is_refused(client, caplog):
    """Every route, every person it does not serve: 401, 403 or 404 — nothing else, and
    in particular never a 2xx, a 409 about the object's state or a 422 about the body."""
    world = await _world(client, caplog)
    wrong = []
    for key, row in POLICY.items():
        for who in sorted(EVERYONE - row.may):
            response = await _call(client, key, row, world, who)
            if response.status_code not in (401, 403, 404):
                wrong.append(f"  {key} as {who}: {response.status_code} {response.text[:120]}")
    assert not wrong, "Answered someone the route does not serve:\n" + "\n".join(wrong)


async def test_everyone_in_a_row_may_read(client, caplog):
    """The other half for reads: who the row names gets an answer. (A write they may make
    is held by the story tests, which own the state it changes.)"""
    world = await _world(client, caplog)
    wrong = []
    for key, row in POLICY.items():
        if not key.startswith("GET ") or row.changes:
            continue
        for who in sorted(row.may):
            response = await _call(client, key, row, world, who)
            if not 200 <= response.status_code < 300:
                wrong.append(f"  {key} as {who}: {response.status_code} {response.text[:120]}")
    assert not wrong, "Refused someone the route serves:\n" + "\n".join(wrong)


def _signed_in_routes() -> dict[str, str]:
    from tests.architecture.test_access import OPEN

    routes = {}
    for route in iter_route_contexts(app.routes):
        for method in route.methods or ():
            key = f"{method} {route.path}"
            if key not in OPEN and method != "HEAD":
                routes[key] = route.endpoint.__module__.rsplit(".", 1)[-1]
    return routes


def _policy_route(key: str) -> str:
    return key.split("?", 1)[0]


def test_every_route_of_a_covered_module_has_its_row():
    """The ratchet: a covered module's new route needs a row before it lands, and a
    module whose routes all have rows leaves ``NOT_YET``."""
    routes = _signed_in_routes()
    covered = {_policy_route(key) for key in POLICY}
    missing = sorted(k for k, m in routes.items() if m not in NOT_YET and k not in covered)
    stale = sorted(k for k in covered if k not in routes)
    finished = sorted(
        m
        for m in NOT_YET
        if (mine := [k for k, mod in routes.items() if mod == m])
        and all(k in covered for k in mine)
    )
    unknown = sorted(NOT_YET - set(routes.values()))
    message = [f"  no row: {k}" for k in missing]
    message += [f"  row for a route that does not exist: {k}" for k in stale]
    message += [f"  every route has its row — delete from NOT_YET: {m}" for m in finished]
    message += [f"  not a module with signed-in routes: {m}" for m in unknown]
    assert not message, "\n".join(message)


@pytest.mark.parametrize("key", sorted(POLICY))
def test_a_row_names_only_known_people(key):
    assert POLICY[key].may <= EVERYONE
