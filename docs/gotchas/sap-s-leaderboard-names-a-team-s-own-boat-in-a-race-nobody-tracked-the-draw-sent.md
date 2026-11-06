# SAP's leaderboard names a team's own boat in a race nobody tracked — the draw sent to its race log is not what a cell's boat says

**Symptom** — after "Send to SAP Sailing", `v2/leaderboards/{name}` gives every cell a
`boat` that is none of the six league boats (`J128d45f`, no colour), and the same boat in
every race for one team; a KeyError on the boat id in the J-10 walk.

**Cause** — `createandadd` makes one boat per competitor, and for a race column without a
tracked race SAP's leaderboard shows that boat. The draw is right: the race log holds a
`RaceLogRegisterCompetitorEvent` per team with our boat (Mongo `RACE_LOGS`, boat id as a
Java-legacy UUID). What misled: the importer was built on recorded DSBL leaderboards,
where every race was tracked, so the cell's boat *was* the boat sailed.

**Rule** — on an event scored on SAP, our draw says who sailed which boat and SAP only
says the result: `app/imports/sap.py::_result` takes the boat from our `RaceEntry` and
never reads the cell's. Never read per-race boats from an untracked SAP leaderboard, and
never test against an imitation of SAP: the in-process fake we had answered with the
race's boat and hid this, so the SAP tests now run against the local SAP only
(`tests/sap_double.py`), which reads the draw from the race log.

**Evidence** — `api/tests/stories/test_journey_sap_scored.py` against `deploy/sap-local/`;
`docker exec sap-sailing-mongo-1 mongosh test --eval 'db.RACE_LOGS.find({"RACE_LOG_EVENT.RACE_LOG_EVENT_CLASS":"RaceLogRegisterCompetitorEvent"})'`.

**Seen** — 2026-11-02
