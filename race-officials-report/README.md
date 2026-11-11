# Race Officials Report: concept

Working title: **Race Officials Report** (IJ/IU Report). A website where World Sailing's
International Judges (IJ) and International Umpires (IU) record the events they officiated
at. It gives them the evidence for renewing their licence and gives the responsible
sub-committees a clean dataset.

It started with a request from Heiko Thoelmann (11 November 2026). Today's site,
wsijreport.org, only records events with an International Jury. There is nothing comparable
for umpires, match racing or team racing.

> **Status:** concept only, not a line of code. None of it has been agreed with the IJSC, the
> IUSC or World Sailing. The most important open questions are in
> [CONCEPT.md § 11](CONCEPT.md#11-open-questions).

## Not part of the Deutsche Segel-Liga website

**This project is not part of the Deutsche Segel-Liga website (SBL) and is not meant to
become part of it.** It sits in the SBL repository as a folder only for convenience, so the
concept is kept next to the template it borrows from. Nothing under `api/`, `web/`, `e2e/` or
`deploy/` uses it, and it is not a feature, story or issue of the site. When implementation
starts, it moves to a repository of its own.

- **Different client, different audience:** race officials worldwide and World Sailing's
  committees, not the league's clubs and sailors.
- **Different data controller:** the SBL processes data on behalf of Deutsche Segel-Liga e.V.
  This project holds data about international officials, including confidential
  assessments. That must not live in the same database or under the same operator.
- **Its own repository, database, login and hosting.** No shared runtime code, no dependency
  in either direction.
- **What is reused is copied, not shared:** the SBL's technology and way of working (FastAPI,
  React, permissions as relation tuples, story → test → code, Docker Compose) serve as the
  template for the skeleton. After that, the two projects evolve independently.
- The SBL's jury pool (stories JU-1 to JU-5) is related in subject but has a different
  purpose: it staffs the league's juries *before* an event. This project reports *after* an
  event. There is no synchronisation between the two.

## Contents

| File | Content |
|---|---|
| [CONCEPT.md](CONCEPT.md) | Background, goals, roles, domain model, workflows, integrations, data protection, technology, phases and effort, risks, open questions |
| [USER_STORIES.md](USER_STORIES.md) | User stories with acceptance criteria, by role |
| [LICENCE_RULES.md](LICENCE_RULES.md) | World Sailing's rules for event levels (L1–L3) and licence renewal (IJ, IU), as the site evaluates them |
| [material/](material/) | Source material: screenshots of today's site, World Sailing documents |
