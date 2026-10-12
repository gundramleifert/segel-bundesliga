# Manage2Sail — how to connect

What can be read from and written to [Manage2Sail](https://www.manage2sail.com) (M2S), the
DSV's regatta manager, and how. As of 2026-10-12. Each statement is either **tested**
(a GET request against a real event, Midsummer-Cup 2026) or names its source.

**Short version:** there is no public developer API and no ready-made connector. There is
an **event access token** that unlocks one read-only report (all registrations of the
event, 118 fields), plus **public, unauthenticated** JSON and XRR endpoints for entries
and results. **Nothing can be written with the token** — notices, results and entries go
into M2S through its portal, by hand or by Excel import.

---

## 1. Getting the token

1. Sign in to the organizer portal, `https://portal.manage2sail.com`, with an account that
   has rights on the event.
2. Open the **event**, then the **API** tab.
3. The page shows the **access token** and the report URL it belongs to.

The token is generated **per event**. Whether one token also opens the club's other events
is untested (no second event was available) — assume not.

**The token is a secret.** It opens names, email addresses, mobile numbers, emergency
contacts, dates of birth and payment status of every participant. Store it like a password
(an environment variable or an encrypted column, never the repo), never log the full URL,
and regenerate it in the portal if it leaked. Import only the fields this site needs (GDPR
data minimisation): a club name and a sail number, not an emergency contact.

## 2. What the token opens

### The check-in report — the one endpoint

```
GET https://portal.manage2sail.com/Club/api/CheckInReportApi/{eventId}
      ?action=SimpleReport&asExcelReport=False&accessToken={token}
```

| Tested | Result |
|---|---|
| with token, `asExcelReport=False` | `200`, `application/json`: `{"Data": [ …one object per entry… ]}` |
| with token, `asExcelReport=True` | `200`, `application/excel` (`.xls`) — the same report |
| without token | `401 {"Message":"Authorization has been denied for this request."}` |
| `action=` anything else (`ExtendedReport`, `Foo`, …) | `200`, byte-identical to `SimpleReport` — the parameter is ignored |

One row per **entry** (boat/team), across **all classes** of the event. The 118 fields,
grouped:

| Group | Fields |
|---|---|
| Entry | `IdText` (entry id, 32 hex chars), `Event`, `Class`, `SailNumber`, `SailNumberCountry`, `SailNumberNumber`, `BowNumber`, `RepresentedCountry`, `BoatTeamName`, `BoatTeamClub`, `RegistrationDate`, `UpdatedDate`, `UpdatedBy` |
| Status | `BoatTeamState` (e.g. `Approved`), `IsApproved`, `IsChecked`, `IsInspected`, `IsPaid`, `HasInsurance`, `HasLicense`, `IsDisclaimer`, `IsCustom1..3`, `RacingAsPara`, `CreatedBySailor` — flags are `"x"` or `null` |
| Skipper | `Skipper`, `SkipperFirstName`, `SkipperLastName`, `SkipperGender`, `SkipperDateofBirth`, `SkipperYearofBirth`, `SkipperISAF` (World Sailing id), `SkipperClub`, `SkipperEmail`, `SkipperCellphone`, address, national id fields |
| Crew | `CrewCount`, `Crew1Firstname`, `Crew1Lastname`, `Crew1Email`, `Crew1Birthday`, `Crew1Club`, `Crew1WSID`, `Crew1Gender`, …, and `RemainingCrew` as **one string** for crew 2+ |
| Registrator / coach | `Registrator`, `RegistratorEmail`, `Coach`, `CoachEmail` |
| Emergency | `EmergencycontactCellphone`, `EmergencycontactLandline` |
| Payment | `Paymentcategory`, `Paymentmethod`, `Ordercodes`, `Paymentdates`, `Total`, `Paid`, `PaidEntryFee`, `ToBePaid`, `Items` |
| Boat | `BoatName`, `BoatType`, `BoatAis`, length/beam/draft, ratings (`BoatYS`, ORC, SRS, TCF, …) |

Watch out for: dates as both ISO (`RegistrationDate`) and German display strings
(`Registration`, `Paymentdates` as `dd/mm/yyyy`), numbers as strings (`"50"`), and
empty string vs `null` used interchangeably.

### What the token does *not* open (tested)

| Path under `portal.manage2sail.com/Club/api/` | With token |
|---|---|
| `EventApi`, `RegattaApi`, `ClubApi` | `401` — they exist but want a signed-in portal session, not the token |
| `NoticeBoardApi`, `NoticeApi`, `PublicationApi`, `DocumentApi`, `ScheduleApi`, `ResultApi`, `ResultReportApi`, `EntryApi`, `EntryReportApi`, `PaymentReportApi`, `CrewReportApi`, `InvoiceApi` | `404` — no such controller |

The check-in controller is **GET-only** (tested): `OPTIONS` answers `405`, and `POST`/`PUT`
answer `405 "The requested resource does not support http method 'POST'"` once a body is
present. A bodyless `POST` first returns `411 Length Required`, which looks like it might
accept an upload — it does not; that is ASP.NET asking for a length before it checks the
method. So **nothing can be uploaded with this token** — no notice, document or result. The
API tab issues a token for a **report**, not a read/write API.

## 3. Public endpoints — no token at all

The public info site (`www.manage2sail.com`) loads its data from JSON endpoints that answer
without authentication (tested):

| What | URL | Format |
|---|---|---|
| Event page (holds the class ids) | `/en-US/event/{eventId}` — the ids appear as `classId={uuid}` in the HTML | HTML |
| Entries of one class | `/api/event/{eventId}/regattaentry?regattaId={classId}` | JSON: `TotalCount`, `RegattaName`, `Entries[]` with `EntryId`, `SailNumber`, `TeamName`, `SkipperName`, `Crew`, `BoatName`, `BoatType`, `Hcp`, … |
| Results of one class | `/api/event/{eventId}/regattaresult/{classId}` | JSON: `RaceNames[]`, `Discards`, `PointSystem`, `OverallReport` (`IsOfficial`, `PublishedDate`), `EntryResults[]` with `Rank`, `TeamName`, `ClubName`, `ClubCode`, `SailNumber`, `EntryRaceResults[]` (`RaceId`, `Points`, …) |
| Results as World Sailing XRR | `/en-US/Home/DownloadXrr/event/{eventId}/regatta/{classId}` | XML, [XRR](https://www.sailing.org/xml) v1.3 |
| Results as HTML | `/en-US/Home/ResultsFragment/event/{eventId}/regatta/{classId}` | HTML |
| Calendar entry | `/api/event/{eventId}/CalendarItem` | referenced by the page, not tested |
| **Event document** (NOR, SI, course chart, logo, …) | `/en-US/Home/DownloadDocument/{documentId}` | the file itself, with its real name in `Content-Disposition` (e.g. a `.png` or `.pdf`) |
| Overall / per-race result report (PDF) | `/en-US/Home/DownloadReport/event/{eventId}/report/{reportId}` | PDF |

The `{documentId}` / `{reportId}` values are on the public event page as `Document/{uuid}`
and `DownloadReport/…/report/{uuid}` links. Document download is **public** — tested with
and without a token, same bytes either way; the access token makes no difference to it.

`/api/event/{eventId}` itself answers `401` — older scrapers used it, it has since been
closed. **Expect the same for the rest**: these are the info site's internals, not a
published API, and M2S's terms do not expressly allow automated retrieval. Poll gently,
cache, and keep a manual upload as fallback (`docs/findings.md` §4).

## 4. The partner API — not ours (yet)

SAP/Eclipse Sailing Analytics imports from
`https://manage2sail.com/api/public/links/event/{eventId}?accesstoken={partnerToken}&mediaType=json`
(source: `configuration/notifyAboutEVENTupdates` and the `com.sap.sailing.manage2sail`
bundle in [SAP/sailing-analytics](https://github.com/SAP/sailing-analytics), Apache 2.0).
With the event token it answers **`401`** — it takes a partner token M2S hands out
case by case. That importer's `Manage2SailEventResultsParserImpl.java` and its test JSON
are the best reference for parsing M2S results.

**To ask M2S / the DSV:** a partner token for `/api/public/links/…`, written permission to
poll the public endpoints, whether any **write** API exists (notice board, results), and
whether they offer OAuth/OIDC sign-in (`docs/findings.md` §4).

## 5. What that means for our use cases

| We want | Possible? | How |
|---|---|---|
| **Registered clubs** of an event | **Yes** | Check-in report: `BoatTeamClub`, `SkipperClub`, `Crew1Club`. The format is `"<code>, <name>"`, e.g. `"WSS, Wassersportclub Seligenstadt e. V."` — the **code before the comma** is the stable key; store it as an `ExternalId`, never match on the name. The public results carry `ClubCode` separately. The report has **no club id**. |
| Teams / entries with crews | **Yes** | Check-in report (crew 1 as fields, crew 2+ only as the `RemainingCrew` string — enough for display, too little for a lineup), or the public `regattaentry` without a token |
| Who has paid / checked in | **Yes** | Check-in report: `IsPaid`, `ToBePaid`, `IsChecked`, `BoatTeamState` |
| Results | **Yes** | Public `regattaresult` JSON or the XRR file, no token |
| **Download event documents** (NOR, SI, course chart, logo) | **Yes** | `/en-US/Home/DownloadDocument/{documentId}`, no token needed; ids from the public event page |
| **Upload notices** (notice board) automatically | **No** | The controller is GET-only (`POST`/`PUT` → `405`). Notices are created in the portal's ORM → *Notice Board* by hand. Options: ask M2S for a write API; until then publish on our site and post the link (or the PDF) on the M2S notice board by hand |
| Push entries into M2S | **Only by hand** | The portal's Excel entry import (M2S handbook v1.6, §4.6) |
| Push results into M2S | **No** | Scoring happens in M2S, or results are imported in the portal |
| Email participants | **In M2S, not via API** | The portal's CheckIn tab mails all entrants of the event (handbook §4.6.1) |

## 6. Manage2Sail vs SAP Sailing — which to use

They are two different systems holding two different parts of an event, and for the DSBL the
better source is usually **SAP**, not Manage2Sail.

| | **Manage2Sail** | **SAP Sailing Analytics** |
|---|---|---|
| What it is | The DSV's **registration / regatta-office** portal | The league's **results, scoring and tracking** platform (`www.sapsailing.com`) |
| Holds | Entries, crews, contact & payment data, check-in, documents (NOR/SI) | Races, scored leaderboard, boats, GPS tracks |
| DSBL coverage | The Bundesliga appears as a *class inside* larger regattas (e.g. Travemünder Woche); junior/other leagues use it more directly | **The league's own matchdays** — `1./2. Segel-Bundesliga YYYY - City`, 2015–2023 on the public server (see `docs/findings.md` §3a) |
| Access | Event **access token** (from the event's API tab) for the check-in report; entries/results/documents public | Public **v1/v2 API, no secret** for DSBL results, races and clubs; GPS tracks need permission (401) |
| Structure match | Per-class entry/result lists | **Matches our model**: flights `F1…F16`, 48 races, boats with `#rrggbb` colours, stable UUIDs → `ExternalId` |
| Write | Nothing writable with the token | Results import via XRR/CSV document + Bearer token (`docs/findings.md` §3) |

**Rule of thumb:**
- Need **who is registered**, crews, contact/payment, check-in, event documents → **Manage2Sail**.
- Need **results, standings, boats, the league's own matchdays** → **SAP**, and for the DSBL
  it imports without a secret, which is the cleaner source.
- The two meet on **club identity**: Manage2Sail's `ClubCode` and SAP's competitor UUID +
  club-flag URL are both stable keys — match through `ExternalId`, never by name.

## Sources

- Requests against the endpoints above, 2026-10-12 (GET only).
- Manage2Sail handbook v1.6 (DSV, 2019): §4.5.5 "API — in preparation", §4.6 CheckIn,
  §6.14 Notice Board — downloadable from manage2sail.com.
- [SAP/sailing-analytics](https://github.com/SAP/sailing-analytics) — the M2S importer.
- [SailHub: manage2sail API](https://sail-hub.de/ratgeber/manage2sail-verein/) — terms of use.
- [manage2sailScraper.py](https://gist.github.com/joabakk/e687fbe7baaec32e27623cea0611273f) —
  the public `regattaentry` / `regattaresult` paths.
