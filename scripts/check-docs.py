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
rules instead of ten files and still know which one to open.

    scripts/check-docs.py         # report, exit 1 on problems
    scripts/check-docs.py --fix   # also rewrite the index
    scripts/check-docs.py --new "a sentence stating the rule"
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STORIES = ROOT / "docs" / "userstories"
GOTCHAS = ROOT / "docs" / "gotchas"
INDEX = GOTCHAS / "INDEX.md"

STORY_HEADING = re.compile(r"^### (?P<id>[A-Z]+-\d+) (?P<marker>[○◐●]) (?P<title>.+)$", re.M)
# A reference looks like `path/to/test.py::Class::test_name`, in backticks, and a line can
# carry several of them plus ordinary prose.
REFERENCE = re.compile(r"`((?:api|e2e)/[\w./-]+(?:::[\w:]+)?)`")
TESTS_LINE = re.compile(r"^Tests: (?P<body>.+?)(?=\n\n|\n### |\Z)", re.M | re.S)
# "Story VA-8", "Stories A-1, A-4 and VA-6", "VA-10:" at the start of a docstring line.
STORY_MENTION = re.compile(r"\b(?:Stor(?:y|ies)\s+)((?:[A-Z]+-\d+)(?:[,\s]+(?:and\s+)?[A-Z]+-\d+)*)")

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
        for group in STORY_MENTION.findall(text):
            for story in re.findall(r"[A-Z]+-\d+", group):
                if story not in known:
                    rel = path.relative_to(ROOT)
                    problems.append(f"{rel} names story {story}, which is not in docs/userstories/")
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
    gotcha_problems, entries = check_gotchas()
    problems += gotcha_problems

    if "--fix" in argv:
        INDEX.write_text(render_index(entries), encoding="utf-8")
        print(f"wrote {INDEX.relative_to(ROOT)} ({len(entries)} notes)")
    elif INDEX.exists() and INDEX.read_text(encoding="utf-8") != render_index(entries):
        problems.append("docs/gotchas/INDEX.md is out of date — run scripts/check-docs.py --fix")

    print(f"{len(known)} stories, {len(entries)} gotchas")
    for problem in problems:
        print(f"  ✗ {problem}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
