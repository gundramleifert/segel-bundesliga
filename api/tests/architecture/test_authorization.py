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
from app.models import Flight, Payment, Race, Team, TeamStatus
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
# Around one live event of the practice season (``season.live``) and its series.
EVENT_MANAGER = "event_manager"  # `manager` held on the event
RACE_OFFICER = "race_officer"  # `race_officer` held on the event
JURY = "jury"  # `jury` held on the event
HELPER = "helper"  # works the day, holds no power on it (VA-12)
SERIES_MANAGER = "series_manager"  # `manager` of the event's series
ENTRANT = "entrant"  # team manager of a club sailing the event
SITE_RACE_OFFICER = "site_race_officer"  # the league's race committee
EDITOR = "editor"  # the site's editorial — writes, organizes nothing

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
        EVENT_MANAGER,
        RACE_OFFICER,
        JURY,
        HELPER,
        SERIES_MANAGER,
        ENTRANT,
        SITE_RACE_OFFICER,
        EDITOR,
    }
)
SIGNED_IN = EVERYONE - {GUEST}
#: Who decides and pays the club's claims and holds its purse (CLAUDE.md, F-2, F-7).
PURSE = frozenset({TREASURER, CLUB_ADMIN, SITE_ADMIN})
#: Who writes the club's tuples: its admin, and the site's (Z-2).
CLUB_TUPLES = frozenset({CLUB_ADMIN, SITE_ADMIN})
#: Who decides who is in the club (V-8, A-8): its admin, and the site's.
CLUB_DOOR = CLUB_TUPLES
#: The club's organizers — admin and team manager — and the site's admin (V-4, V-13).
ORGANIZERS = frozenset({TEAM_MANAGER, CLUB_ADMIN, SITE_ADMIN})
#: Who is in the club: its members (the claimant is one).
MEMBERS = frozenset({MEMBER, CLAIMANT})
#: The event's organizers by the model: its own manager, its series', the league's race
#: committee, the site's admin (CLAUDE.md, review 4.1).
EVENT_ORGS = frozenset({EVENT_MANAGER, SERIES_MANAGER, SITE_RACE_OFFICER, SITE_ADMIN})
#: Who runs the races: the event's race officers and the league's (WL-2, WL-3).
RACE_COMMITTEE = frozenset({RACE_OFFICER, SITE_RACE_OFFICER, SITE_ADMIN})
#: The series' own: its manager and the site's admin.
SERIES_ORGS = frozenset({SERIES_MANAGER, SITE_ADMIN})


