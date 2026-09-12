# A sandbox-denied file shows up as a 0-byte `/dev/null`, so `ls` and `stat` describe something that is not there

**Symptom** — `cat api/.env.example` → `Permission denied`. `ls -l` reports
`crw-rw-rw- 1 nobody nogroup 1, 3`, and `stat` says **0 bytes**. The file is plainly present
in `git status` as untracked, and the user can read it perfectly well.

**Cause** — The Bash sandbox enforces its read-deny list by bind-mounting `/dev/null` over
the denied path (major/minor `1, 3` *is* `/dev/null`). So the metadata an agent sees
describes the bind mount, not the file: character device, zero bytes, owned by `nobody`. A
`cat` that prints nothing is the sandbox, not an empty file.

I lost three attempts to this: two `cat`s and a `stat`, each read as "the file is empty or
unreadable for some ordinary reason" rather than "I am looking at a different inode".

**Rule** — `0 bytes` plus `crw-rw-rw-` plus `nobody nogroup` means **denied**, not empty.
Do not infer content, and do not try to commit the path as a workaround: `git hash-object`
and `git add` fail with the same `Permission denied`, so the file cannot be staged from
inside the sandbox at all — which is the safe outcome, but only reachable by asking the
user to commit it themselves. A file the sandbox hides is a file this session cannot
handle; say so and hand it back.

**Evidence** — `ls -l api/.env.example` and `git hash-object api/.env.example` in this
repository, with `api/.env.example` on the session's deny list.

**Seen** — 2026-09-12.
