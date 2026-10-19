#!/usr/bin/env python3
"""Keeps the documentation from lying, and keeps the gotchas readable.

Three jobs, all of them things that went wrong here before:

1. **Every `Tests:` reference in `docs/userstories/` must resolve.** Seventeen of them
   pointed at classes that had been renamed or deleted. A stale reference is worse than
   none: it makes a story look covered when nothing covers it.
2. **Every story ID a test claims must exist.** Tests name their story in the docstring, so
   a story that is renamed without its tests leaves orphans that nobody will find again.
   The stories are one file per role, so an ID must also appear in only one of them, and
   every link from one file into another must land on a heading that exists — a story
   moved to another role's file would otherwise leave a link that scrolls to nothing.
3. **Every note in `docs/gotchas/` must carry its four sections**, Evidence included. A note
   without evidence is a rumour, and a rumour in a folder agents are told to trust is worse
   than an empty folder.

It also regenerates `docs/gotchas/INDEX.md`, which exists so an agent can load ten one-line
rules instead of ten files and still know which one to open, and `docs/traceability.md`:
every story with its status, the backend tests that cover it, the browser test groups
tagged with it, the journey steps that walk it and the help pages that explain it — the
one page that answers "what proves this story?", and the gaps where nothing does — with
one table per journey (`docs/journeys/`), step by step.

    scripts/check-docs.py         # report, exit 1 on problems
    scripts/check-docs.py --fix   # also rewrite the generated pages and docs/stories.json
    scripts/check-docs.py --new "a sentence stating the rule"
    scripts/check-docs.py --handbook-snapshot   # the help's structure baseline, last step of a reviewed run

And it holds the help pages (`web/src/handbook/`, Story B-18) to the stories, the journeys,
the routes and each other — both languages, unique anchors, links that land, the structure
lock against `web/src/handbook/.baseline/`.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from dataclasses import asdict, dataclass, fields, replace
from pathlib import Path
from typing import NamedTuple

ROOT = Path(__file__).resolve().parent.parent
STORIES = ROOT / "docs" / "userstories"
JOURNEYS = ROOT / "docs" / "journeys"
HANDBOOK = ROOT / "web" / "src" / "handbook"
GOTCHAS = ROOT / "docs" / "gotchas"
INDEX = GOTCHAS / "INDEX.md"
TRACEABILITY = ROOT / "docs" / "traceability.md"
STORIES_JSON = ROOT / "docs" / "stories.json"

STORY_HEADING = re.compile(r"^### (?P<id>[A-Z]+-\d+) (?P<marker>[○◐●]) (?P<title>.+)$", re.M)
# A reference looks like `path/to/test.py::Class::test_name`, in backticks, and a line can
# carry several of them plus ordinary prose.
REFERENCE = re.compile(r"`((?:api|e2e)/[\w./-]+(?:::[\w:]+)?)`")
TESTS_LINE = re.compile(r"^Tests: (?P<body>.+?)(?=\n\n|\n### |\Z)", re.M | re.S)
# "Story VA-8", "Stories A-1, A-4 and VA-6", "VA-10:" at the start of a docstring line.
STORY_MENTION = re.compile(r"\b(?:Stor(?:y|ies)\s+)((?:[A-Z]+-\d+)(?:[,\s]+(?:and\s+)?[A-Z]+-\d+)*)")
# An e2e spec names its stories in the title it hands `describeStory` ("VA-8/VA-9: …");
# `e2e/fixtures.ts` turns them into tags, so an unknown one would be a tag for nothing.
E2E_STORY_TITLE = re.compile(r"describeStory\(\s*\"(?P<ids>[A-Z]+-\d+(?:/[A-Z]+-\d+)*):")
# A journey test's steps: `step("J-1.6", …)` in pytest (`api/tests/journeys.py`) and in a
# Playwright `describeJourney` (`e2e/fixtures.ts`) — never Playwright's own `test.step`.
STEP_CALL = re.compile(r"(?<![.\w])step\(\s*\"(?P<id>[A-Z]+-[\d.]+)\"")
E2E_JOURNEY_TITLE = re.compile(r"describeJourney\(\s*\"(?P<ids>J-\d+):")
# A journey file (`docs/journeys/<slug>.md`): its heading, its step table, its diagram.
JOURNEY_HEADING = re.compile(r"^# (?P<id>J-\d+) (?P<marker>[○◐●]) (?P<title>.+)$", re.M)
STEP_ID = re.compile(r"J-\d+\.\d+")
STEP_ROW = re.compile(
    r"^\| (?P<id>J-\d+\.\d+) \| (?P<path>[^|]+?) \| (?P<story>[^|]+?) \| (?P<who>[^|]+?) \| (?P<what>[^|]*?) \|$",
    re.M,
)
# The actors (docs/userstories/journeys.md § Actors): "| club admin | CA | …".
ACTOR_ROW = re.compile(r"^\| (?P<name>[a-z][a-z ]*) \| (?P<alias>[A-Z]+) \|", re.M)
PARTICIPANT = re.compile(r"^\s*(?:actor|participant) (?P<alias>\w+) as (?P<name>.+?)\s*$", re.M)
MERMAID = re.compile(r"^```mermaid\n(?P<body>.*?)^```", re.M | re.S)
RETIRED = re.compile(r"^Retired steps: (?P<body>.+)$", re.M)
# A test that covers one step without walking the journey says so in its docstring:
# "Journey step J-5.6", "Journey steps J-5.2 and J-5.3".
STEP_MENTION = re.compile(r"\bJourney steps?\s+((?:J-\d+\.\d+)(?:(?:[,\s]+|\s+and\s+)J-\d+\.\d+)*)")

REQUIRED_SECTIONS = ("**Symptom**", "**Cause**", "**Rule**", "**Evidence**")

TEMPLATE = """# {rule}

**Symptom** — what it looked like, in the words you would have searched for.

**Cause** — what was actually happening. If you were wrong on the way here, say what misled
you, in one line. That line is the point of this note.

**Rule** — what to do or avoid next time, stated so it applies beyond this one incident.

**Evidence** — the file, command or measurement that proves it.

