# SAP keeps a race's log by leaderboard name after its event is deleted — a new event of the same name takes the old teams and results back

**Symptom** — after emptying the local SAP and sending the same act again, SAP's
leaderboard shows a handful of scored cells and odd totals (one team 54 points after a
clean day), the site takes 0 results back, and a re-send says the teams were "kept" though
the event had been deleted.

**Cause** — `DELETE /v1/events/{id}` (with groups, leaderboards and regattas) leaves
MongoDB's `RACE_LOGS` and `REGATTA_LOGS`, which are keyed by leaderboard name, race column
and fleet — not by the deleted objects. A new regatta of the same name reads them back:
the old `RaceLogRegisterCompetitorEvent`s (old team ids) and old finish lists mix into the
new races. What misled: the REST lists all said 0 events, regattas and leaderboards — the
leftovers are in no list.

**Rule** — emptying SAP means deleting the logs too (`deploy/sap-local/clean.sh` does);
tests send under names of their own (a tag in the venue or matchday), so no two runs share
a leaderboard name. On SAP's hosted server, an act deleted and sent again under its name
brings back what its races held — ask SAP before deleting an event there.

**Evidence** — 2026-11-02: `scripts/sap-season.py --sail 1` after a clean that kept
`RACE_LOGS` (9742 entries): 19 of 48 races scored at SAP, 0 results on the site; with the
logs deleted, 48 of 48.

**Seen** — 2026-11-02
