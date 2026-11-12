"""The architecture's rules, checked — what an agent must not get wrong, enforced.

Every rule here is one CLAUDE.md states in prose. Prose is read and then broken, by people
and agents alike; a failing test is not. Each test names the rule in its docstring, finds
every violation in the code, and compares it with its ``KNOWN`` list: the violations that
existed when the rule was written down, each with its item in ``docs/REVIEW_2026-11.md``.

The lists are a **ratchet**:

* a violation not in the list fails — nothing new gets in;
* a listed violation that is gone fails too — fixing one means deleting its line, so the
  list only ever shrinks, and never claims a violation that is no longer there.

Rules that an import expresses are ruff's (`TID251` in pyproject.toml, with `RUF100`
making a stale `# noqa` an error) — this file holds the ones lint cannot see.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

API = Path(__file__).resolve().parents[2]
APP = API / "app"
ROOT = API.parent


def _modules() -> dict[str, ast.Module]:
    return {
        path.relative_to(API).as_posix(): ast.parse(path.read_text("utf-8"))
        for path in sorted(APP.rglob("*.py"))
    }


MODULES = _modules()


def _ratchet(rule: str, found: set[str], known: dict[str, str]) -> None:
    new = sorted(found - known.keys())
    gone = sorted(known.keys() - found)
    message = [f"Rule: {rule}"]
    if new:
        message.append("New violations — fix them, don't list them:")
        message += [f"  {item}" for item in new]
    if gone:
        message.append("Fixed — delete these lines from KNOWN (and tick the review item):")
        message += [f"  {item}  ({known[item]})" for item in gone]
    assert not new and not gone, "\n".join(message)


# ------------------------------------------------------------------- one writer per state


#: Each status has one service that changes it, through its transitions.
STATUS_OWNERS = {
    "EventStatus": {"app/services/event_state.py"},
    "RaceStatus": {"app/services/race_state.py"},
    "ClaimStatus": {"app/services/expenses.py"},
    "PaymentStatus": {"app/services/payments.py"},
    "MembershipStatus": {"app/services/participation.py"},
    "TeamStatus": {"app/services/registrations.py"},
}

KNOWN_STATUS_WRITES = {
    "app/routers/applications.py: TeamStatus": "REVIEW 7.3",
}


def test_a_status_changes_only_in_its_owner():
    """A status is changed only by the service that owns its transitions — never set by an
    importer, a router or a fixture (CLAUDE.md: "The status changes only through these
    transitions"). Building a row with an initial status is not a change."""
    found = set()
    for name, module in MODULES.items():
        for node in ast.walk(module):
            if not isinstance(node, ast.Assign):
                continue
            if not any(
                isinstance(target, ast.Attribute) and target.attr == "status"
                for target in node.targets
            ):
                continue
            for enum in _status_enums(node.value):
                if name not in STATUS_OWNERS[enum]:
                    found.add(f"{name}: {enum}")
    _ratchet("one writer per status", found, KNOWN_STATUS_WRITES)


def _status_enums(value: ast.expr) -> set[str]:
    """The status enums an assigned expression names — `XStatus.A`, or `XStatus.A if … else
    XStatus.B`, or a variable is missed; a literal member is what a transition writes."""
    return {
        node.value.id
        for node in ast.walk(value)
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id in STATUS_OWNERS
    }


# ------------------------------------------------------------------- one creator per row

#: Rows whose invariants live in one constructor function.
CREATORS = {
    "Team": {"app/services/participation.py", "app/models/org.py"},
}

KNOWN_CREATIONS = {
    "app/imports/common.py: Team": "REVIEW 3.1",
    "app/imports/m2s.py: Team": "REVIEW 3.1",
    "app/practice.py: Team": "REVIEW 3.1",
    "app/routers/applications.py: Team": "REVIEW 3.1",
    "app/routers/series.py: Team": "REVIEW 3.1",
    "app/seed.py: Team": "REVIEW 3.1",
    "app/services/registrations.py: Team": "REVIEW 3.1",
}


def test_an_entry_is_created_only_by_participation():
    """A `Team` — a series registration or an event entry — is made only in
    app/services/participation.py, which checks the registration, the per-club limit and
    the series it belongs to. A row built anywhere else skips them."""
    found = set()
    for name, module in MODULES.items():
        for node in ast.walk(module):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in CREATORS
                and name not in CREATORS[node.func.id]
            ):
                found.add(f"{name}: {node.func.id}")
    _ratchet("one creator per row", found, KNOWN_CREATIONS)