**Seen** — {date}
"""


# `[text](#anchor)` inside a file, `[text](other.md#anchor)` or `[text](other.md)` across files.
LINK = re.compile(r"\]\((?P<file>[\w-]+\.md)?(?:#(?P<anchor>[\w-]+))?\)")
HEADING = re.compile(r"^#{1,6} (?P<text>.+)$", re.M)


FENCE = re.compile(r"^(?P<ticks>`{3,}).*?^(?P=ticks)$", re.M | re.S)


def story_files() -> dict[str, str]:
    """Filename → text, for every story file in the folder (README included: it links).

    Fenced code is dropped first: the README shows the story format in a fence, and that
    example would otherwise count as a second B-1."""
    return {p.name: FENCE.sub("", p.read_text(encoding="utf-8")) for p in sorted(STORIES.glob("*.md"))}


def story_ids(files: dict[str, str]) -> tuple[set[str], list[str]]:
    """The IDs across all files, and a problem for any ID that appears in two of them."""
    seen: dict[str, str] = {}
    problems: list[str] = []
    for name, text in files.items():
        for m in STORY_HEADING.finditer(text):
            if m["id"] in seen:
                problems.append(f"{name}: story {m['id']} is also in {seen[m['id']]}")
            seen[m["id"]] = name
    return set(seen), problems


def anchor(heading: str) -> str:
    """GitHub's slug: lowercase, punctuation dropped, spaces to hyphens — `A-1 ● Create clubs`
    becomes `a-1--create-clubs`, the double hyphen standing where the marker was."""
    return re.sub(r"[^\w\- ]", "", heading.lower()).replace(" ", "-")


def check_links(files: dict[str, str]) -> list[str]:
    """Every link between the story files must land on a file, and on a heading in it."""
    anchors = {name: {anchor(m["text"]) for m in HEADING.finditer(text)} for name, text in files.items()}
    problems: list[str] = []
    for name, text in files.items():
        for m in LINK.finditer(text):
            target = m["file"] or name
            if target not in anchors:
                problems.append(f"{name} links to {target}, which is not in docs/userstories/")
            elif m["anchor"] and m["anchor"] not in anchors[target]:
                problems.append(f"{name} links to {target}#{m['anchor']}, which is not a heading there")
    return problems


def check_story_references(files: dict[str, str]) -> list[str]:
    """Every `path::Node` under a `Tests:` line must exist on disk and in that file."""
    problems: list[str] = []
    for name, text in files.items():
        for match in TESTS_LINE.finditer(text):
            for reference in REFERENCE.findall(match["body"]):
                path_part, _, node = reference.partition("::")
                path = ROOT / path_part
                if not path.exists():
                    problems.append(f"{name} references a missing file: {reference}")
                    continue
                if not node:
                    continue
                # The last segment is the interesting one: a class or a test function.
                leaf = node.split("::")[-1]
                source = path.read_text(encoding="utf-8")
                if not re.search(rf"\b(?:class|def|test)\b.*\b{re.escape(leaf)}\b", source):
                    problems.append(f"{name} references {reference}, but {leaf} is not in that file")
    return problems


def check_test_story_ids(known: set[str]) -> list[str]:
    """Every story ID a test names in its docstring must be a story that exists."""
    problems: list[str] = []
    for path in sorted((ROOT / "api" / "tests").rglob("test_*.py")) + sorted((ROOT / "e2e").glob("*.spec.ts")):
        text = path.read_text(encoding="utf-8")
        groups = STORY_MENTION.findall(text)
        if path.suffix == ".ts":
            groups += [m.group("ids") for m in E2E_STORY_TITLE.finditer(text)]
            groups += [m.group("ids") for m in E2E_JOURNEY_TITLE.finditer(text)]
        groups += [m.group("id") for m in STEP_CALL.finditer(text)]
        for group in groups:
            for story in re.findall(r"[A-Z]+-\d+", group):
                if story not in known:
                    rel = path.relative_to(ROOT)
                    problems.append(f"{rel} names story {story}, which is not in docs/userstories/")
    return problems


def _test_region(reference: str) -> str | None:
    """The source of the one test a `Tests:` reference names — a pytest function
    (`path::Class::test_x`) or a Playwright journey (`e2e/x.spec.ts::J-1: title`)."""
    path, _, node = reference.partition("::")
    file = ROOT / path
    if not file.is_file() or not node:
        return None
    source = file.read_text(encoding="utf-8")
    if path.endswith(".py"):
        leaf = node.split("::")[-1]
        m = re.search(rf"^(?P<indent>[ \t]*)(?:async )?def {re.escape(leaf)}\(", source, re.M)
        if not m:
            return None
        rest = source[m.end():]
        end = re.search(rf"^[ \t]{{0,{len(m['indent'])}}}(?:async def|def|class) ", rest, re.M)
        return rest[: end.start()] if end else rest
    start = source.find(f'describeJourney("{node}"')
    if start < 0:
        return None
    rest = source[start + 1:]
    end = re.search(r"^(?:describeJourney|describeStory|test\.describe)\(", rest, re.M)
    return rest[: end.start()] if end else rest


class Step(NamedTuple):
    id: str
    path: str
    story: str
    who: str
    what: str

    @property
    def offline(self) -> bool:
        """Happens away from the site — a guardian signing paper — so no test can walk it."""
        return "(offline)" in self.who


class Journey(NamedTuple):
    id: str
    marker: str
    title: str
    file: str  # relative to ROOT
    text: str
    steps: list[Step]
    blocks: list[str]  # each diagram's source: the main path first, then each branch
    participants: list[tuple[str, str]]  # (alias, name) of every `actor`/`participant`
    retired: list[str]
    tests: list[str]  # the references on its `Tests:` line

    @property
    def views(self) -> list[list[str]]:
        """The `[J-n.k]` of every arrow, per diagram, in reading order."""
        return [re.findall(r"\[(J-\d+\.\d+)\]", block) for block in self.blocks]

    @property
    def diagram(self) -> list[str]:
        """The same over all its diagrams."""
        return [sid for view in self.views for sid in view]


def journeys() -> list[Journey]:
    """Every journey in `docs/journeys/`, one per file, in ID order."""
    out: list[Journey] = []
    for path in sorted(JOURNEYS.glob("*.md")):
        if path.name == "README.md":
            continue
        raw = path.read_text(encoding="utf-8")
        heading = JOURNEY_HEADING.search(raw)
        if not heading:
            out.append(Journey("?", "?", path.name, str(path.relative_to(ROOT)), raw, [], [], [], [], []))
            continue
        blocks = [m["body"] for m in MERMAID.finditer(raw)]
        diagrams = "\n".join(blocks)
        text = FENCE.sub("", raw)
        retired = RETIRED.search(text)
        tests_line = TESTS_LINE.search(text)
        out.append(Journey(
            id=heading["id"],
            marker=heading["marker"],
            title=heading["title"],
            file=str(path.relative_to(ROOT)),
            text=text,
            steps=[Step(*(g.strip() for g in m.groups())) for m in STEP_ROW.finditer(text)],
            blocks=blocks,
            participants=[(m["alias"], m["name"]) for m in PARTICIPANT.finditer(diagrams)],
            retired=STEP_ID.findall(retired["body"]) if retired else [],
            tests=REFERENCE.findall(tests_line["body"]) if tests_line else [],
        ))
    return sorted(out, key=lambda j: int(j.id[2:]) if j.id[2:].isdigit() else 0)


def _test_sources() -> list[Path]:
    return sorted((ROOT / "api" / "tests").rglob("test_*.py")) + sorted((ROOT / "e2e").glob("*.spec.ts"))


def step_mentions() -> dict[str, list[str]]:
    """Step ID → the tests that cover it without walking the journey ("Journey step J-5.6"
    in a docstring), each as `file::test` — the test function or class the mention sits in."""
    out: dict[str, list[str]] = {}
    for path in _test_sources():
        source = path.read_text(encoding="utf-8")
        for m in STEP_MENTION.finditer(source):
            owner = None
            for d in re.finditer(r"^[ \t]*(?:async )?(?:def|class) (\w+)", source[: m.start()], re.M):
                owner = d[1]
            label = f"{path.name}::{owner}" if owner else path.name
            for sid in STEP_ID.findall(m[1]):
                if label not in out.setdefault(sid, []):
                    out[sid].append(label)
    return out


def walks(journey: Journey) -> dict[str, list[str]]:
    """Each test on the journey's `Tests:` line → the step IDs it walks, in order."""
    out: dict[str, list[str]] = {}
    for reference in journey.tests:
        region = _test_region(reference)
        if region is not None:  # check_story_references reports one that does not resolve
            out[reference] = [c["id"] for c in STEP_CALL.finditer(region)]
    return out


