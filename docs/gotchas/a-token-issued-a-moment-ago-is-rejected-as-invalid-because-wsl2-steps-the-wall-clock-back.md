# A token issued a moment ago is rejected as "Invalid access token", because WSL2 steps the wall clock backwards

**Symptom** — In a long test run, the first request after a fresh login answered 401
`Invalid access token.` — in a *different* story test each time, never in a short run, and
never reproducible alone. The token had been issued by the same process a millisecond
earlier with the same secret.

**Cause** — The wall clock on WSL2 is stepped by time sync, backwards included: measured
here, a 656 ms step back within 15 s. `create_access_token` writes `iat` as the current
second; PyJWT refuses a token whose `iat` lies after the verifier's clock
(`ImmatureSignatureError`, a subclass of `InvalidTokenError`, so it surfaces under the generic
"Invalid access token" message). A step back across a second boundary between issue and
first use is enough. What misled: the message says "invalid", the flake moved between
unrelated tests, and bisecting by test file pointed at whichever file happened to make the
run long enough.

**Rule** — Verify tokens with a `leeway` (`app/auth.py`: 30 s). More generally: when a
"never happens" auth failure appears only in long runs and only on the request right after
issuing something time-stamped, suspect the clock before the code — and check it with a
wall-vs-monotonic loop, which takes fifteen seconds:

    python3 -c "import time; w,m=time.time(),time.monotonic(); worst=0
    for _ in range(150): time.sleep(.1); worst=min(worst,(time.time()-w)-(time.monotonic()-m))
    print(worst)"

**Evidence** — The loop above printed `-0.656` on 2026-09-15. Story runs
`tests/stories/test_race_control.py::TestSignals` + `tests/stories/test_event_closing.py`
failed once with the 401 and passed the next time unchanged; with `leeway=30` the full suite
is green.

**Seen** — 2026-09-15
