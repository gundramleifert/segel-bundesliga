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
"""

from __future__ import annotations

import json
import re
import sys
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
# The actors (docs/userstories/journeys.md § Actors): "| club manager | CM | …".
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
    diagram: list[str]  # the `[J-n.k]` of every arrow, in reading order
    participants: list[tuple[str, str]]  # (alias, name) of every `actor`/`participant`
    retired: list[str]
    tests: list[str]  # the references on its `Tests:` line


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
        diagrams = "\n".join(m["body"] for m in MERMAID.finditer(raw))
        diagram = re.findall(r"\[(J-\d+\.\d+)\]", diagrams)
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
            diagram=diagram,
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
        if j.diagram != ids:
            missing = [i for i in ids if i not in j.diagram]
            extra = [i for i in j.diagram if i not in ids]
            if missing or extra:
                problems.append(
                    f"{where}: the diagram and the table disagree — "
                    + "; ".join(filter(None, [
                        missing and f"no arrow for {', '.join(missing)}",
                        extra and f"arrow without a row: {', '.join(extra)}",
                    ]))
                )
            else:
                problems.append(
                    f"{where}: the table must list the steps in the diagram's order: "
                    f"{' → '.join(j.diagram)}"
                )
        if "main" not in {s.path for s in j.steps}:
            problems.append(f"{where}: {j.id} has no step on path main")

        position = {s.id: n for n, s in enumerate(j.steps)}
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
