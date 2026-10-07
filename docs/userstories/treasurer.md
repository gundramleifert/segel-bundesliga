# Treasurer

Part of the [user stories](README.md); the format, the status marks and the
identifier rule are explained there.

Race officers, jury, umpires and helpers travel to an event, and **the club hosting it pays
their costs** (decision of 2026-10-04). A club also pays back what its own members spend
for it — a trip to a meeting, a new set of sail numbers. So a claim is filed against an
**event** or a **club**, and the one who settles it is that event's or club's **manager or
treasurer** (decision of 2026-10-07): a small club often has no treasurer, and its
organizer pays. The plan these stories follow is `docs/PLAN_DATA_MODEL.md`.

## Who holds the money

### F-1 ● The event's treasurer is a tuple, and the host club's treasurer is it for every event the club hosts
As the **treasurer of a club** I want to **see and decide the expense claims of every event
my club hosts, and no other money**, so that **the club pays what it owes and nobody else
reads its books**.

`treasurer` is a relation of the authorization model (Story Z-2), on two object types:

```
type club
  relations
    define treasurer: [user] or admin

type event
  relations
    define treasurer: [user] or admin or treasurer from host_club
```

Acceptance criteria:
- A club's admin names the club's treasurer like any other relation on the club: one
  tuple, written and deleted one at a time. The club's admin is its treasurer too.
- **The host club's treasurer is the treasurer of every event the club hosts** — the
  same rewrite that makes the host club's admin the admin of its events.
- A treasurer can be named for **one event only** (`user:treasurer:event:<id>`): they are
  treasurer there and nowhere else, and in particular **not** of the host club.
- **Another club's treasurer is nothing on this event.** Hosting decides, not holding the
  relation somewhere.
- An event without a host club has a treasurer only through its own tuples and its
  admins.
- `treasurer` exists on neither a series nor the site: neither pays. Writing one there
  is refused (`tuple-relation-invalid`). A series' or the site's admin reaches it through
  "admin is everything within" — open question Q1 of the plan.
- Holding `treasurer` anywhere shows up as the summary role `treasurer` (Story Z-2,
  "Summary roles").

Tests: `api/tests/stories/test_treasurer.py::TestTreasurerRelation`

## Expense claims

### F-2 ● File an expense claim for an event or for my club
As a **race officer, jury member, umpire or helper** I want to **claim my travel,
accommodation and meal costs for an event I worked at**, and as a **club member** what I
spent for my club, so that **the event's host club, or my club, pays them back**.

Acceptance criteria:
- A claim belongs to exactly one event **or** exactly one club — never both, never
  neither; the database refuses either.
- **On an event:** the payer is its host club, recorded at submission. An event without
  a host club takes no claim (`event-has-no-host-club`). Only someone holding
  `race_officer`, `jury`, `manager` or `helper` **directly** on the event, or
  `race_officer`, `jury` or `manager` directly on its series, may file (the club's policy
  names the eligible relations). A relation inherited from the site does not entitle
  anyone to travel costs.
- **On a club:** the payer is the club. Any **member** of the club may file
  (`user:member:club`); the manager or treasurer decides whether it was justified.
- Anyone else is refused (`claim-not-eligible`). The account page offers the events and
  clubs one may claim on (`GET /api/me/claim-targets`), and nothing else.