@dataclass(frozen=True)
class Row:
    """One route: who it serves, and what a call carries."""

    may: frozenset[str]
    json: dict | None = None
    upload: bool = False
    #: Played for refusals only: a GET that changes something (the GiroCode issues a
    #: payment, F-8), or one whose answer depends on state the world does not build.
    refusals_only: bool = False
    #: Form fields sent with the upload.
    form: dict | None = None
    #: A path parameter filled from another of the world's ids, where two routes use
    #: one name for different things (``document_id`` of a claim or of a person).
    ids: tuple[tuple[str, str], ...] = ()


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
    "GET /api/claims/{claim_id}/girocode": Row(PURSE, refusals_only=True),
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
    # ------------------------------------------------------------------ the club's people
    # Membership is shown to the club's own members and organizers (V-10).
    "GET /api/clubs/{club_id}/members": Row(MEMBERS | ORGANIZERS),
    # A member sees the roster — names and roles, no address or birth date (V-10, #45).
    "GET /api/clubs/{club_id}/people": Row(MEMBERS | ORGANIZERS),
    "POST /api/clubs/{club_id}/members": Row(CLUB_DOOR, json={"email": "{nobody_email}"}),
    "POST /api/clubs/{club_id}/members/{person_id}/accept": Row(CLUB_DOOR),
    # Either side ends a membership: the club's admin, or the member themself (Z-5).
    "DELETE /api/clubs/{club_id}/members/{person_id}": Row(CLUB_DOOR | {MEMBER}),
    # My own memberships: asked of the account asking.
    "GET /api/me/memberships": Row(SIGNED_IN),
    "POST /api/me/memberships": Row(SIGNED_IN, json={"club_id": "{club_id}"}),
    "POST /api/me/memberships/{club_id}/accept": Row(SIGNED_IN),
    "DELETE /api/me/memberships/{club_id}": Row(SIGNED_IN),
    # The data processing agreement is accepted by the club's admin (V-17).
    # Whether it is in force: for everyone holding an office there (it gates their work).
    "GET /api/clubs/{club_id}/dpa": Row(ORGANIZERS | {TREASURER}),
    "POST /api/clubs/{club_id}/dpa": Row(CLUB_DOOR, json={"version": "x", "authorized": True}),
    # My space: "mine" — a club context for who holds something on it (Z-8).
    "GET /api/me/contexts": Row(SIGNED_IN),
    "GET /api/me/contexts/{kind}/{object_id}": Row(
        MEMBERS | {TEAM_MANAGER, CLUB_ADMIN, TREASURER, SITE_ADMIN},
        ids=(("kind", "club_kind"), ("object_id", "club_id")),
    ),
    # A person's documents: the owner and their club's organizers (S-5).
    "GET /api/me/documents": Row(SIGNED_IN),
    "POST /api/me/documents": Row(SIGNED_IN, upload=True, form={"kind": "boat_licence_sea"}),
    "DELETE /api/me/documents/{document_id}": Row(
        frozenset({MEMBER}), ids=(("document_id", "personal_document_id"),)
    ),
    "GET /api/people/{user_id}/documents": Row(frozenset({MEMBER}) | ORGANIZERS),
    "GET /api/documents/{document_id}/file": Row(
        frozenset({MEMBER}) | ORGANIZERS, ids=(("document_id", "personal_document_id"),)
    ),
    # My own bank account: its owner only, and always the one asking (S-6).
    "GET /api/me/bank-account": Row(SIGNED_IN),
    "PUT /api/me/bank-account": Row(SIGNED_IN, json={"holder": "x", "iban": CLUB_IBAN}),
    "DELETE /api/me/bank-account": Row(SIGNED_IN),
    # Parents: linked by the child's club's organizers (V-13).
    "GET /api/clubs/{club_id}/guardians": Row(ORGANIZERS),
    "POST /api/people/{person_id}/guardians": Row(ORGANIZERS, json={"email": "{guardian_email}"}),
    "DELETE /api/people/{person_id}/guardians/{tuple_id}": Row(
        ORGANIZERS, ids=(("tuple_id", "guardian_tuple_id"),)
    ),
    # People: my own profile; the club's people for its organizers (V-4).
    "GET /api/people/me": Row(SIGNED_IN),
    "PATCH /api/people/me": Row(SIGNED_IN, json={"first_name": "Y"}),
    "POST /api/people/me/photo": Row(SIGNED_IN, upload=True),
    "DELETE /api/people/me/photo": Row(SIGNED_IN),
    # The people of the clubs I organize — any club's organizer gets their own.
    "GET /api/admin/people": Row(ORGANIZERS | {ENTRANT}),
    "POST /api/admin/people": Row(
        CLUB_DOOR,
        json={
            "first_name": "N",
            "last_name": "N",
            "email": "{fresh_email}",
            "club_id": "{club_id}",
        },
    ),
    "PATCH /api/admin/people/{person_id}": Row(ORGANIZERS, json={"first_name": "Z"}),
    "DELETE /api/admin/people/{person_id}/clubs/{club_id}": Row(CLUB_DOOR),
    # A squad is public participation (B-12) — read by anyone signed in; set by the club.
    "GET /api/admin/teams/{team_id}/members": Row(SIGNED_IN),
    "PUT /api/admin/teams/{team_id}/members": Row(ORGANIZERS, json={"members": []}),
    # Clubs: created and enrolled by the league office; kept by their admin (A-1, V-3).
    "GET /api/admin/clubs": Row(frozenset({SITE_ADMIN})),
    "POST /api/admin/clubs": Row(frozenset({SITE_ADMIN}), json={"name": "Az Club"}),
    "PATCH /api/admin/clubs/{club_id}": Row(CLUB_DOOR, json={"city": "Kiel"}),
    "PUT /api/admin/clubs/{club_id}/series": Row(frozenset({SITE_ADMIN}), json={"series": []}),
    "POST /api/admin/clubs/{club_id}/logo": Row(CLUB_DOOR, upload=True),
    "DELETE /api/admin/clubs/{club_id}/logo": Row(CLUB_DOOR),
    # ------------------------------------------------------------------ an event
    "GET /api/admin/events/create-options": Row(SIGNED_IN),
    # The events *my* tuples reach — a 403 for whom they reach none (and a club only
    # through its admin, 4.1).
    "GET /api/admin/events": Row(
        frozenset(
            {CLUB_ADMIN, EVENT_MANAGER, RACE_OFFICER, JURY, SERIES_MANAGER, SITE_RACE_OFFICER}
        )
        | {EDITOR, SITE_ADMIN}
    ),
    "POST /api/admin/events": Row(
        frozenset({SERIES_MANAGER, SITE_RACE_OFFICER, SITE_ADMIN}),
        json={"title": "Az Act", "series": "{series_id}"},
    ),
    "GET /api/admin/events/{event_id}": Row(EVENT_ORGS | RACE_COMMITTEE),
    "GET /api/admin/events/{event_id}/boats": Row(EVENT_ORGS | RACE_COMMITTEE),
    "GET /api/admin/events/{event_id}/readiness": Row(EVENT_ORGS | RACE_COMMITTEE),
    "PATCH /api/admin/events/{event_id}": Row(EVENT_ORGS, json={"title": "Az"}),
    "POST /api/admin/events/{event_id}/publish": Row(EVENT_ORGS),
    "POST /api/admin/events/{event_id}/unpublish": Row(EVENT_ORGS),
    "POST /api/admin/events/{event_id}/start": Row(EVENT_ORGS | RACE_COMMITTEE),
    "POST /api/admin/events/{event_id}/finish": Row(EVENT_ORGS | RACE_COMMITTEE),
    "POST /api/admin/events/{event_id}/cancel": Row(EVENT_ORGS | RACE_COMMITTEE),
    "POST /api/admin/events/{event_id}/reopen": Row(EVENT_ORGS | RACE_COMMITTEE),
    "GET /api/admin/events/{event_id}/clubs": Row(EVENT_ORGS),
    "GET /api/admin/events/{event_id}/candidate-clubs": Row(EVENT_ORGS),
    "PUT /api/admin/events/{event_id}/clubs": Row(EVENT_ORGS, json={"clubs": []}),
    # The draw (4.6: the league office's alone for now).
    "GET /api/admin/pairing/catalog": Row(SIGNED_IN),
    "POST /api/admin/events/{event_id}/pairing/from-catalog": Row(frozenset({SITE_ADMIN})),
    "POST /api/admin/events/{event_id}/pairing/import": Row(
        frozenset({SITE_ADMIN}), json={"schedule_config": "x", "pairing_list": "x"}
    ),
    # Race day: the race committee's (WL-2, WL-3). Organizing is not racing.
    "GET /api/admin/events/{event_id}/races": Row(RACE_COMMITTEE),
    "POST /api/admin/events/{event_id}/races/{race_id}/start": Row(RACE_COMMITTEE, json={}),
    "POST /api/admin/events/{event_id}/races/{race_id}/recall": Row(RACE_COMMITTEE),
    "POST /api/admin/events/{event_id}/races/{race_id}/abandon": Row(RACE_COMMITTEE),
    "POST /api/admin/events/{event_id}/races/{race_id}/signal": Row(
        RACE_COMMITTEE, json={"signal": None}
    ),
    "PUT /api/admin/events/{event_id}/races/{race_id}/sequence": Row(RACE_COMMITTEE, json={}),
    "PUT /api/admin/events/{event_id}/races/{race_id}/result": Row(
        RACE_COMMITTEE, json={"results": []}
    ),
    "PUT /api/admin/events/{event_id}/teams/{team_id}/penalty": Row(
        RACE_COMMITTEE, json={"points": None}, ids=(("team_id", "event_team_id"),)
    ),
    # The notice board: race committee, jury and organizer each speak for themselves (VA-11).
    "POST /api/admin/events/{event_id}/announcements": Row(
        EVENT_ORGS | RACE_COMMITTEE | {JURY},
        json={"issuer": "organizer", "title": "x", "body": "x"},
    ),
    "DELETE /api/admin/events/{event_id}/announcements/{announcement_id}": Row(
        EVENT_ORGS | RACE_COMMITTEE | {JURY}
    ),
    # A crew is the club's to name (V-2) — and the event's organizers' and race
    # committee's, who change it at check-in.
    "PUT /api/admin/events/{event_id}/crew": Row(
        EVENT_ORGS | RACE_COMMITTEE | {ENTRANT}, json={"team_id": "{event_team_id}", "members": []}
    ),
    # SAP: the organizer sends, the race committee fetches (VA-15, WL-5).
    "POST /api/events/{event_id}/sap/send": Row(EVENT_ORGS),
    "POST /api/events/{event_id}/sap/results": Row(EVENT_ORGS | RACE_COMMITTEE),
    # The course and the trackers: race day (L-1, L-2).
    # The practice event has no course laid: 404 course-not-laid for the committee.
    "GET /api/admin/events/{event_id}/course": Row(RACE_COMMITTEE, refusals_only=True),
    "PUT /api/admin/events/{event_id}/course": Row(RACE_COMMITTEE, json={"marks": []}),
    "POST /api/admin/events/{event_id}/course/default": Row(RACE_COMMITTEE, json={}),
    "GET /api/admin/events/{event_id}/trackers": Row(RACE_COMMITTEE),
    # ------------------------------------------------------------------ a series
    # The series *my* tuples reach — a 403 for whom they reach none.
    "GET /api/admin/series": Row(SERIES_ORGS | {EDITOR}),
    "POST /api/admin/series": Row(frozenset({SITE_ADMIN}), json={"name": "Az Series"}),
    "PATCH /api/admin/series/{series_id}": Row(SERIES_ORGS, json={"description": "x"}),
    "POST /api/admin/series/{series_id}/publish": Row(SERIES_ORGS),
    "POST /api/admin/series/{series_id}/unpublish": Row(SERIES_ORGS),
    "PUT /api/admin/series/{series_id}/clubs": Row(SERIES_ORGS, json={"clubs": []}),
    "GET /api/clubs/mine": Row(SIGNED_IN),
}