def check_journeys(markers: dict[str, str], all_journeys: list[Journey], index: str) -> tuple[list[str], list[str]]:
    """A journey (`docs/journeys/<slug>.md`) proves itself: stable step IDs, a diagram that
    shows exactly the table, tests that walk the main path in order, and a status that
    follows from what is tested. Returns (problems, warnings)."""
    problems: list[str] = []
    warnings: list[str] = []
    mentions = step_mentions()
    seen_ids: dict[str, str] = {}
    all_steps = {s.id for j in all_journeys for s in j.steps}
    all_retired = {r for j in all_journeys for r in j.retired}
    actors_section = index.partition("## Actors")[2].partition("\n## ")[0]
    actors = {m["name"]: m["alias"] for m in ACTOR_ROW.finditer(actors_section)}
    if not actors:
        problems.append("docs/userstories/journeys.md: no actor table under '## Actors'")

    def unknown_actors(cell: str) -> list[str]:
        names = re.split(r",\s*|\s+or\s+", cell.replace("(offline)", "").strip())
        return [n for n in (x.strip() for x in names) if n and n not in actors]

    for j in all_journeys:
        where = j.file
        if j.id == "?":
            problems.append(f"{where}: first heading must be '# J-<n> <○|◐|●> <title>'")
            continue
        if j.id in seen_ids:
            problems.append(f"{where}: journey {j.id} is also {seen_ids[j.id]}")
        seen_ids[j.id] = where
        if f"../journeys/{Path(where).name}" not in index:
            problems.append(f"{where}: not listed in docs/userstories/journeys.md")
        if not j.steps:
            problems.append(f"{where}: {j.id} has no step table (| Step | Path | Story | Who | What is then true |)")
            continue

        who = re.search(r"^Who: (?P<body>.+)$", j.text, re.M)
        for name in unknown_actors(who["body"]) if who else ["(no Who: line)"]:
            problems.append(f"{where}: Who: names '{name}', which is not an actor in journeys.md")
        for alias, shown in j.participants:
            name = shown.lower()
            if name not in actors:
                problems.append(f"{where}: the diagram's '{shown}' is not an actor in journeys.md")
            elif alias != actors[name]:
                problems.append(f"{where}: the diagram calls {name} '{alias}', journeys.md '{actors[name]}'")

        ids = [s.id for s in j.steps]
        for sid in {i for i in ids if ids.count(i) > 1}:
            problems.append(f"{where}: step {sid} is in the table twice")
        for s in j.steps:
            if not s.id.startswith(j.id + "."):
                problems.append(f"{where}: step {s.id} does not belong to {j.id}")
            if s.story not in markers or s.story.startswith("J-"):
                problems.append(f"{where}: step {s.id} names {s.story}, which is not a story")
            for name in unknown_actors(s.who):
                problems.append(f"{where}: step {s.id} is done by '{name}', which is not an actor in journeys.md")
        for r in j.retired:
            if r in ids:
                problems.append(f"{where}: step {r} is retired and must not be in the table again")
        # One diagram per way through: the main path first, then each branch on its own.
        # Every step is one arrow in exactly one of them, and each draws its steps in the
        # table's order — the table is the flow, the diagrams are views of it.
        diagram = j.diagram
        missing = [i for i in ids if i not in diagram]
        extra = [i for i in diagram if i not in ids]
        if missing or extra:
            problems.append(
                f"{where}: the diagrams and the table disagree — "
                + "; ".join(filter(None, [
                    missing and f"no arrow for {', '.join(missing)}",
                    extra and f"arrow without a row: {', '.join(extra)}",
                ]))
            )
        for sid in sorted(sid for sid, count in Counter(diagram).items() if count > 1):
            problems.append(f"{where}: step {sid} is drawn twice — each step is an arrow in one diagram")
        position = {s.id: n for n, s in enumerate(j.steps)}
        for n, (view, block) in enumerate(zip(j.views, j.blocks), 1):
            drawn = [sid for sid in view if sid in position]
            ordered = sorted(drawn, key=position.__getitem__)
            if drawn != ordered:
                problems.append(
                    f"{where}: diagram {n} must draw its steps in the table's order: {' → '.join(ordered)}"
                )
            # Mermaid ends a statement at `;` — the rest of the line is a parse error, and
            # GitHub shows the error box instead of the diagram (two journeys did, unnoticed).
            for line in block.splitlines():
                if ";" in line:
                    problems.append(f"{where}: diagram {n} has a ';', which ends a Mermaid line: {line.strip()}")
            if re.search(r"^\s*(?:opt|alt|else)\b", block, re.M):
                problems.append(
                    f"{where}: diagram {n} draws a branch as an opt/alt block — "
                    "give the branch a diagram of its own"
                )
        first = set(j.views[0]) if j.views else set()
        for s in j.steps:
            if s.path == "main" and s.id not in first:
                problems.append(f"{where}: main step {s.id} belongs in the first diagram, the main path")
        if "main" not in {s.path for s in j.steps}:
            problems.append(f"{where}: {j.id} has no step on path main")

        main = [s.id for s in j.steps if s.path == "main" and not s.offline]
        walked: set[str] = set()
        journey_walks = walks(j)
        for reference, sequence in journey_walks.items():
            foreign = [i for i in sequence if i not in position]
            if foreign:
                problems.append(f"{where}: {reference} walks {', '.join(foreign)}, not a step of {j.id}")
                continue
            if [position[i] for i in sequence] != sorted(position[i] for i in set(sequence)):
                problems.append(
                    f"{where}: {reference} walks {' → '.join(sequence)}, which is not the table's order"
                )
            skipped = [i for i in main if i not in sequence]
            if skipped:
                problems.append(f"{where}: {reference} skips the main steps {', '.join(skipped)}")
            walked.update(sequence)

        covered = walked | {s.id for s in j.steps if s.id in mentions}
        uncovered = [s.id for s in j.steps if not s.offline and s.id not in covered]
        weak = list(dict.fromkeys(s.story for s in j.steps if markers.get(s.story) != "●"))
        expected = "○" if not journey_walks else ("●" if not uncovered and not weak else "◐")
        if j.marker != expected:
            why = (
                "no test walks it" if not journey_walks
                else "; ".join(filter(None, [
                    uncovered and f"no test covers {', '.join(uncovered)}",
                    weak and ", ".join(f"{sid} is {markers.get(sid, '?')}" for sid in weak),
                ])) or "it is walked, every step is covered and every story is ●"
            )
            problems.append(f"{where}: {j.id} is marked {j.marker}, but must be {expected} — {why}")
        if journey_walks and uncovered:
            warnings.append(f"{where}: no test covers {', '.join(uncovered)} (walk it, or name 'Journey step …' in a test)")

    for sid, tests in mentions.items():
        if sid in all_retired:
            problems.append(f"{', '.join(tests)} names step {sid}, which is retired")
        elif sid not in all_steps:
            problems.append(f"{', '.join(tests)} names step {sid}, which is in no journey")
    for path in _test_sources():
        for c in STEP_CALL.finditer(path.read_text(encoding="utf-8")):
            if c["id"] in all_retired:
                problems.append(f"{path.relative_to(ROOT)} walks step {c['id']}, which is retired")
            elif c["id"] not in all_steps:
                problems.append(f"{path.relative_to(ROOT)} walks {c['id']}, which is no journey step (J-n.k)")
    return problems, warnings


