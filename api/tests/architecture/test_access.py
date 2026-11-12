"""Who may reach which route without signing in — the API's whole open surface, listed.

Every route either requires a signed-in account (a ``current_user`` or ``require_*``
dependency) or stands in ``OPEN`` with the reason it may be reached by anyone. A new
route nobody thought about fails here — the one place a forgotten ``Depends`` shows
before a stranger finds it. ``OPEN`` is a ratchet like ``test_rules.py``'s lists: a
route that now requires sign-in must leave it too.

This is the first of two layers. Being signed in says nothing about *which* club or
event: that is ``app/authz.py``, asked inside the handler, and held by the story tests
of each role. The list here only keeps the door count honest — the inventory found
``GET /api/admin/events/{id}/crew/{team}`` answering anyone, draft events included.
"""

from __future__ import annotations

from fastapi.routing import iter_route_contexts

from app.main import app

#: Method and path → why anyone may call it. "public" means published data only — the
#: handler answers 404 for a draft (CLAUDE.md: publication decides who sees it).
OPEN: dict[str, str] = {
    "GET /": "the API's signpost",
    "GET /health": "the health check",
    # The public site: published data only.
    "GET /api/leagues": "public",
    "GET /api/leagues/{slug}": "public",
    "GET /api/series": "public",
    "GET /api/series/{series_id}/table": "public",
    "GET /api/series/{series_id}/documents": "public — the notice board",
    "GET /api/live": "public — the live stream (B-5), version tokens only",
    "GET /api/live/now": "public",
    "GET /api/clubs": "public — enrolled clubs only",
    "GET /api/clubs/{club_id}": "public",
    "GET /api/clubs/{club_id}/logo": "public — the crest",
    "GET /api/people/{person_id}": "public profile, or 404 when switched off (S-4)",
    "GET /api/people/{person_id}/photo": "public profile's photo, under the same switch",
    "GET /api/events": "public",
    "GET /api/events/{event_id}": "public",
    "GET /api/events/{event_id}/access": "answers what the caller may do; a guest nothing",
    "GET /api/events/{event_id}/crew": "public — participation is public (B-12)",
    "GET /api/events/{event_id}/documents": "public — the notice board",
    "GET /api/events/{event_id}/announcements": "public",
    "GET /api/events/{event_id}/pairing": "public",
    "GET /api/events/{event_id}/pairing.pdf": "public",
    "GET /api/events/{event_id}/live": "public — boats on the water",
    "GET /api/admin/events/{event_id}/crew/{team_id}": (
        "a published event's lineup; a draft's only for its organizers and the club"
    ),
    "GET /api/posts": "public — published posts",
    "GET /api/posts/{slug}": "public",
    "GET /api/media": "public — the library's published pictures",
    "GET /api/media/{file_name}": "public — the served sizes, never the original",
    "GET /api/waiver": "the waiver's text, read before signing",
    # Signing in — nobody is signed in yet.
    "GET /api/auth/providers": "sign-in",
    "POST /api/auth/register": "sign-in (SBL_ALLOW_REGISTRATION)",
    "POST /api/auth/email/request": "sign-in",
    "POST /api/auth/email/verify": "sign-in",
    "POST /api/auth/oidc/{provider}": "sign-in",
    "POST /api/auth/password/login": "sign-in",
    "GET /api/invitations/{token}": "the invitation's token is the credential",
    "POST /api/invitations/{token}/redeem": "the invitation's token is the credential",
    # Machines with credentials of their own.
    "POST /api/track/fixes": "a tracker's token is the credential (L-1)",
    "GET /api/import/key": "an import key is the credential (R-2)",
    "POST /api/import/media": "an import key is the credential (R-2)",
    # Development only: the router exists only with SBL_DEV_LOGIN (never in production).
    "GET /api/dev/users": "dev login only",
    "POST /api/dev/login": "dev login only",
    "GET /api/dev/smtp-config": "dev login only",
    "POST /api/dev/test-email": "dev login only",
    "GET /api/dev/network-probe": "dev login only",
    "POST /api/dev/emulate": "dev login only",
    "POST /api/dev/season": "dev login only",
}


def _dependencies(dependant, names: set[str]) -> set[str]:
    for sub in dependant.dependencies:
        names.add(getattr(sub.call, "__name__", ""))
        _dependencies(sub, names)
    return names


def _signs_in(route) -> bool:
    names = _dependencies(route.dependant, set())
    return "current_user" in names or any(name.startswith("require") for name in names)


def test_every_open_route_is_listed_with_its_reason():
    found = {
        f"{method} {route.path}"
        for route in iter_route_contexts(app.routes)
        if getattr(route, "dependant", None) is not None and not _signs_in(route)
        for method in route.methods or ()
        if method != "HEAD"
    }
    new = sorted(found - OPEN.keys())
    gone = sorted(OPEN.keys() - found)
    message = ["Rule: a route without sign-in is listed in OPEN with its reason"]
    message += [f"  open, not listed: {route}" for route in new]
    message += [f"  listed, no longer open — delete it: {route}" for route in gone]
    assert not new and not gone, "\n".join(message)