#: Modules whose routes have no row yet — the ratchet. A module leaves when every one of
#: its signed-in routes is in ``POLICY``.
NOT_YET: frozenset[str] = frozenset(
    {
        "applications",
        "auth",
        "invitations",
        "jury",
        "media",
        "posts",
        "waivers",
    }
)


# --------------------------------------------------------------------------- the world


@dataclass
class World:
    headers: dict[str, dict[str, str]]
    ids: dict[str, int | str]


async def _world(client, caplog, season) -> World:
    """One club with its people, one claim of each kind the routes need, one run — and
    the people around the practice season's live event."""
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
    live, series = {"event_id": season.live}, {"series_id": season.series}
    entrant_club = next(iter(season.squads))
    headers |= {
        EVENT_MANAGER: await person(EVENT_MANAGER, Grant(relation=Relation.MANAGER, **live)),
        RACE_OFFICER: await person(RACE_OFFICER, Grant(relation=Relation.RACE_OFFICER, **live)),
        JURY: await person(JURY, Grant(relation=Relation.JURY, **live)),
        HELPER: await person(HELPER, Grant(relation=Relation.HELPER, **live)),
        SERIES_MANAGER: await person(SERIES_MANAGER, Grant(relation=Relation.MANAGER, **series)),
        ENTRANT: await person(ENTRANT, Grant(relation=Relation.MANAGER, club_id=entrant_club)),
        SITE_RACE_OFFICER: await person(SITE_RACE_OFFICER, Grant(relation=Relation.RACE_OFFICER)),
        EDITOR: await person(EDITOR, Grant(relation=Relation.EDITOR)),
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

    # The member: their person, account, a document and a linked parent.
    member = headers[MEMBER]
    person_id = (await client.get("/api/people/me", headers=member)).json()["id"]
    user_id = (await client.get("/api/auth/me", headers=member)).json()["id"]
    document = await client.post(
        "/api/me/documents",
        headers=member,
        data={"kind": "boat_licence_sea"},
        files={"file": ("l.png", _png(), "image/png")},
    )
    assert document.status_code in (200, 201), document.text
    guardian_email = f"az-guardian-{tag}@example.org"
    await login(client, caplog, guardian_email)
    linked = await client.post(
        f"/api/people/{person_id}/guardians",
        headers=headers[CLUB_ADMIN],
        json={"email": guardian_email},
    )
    assert linked.status_code == 201, linked.text
    # The club's registration for the series — the squad the team routes are about.
    async with SessionLocal() as session:
        team = Team(name="HST", series_id=w.series, club_id=w.club, status=TeamStatus.ACCEPTED)
        session.add(team)
        await session.commit()
        team_id = team.id

    # The live event: one of its races, the entrant's team, a notice on its board.
    async with SessionLocal() as session:
        race_id = (
            (
                await session.execute(
                    select(Race.id)
                    .join(Flight, Flight.id == Race.flight_id)
                    .where(Flight.event_id == season.live)
                    .order_by(Race.id)
                )
            )
            .scalars()
            .first()
        )
    announced = await client.post(
        f"/api/admin/events/{season.live}/announcements",
        headers=headers[EVENT_MANAGER],
        json={"issuer": "organizer", "title": "Az notice", "body": "x"},
    )
    assert announced.status_code == 201, announced.text

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
            "nobody_email": f"az-{NOBODY}-{tag}@example.org",
            "fresh_email": f"az-fresh-{tag}@example.org",
            "guardian_email": guardian_email,
            "person_id": person_id,
            "user_id": user_id,
            "personal_document_id": document.json()["id"],
            "guardian_tuple_id": linked.json()["id"],
            "team_id": team_id,
            "club_kind": "club",
            "event_id": season.live,
            "series_id": season.series,
            "race_id": race_id,
            "event_team_id": season.entries[(season.live, entrant_club)],
            "announcement_id": announced.json()["id"],
        },
    )