- Items: car (km × the paying club's rate, frozen at submission), public transport,
  accommodation, per-diem, meals, other. Amounts in whole cents.
- `draft` → `submitted`. Submitting needs at least one item and a saved bank account
  (Story S-6, `bank-account-missing`); the account holder and IBAN are **copied onto the
  claim** then, so a payout goes where the claimant said at the time. The claimant can
  withdraw until it is decided, and edit again once it is returned.

Tests: `api/tests/stories/test_expenses.py::TestClaimTotals`,
`api/tests/stories/test_expenses.py::TestTheDatabaseKeepsTheBooksStraight`,
`api/tests/stories/test_reimbursements.py::TestFilingAClaim`

### F-3 ● The manager or the treasurer approves, returns or rejects a claim
As the **manager or treasurer of the event or club a claim is filed against** I want to
**check each claim and decide it**, so that **only justified costs are paid**.

Acceptance criteria:
- **Who decides:** on an event, its `treasurer` (Story F-1), whoever holds `manager`
  **directly** on the event, and the host club's manager; on a club, its manager or
  treasurer (and their admins, who are both). A series' manager, the site's editor and
  the site's race committee are managers of events by the model's rewrite, but **not**
  of their money: the check is on the tuple, not on `can(manager)`.
- Approve (optionally lowering single items, never raising them), return with a note, or
  reject with a note. Only a `submitted` claim is decided.
- **Nobody decides their own claim**, whatever relations they hold
  (`claim-own-decision`).
- Every transition is in the audit log with who and when.

Tests: `api/tests/stories/test_reimbursements.py::TestDecidingAClaim`

### F-4 ◐ The manager or treasurer pays and exports
As the **manager or treasurer** I want to **mark approved claims as paid and export them**,
so that **the club's bookkeeping gets one list with payee, IBAN, amount and reference**.

Acceptance criteria:
- A payment is its own record (`draft` → `issued` → `settled`, or `failed` / `cancelled`),
  not a status of the claim: a transfer that bounces after approval must not reopen the
  approval (`docs/PLAN_DATA_MODEL.md` §2.5).
- One payment settles any number of claims of one payee for one paying club; a claim can
  be paid in parts (`PaymentAllocation`), never beyond its approved total.
- Whether a claim is paid (`unpaid`, `in_payment`, `partially_paid`, `paid`) is computed
  from the settled allocations, never stored. A failed payment is kept as it is and stops
  counting; a new payment is made.
- Whoever issues a payment is recorded, and is never the payee.
- **"Mark as paid"** is the short way for the transfer the decider has just made in their
  own online banking: one settled payment over what is still open on that claim, to the
  IBAN copied onto it, with the date and an optional reference.

Done: the data model, the computed payment state and "mark as paid". Open: payments over
several claims, `issued` → `failed`, the export.

Tests: `api/tests/stories/test_expenses.py::TestPaymentState`,
`api/tests/stories/test_expenses.py::TestTheDatabaseKeepsTheBooksStraight::test_a_claim_is_allocated_to_a_payment_once`,
`api/tests/stories/test_reimbursements.py::TestPayingAClaim`

### F-5 ● Upload documents to a claim, readable only by the claimant and whoever decides it
As a **claimant** I want to **attach receipts, invoices and tickets to my claim**, so that
**the manager or treasurer can check what I paid**.

Acceptance criteria:
- Any number of documents per claim, each optionally tied to one item.
- Uploaded and deleted while the claim is `draft` or `returned`; frozen from submission.
- The club's policy names the kinds that need a document; submitting without one is
  refused (`expense-document-missing`) and names the items.
- PDF, JPEG or PNG by content, at most 10 MB, stored under a random name. Read through one
  endpoint that admits the claimant and whoever may decide the claim (Story F-3), and
  logs every look by someone else.

Tests: `api/tests/stories/test_expenses.py::TestTheDatabaseKeepsTheBooksStraight::test_a_document_is_at_most_ten_megabytes`,
`api/tests/stories/test_reimbursements.py::TestClaimDocuments`

### F-6 ● Pending reimbursements in one list
As the **manager or treasurer of an event or a club** I want to **see every claim waiting
for me in one place**, so that **nothing is forgotten between matchdays**.

Acceptance criteria:
- One list (`GET /api/claims/pending`, the page "Reimbursements") of the claims the
  person may decide (Story F-3) that are `submitted` (to decide) or `approved` and not yet
  paid (to pay) — across every event and club they hold the money of.
- Never the person's own claims, which they cannot decide, and never a draft: a draft is
  the claimant's own until submitted.
- Each row names the claimant, the event or club, the amounts and what is to be done.

Tests: `api/tests/stories/test_reimbursements.py::TestPendingList`
