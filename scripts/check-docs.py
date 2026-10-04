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
tagged with it and the journeys that walk it — the one page that answers "what proves
this story?", and the gaps where nothing does.

    scripts/check-docs.py         # report, exit 1 on problems
    scripts/check-docs.py --fix   # also rewrite the generated pages and docs/stories.json
    scripts/check-docs.py --new "a sentence stating the rule"
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STORIES = ROOT / "docs" / "userstories"
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
# A journey test's steps: `step("VA-7", …)` in pytest (`api/tests/journeys.py`) and in a
# Playwright `describeJourney` (`e2e/fixtures.ts`) — never Playwright's own `test.step`.
STEP_CALL = re.compile(r"(?<![.\w])step\(\s*\"(?P<id>[A-Z]+-\d+)\"")
E2E_JOURNEY_TITLE = re.compile(r"describeJourney\(\s*\"(?P<ids>J-\d+):")
# In a journey's section: "3. VA-8  …" is a main step, "5a. VA-8  …" a variation.
JOURNEY_STEP = re.compile(r"^(?P<number>\d+)(?P<variant>[a-z]?)\.\s+(?P<id>[A-Z]+-\d+)\s", re.M)

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


FENCE = re.compile(r"^```.*?^```", re.M | re.S)


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


def check_journeys(files: dict[str, str]) -> list[str]:
    """A journey (`J-…`, docs/userstories/journeys.md) is walked by its tests step by step:
    each test's `step(...)` IDs are the main steps, in order; every step is a real story;
    and the journey is ● only when it has a test and every main step's story is ●."""
    markers = {m["id"]: m["marker"] for text in files.values() for m in STORY_HEADING.finditer(text)}
    problems: list[str] = []
    for name, text in files.items():
        for m in STORY_HEADING.finditer(text):
            if not m["id"].startswith("J-"):
                continue
            journey = m["id"]
            following = re.search(r"^### ", text[m.end():], re.M)
            section = text[m.end(): m.end() + following.start()] if following else text[m.end():]
            steps = list(JOURNEY_STEP.finditer(section))
            main = [s["id"] for s in steps if not s["variant"]]
            if not main:
                problems.append(f"{name}: journey {journey} has no numbered steps")
            for step in steps:
                if step["id"] not in markers:
                    problems.append(f"{name}: journey {journey} step {step['number']}{step['variant']} names {step['id']}, which is not a story")
            tests_line = TESTS_LINE.search(section)
            references = REFERENCE.findall(tests_line["body"]) if tests_line else []
            for reference in references:
                region = _test_region(reference)
                if region is None:
                    continue  # check_story_references reports a reference that does not resolve
                walked = [c["id"] for c in STEP_CALL.finditer(region)]
                if walked != main:
                    problems.append(
                        f"{name}: journey {journey} has steps {' → '.join(main)}, "
                        f"but {reference} walks {' → '.join(walked) or 'no step(...) at all'}"
                    )
            weakest = [sid for sid in dict.fromkeys(main) if markers.get(sid) != "●"]
            expected = "○" if not references else ("◐" if weakest else "●")
            if m["marker"] != expected:
                why = (
                    "it has no test" if not references
                    else f"{', '.join(f'{sid} is {markers.get(sid, '?')}' for sid in weakest)}" if weakest
                    else "it has a test and every step is ●"
                )
                problems.append(f"{name}: journey {journey} is marked {m['marker']}, but must be {expected} — {why}")
    return problems


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