def _fill(value, ids: dict[str, int | str]):
    if isinstance(value, str):
        filled = value.format(**ids)
        whole = value.startswith("{") and value.endswith("}") and value.count("{") == 1
        return int(filled) if whole and filled.isdigit() else filled
    if isinstance(value, dict):
        return {k: _fill(v, ids) for k, v in value.items()}
    return value


async def _call(client, key: str, row: Row, world: World, who: str):
    method, target = key.split(" ", 1)
    ids = world.ids | {name: world.ids[source] for name, source in row.ids}
    kwargs: dict = {"headers": world.headers[who]}
    if row.json is not None:
        kwargs["json"] = _fill(row.json, ids)
    if row.upload:
        kwargs["files"] = {"file": ("r.png", _png(), "image/png")}
    if row.form is not None:
        kwargs["data"] = row.form
    return await client.request(method, _fill(target, ids), **kwargs)


# --------------------------------------------------------------------------- the tests


@pytest.fixture
async def matrix(client, caplog, season):
    """The world, built per test; what it put on the shared season goes again after."""
    built = await _world(client, caplog, season)
    yield built
    await client.delete(
        f"/api/admin/events/{built.ids['event_id']}/announcements/{built.ids['announcement_id']}",
        headers=built.headers[SITE_ADMIN],
    )