def check_gotchas() -> tuple[list[str], list[tuple[str, str]]]:
    """Format check, and the (filename, rule) pairs the index is built from."""
    problems: list[str] = []
    entries: list[tuple[str, str]] = []
    for path in sorted(GOTCHAS.glob("*.md")):
        # The folder also holds its own instructions; only the notes are checked.
        if path.name in {"README.md", "INDEX.md", "REFLECT.md"}:
            continue
        text = path.read_text(encoding="utf-8")
        heading = text.splitlines()[0] if text else ""
        if not heading.startswith("# "):
            problems.append(f"{path.name}: first line must be '# <the rule as a sentence>'")
            continue
        missing = [s for s in REQUIRED_SECTIONS if s not in text]
        if missing:
            problems.append(f"{path.name}: missing {', '.join(missing)}")
        entries.append((path.name, heading[2:].strip()))
    return problems, entries


def render_index(entries: list[tuple[str, str]]) -> str:
    lines = [
        "# Gotchas index",
        "",
        "Generated by `scripts/check-docs.py --fix` — do not edit by hand.",
        "",
        "One line per note, so this whole folder can be skimmed for the price of one file.",
        "Open the note whose rule matches what you are about to do, or what just surprised you.",
        "",
    ]
    lines += [f"- [{rule}]({name})" for name, rule in entries]
    lines.append("")
    return "\n".join(lines)


def scaffold(rule: str) -> int:
    from datetime import date

    slug = re.sub(r"[^a-z0-9]+", "-", rule.lower()).strip("-")[:80]
    path = GOTCHAS / f"{slug}.md"
    if path.exists():
        print(f"{path.relative_to(ROOT)} already exists — correct that note rather than adding a second one")
        return 1
    path.write_text(TEMPLATE.format(rule=rule, date=date.today().isoformat()), encoding="utf-8")
    print(f"wrote {path.relative_to(ROOT)} — fill it in, then run scripts/check-docs.py --fix")
    return 0


# A `describeStory("VA-8/VA-9: rest", …)` or `describeJourney("J-1: rest", …)` call, whole.
E2E_GROUP = re.compile(r"describe(?P<kind>Story|Journey)\(\s*\"(?P<title>(?P<ids>[A-Z]+-\d+(?:/[A-Z]+-\d+)*): [^\"]*)\"")
TICKED = re.compile(r"`([^`]+)`")


def _tests_line_references(section: str) -> list[str]:
    """The references under a `Tests:` line, a bare `::TestX` continuing the path before it."""
    match = TESTS_LINE.search(section)
    out: list[str] = []
    path = ""
    for token in TICKED.findall(match["body"]) if match else []:
        if token.startswith("::") and path:
            out.append(path + token)
        elif token.startswith(("api/", "e2e/")):
            path = token.partition("::")[0]
            out.append(token)
    return out


def _short(reference: str) -> str:
    """`api/tests/stories/test_x.py::TestY` → `test_x.py::TestY`; an e2e title stays whole."""
    path, _, node = reference.partition("::")
    return f"{Path(path).name}::{node}" if node else Path(path).name


def handbook_pages() -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """The handbook's pages (`web/src/handbook/<id>.en.md`, the `handbook` skill) by the
    stories and by the journey each cites in its frontmatter — the "auto-documentation"
    end of the chain. Empty until the handbook exists."""
    by_story: dict[str, list[str]] = {}
    by_journey: dict[str, list[str]] = {}
    for path in sorted(HANDBOOK.glob("*.en.md")) if HANDBOOK.is_dir() else []:
        head = path.read_text(encoding="utf-8").split("---")
        meta = head[1] if len(head) > 2 else ""
        page = path.name.removesuffix(".en.md")
        stories = re.search(r"^stories:\s*\[(?P<ids>[^\]]*)\]", meta, re.M)
        for sid in re.findall(r"[A-Z]+-\d+", stories["ids"]) if stories else []:
            by_story.setdefault(sid, []).append(page)
        journey = re.search(r"^journey:\s*(?P<id>J-\d+)", meta, re.M)
        if journey:
            by_journey.setdefault(journey["id"], []).append(page)
    return by_story, by_journey


# --- The handbook (`web/src/handbook/`, the `handbook` skill, Story B-18) -------------------
#
# The help pages are derived from the stories and journeys, so they rot the same way: a story
# renamed, a route moved, an anchor another page links to dropped, one locale forgotten. The
# rules are `.claude/skills/handbook/references/checks.md`; each was broken on purpose once.

# The help is for signed-in people only — the public site has to explain itself (decided
# 2026-10-18), so visitors are no audience and `visitor.md`'s stories need no help page.
AUDIENCES = ("sailor", "club", "event-organizer", "race-committee", "treasurer", "administration")
PAGE_TYPES = ("start", "guide", "journey", "doc", "faq")
LOCALES = ("en", "de")
BASELINE = HANDBOOK / ".baseline" / "structure.json"
SCREENSHOTS = ROOT / "web" / "public" / "handbook" / "screenshots"
APP_TSX = ROOT / "web" / "src" / "App.tsx"
PLACES_TS = HANDBOOK / "places.ts"
# One entry of `PLACES` in places.ts: `"club.money": { path: "/me/club/:id", tab: "money" },`
PLACE_ENTRY = re.compile(r'^\s*"(?P<id>[a-z0-9.-]+)":\s*\{\s*path:\s*"(?P<path>[^"]+)"(?:,\s*tab:\s*"(?P<tab>[^"]+)")?', re.M)
PLACE_LINK = "place:"
PAGE_FILE = re.compile(r"^(?P<id>[a-z0-9-]+)\.(?P<locale>[a-z]{2})\.md$")
FRONTMATTER = re.compile(r"\A---\n(?P<meta>.*?)\n---\n(?P<body>.*)\Z", re.S)
META_LINE = re.compile(r"^(?P<key>[a-z_]+):\s*(?P<value>.*)$")
ANCHORED = re.compile(r"^#{2,4} .*?\{#(?P<anchor>[a-z0-9-]+)\}\s*$", re.M)
H3 = re.compile(r"^### (?P<text>.+)$", re.M)
MD_LINK = re.compile(r"\]\((?P<target>[^)\s]+)\)")
SHOT = re.compile(r"\(shot:(?P<id>[\w-]+)\)")
PAGE_STEP = re.compile(r"^\| *(?P<id>J-\d+\.\d+) *\|", re.M)
BUDGET = {"start": 250, "guide": 350, "journey": 300, "doc": 450, "faq": 600}
# Which story file tells which audience's stories (`references/sources.md`).
STORY_FILE_AUDIENCE = {"sailor.md": "sailor", "club.md": "club",
                       "event-organizer.md": "event-organizer", "race-committee.md": "race-committee",
                       "treasurer.md": "treasurer", "administration.md": "administration"}


class ReservedPage(NamedTuple):
    """A page other code links to: its id, type and anchors are fixed (`content-model.md`)."""
    id: str
    type: str
    anchors: tuple[str, ...]


RESERVED = (ReservedPage("roles", "doc", ("roles-list", "roles-matrix", "roles-getting")),
            ReservedPage("terms", "doc", ("terms-competition", "terms-people", "terms-event-states")))


