#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml>=6"]
# ///
"""Every sops file is encrypted, and encrypted for the recipients its `.sops.yaml` rule names.

Needs no key — it reads only what sops writes in the clear. Two mistakes it catches, both
silent until it is too late:

  plaintext   a secrets file saved decrypted (`sops decrypt … > file`, an editor writing
              the wrong buffer) and committed: every value is in git history for good
  recipients  a key added to `.sops.yaml` but the file not re-keyed (`sops updatekeys`),
              so decryption fails for exactly that person — or a key removed there that
              can still read every new value

The files are what git knows about plus what it would add (`-co --exclude-standard`), so
a new file is checked before its first commit. Dotenv files (`*.sops.env`) for now, the
only kind the repository has.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
_RECIPIENT = re.compile(r"^sops_age__list_\d+__map_recipient=(.*)$")


def _key(recipient: str) -> str:
    """An SSH key without its comment, which sops keeps but which says nothing."""
    return " ".join(recipient.split()[:2])


def _files() -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files", "-co", "--exclude-standard", "-z", "*.sops.env"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return sorted({ROOT / p for p in out.split("\0") if p})


def _problems(path: Path, rules: list[dict]) -> list[str]:
    rel = path.relative_to(ROOT).as_posix()
    lines = path.read_text().splitlines()
    found: list[str] = []
    if not any(line.startswith("sops_mac=") for line in lines):
        return ["not encrypted — no sops metadata; encrypt it with `sops encrypt -i`"]
    for number, line in enumerate(lines, 1):
        if not line.strip() or line.startswith("sops_"):
            continue
        if line.startswith("#"):
            if not line.startswith("#ENC["):
                found.append(f"line {number}: a comment in plaintext")
            continue
        name, _, value = line.partition("=")
        if value and not value.startswith("ENC[") and not name.endswith("_unencrypted"):
            found.append(f"line {number}: {name} in plaintext")
    rule = next((r for r in rules if re.search(r["path_regex"], rel)), None)
    if rule is None:
        return [*found, "no creation rule in .sops.yaml matches it"]
    wanted = rule.get("age") or []
    if isinstance(wanted, str):
        wanted = wanted.split(",")
    have = sorted(_key(m.group(1)) for line in lines if (m := _RECIPIENT.match(line)))
    want = sorted(_key(r) for r in wanted)
    if have != want:
        missing = sorted(set(want) - set(have))
        extra = sorted(set(have) - set(want))
        found.append(
            "recipients differ from .sops.yaml — run `sops updatekeys -y "
            f"{rel}`"
            + (f"; missing {missing}" if missing else "")
            + (f"; not in the rule {extra}" if extra else "")
        )
    return found


def main() -> int:
    rules = (yaml.safe_load((ROOT / ".sops.yaml").read_text()) or {}).get("creation_rules", [])
    failed = 0
    for path in _files():
        for problem in _problems(path, rules):
            print(f"  ✗ {path.relative_to(ROOT).as_posix()}: {problem}")
            failed += 1
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
