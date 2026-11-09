# pkill -f kills the shell that runs it when its pattern is also in that shell's command line

**Symptom** — a command that stops a hand-started stack (`pkill -f "uvicorn … --port 8100"`)
and then restarts it ends with exit code 144 and no output: nothing after the `pkill` ran,
the server is gone and was never started again.

**Cause** — `pkill -f` matches against every process's *full* command line, and the tool
runs the whole command as `bash -c '<everything you typed>'` — so that bash's own command
line contains the pattern too, and `pkill` sends it SIGTERM along with the server
(128 + 15 = 143/144). It looked like the restart had failed; it had never run.

**Rule** — never `pkill -f` from the same command line that goes on afterwards. Find the
PID first (`ps -eo pid,args | grep -E "port 81[0]0"` — the `[0]` keeps grep from matching
itself) and `kill <pid>`, or keep the stop in a call of its own.

**Evidence** — `pkill -f "port 8100 --host"; …; nohup uv run uvicorn … --port 8100 --host …`
in one call: exit 144, the API down afterwards (`ps` showed no uvicorn on 8100); the same
stop as `kill <pid>` followed by the start worked.

**Seen** — 2026-11-08