@dataclass(frozen=True)
class Frontmatter:
    """The restricted frontmatter the viewer reads — flat `key: value`, `[a, b]` lists. Every
    field but `title` is identical in both locales, which is why this is a value: two of
    them compare with `==` once the title is set aside."""
    id: str | None = None
    type: str | None = None
    order: int | None = None
    audience: tuple[str, ...] = ()
    stories: tuple[str, ...] = ()
    journey: str | None = None
    route: str | None = None
    tags: tuple[str, ...] = ()
    title: str | None = None

    def without_title(self) -> Frontmatter:
        return replace(self, title=None)


FRONTMATTER_FIELDS = {f.name for f in fields(Frontmatter)}
REQUIRED_FIELDS = ("type", "order", "audience", "title")


class Page(NamedTuple):
    id: str
    locale: str
    file: str
    meta: Frontmatter
    present: frozenset[str]  # the keys the file actually wrote, to tell "missing" from "null"
    body: str

    @property
    def prose(self) -> str:
        return FENCE.sub("", self.body)

    @property
    def anchors(self) -> list[str]:
        return ANCHORED.findall(self.prose)

    @property
    def shots(self) -> list[str]:
        return sorted(SHOT.findall(self.prose))

    @property
    def words(self) -> int:
        """Counted without tables, which the budget counts lightly."""
        lines = [line for line in self.prose.splitlines() if not line.lstrip().startswith("|")]
        return len(re.findall(r"\w+", " ".join(lines)))


class Store(NamedTuple):
    pages: list[Page]
    problems: list[str]


class Findings(NamedTuple):
    """Problems fail the gate; warnings are printed after them and never do."""
    problems: list[str]
    warnings: list[str]


class Slot(NamedTuple):
    """A page's position: `order` is unique within its type."""
    type: str | None
    order: int | None


@dataclass(frozen=True)
class PageShape:
    """What the structure lock compares — never the prose, which may change freely."""
    type: str | None
    order: int | None
    audience: tuple[str, ...]
    anchors: tuple[str, ...]
    locales: tuple[str, ...]


Structure = dict[str, PageShape]  # page id → its shape
StoryMarkers = dict[str, str]  # story id → ○ ◐ ●
StoryFiles = dict[str, str]  # file name in docs/userstories/ → its text


def _meta_value(raw: str) -> str | int | tuple[str, ...] | None:
    raw = raw.strip()
    if raw.startswith("[") and raw.endswith("]"):
        return tuple(part.strip().strip("\"'") for part in raw[1:-1].split(",") if part.strip())
    if raw in ("null", ""):
        return None
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "\"'":
        return raw[1:-1]
    return int(raw) if raw.isdigit() else raw


def handbook_store() -> Store:
    """Every `<id>.<locale>.md` in the store, parsed the way the viewer parses it — a page
    this cannot read, the viewer cannot either."""
    store = Store([], [])
    for path in sorted(HANDBOOK.glob("*.md")) if HANDBOOK.is_dir() else []:
        rel = str(path.relative_to(ROOT))
        name = PAGE_FILE.match(path.name)
        if not name or name["locale"] not in LOCALES:
            store.problems.append(f"{rel}: a page is named <id>.<{'|'.join(LOCALES)}>.md")
            continue
        m = FRONTMATTER.match(path.read_text(encoding="utf-8"))
        if not m:
            store.problems.append(f"{rel}: no frontmatter between two '---' lines")
            continue
        values: dict[str, str | int | tuple[str, ...] | None] = {}
        for line in m["meta"].splitlines():
            field = META_LINE.match(line)
            if not field or field["key"] not in FRONTMATTER_FIELDS:
                store.problems.append(f"{rel}: frontmatter line the viewer cannot read: {line!r}")
                continue
            values[field["key"]] = _meta_value(field["value"])
        try:
            meta = Frontmatter(**values)  # type: ignore[arg-type]
        except TypeError as e:
            store.problems.append(f"{rel}: frontmatter: {e}")
            continue
        store.pages.append(Page(name["id"], name["locale"], rel, meta, frozenset(values), m["body"]))
    return store


def app_routes() -> list[str]:
    """The route patterns of `web/src/App.tsx`, as absolute paths. Every route there is
    written relative to a layout route without a path, so `/` + the path is the URL."""
    if not APP_TSX.exists():
        return []
    text = APP_TSX.read_text(encoding="utf-8")
    # The catch-all `*` redirects whatever nothing else matches; counting it would let
    # every link pass, so it is left out.
    routes = ["/"] + ["/" + p for p in re.findall(r'<Route\s+path="([^"]+)"', text) if p != "*"]
    # A league's pages are one list, `LEAGUE_ROUTES`, rendered under `:league` (and the
    # old `dsbl`): `[sub, <Page />]` entries, `""` being the league's own page.
    table = re.search(r"const LEAGUE_ROUTES[^=]*=\s*\[(.*?)\n\];", text, re.S)
    for sub in re.findall(r'\[\s*"([^"]*)"\s*,', table.group(1)) if table else []:
        routes += [f"/:league/{sub}" if sub else "/:league", f"/dsbl/{sub}" if sub else "/dsbl"]
    return routes


def _matches_route(path: str, patterns: list[str]) -> bool:
    segments = [s for s in path.split("?")[0].split("#")[0].split("/") if s]
    for pattern in patterns:
        parts = [s for s in pattern.split("/") if s]
        wildcard = bool(parts) and parts[-1] == "*"
        fixed = parts[:-1] if wildcard else parts
        if (len(segments) >= len(fixed) if wildcard else len(segments) == len(fixed)) and all(
            p.startswith(":") or p == s for p, s in zip(fixed, segments)
        ):
            return True
    return False


def _known_route(path: str, routes: list[str]) -> bool:
    """A path the site has. A pattern of placeholders only (`/:league`,
    `/:league/:year/:act`) matches any path of its length, so it proves nothing: the path
    must then be that pattern itself, as a page's `route:` is written."""
    literal = [r for r in routes if any(not s.startswith(":") for s in r.split("/") if s)]
    return path in routes or path == "/" or _matches_route(path, literal)


def handbook_structure(pages: list[Page]) -> Structure:
    locales: dict[str, set[str]] = {}
    for page in pages:
        locales.setdefault(page.id, set()).add(page.locale)
    return {
        page.id: PageShape(page.meta.type, page.meta.order, page.meta.audience,
                           tuple(sorted(page.anchors)), tuple(sorted(locales[page.id])))
        for page in sorted(pages, key=lambda p: p.id)
        if page.locale == "en"
    }


def read_baseline() -> Structure | None:
    if not BASELINE.exists():
        return None
    raw = json.loads(BASELINE.read_text(encoding="utf-8"))
    return {pid: PageShape(s["type"], s["order"], tuple(s["audience"]), tuple(s["anchors"]), tuple(s["locales"]))
            for pid, s in raw.items()}