# ------------------------------------------------------------------- layers

KNOWN_ROUTER_IMPORTS = {
    "app/routers/announcements.py -> app.routers.public": "REVIEW 7.4",
    "app/routers/events.py -> app.routers.public": "REVIEW 7.4",
    "app/routers/payments.py -> app.routers.personal": "REVIEW 7.4",
    "app/routers/posts.py -> app.routers.media": "REVIEW 7.4",
    "app/routers/public.py -> app.routers.people": "REVIEW 7.4",
    "app/routers/tracking.py -> app.routers.public": "REVIEW 7.4",
}


def test_a_router_never_imports_a_router():
    """A router parses, authorizes, calls a service and serializes. What two routers share
    — a query, a serializer, a check — belongs in app/services/ or app/schemas/, where the
    next agent looks for it; a router used as a library hides it."""
    found = set()
    for name, module in MODULES.items():
        if not name.startswith("app/routers/") or name.endswith("__init__.py"):
            continue
        for node in ast.walk(module):
            if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("app.routers"):
                found.add(f"{name} -> {node.module}")
    _ratchet("routers do not import routers", found, KNOWN_ROUTER_IMPORTS)


#: SQL statements built in each router — ``select``/``insert``/``update``/``delete`` calls.
#: A router parses, authorizes, calls a service and serializes (review 7.3); a query in it
#: is a rule nobody else can call, and the next screen writes it again. The counts are a
#: ratchet like the lists above: a router may lose queries, never gain one.
KNOWN_ROUTER_QUERIES = {
    "app/routers/admin.py": 4,
    "app/routers/announcements.py": 1,
    "app/routers/applications.py": 5,
    "app/routers/auth.py": 4,
    "app/routers/club_members.py": 6,
    "app/routers/clubs.py": 6,
    "app/routers/crew.py": 1,
    "app/routers/dev.py": 3,
    "app/routers/events.py": 15,
    "app/routers/expenses.py": 1,
    "app/routers/guardians.py": 2,
    "app/routers/jury.py": 5,
    "app/routers/media.py": 5,
    "app/routers/people.py": 12,
    "app/routers/personal.py": 2,
    "app/routers/posts.py": 2,
    "app/routers/public.py": 39,
    "app/routers/series.py": 7,
    "app/routers/tracking.py": 1,
    "app/routers/waivers.py": 11,
}

_STATEMENTS = {"select", "insert", "update", "delete"}


def test_a_router_gains_no_query():
    """Queries live in ``app/services/`` (review 7.3): where the next agent looks for the
    rule, and where the next screen calls it instead of writing it again. A router with
    more statements than its count fails — move the query into a service; one with fewer
    fails too — lower its count, so the ratchet keeps what was won."""
    found = {}
    for name, module in MODULES.items():
        if not name.startswith("app/routers/"):
            continue
        count = sum(
            1
            for node in ast.walk(module)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in _STATEMENTS
        )
        if count:
            found[name] = count
    grown = {n: c for n, c in found.items() if c > KNOWN_ROUTER_QUERIES.get(n, 0)}
    shrunk = {n: c for n, c in found.items() if c < KNOWN_ROUTER_QUERIES.get(n, 0)}
    shrunk |= {n: 0 for n in KNOWN_ROUTER_QUERIES.keys() - found.keys()}
    message = ["Rule: a router gains no query (move it into app/services/)"]
    message += [
        f"  {n}: {c} statements, {KNOWN_ROUTER_QUERIES.get(n, 0)} allowed" for n, c in grown.items()
    ]
    message += [
        f"  {n}: down to {c} — lower its count in KNOWN_ROUTER_QUERIES" for n, c in shrunk.items()
    ]
    assert not grown and not shrunk, "\n".join(message)