def render_traceability(files: dict[str, str]) -> str:
    """docs/traceability.md: one row per story — status, backend tests, browser groups,
    journeys — grouped by the file the story is told in, in the README's order."""
    order = re.findall(r"^\| \[([\w-]+\.md)\]", (STORIES / "README.md").read_text(encoding="utf-8"), re.M)
    names = [n for n in order if n in files] + [n for n in files if n not in order and n != "README.md"]

    browser: dict[str, list[str]] = {}
    journeys: dict[str, list[str]] = {}
    for path in sorted((ROOT / "e2e").glob("*.spec.ts")):
        source = path.read_text(encoding="utf-8")
        for m in E2E_GROUP.finditer(source):
            label = f"{path.name}::{m['title']}"
            for sid in m["ids"].split("/"):
                browser.setdefault(sid, []).append(label)
            if m["kind"] == "Journey":
                region = _test_region(f"e2e/{path.name}::{m['title']}") or ""
                for c in STEP_CALL.finditer(region):
                    browser.setdefault(c["id"], []).append(f"{label} (step)")
    for text in files.values():
        for m in STORY_HEADING.finditer(text):
            if m["id"].startswith("J-"):
                following = re.search(r"^### ", text[m.end():], re.M)
                section = text[m.end(): m.end() + following.start()] if following else text[m.end():]
                for step in JOURNEY_STEP.finditer(section):
                    entry = m["id"] if not step["variant"] else f"{m['id']} (variation)"
                    if entry not in journeys.setdefault(step["id"], []):
                        journeys[step["id"]].append(entry)

    rows: dict[str, list[str]] = {}
    totals = {"●": 0, "◐": 0, "○": 0}
    covered = {"backend": 0, "browser": 0, "journey": 0, "none": 0}
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
            walked = journeys.get(sid, [])
            totals[m["marker"]] += 1
            covered["backend"] += bool(backend)
            covered["browser"] += bool(groups)
            covered["journey"] += bool(walked)
            covered["none"] += not (backend or groups)
            link = f"[{sid}](userstories/{name}#{anchor(m.group(0)[4:])})"
            cell = lambda items: "<br>".join(f"`{i}`" for i in items) or "—"  # noqa: E731
            rows.setdefault(name, []).append(
                f"| {link} | {m['marker']} | {m['title']} | {cell(backend)} | {cell(groups)} | {', '.join(walked) or '—'} |"
            )

    lines = [
        "# Traceability",
        "",
        "Generated by `scripts/check-docs.py --fix` — do not edit by hand; `scripts/check.sh`",
        "fails when it is stale.",
        "",
        "Every story, and what proves it: the backend tests its `Tests:` line names, the browser",
        "test groups tagged with it (`describeStory` / `describeJourney` in `e2e/`), and the",
        "journeys that walk it. The recordings are not here — they exist only after an evidence",
        "run: `pnpm e2e:evidence`, then open `e2e-evidence/traceability.html`, which lists the",
        "same stories with each test's result, video and trace.",
        "",
        f"**{sum(totals.values())} stories** — ● {totals['●']} implemented and tested · "
        f"◐ {totals['◐']} partial · ○ {totals['○']} open. "
        f"With backend tests: {covered['backend']} · with browser tests: {covered['browser']} · "
        f"walked by a journey: {covered['journey']} · **with no test at all: {covered['none']}**.",
    ]
    for name in names:
        if name not in rows:
            continue
        lines += [
            "",
            f"## [{name}](userstories/{name})",
            "",
            "| Story | | Title | Backend tests | Browser tests | Journeys |",
            "|---|---|---|---|---|---|",
            *rows[name],
        ]
    return "\n".join(lines) + "\n"


def render_stories_json(files: dict[str, str]) -> str:
    """docs/stories.json: every story's title, status and place — the file's `#` heading
    (the role) and the `##` heading above it (the phase). Read by the Allure hooks
    (`api/tests/conftest.py`, `e2e/fixtures.ts`) so the report's Behaviors tree is
    role → phase → story without either side parsing Markdown."""
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
    problems += check_links(files)
    problems += check_story_references(files)
    problems += check_test_story_ids(known)
    problems += check_journeys(files)
    gotcha_problems, entries = check_gotchas()
    problems += gotcha_problems

    traceability = render_traceability(files)
    stories_json = render_stories_json(files)
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

    print(f"{len(known)} stories, {len(entries)} gotchas")
    for problem in problems:
        print(f"  ✗ {problem}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