def write_baseline(structure: Structure) -> None:
    BASELINE.parent.mkdir(parents=True, exist_ok=True)
    BASELINE.write_text(json.dumps({pid: asdict(shape) for pid, shape in structure.items()},
                                   ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def _places_named(page: Page) -> list[str]:
    """The `place:<id>` links of a page, in order — a translation names the same places."""
    return [m["target"][len(PLACE_LINK):] for m in MD_LINK.finditer(page.prose) if m["target"].startswith(PLACE_LINK)]


def _check_locales(pid: str, en: Page, others: list[Page]) -> list[str]:
    """Both locales are one page: same frontmatter but the title, same anchors, same shots."""
    problems: list[str] = []
    for other in others:
        if other.meta.without_title() != en.meta.without_title():
            a, b = asdict(en.meta.without_title()), asdict(other.meta.without_title())
            diff = sorted(k for k in a if a[k] != b[k])
            problems.append(f"{other.file}: frontmatter differs from {en.file} in {', '.join(diff)} — only the title may")
        if sorted(other.anchors) != sorted(en.anchors):
            problems.append(f"{other.file}: anchors differ from {en.file}: {sorted(set(other.anchors) ^ set(en.anchors))}")
        if other.shots != en.shots:
            problems.append(f"{other.file}: screenshots differ from {en.file}")
        if _places_named(other) != _places_named(en):
            problems.append(f"{other.file}: places differ from {en.file} — {', '.join(_places_named(other))} "
                            f"against {', '.join(_places_named(en))}")
    return problems


def _check_journey_page(page: Page, journey: Journey) -> list[str]:
    """The step table lists the journey's main steps, in the journey's order."""
    listed = [m["id"] for m in PAGE_STEP.finditer(page.prose)]
    main = [s.id for s in journey.steps if s.path == "main"]
    problems: list[str] = []
    if [sid for sid in listed if sid in main] != main:
        problems.append(f"{page.file}: the step table must list {journey.id}'s main steps in order "
                        f"({', '.join(main)}), it lists {', '.join(sid for sid in listed if sid in main) or 'none'}")
    unknown = [sid for sid in listed if sid not in {s.id for s in journey.steps}]
    if unknown:
        problems.append(f"{page.file}: {', '.join(unknown)} are not steps of {journey.id}")
    return problems


class PlaceRoute(NamedTuple):
    """Where a place of places.ts leads: the route as App.tsx writes it, and its `?tab=`."""
    path: str
    tab: str | None


def handbook_places() -> dict[str, PlaceRoute]:
    """The places a page may link to (`place:<id>`, Story B-18), read from `PLACES` in
    web/src/handbook/places.ts."""
    if not PLACES_TS.exists():
        return {}
    text = PLACES_TS.read_text(encoding="utf-8")
    table = re.search(r"export const PLACES = \{(.*?)\n\}", text, re.S)
    return {m["id"]: PlaceRoute(m["path"], m["tab"]) for m in PLACE_ENTRY.finditer(table.group(1) if table else "")}


def _covering_places(target: str, places: dict[str, PlaceRoute]) -> list[str]:
    """The places a raw link's address is one of — those with its `?tab=` first, if any."""
    on_path = sorted(pid for pid, place in places.items() if _matches_route(target, [place.path]))
    tab = re.search(r"[?&]tab=([\w-]+)", target)
    exact = [pid for pid in on_path if places[pid].tab == (tab[1] if tab else None)]
    return exact or on_path


def _check_body(page: Page, owners: dict[str, str], routes: list[str], places: dict[str, PlaceRoute]) -> list[str]:
    """Headings carry their anchors, and every link lands: on an anchor some page owns, on
    a place places.ts declares, or on a route the site has that no place covers — a place
    is resolved per reader and survives a renamed route or tab, a raw address does not."""
    problems: list[str] = []
    for m in H3.finditer(page.prose):
        if "{#" not in m["text"]:
            problems.append(f"{page.file}: '### {m['text']}' has no {{#anchor}}")
    for a in page.anchors:
        if not a.startswith(page.id + "-"):
            problems.append(f"{page.file}: anchor #{a} must start with the page id ({page.id}-)")
    if re.search(r"^# ", page.prose, re.M):
        problems.append(f"{page.file}: a page has no '# ' heading — the site's header is the page's h1")
    if re.search(r"<[a-zA-Z][^>]*>", page.prose):
        problems.append(f"{page.file}: raw HTML — the viewer renders markdown only")
    for m in MD_LINK.finditer(page.prose):
        target = m["target"]
        if target.startswith("#") and target[1:] not in owners:
            problems.append(f"{page.file}: link to {target}, which no page owns")
        elif target.startswith(PLACE_LINK) and target[len(PLACE_LINK):] not in places:
            problems.append(f"{page.file}: link to {target}, which is not a place in web/src/handbook/places.ts")
        elif target.startswith("/") and not _known_route(target, routes):
            problems.append(f"{page.file}: link to {target}, which is not a route in web/src/App.tsx")
        elif target.startswith("/"):
            covering = _covering_places(target, places)
            if covering:
                problems.append(f"{page.file}: link to {target} — name the place instead "
                                f"({', '.join('place:' + pid for pid in covering)}), so it is resolved per reader")
    return problems


def _check_lock(before: Structure, now: Structure) -> list[str]:
    """`content-model.md` § Structure lock: pages may be added and rewritten, never silently
    restructured — they are bookmarked and linked from mails."""
    problems: list[str] = []
    for pid, old in before.items():
        where = f"web/src/handbook/{pid}"
        new = now.get(pid)
        if not new:
            problems.append(f"{where}: removed-page — a page in the baseline is gone (a rename is a removal)")
            continue
        if old.order != new.order:
            problems.append(f"{where}: reorder — order was {old.order}, is {new.order}")
        if old.type != new.type:
            problems.append(f"{where}: retype — type was {old.type}, is {new.type}")
        problems += [f"{where}: lost-anchor — #{a} is in the baseline" for a in sorted(set(old.anchors) - set(new.anchors))]
        problems += [f"{where}: lost-locale — {loc}" for loc in sorted(set(old.locales) - set(new.locales))]
        problems += [f"{where}: audience-dropped — {a}" for a in sorted(set(old.audience) - set(new.audience))]
    return problems


def check_handbook(markers: StoryMarkers, all_journeys: list[Journey], files: StoryFiles) -> Findings:
    store = handbook_store()
    found = Findings(list(store.problems), [])
    if not store.pages:
        return found
    problems, warnings = found
    by_id: dict[str, dict[str, Page]] = {}
    for page in store.pages:
        by_id.setdefault(page.id, {})[page.locale] = page
    routes = app_routes()
    places = handbook_places()
    if not places:
        problems.append(f"{PLACES_TS.relative_to(ROOT)}: no PLACES found — the help's links into the site come from there")
    problems += [f"{PLACES_TS.relative_to(ROOT)}: place {pid} leads to {path}, which is not a route in web/src/App.tsx"
                 for pid, (path, _tab) in places.items() if not _known_route(path, routes)]
    owners: dict[str, str] = {pid: pid for pid in by_id}  # anchor → the page that owns it
    for page in store.pages:
        if page.locale != "en":
            continue
        for a in page.anchors:
            if a in owners:
                problems.append(f"{page.file}: anchor #{a} is also on page {owners[a]}")
            owners[a] = page.id
    journeys_by_id = {j.id: j for j in all_journeys}
    slots: dict[Slot, str] = {}
    route_owners: dict[str, str] = {}
    shots_used: set[str] = set()

    for pid, locales in sorted(by_id.items()):
        problems += [f"web/src/handbook/{pid}.{loc}.md is missing — every page exists in {', '.join(LOCALES)}"
                     for loc in LOCALES if loc not in locales]
        en = locales.get("en") or next(iter(locales.values()))
        problems += _check_locales(pid, en, [p for p in locales.values() if p is not en])
        meta = en.meta
        if meta.id != pid:
            problems.append(f"{en.file}: id is {meta.id!r}, the file name says {pid!r}")
        problems += [f"{en.file}: frontmatter has no {key}" for key in REQUIRED_FIELDS if key not in en.present]
        if meta.type not in PAGE_TYPES:
            problems.append(f"{en.file}: type {meta.type!r} is not one of {', '.join(PAGE_TYPES)}")
        problems += [f"{en.file}: audience {a!r} is not one of {', '.join(AUDIENCES)}"
                     for a in meta.audience if a not in AUDIENCES]
        if meta.type == "guide" and len(meta.audience) != 1:
            problems.append(f"{en.file}: a guide is written for exactly one audience, not {list(meta.audience)}")
        slot = Slot(meta.type, meta.order)
        if not isinstance(meta.order, int) or meta.order % 10:
            problems.append(f"{en.file}: order must be a multiple of 10")
        elif slot in slots:
            problems.append(f"{en.file}: order {meta.order} is also {slots[slot]}'s")
        else:
            slots[slot] = pid
        if meta.route:
            if not _known_route(meta.route, routes):
                problems.append(f"{en.file}: route {meta.route} is not a route in web/src/App.tsx")
            elif meta.route in route_owners:
                problems.append(f"{en.file}: route {meta.route} is also {route_owners[meta.route]}'s — one page per route")
            else:
                route_owners[meta.route] = pid
        problems += [f"{en.file}: story {sid} is not in docs/userstories/" for sid in meta.stories if sid not in markers]
        cited = [markers[s] for s in meta.stories if s in markers]
        if cited and all(m == "○" for m in cited):
            problems.append(f"{en.file}: cites only stories marked ○ — it documents nothing that exists")
        half = [s for s in meta.stories if markers.get(s) == "◐"]
        if half:
            warnings.append(f"{en.file}: cites ◐ {', '.join(half)} — check it documents only the built part")
        if meta.type == "journey":
            journey = journeys_by_id.get(meta.journey or "")
            if not journey:
                problems.append(f"{en.file}: journey {meta.journey!r} is not a journey in docs/journeys/")
            else:
                for page in locales.values():
                    problems += _check_journey_page(page, journey)
        elif meta.journey:
            problems.append(f"{en.file}: only a journey page names a journey")
        for page in locales.values():
            problems += _check_body(page, owners, routes, places)
            shots_used.update(page.shots)
        budget = BUDGET.get(meta.type or "")
        if budget and en.words > budget * 1.2:
            warnings.append(f"{en.file}: {en.words} words, budget {budget} for a {meta.type}")

    in_use = {a for p in store.pages for a in p.meta.audience}
    problems += [f"web/src/handbook/start-{a}.en.md is missing — every audience in use has a start page"
                 for a in sorted(in_use) if f"start-{a}" not in by_id]
    for reserved in RESERVED:
        page = by_id.get(reserved.id, {}).get("en")
        if not page:
            problems.append(f"web/src/handbook/{reserved.id}.en.md is missing — a reserved page other code links to")
            continue
        if page.meta.type != reserved.type:
            problems.append(f"{page.file}: a reserved page of type {reserved.type}")
        problems += [f"{page.file}: reserved anchor #{a} is missing" for a in reserved.anchors if a not in page.anchors]

    cited_anywhere = {s for p in store.pages for s in p.meta.stories}
    for name, audience in STORY_FILE_AUDIENCE.items():
        if audience in in_use:
            warnings += [f"story {m['id']} ● ({name}) is cited by no help page — a task nobody explains yet"
                         for m in STORY_HEADING.finditer(files.get(name, ""))
                         if m["marker"] == "●" and m["id"] not in cited_anywhere]

    pngs = {p.name for p in SCREENSHOTS.glob("*.png")} if SCREENSHOTS.is_dir() else set()
    warnings += [f"screenshot {shot} has no PNG under web/public/handbook/screenshots/"
                 for shot in sorted(shots_used) if not any(n.startswith(f"{shot}_") for n in pngs)]
    warnings += [f"web/public/handbook/screenshots/{name} is used by no page"
                 for name in sorted(pngs) if re.sub(r"_(en|de)(_phone)?\.png$", "", name) not in shots_used]

    before = read_baseline()
    if before is not None:
        problems += _check_lock(before, handbook_structure(store.pages))
    return found


def render_traceability(files: dict[str, str], all_journeys: list[Journey]) -> str:
    """docs/traceability.md: one row per story — status, backend tests, browser groups,
    journey steps, help pages — grouped by the file the story is told in, in the README's
    order; then one table per journey, step by step."""
    order = re.findall(r"^\| \[([\w-]+\.md)\]", (STORIES / "README.md").read_text(encoding="utf-8"), re.M)
    names = [n for n in order if n in files] + [n for n in files if n not in order and n != "README.md"]
    step_story = {s.id: s.story for j in all_journeys for s in j.steps}
    help_by_story, help_by_journey = handbook_pages()

    browser: dict[str, list[str]] = {}
    for path in sorted((ROOT / "e2e").glob("*.spec.ts")):
        source = path.read_text(encoding="utf-8")
        for m in E2E_GROUP.finditer(source):
            label = f"{path.name}::{m['title']}"
            for sid in m["ids"].split("/"):
                browser.setdefault(sid, []).append(label)
            if m["kind"] == "Journey":
                region = _test_region(f"e2e/{path.name}::{m['title']}") or ""
                for c in STEP_CALL.finditer(region):
                    story = step_story.get(c["id"])
                    if story and f"{label} (step)" not in browser.setdefault(story, []):
                        browser[story].append(f"{label} (step)")
    walked_in: dict[str, list[str]] = {}
    for j in all_journeys:
        for s in j.steps:
            walked_in.setdefault(s.story, []).append(s.id)

    rows: dict[str, list[str]] = {}
    totals = {"●": 0, "◐": 0, "○": 0}
    covered = {"backend": 0, "browser": 0, "journey": 0, "none": 0}
    cell = lambda items: "<br>".join(f"`{i}`" for i in items) or "—"  # noqa: E731
    for name in names:
        text = files[name]
        for m in STORY_HEADING.finditer(text):
            sid = m["id"]
            following = re.search(r"^### ", text[m.end():], re.M)
            section = text[m.end(): m.end() + following.start()] if following else text[m.end():]
            references = _tests_line_references(section)
            backend = list(dict.fromkeys(_short(r) for r in references if r.startswith("api/")))
            groups = list(dict.fromkeys(
                [_short(r) for r in references if r.startswith("e2e/")] + browser.get(sid, [])
            ))
            walked = walked_in.get(sid, [])
            totals[m["marker"]] += 1
            covered["backend"] += bool(backend)
            covered["browser"] += bool(groups)
            covered["journey"] += bool(walked)
            covered["none"] += not (backend or groups)
            link = f"[{sid}](userstories/{name}#{anchor(m.group(0)[4:])})"
            rows.setdefault(name, []).append(
                f"| {link} | {m['marker']} | {m['title']} | {cell(backend)} | {cell(groups)} "
                f"| {', '.join(walked) or '—'} | {cell(help_by_story.get(sid, []))} |"
            )

    lines = [
        "# Traceability",
        "",
        "Generated by `scripts/check-docs.py --fix` — do not edit by hand; `scripts/check.sh`",
        "fails when it is stale.",
        "",
        "The chain is **journey → story → tests → help → report**. Every journey step names one",
        "story; every story names the backend tests on its `Tests:` line and is tagged by the",
        "browser groups (`describeStory` / `describeJourney` in `e2e/`); the help pages",
        "(`web/src/handbook/`) cite the stories and journeys they explain; and the Allure report",
        "(`scripts/allure-report.sh`) shows each test's last result under the same story and",
        "journey names, a journey's walk with one Allure step per journey step. Results are not",
        "here — this page says what *exists*, the report what *passed*.",
        "",
        f"**{sum(totals.values())} stories** — ● {totals['●']} implemented and tested · "
        f"◐ {totals['◐']} partial · ○ {totals['○']} open. "
        f"With backend tests: {covered['backend']} · with browser tests: {covered['browser']} · "
        f"walked by a journey: {covered['journey']} · **with no test at all: {covered['none']}**.",
    ]

    if all_journeys:
        mentions = step_mentions()
        lines += ["", "## Journeys", ""]
        lines += [f"- [{j.id} {j.marker} {j.title}](#{anchor(f'{j.id} {j.marker} {j.title}')})" for j in all_journeys]
        for j in all_journeys:
            journey_walks = walks(j)
            markers = {sid: mk for t in files.values() for sid, mk in ((x["id"], x["marker"]) for x in STORY_HEADING.finditer(t))}
            lines += [
                "",
                f"### {j.id} {j.marker} {j.title}",
                "",
                f"[{Path(j.file).name}]({Path(j.file).relative_to('docs')}) · "
                f"help: {', '.join(f'`{p}`' for p in help_by_journey.get(j.id, [])) or '—'} · "
                f"report: Allure → story *{j.id} · {j.title}*, one step per row below",
                "",
            ]
            names = {r: f"W{n}" for n, r in enumerate(journey_walks, 1)}
            lines += [f"- **{names[r]}** `{_short(r)}`" for r in journey_walks] or ["- no walk yet"]
            lines += [
                "",
                "| Step | Path | Story | | Walked by | Also covered by | Help |",
                "|---|---|---|---|---|---|---|",
            ]
            for s in j.steps:
                by = [names[r] for r, seq in journey_walks.items() if s.id in seq]
                also = mentions.get(s.id, [])
                walked_cell = "*(offline)*" if s.offline else (", ".join(by) or "—")
                lines.append(
                    f"| {s.id} | {s.path} | {s.story} | {markers.get(s.story, '?')} | {walked_cell} "
                    f"| {cell(also)} | {cell(help_by_story.get(s.story, []))} |"
                )
    for name in names:
        if name not in rows:
            continue
        lines += [
            "",
            f"## [{name}](userstories/{name})",
            "",
            "| Story | | Title | Backend tests | Browser tests | Journey steps | Help |",
            "|---|---|---|---|---|---|---|",
            *rows[name],
        ]
    return "\n".join(lines) + "\n"


def render_stories_json(files: dict[str, str], all_journeys: list[Journey]) -> str:
    """docs/stories.json: every story's title, status and place — the file's `#` heading
    (the role) and the `##` heading above it (the phase) — every journey, and every journey
    step with its story. Read by the Allure hooks (`api/tests/conftest.py`,
    `e2e/fixtures.ts`) and by `step()`, so the report's tree is role → phase → story and a
    step reads "J-5.4 · V-2: …" without either side parsing Markdown."""
    out: dict[str, dict[str, str]] = {}
    for name, text in files.items():
        if name == "README.md":
            continue
        role = next((m["text"] for m in HEADING.finditer(text) if text[m.start():].startswith("# ")), name)
        for m in STORY_HEADING.finditer(text):
            phases = [h for h in re.finditer(r"^## (?P<text>.+)$", text[: m.start()], re.M)]
            out[m["id"]] = {
                "title": m["title"],
                "status": m["marker"],
                "role": role,
                "phase": phases[-1]["text"] if phases else role,
                "file": f"docs/userstories/{name}",
                "anchor": anchor(m.group(0)[4:]),
            }
    for j in all_journeys:
        out[j.id] = {
            "title": j.title,
            "status": j.marker,
            "role": "Journeys",
            "phase": "Journeys",
            "file": j.file,
            "anchor": "",
        }
        for s in j.steps:
            out[s.id] = {"journey": j.id, "story": s.story, "path": s.path, "who": s.who, "what": s.what}
    return json.dumps(dict(sorted(out.items())), ensure_ascii=False, indent=1) + "\n"


def main(argv: list[str]) -> int:
    if "--new" in argv:
        rule = " ".join(argv[argv.index("--new") + 1:]).strip()
        if not rule:
            print('usage: scripts/check-docs.py --new "a sentence stating the rule"')
            return 2
        return scaffold(rule)

    files = story_files()
    known, problems = story_ids(files)
    all_journeys = journeys()
    markers = {m["id"]: m["marker"] for text in files.values() for m in STORY_HEADING.finditer(text)}
    problems += check_links(files)
    problems += check_story_references({**files, **{j.file: j.text for j in all_journeys}})
    problems += check_test_story_ids(known | {j.id for j in all_journeys})
    journey_problems, warnings = check_journeys(markers, all_journeys, files.get("journeys.md", ""))
    problems += journey_problems
    gotcha_problems, entries = check_gotchas()
    problems += gotcha_problems
    handbook = check_handbook(markers, all_journeys, files)
    problems += handbook.problems
    warnings = [*warnings, *handbook.warnings]

    if "--handbook-snapshot" in argv:
        if problems:
            print("not writing the handbook baseline while there are problems:")
            for problem in problems:
                print(f"  ✗ {problem}")
            return 1
        write_baseline(handbook_structure(handbook_store().pages))
        print(f"wrote {BASELINE.relative_to(ROOT)}")
        return 0

    traceability = render_traceability(files, all_journeys)
    stories_json = render_stories_json(files, all_journeys)
    if "--fix" in argv:
        STORIES_JSON.write_text(stories_json, encoding="utf-8")
        print(f"wrote {STORIES_JSON.relative_to(ROOT)}")
        INDEX.write_text(render_index(entries), encoding="utf-8")
        print(f"wrote {INDEX.relative_to(ROOT)} ({len(entries)} notes)")
        TRACEABILITY.write_text(traceability, encoding="utf-8")
        print(f"wrote {TRACEABILITY.relative_to(ROOT)}")
    else:
        if INDEX.exists() and INDEX.read_text(encoding="utf-8") != render_index(entries):
            problems.append("docs/gotchas/INDEX.md is out of date — run scripts/check-docs.py --fix")
        if not STORIES_JSON.exists() or STORIES_JSON.read_text(encoding="utf-8") != stories_json:
            problems.append("docs/stories.json is out of date — run scripts/check-docs.py --fix")
        if not TRACEABILITY.exists() or TRACEABILITY.read_text(encoding="utf-8") != traceability:
            problems.append("docs/traceability.md is out of date — run scripts/check-docs.py --fix")

    print(f"{len(known)} stories, {len(all_journeys)} journeys, {len(entries)} gotchas")
    for problem in problems:
        print(f"  ✗ {problem}")
    # Warnings never fail the gate, and are printed after the problems so they never hide one.
    for warning in warnings:
        print(f"  ! {warning}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