def test_a_service_never_imports_a_router():
    """Dependencies point inward: routers → services → models, never back."""
    found = {
        f"{name} -> {node.module}"
        for name, module in MODULES.items()
        if not name.startswith(("app/routers/", "app/main.py"))
        for node in ast.walk(module)
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("app.routers")
    }
    _ratchet("only routers and main import routers", found, {})


# ------------------------------------------------------------------- derived, never stored


def test_no_point_or_standing_is_stored():
    """Points, ranks and tables are computed from ``RaceEntry``'s raw results on every
    read (review 2.1): a stored copy is one that a forgotten recompute — an import, a
    cancellation, a scoring change — leaves wrong. No table holds a standing, and no
    column a point."""
    from app.models import Base

    found = set()
    for table in Base.metadata.tables.values():
        if "standing" in table.name:
            found.add(f"table {table.name}")
        for column in table.columns:
            if column.name in {"points", "net_points", "total_points", "is_discarded", "rank"}:
                found.add(f"{table.name}.{column.name}")
    _ratchet("points and standings are computed, never stored", found, {})


# ------------------------------------------------------------------- the API's words

LOCALES = ROOT / "web" / "src" / "i18n" / "locales"

KNOWN_UNWORDED_CODES: dict[str, str] = {}


def _problem_codes() -> set[str]:
    codes = set()
    for module in MODULES.values():
        for node in ast.walk(module):
            if (
                isinstance(node, ast.Call)
                and getattr(node.func, "id", getattr(node.func, "attr", None)) == "Problem"
                and len(node.args) >= 2
                and isinstance(node.args[1], ast.Constant)
                and isinstance(node.args[1].value, str)
            ):
                codes.add(node.args[1].value)
    return codes


def test_every_problem_the_api_raises_is_worded_in_both_languages():
    """An error is a code; the frontend words it (`errors` namespace, CLAUDE.md "Errors").
    A code with no entry shows the English fallback title to everyone — renaming a code in
    the backend breaks no compile, so this is where it is caught."""
    found = set()
    for language in ("en", "de"):
        worded = json.loads((LOCALES / language / "errors.json").read_text("utf-8"))
        found |= {f"{language}: {code}" for code in _problem_codes() if code not in worded}
    _ratchet("every problem code has a translation", found, KNOWN_UNWORDED_CODES)


# ------------------------------------------------------------------- docs against the model

KNOWN_UNMODELLED_RELATIONS: dict[str, str] = {}


def test_claude_md_names_only_relations_the_model_has():
    """CLAUDE.md's permission rules are read by every agent as fact; `MODEL` is the truth.
    A relation the prose names and the model lacks gets granted, tested and checked for —
    and does nothing."""
    from app.models.auth import MODEL

    relations = set(re.findall(r"define (\w+):", MODEL))
    types = set(re.findall(r"^type (\w+)", MODEL, re.M))
    text = (ROOT / "CLAUDE.md").read_text("utf-8")
    table = text[text.index("## Permissions by area") : text.index("## Tests")]
    # The table's role column — a word there is a relation, or it is wrong.
    named = {
        word
        for row in table.splitlines()
        if row.startswith("| ") and row.count("|") >= 3
        for word in re.findall(r"`([a-z_]+)`", row.split("|")[2])
    }
    found = {word for word in named if word not in relations | types}
    _ratchet("CLAUDE.md names only modelled relations", found, KNOWN_UNMODELLED_RELATIONS)
