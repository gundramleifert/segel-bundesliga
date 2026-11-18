"""Who may call which route on *this* club or event — the second layer under
``test_access.py``.

``test_access.py`` keeps the door count honest: every route without sign-in is listed.
Being signed in says nothing about *which* club or event, though. Here every signed-in
route is one row of a table — the people around one club and one live event (organizer,
race committee, jury, helper, treasurer, team manager, guardian, editorial, …), and which
of them the route serves — and the test plays every row against the running app:

- everyone **not** in the row is refused (401, 403 or 404) — and since a refusal changes
  nothing, every route is tried, writes included;
- everyone in the row gets an answer to a read (2xx). A write they may make is the story
  tests' to hold (``test_reimbursements.py``, ``test_payment_runs.py``, …): running it here
  would change the world the next row is played in.

**Every signed-in route has its row**, so a new route cannot land without someone writing
down who it serves. ``NOT_YET`` (empty since 2026-11-13) is the ratchet that got there:
never grow it again.

A refusal is checked before any state: a route that answers a stranger "already paid"
(409) instead of 403 tells them the claim exists and what became of it.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from datetime import date
from uuid import uuid4

import pytest
from fastapi.routing import iter_route_contexts
from PIL import Image
from sqlalchemy import delete, select

from app.db import SessionLocal
from app.main import app
from app.models import Flight, MediaItem, Payment, Person, Race, Team, TeamStatus
from app.models.auth import Grant, Relation
from app.models.jury import JuryRequest
from tests.stories.test_media import picture
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
SERIES_EDITOR = "series_editor"  # editor of the event's series (R-1, R-2)
JURY_ORGANIZER = "jury_organizer"  # the site's jury organizer (JU-1…JU-5)
JUDGE = "judge"  # in the judges' pool, asked for the live event
GUARDIAN = "guardian"  # the member's linked parent (V-13, S-8)

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
        SERIES_EDITOR,
        JURY_ORGANIZER,
        JUDGE,
        GUARDIAN,
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
#: Who may confirm a waiver for the member: they, their club's organizers, their
#: guardian (`waivers.may_confirm_for`).
WAIVER_SIGNERS = frozenset({MEMBER, GUARDIAN}) | ORGANIZERS
#: The jury's office: the site's jury organizer (and admin).
JURY_OFFICE = frozenset({JURY_ORGANIZER, SITE_ADMIN})
#: Editorial: the site's (all), a series' (its regatta's).
SITE_EDITORS = frozenset({EDITOR, SITE_ADMIN})
ANY_EDITOR = SITE_EDITORS | {SERIES_EDITOR}


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
    # --------------------------------------------------------------------------- the club's people
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
    # ------------------------------------------------------------------------------------ an event
    "GET /api/admin/events/create-options": Row(SIGNED_IN),
    # The events *my* tuples reach — a 403 for whom they reach none (and a club only
    # through its admin, 4.1).
    "GET /api/admin/events": Row(
        frozenset(
            {CLUB_ADMIN, EVENT_MANAGER, RACE_OFFICER, JURY, SERIES_MANAGER, SITE_RACE_OFFICER}
        )
        | {EDITOR, SERIES_EDITOR, SITE_ADMIN}
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
    # Check-in, gated by the waiver: whoever may set the crew (VA-2, VA-5).
    "POST /api/admin/events/{event_id}/teams/{team_id}/check-in": Row(
        EVENT_ORGS | RACE_COMMITTEE | {ENTRANT}, ids=(("team_id", "event_team_id"),)
    ),
    "DELETE /api/admin/events/{event_id}/teams/{team_id}/check-in": Row(
        EVENT_ORGS | RACE_COMMITTEE | {ENTRANT}, ids=(("team_id", "event_team_id"),)
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
    # ------------------------------------------------------------------------------------ a series
    # The series *my* tuples reach — a 403 for whom they reach none.
    "GET /api/admin/series": Row(SERIES_ORGS | {EDITOR, SERIES_EDITOR}),
    "POST /api/admin/series": Row(frozenset({SITE_ADMIN}), json={"name": "Az Series"}),
    "PATCH /api/admin/series/{series_id}": Row(SERIES_ORGS, json={"description": "x"}),
    "POST /api/admin/series/{series_id}/publish": Row(SERIES_ORGS),
    "POST /api/admin/series/{series_id}/unpublish": Row(SERIES_ORGS),
    "PUT /api/admin/series/{series_id}/clubs": Row(SERIES_ORGS, json={"clubs": []}),
    "GET /api/clubs/mine": Row(SIGNED_IN),
    # --------------------------------------------------------------- waivers (S-1, S-3, S-8, VA-5)
    "GET /api/waiver/me": Row(SIGNED_IN),
    "GET /api/waiver/wards": Row(SIGNED_IN),
    "GET /api/waiver/form?scope=event&scope_id={event_id}&person_id={person_id}": Row(
        WAIVER_SIGNERS
    ),
    "POST /api/series/{series_id}/waiver": Row(WAIVER_SIGNERS, json={"person_id": "{person_id}"}),
    "POST /api/events/{event_id}/waiver": Row(WAIVER_SIGNERS, json={"person_id": "{person_id}"}),
    "POST /api/series/{series_id}/waiver/scan": Row(
        WAIVER_SIGNERS, upload=True, form={"person_id": "{person_id}", "guardian_name": "R. Ver"}
    ),
    "POST /api/events/{event_id}/waiver/scan": Row(
        WAIVER_SIGNERS, upload=True, form={"person_id": "{person_id}", "guardian_name": "R. Ver"}
    ),
    # The scan, the most sensitive file here: the sailor and their guardian, the club's
    # organizers, the event's organizers and race committee.
    "GET /api/waiver/confirmations/{confirmation_id}/scan": Row(
        frozenset({MEMBER, GUARDIAN}) | ORGANIZERS | EVENT_ORGS | RACE_COMMITTEE
    ),
    "GET /api/admin/waiver/texts": Row(frozenset({SITE_ADMIN})),
    "POST /api/admin/waiver/texts": Row(
        frozenset({SITE_ADMIN}),
        json={"title_en": "x", "body_en": "x", "title_de": "x", "body_de": "x"},
    ),
    "GET /api/admin/events/{event_id}/waivers": Row(EVENT_ORGS | RACE_COMMITTEE),
    "GET /api/clubs/{club_id}/waivers": Row(ORGANIZERS),
    # ---------------------------------------------------------------------------- jury (JU-1…JU-5)
    "GET /api/jury/judges": Row(JURY_OFFICE),
    "GET /api/jury/candidates": Row(JURY_OFFICE),
    "POST /api/jury/judges": Row(JURY_OFFICE, json={"user_id": "{user_id}"}),
    "DELETE /api/jury/judges/{user_id}": Row(JURY_OFFICE, ids=(("user_id", "judge_user_id"),)),
    "GET /api/jury/events": Row(JURY_OFFICE),
    "POST /api/jury/invitations": Row(
        JURY_OFFICE, json={"event_ids": ["{event_id}"], "user_ids": ["{judge_user_id}"]}
    ),
    "POST /api/jury/messages": Row(
        JURY_OFFICE, json={"user_ids": ["{judge_user_id}"], "subject": "x", "text": "x"}
    ),
    "PUT /api/jury/events/{event_id}/judges/{user_id}": Row(
        JURY_OFFICE, ids=(("user_id", "judge_user_id"),)
    ),
    "DELETE /api/jury/events/{event_id}/judges/{user_id}": Row(
        JURY_OFFICE, ids=(("user_id", "judge_user_id"),)
    ),
    # The judge's own: licences once in the pool; an answer to a request made to them.
    "GET /api/me/jury": Row(SIGNED_IN),
    "PUT /api/me/jury/licences": Row(frozenset({JUDGE}), json={"licences": []}),
    "PUT /api/me/jury/requests/{event_id}": Row(frozenset({JUDGE}), json={"available": True}),
    # ---------------------------------------------------------------- applications (V-5, V-6, A-9)
    "GET /api/applications": Row(SIGNED_IN),  # my clubs' — empty for most
    "POST /api/applications": Row(
        ORGANIZERS, json={"club_id": "{club_id}", "series_id": "{series_id}"}
    ),
    "DELETE /api/applications/{team_id}": Row(ORGANIZERS, ids=(("team_id", "application_id"),)),
    "POST /api/admin/applications/{team_id}/accept": Row(
        SERIES_ORGS, json={}, ids=(("team_id", "application_id"),)
    ),
    "POST /api/admin/applications/{team_id}/reject": Row(
        SERIES_ORGS, json={"note": "x"}, ids=(("team_id", "application_id"),)
    ),
    "GET /api/admin/applications": Row(frozenset({SITE_ADMIN})),
    "GET /api/admin/applications?series_id={series_id}": Row(SERIES_ORGS),
    "GET /api/admin/applications?event_id={event_id}": Row(EVENT_ORGS),
    # -------------------------------------------------------------------------- invitations (V-16)
    "POST /api/clubs/{club_id}/invitations": Row(
        CLUB_DOOR, json={"email": "{fresh_email}", "first_name": "N", "last_name": "N"}
    ),
    "POST /api/clubs/{club_id}/people/{person_id}/invitation": Row(
        CLUB_DOOR, ids=(("person_id", "invited_person_id"),)
    ),
    "POST /api/clubs/{club_id}/people/{person_id}/invitation/resend": Row(
        CLUB_DOOR, ids=(("person_id", "invited_person_id"),)
    ),
    "DELETE /api/clubs/{club_id}/people/{person_id}/invitation": Row(
        CLUB_DOOR, ids=(("person_id", "invited_person_id"),)
    ),
    # --------------------------------------------------------- accounts and tuples (Z-2, Z-7, Z-9)
    "GET /api/auth/me": Row(SIGNED_IN),
    "DELETE /api/auth/me": Row(SIGNED_IN),
    "PUT /api/auth/password": Row(SIGNED_IN, json={"new_password": "correct horse battery"}),
    "DELETE /api/auth/password": Row(SIGNED_IN),
    "GET /api/auth/model": Row(SIGNED_IN),
    "GET /api/auth/users": Row(frozenset({SITE_ADMIN})),
    "POST /api/auth/users": Row(
        frozenset({SITE_ADMIN}), json={"email": "{fresh_email}", "display_name": "x"}
    ),
    "GET /api/auth/users/{user_id}": Row(frozenset({SITE_ADMIN})),
    "DELETE /api/auth/users/{user_id}": Row(frozenset({SITE_ADMIN})),
    "DELETE /api/auth/users/{user_id}/password": Row(frozenset({SITE_ADMIN})),
    # Tuples on an object: its admin (grants.may_administer) — an event's own manager
    # sets it up but names nobody.
    "GET /api/auth/tuples?object=site": Row(frozenset({SITE_ADMIN})),
    "GET /api/auth/tuples?object=series:{series_id}": Row(frozenset({SITE_ADMIN})),
    "GET /api/auth/tuples?object=event:{event_id}": Row(frozenset({SITE_ADMIN})),
    "GET /api/auth/tuples?object=event:{host_event_id}": Row(CLUB_TUPLES),
    "GET /api/auth/tuples?object=person:{person_id}": Row(frozenset({SITE_ADMIN})),
    # --------------------------------------------------------------------------------- posts (R-1)
    "GET /api/admin/posts": Row(ANY_EDITOR),
    "POST /api/admin/posts": Row(ANY_EDITOR, json={"title": "Az post", "series_id": "{series_id}"}),
    "POST /api/admin/posts/preview": Row(
        ANY_EDITOR, json={"title": "Az post", "series_id": "{series_id}"}
    ),
    "GET /api/admin/posts/{post_id}": Row(ANY_EDITOR),
    "PATCH /api/admin/posts/{post_id}": Row(ANY_EDITOR, json={"title": "Az post 2"}),
    "DELETE /api/admin/posts/{post_id}": Row(ANY_EDITOR),
    # ------------------------------------------------------------------------------ pictures (R-2)
    "GET /api/admin/media": Row(ANY_EDITOR),
    "POST /api/admin/media": Row(ANY_EDITOR, upload=True, form={"series_id": "{series_id}"}),
    "POST /api/admin/media/from-url": Row(SITE_EDITORS, json={"url": "https://example.com/a.png"}),
    "GET /api/admin/media/named/{name}": Row(ANY_EDITOR, ids=(("name", "media_name"),)),
    "GET /api/admin/media/{media_id}": Row(ANY_EDITOR),
    "GET /api/admin/media/{media_id}/original": Row(ANY_EDITOR),
    "PATCH /api/admin/media/{media_id}": Row(ANY_EDITOR, json={"credit": "x"}),
    "PATCH /api/admin/media": Row(ANY_EDITOR, json={"ids": ["{media_id}"], "credit": "x"}),
    "POST /api/admin/media/delete": Row(ANY_EDITOR, json={"ids": ["{media_id}"]}),
    "DELETE /api/admin/media/{media_id}": Row(ANY_EDITOR),
    # Import keys: the site's editorial only.
    "GET /api/admin/import-keys": Row(SITE_EDITORS),
    "POST /api/admin/import-keys": Row(SITE_EDITORS, json={"label": "Az key"}),
    "DELETE /api/admin/import-keys/{key_id}": Row(SITE_EDITORS),
}

#: Modules whose routes have no row yet — the ratchet. A module leaves when every one of
#: its signed-in routes is in ``POLICY``.
NOT_YET: frozenset[str] = frozenset()


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
        SERIES_EDITOR: await person(SERIES_EDITOR, Grant(relation=Relation.EDITOR, **series)),
        JURY_ORGANIZER: await person(JURY_ORGANIZER, Grant(relation=Relation.JURY_ORGANIZER)),
        JUDGE: await person(JUDGE, Grant(relation=Relation.JUDGE)),
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
    headers[GUARDIAN] = await login(client, caplog, guardian_email)
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

    # The member as a minor, with a guardian's scan on the live event (S-1, S-8).
    async with SessionLocal() as session:
        (await session.get(Person, person_id)).birth_date = date(2015, 1, 1)
        await session.commit()
    scan = await client.post(
        f"/api/events/{season.live}/waiver/scan",
        headers=member,
        data={"person_id": str(person_id), "guardian_name": "R. Ver"},
        files={"file": ("s.png", _png(), "image/png")},
    )
    assert scan.status_code == 201, scan.text
    # A judge asked for the live event (JU-3).
    judge_user_id = (await client.get("/api/auth/me", headers=headers[JUDGE])).json()["id"]
    asked = await client.post(
        "/api/jury/invitations",
        headers=headers[JURY_ORGANIZER],
        json={"event_ids": [season.live], "user_ids": [judge_user_id]},
    )
    assert asked.status_code == 200, asked.text
    # The club's application to the practice series, waiting (V-5).
    applied = await client.post(
        "/api/applications",
        headers=headers[TEAM_MANAGER],
        json={"club_id": w.club, "series_id": season.series},
    )
    assert applied.status_code == 201, applied.text
    # An invitation to someone with no account yet (V-16).
    invited = await client.post(
        f"/api/clubs/{w.club}/invitations",
        headers=headers[CLUB_ADMIN],
        json={"email": f"az-invitee-{tag}@example.org", "first_name": "In", "last_name": "V"},
    )
    assert invited.status_code == 201, invited.text
    # A post and a picture about the practice series, an import key (R-1, R-2).
    post = await client.post(
        "/api/admin/posts",
        headers=headers[EDITOR],
        json={"title": f"Az post {tag}", "body": "<p>x</p>", "series_id": season.series},
    )
    assert post.status_code == 201, post.text
    pic = await client.post(
        "/api/admin/media",
        headers=headers[EDITOR],
        files={"file": ("a.jpg", picture(), "image/jpeg")},
        data={"series_id": str(season.series)},
    )
    assert pic.status_code == 201, pic.text
    async with SessionLocal() as session:
        media_name = (await session.get(MediaItem, pic.json()["id"])).name
    key = await client.post(
        "/api/admin/import-keys", headers=headers[EDITOR], json={"label": "Az key"}
    )
    assert key.status_code == 201, key.text

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
            "host_event_id": w.event,
            "confirmation_id": scan.json()["id"],
            "judge_user_id": judge_user_id,
            "application_id": applied.json()["team_id"],
            "invited_person_id": invited.json()["person_id"],
            "post_id": post.json()["id"],
            "media_id": pic.json()["id"],
            "media_name": media_name,
            "key_id": key.json()["id"],
        },
    )


def _fill(value, ids: dict[str, int | str]):
    if isinstance(value, str):
        filled = value.format(**ids)
        whole = value.startswith("{") and value.endswith("}") and value.count("{") == 1
        return int(filled) if whole and filled.isdigit() else filled
    if isinstance(value, dict):
        return {k: _fill(v, ids) for k, v in value.items()}
    if isinstance(value, list):
        return [_fill(v, ids) for v in value]
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
        kwargs["data"] = _fill(row.form, ids)
    return await client.request(method, _fill(target, ids), **kwargs)


# --------------------------------------------------------------------------- the tests


@pytest.fixture
async def matrix(client, caplog, season):
    """The world, built per test; what it put on the shared season goes again after."""
    built = await _world(client, caplog, season)
    yield built
    ids, admin = built.ids, built.headers[SITE_ADMIN]
    await client.delete(
        f"/api/admin/events/{ids['event_id']}/announcements/{ids['announcement_id']}",
        headers=admin,
    )
    await client.delete(f"/api/applications/{ids['application_id']}", headers=admin)
    await client.delete(f"/api/admin/posts/{ids['post_id']}", headers=admin)
    await client.delete(f"/api/admin/media/{ids['media_id']}", headers=admin)
    async with SessionLocal() as session:
        await session.execute(
            delete(JuryRequest).where(JuryRequest.user_id == ids["judge_user_id"])
        )
        await session.commit()


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