async def test_everyone_outside_a_row_is_refused(client, matrix):
    """Every route, every person it does not serve: 401, 403 or 404 — nothing else, and
    in particular never a 2xx, a 409 about the object's state or a 422 about the body."""
    world = matrix
    wrong = []
    for key, row in POLICY.items():
        for who in sorted(EVERYONE - row.may):
            response = await _call(client, key, row, world, who)
            if response.status_code not in (401, 403, 404):
                wrong.append(f"  {key} as {who}: {response.status_code} {response.text[:120]}")
    assert not wrong, "Answered someone the route does not serve:\n" + "\n".join(wrong)


async def test_everyone_in_a_row_may_read(client, matrix):
    """The other half for reads: who the row names gets an answer. (A write they may make
    is held by the story tests, which own the state it changes.)"""
    world = matrix
    wrong = []
    for key, row in POLICY.items():
        if not key.startswith("GET ") or row.refusals_only:
            continue
        for who in sorted(row.may):
            response = await _call(client, key, row, world, who)
            if not 200 <= response.status_code < 300:
                wrong.append(f"  {key} as {who}: {response.status_code} {response.text[:120]}")
    assert not wrong, "Refused someone the route serves:\n" + "\n".join(wrong)


def _signed_in_routes() -> dict[str, str]:
    """Method and path → router module, of every route that requires sign-in — the
    complement of ``test_access.OPEN``."""
    from tests.architecture.test_access import _signs_in

    routes = {}
    for route in iter_route_contexts(app.routes):
        if getattr(route, "dependant", None) is None or not _signs_in(route):
            continue
        for method in route.methods or ():
            if method != "HEAD":
                routes[f"{method} {route.path}"] = route.endpoint.__module__.rsplit(".", 1)[-1]
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
