# Treasurer

Part of the [user stories](README.md); the format, the status marks and the
identifier rule are explained there.

Race officers, jury and umpires travel to an event, and **the club hosting it pays their
costs** (decision of 2026-10-04). The event therefore has a treasurer: the person who
checks the claims filed for it, approves or returns them, and pays. The plan these stories
follow is `docs/PLAN_DATA_MODEL.md`.

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

### F-2 ◐ File an expense claim for an event
As a **race officer, jury member or umpire** I want to **claim my travel, accommodation
and meal costs for an event I worked at**, so that **the host club pays them back**.

Acceptance criteria:
- A claim belongs to exactly one event; the payer is that event's host club, recorded at
  submission. An event without a host club takes no claim
  (`event-has-no-host-club`).
- Only someone holding `race_officer`, `jury` or `manager` **directly** on the event or
  its series may file (the club's policy names the eligible relations). A relation
  inherited from the site does not entitle anyone to travel costs.
- Items: car (km × the club's rate, frozen at submission), public transport,
  accommodation, per-diem, meals, other. Amounts in whole cents.
- `draft` → `submitted`; the claimant can withdraw until it is decided.

Done: the data model — `ExpenseClaim` and `ExpenseItem` in `app/models/finance.py`, the
totals computed, and the database refusing a car item whose amount is not distance × rate,
a negative amount, or an approval above the claim. Open: the endpoints and the screen.

Tests: `api/tests/stories/test_expenses.py::TestClaimTotals`,
`api/tests/stories/test_expenses.py::TestTheDatabaseKeepsTheBooksStraight`

### F-3 ○ The treasurer approves, returns or rejects a claim
As the **event's treasurer** I want to **check each claim and decide it**, so that **only
justified costs are paid**.

Acceptance criteria:
- Approve (optionally lowering single items), return with a note, or reject with a note.
- **Nobody decides their own claim**, whatever relations they hold.
- Every transition is in the audit log with who and when.

Tests: none yet

### F-4 ◐ The treasurer pays and exports
As the **event's treasurer** I want to **mark approved claims as paid and export them**,
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

Done: the data model and the computed payment state. Open: the endpoints, the export, the
screen.

Tests: `api/tests/stories/test_expenses.py::TestPaymentState`,
`api/tests/stories/test_expenses.py::TestTheDatabaseKeepsTheBooksStraight::test_a_claim_is_allocated_to_a_payment_once`

### F-5 ◐ Upload documents to a claim, readable only by the claimant and the treasurer
As a **claimant** I want to **attach receipts, invoices and tickets to my claim**, so that
**the treasurer can check what I paid**.

Acceptance criteria:
- Any number of documents per claim, each optionally tied to one item.
- Uploaded and deleted while the claim is `draft` or `returned`; frozen from submission.
- The club's policy names the kinds that need a document; submitting without one is
  refused (`expense-document-missing`) and names the items.
- PDF, JPEG or PNG by content, at most 10 MB, stored under a random name. Read through one
  endpoint that admits the claimant and the event's treasurer, and logs every look.

Done: `ExpenseDocument`, with the size limit in the database. Open: the upload, the
serving endpoint, the check by content.

Tests: `api/tests/stories/test_expenses.py::TestTheDatabaseKeepsTheBooksStraight::test_a_document_is_at_most_ten_megabytes`
