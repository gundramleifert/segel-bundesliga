#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx"]
# ///
"""Records Manage2Sail's public answers for the 1. and 2. Liga 2026, for the seed to replay.

    scripts/record-m2s.py            # writes api/app/seed_data/m2s-2026/

The league registers each weekend once at Manage2Sail, one class per league, plus one
event for the season's own documents. The ids are the ones deutsche-segelbundesliga.de's
matchday pages link (`/dsbl-event/<n>-spieltag-2026/`, read 2026-10-28).

Only what the public event page itself reads (docs/manage2sail.md §3), once per run and
gently: per event its page — kept as its title and bootstrap data only — and per class
its entry list and its documents, plus the event's own documents. Nothing is written
when an answer fails, so a recording is never half old, half new.

**No person is recorded:** an entry keeps only what the importer needs — its id, club and
sail number (`KEEP`); the team's name (at the league a helmsman's) and the crew stay at
Manage2Sail, since this repository is public.

`app.imports.m2s.recorded_transport` replays the folder; `app.seed` imports it.
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

import httpx

BASE = "https://www.manage2sail.com"
OUT = Path(__file__).resolve().parent.parent / "api/app/seed_data/m2s-2026"

# (what it is, the Manage2Sail event id)
EVENTS = [
    ("season", "682a8f18-b0a8-46d6-a11b-1a1e77c28482"),
    ("weekend", "d21aea23-44f4-4d1e-b910-cb9813b17535"),
    ("weekend", "564b3310-ef2c-412e-8e73-5002aeae8128"),
    ("weekend", "5d70628f-39fe-491a-a634-fb05066d504c"),
    ("weekend", "931d40a9-6bc7-4b45-a0a1-100992a25a21"),
    ("weekend", "e5db1982-5983-47a5-b3ae-8b1466ec7320"),
    ("weekend", "cfbabf9e-efe5-4fa2-b02a-82ef4103b8cf"),
]

# The fields of an entry the importer reads (app/imports/m2s.py) — nothing about a person.
KEEP = ("EntryId", "ClubCode", "ClubName", "SailNumber")

_BOOTSTRAP = re.compile(r"window\.boostrapedResourceData\s*=\s*(\{.*?\});\s*$", re.S | re.M)
_TITLE = re.compile(r"<title>.*?</title>", re.S | re.I)


def record(http: httpx.Client) -> dict[Path, bytes]:
    files: dict[Path, bytes] = {}
    index = []

    def get(path: str, **params: str) -> httpx.Response:
        time.sleep(0.5)
        response = http.get(f"{BASE}/{path}", params=params or None)
        response.raise_for_status()
        return response

    for kind, event in EVENTS:
        html = get(f"en-US/event/{event}").text
        boot, title = _BOOTSTRAP.search(html), _TITLE.search(html)
        if boot is None or title is None:
            raise SystemExit(f"{event}: no title or event data on its page")
        files[Path(event, "page.html")] = (
            f"{title.group(0)}\n<script>\nwindow.boostrapedResourceData = {boot.group(1)};\n"
            "</script>\n"
        ).encode()
        data = json.loads(boot.group(1))
        classes = data.get("Regatta") or []
        files[Path(event, f"documents-{event}.json")] = get(
            f"api/event/{event}/document/{event}"
        ).content
        counts = []
        for cls in classes:
            answer = get(f"api/event/{event}/regattaentry", regattaId=cls["Id"]).json() or {}
            answer["Entries"] = [
                {field: entry.get(field) for field in KEEP} for entry in answer.get("Entries") or []
            ]
            files[Path(event, f"entries-{cls['Id']}.json")] = (
                json.dumps(answer, indent=2, ensure_ascii=False) + "\n"
            ).encode()
            files[Path(event, f"documents-{cls['Id']}.json")] = get(
                f"api/event/{event}/document/{cls['Id']}"
            ).content
            entries = json.loads(files[Path(event, f"entries-{cls['Id']}.json")]) or {}
            documents = json.loads(files[Path(event, f"documents-{cls['Id']}.json")]) or []
            counts.append(
                f"{cls['Name']}: {len(entries.get('Entries') or [])} entries, "
                f"{len(documents)} documents"
            )
        index.append({"kind": kind, "event": event, "classes": [c["Name"] for c in classes]})
        print(f"{kind:8} {event}  {'; '.join(counts)}")
    files[Path("events.json")] = (json.dumps(index, indent=2, ensure_ascii=False) + "\n").encode()
    return files


def main() -> int:
    with httpx.Client(headers={"User-Agent": "segelliga-seed-recorder"}, timeout=30) as http:
        files = record(http)
    for path, content in files.items():
        (OUT / path).parent.mkdir(parents=True, exist_ok=True)
        (OUT / path).write_bytes(content)
    print(f"{len(files)} files in {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
