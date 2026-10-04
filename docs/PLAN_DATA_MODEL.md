# Plan: permissions, states, finance

Status: **proposal, 2026-10-04** — nothing below is built yet unless it says "exists".
Decisions still open are collected at the end; answer those before the stories are
written.

**Scope: authorization, not authentication.** How a person proves who they are (login,
identities, tokens) is out of scope here and comes later. This plan is about what an
already identified user may see and do: on which object, in which state, with which
money. Section 1 comes first because states (§2) and finance (§3) are both expressed
through it. Every transition and every claim decision below is a `User.can` / `holds`
check on a named object, never a role flag.

Three principles from `CLAUDE.md` carry every choice here, so they are not re-argued:

1. **Permissions are relation tuples** (`user:relation:object`), checked by
   `User.can(relation, on=obj)`. New powers are new relations in `MODEL`, never a column
   or a role flag.
2. **Derived, never stored.** Points, readiness, frozen-ness, waiver status. The same
   holds for an event's displayed *phase* and a claim's *total*.
3. **Orthogonal flags instead of one state machine.** Who may *see* a thing
   (`published`) and where it *stands* (`status`) are separate columns.

---

## 1. Permissions

### 1.1 Objects and relations (exists, plus one relation)

| Object | `admin` | `manager` | `race_officer` | `jury` | `member` | `editor` | **`treasurer`** (new) |
|---|---|---|---|---|---|---|---|
| `site` (the association) | ✓ | — | ✓ | — | — | ✓ | — |
| `club` | ✓ | ✓ | — | — | ✓ | — | ✓ |
| `series` | ✓ | ✓ | ✓ | ✓ | — | — | — |
| `event` | ✓ | ✓ | ✓ | ✓ | — | — | ✓ |

Proposed addition to `MODEL` (`api/app/models/auth.py`):

```
type club
  relations
    define treasurer: [user] or admin

type event
  relations
    define treasurer: [user] or admin or treasurer from host_club
```

**The event's costs are paid by its host club** (decision of 2026-10-04). Race
officers, jury and umpires travel to an event, and the club hosting it reimburses them.
So the **event** has a treasurer: the person who checks and pays its claims. The host
club's treasurer is automatically treasurer of every event the club hosts, the same way
the host club's admin is admin of its events. A treasurer appointed for one event only
(`user:treasurer:event`) sees that event's claims and no other money of the club.

**Not on series or site:** neither pays. A series' or the site's admin still reaches an
event's claims through `admin` ⇒ `treasurer`, because "admin is everything within"
(open question Q1).

**An event without a host club has no payer.** Filing a claim on it is refused with
`/errors/event-has-no-host-club`, until a host club is set.

### 1.2 Who may do what

Each row names the relation `User.can` checks and the object it is checked on. "←"
means the relation is also inherited by the rewrite rules, e.g. an event's `manager`
inherits from its series, its host club, the site editor and the site race committee.

| Action | Relation · object |
|---|---|
| Create club, enroll it in a series | `editor` · site |
| Create series | `admin` · site |
| Edit series: dates, participants, publish, scoring | `manager` · series |
| Create event | `manager` · site, the series, or the host club |
| Edit event, publish, draw, start, finish, cancel, reopen | `manager` · event ← |
| Run races, enter results, trackers | `race_officer` · event ← |
| Announcements, protest decisions | `jury` · event ← |
| Write/delete tuples on an object | `admin` · that object ← |
| Put people in a club | `admin` · club |
| Register for series/event, squad, crew | `manager` · club |
| See the club roster | `member` or `manager` · club, `editor` · site |
| **File an expense claim** on an event | a direct `race_officer`/`jury`/`manager` tuple on the event or its series, per the host club's policy (§3.4) |
| **See / decide / pay a claim** | `treasurer` · event ← (inherited from the host club) |
| **Set the club's expense rates** | `treasurer` · club |
| **Approve one's own claim** | never (four-eyes rule, enforced in the service) |

The CLAUDE.md "Permissions by area" table gets replaced by this one once it is agreed.
It still names `club_manager` as a role, which is a leftover from before tuples.

---

## 2. States

### 2.1 Event: two stored fields, two computed facts, and one phase for display

**Stored (exists):**

| Field | Values | Answers |
|---|---|---|
| `Event.published` | `false` / `true` | Who may see it |
| `Event.status` | `planned` → `live` → `final`, `cancelled` | Where it stands sportingly |

**Computed (exists):** `readiness(event)` returns a list of reasons, and
`configuration_frozen(event)` says whether the first race has happened.

**New, computed: `Event.phase`.** One value the UI can show as a badge or filter on, so
nobody has to combine four facts in a component. Derived in
`app/services/event_readiness.py`, never stored:

| Phase | Condition | Badge |
|---|---|---|
| `draft` | `planned`, not published | Draft |
| `announced` | `planned`, published, entries not open or closed | Announced |
| `entries_open` | `planned`, published, today ≤ `entries_close_on` | Entries open |
| `ready` | `planned`, readiness empty, pairing list drawn | Ready |
| `live` | `live` | Live |
| `provisional` | `final`, today < `results_official_at` | Results provisional |
| `final` | `final` | Final |
| `cancelled` | `cancelled` | Cancelled |

Two new optional columns make the phases above real:

- `Event.entries_close_on: date | None`: the entry deadline. Empty means no deadline.
  This is the "fixed deadline structure" `concepts.md` deferred. It is now a single
  date, and still optional. (Series gets the same column for series registration.)
- `Event.results_official_at: datetime | None`: when protest time ends and results stop
  being provisional. Set by `finish`, or later by the jury. It locks nothing. A protest
  heard after it still lands, consistent with "closing freezes nothing".

Transitions stay in one service each, and each one writes an `AuditLog` row:
`publish`/`unpublish` (any time), `start` (gated by readiness), `finish`, `cancel`
(from `planned` or `live`), `reopen` (`final`→`live`, `cancelled`→`planned`).

**Not adding:** `postponed` (a new date on a `planned` event says it), `archived` (a
`final` event in a past year already *is* archived; the current-year rule handles the
public page).

### 2.2 Series: published is stored, phase is derived

`Series.published` exists. Its phase is derived from its events: `upcoming` (no event
`live`/`final`), `running`, `completed` (every event `final` or `cancelled`, and at
least one `final`). `entries_close_on` as for an event. There is no stored status
column. A series' state is exactly the state of its events, and a second copy would
drift.

### 2.3 Team (participation): one value added

| `Team.status` | Meaning |
|---|---|
| `requested` | Club applied. Counts nowhere. (exists) |
| `accepted` | Participant. (exists) |
| `rejected` | With `decision_note`. (exists) |
| **`withdrawn`** | Club pulled out. The row stays, because results or a squad may hang off it. Counts as "missed" in series scoring (participants + 1), not as "never registered". |

Today the only exit is deleting the row, which is impossible once a race exists.
`withdrawn` gives that case a name.

### 2.4 Race: unchanged

`scheduled` → `running` → `finished` / `abandoned`, owned by
`app/services/race_state.py` (exists).

### 2.5 Expense claim and payment: two state machines, not one

**Approval and payment are separate, as in every established system.** Odoo
(`hr.expense.sheet.approval_state` plus `payment_state`, and `account.payment` as its own
record), ERPNext (an Expense Claim's `approval_status` plus a separate Payment Entry),
SAP Concur (approval status plus payment status) and Stripe (`Payout` with its own
lifecycle) all split the two. The reason applies here too: **a transfer can fail or come
back days after the claim was approved** (wrong IBAN, closed account; SEPA "returns"
arrive after settlement). That must never reopen the approval, and one transfer often
settles several claims of the same person. (Expensify shows one combined status, but
that is a simplified UI on top.) Sources are in §6.

**The claim stops at the decision.** It is a linear workflow with one owner per step,
and an auditor will ask "who approved this, when":

```
          ┌──────── returned ◄────────┐
          ▼                           │
draft ──► submitted ──────────────────┤
  │           │                       ▼
  ▼           ├──► approved      rejected
withdrawn     │
              └──► withdrawn
```

| `ExpenseClaim.status` | Who moves it | What can still change |
|---|---|---|
| `draft` | claimant | everything, documents included |
| `submitted` | claimant → | nothing. Rates, payer and documents are frozen now |
| `returned` | treasurer, with a note | claimant edits and resubmits |
| `approved` | treasurer (not the claimant) | per-item approved amount is set at approval |
| `rejected` | treasurer, with a note | final |
| `withdrawn` | claimant, from `draft`/`submitted`/`returned` | final |

**"Paid" is not a claim status. It is computed from the payments** (derived, never
stored, like points). The names follow Odoo's `payment_state`:

| Claim's payment state | Condition |
|---|---|
| `unpaid` | approved, no payment allocated |
| `in_payment` | allocations exist, but not all are on `settled` payments |
| `partially_paid` | settled allocations < approved total |
| `paid` | settled allocations = approved total |

**The payment is its own record with its own lifecycle** (Odoo `account.payment`,
Stripe `Payout`, SEPA pain.002):

```
draft ──► issued ──► settled
  │          │          │
  ▼          ▼          ▼
cancelled  failed     failed   (a return after settlement)
```

| `Payment.status` | Meaning | Who |
|---|---|---|
| `draft` | prepared, not sent: amounts can still change | treasurer |
| `issued` | transfer made or SEPA file exported (Odoo `in_process`, Stripe `in_transit`) | treasurer |
| `settled` | confirmed on the bank statement (SEPA `ACSC`) | treasurer |
| `failed` | rejected or returned, with a reason code (SEPA R-reason, e.g. `AC04` closed account) | treasurer |
| `cancelled` | dropped before it was issued | treasurer |

**Never edit, never delete; reverse instead** (Fowler's *Reversal Adjustment*, Odoo's
reset-to-draft, Stripe's `reversed_by`). A failed payment stays as it is, and the claim
falls back to `unpaid` by itself because the computation no longer counts it. A new
payment is made. Every transition of either machine writes an `AuditLog` row with the
person, the time and the reason. `returned`, `rejected` and `failed` require a note.

**Four eyes, as German club finance rules (Finanzordnungen) require:** whoever confirms
a claim is "sachlich und rechnerisch richtig" (factually and arithmetically correct) is
recorded (`decided_by`), and whoever issues the payment is recorded too
(`Payment.issued_by`). The claimant can never be either; that is enforced. Whether
approver and payer must also be **different people** is a setting in the club's policy
(`"separate_payer": false` by default), because a small club often has a single
treasurer (Q2).

## 3. Finance: expense claims

### 3.1 What it covers

Travel by car (km), public transport, accommodation, meals or a per-diem, and other
costs that someone incurs **for an event**. Typical claimants: race officers, jury and
umpires travelling to a matchday. **The host club pays**, and the event's treasurer
decides. Every claim belongs to exactly one event; there are no claims without one.

### 3.2 Tables

```
ExpenseClaim                                    ExpenseItem
───────────────────────────────                 ───────────────────────────────
id                                              id
claimant_user_id   → app_user                   claim_id        → expense_claim
event_id           → event    (required)        kind            travel_car | travel_public
payer_club_id      → club     snapshot of the                   | accommodation | per_diem
                    host club at submit                         | meals | other
                                                incurred_on     date
                                                description     str
title              str                          # car only
status             ClaimStatus                  distance_km     int | None
payee_name         str   } snapshot at          rate_cents      int | None   (snapshot)
iban               str   } submit, encrypted    # all kinds
submitted_at       datetime | None              amount_cents    int          (claimed)
decided_by_user_id → app_user | None            approved_cents  int | None   (None = as claimed)
decided_at         datetime | None
decision_note      str | None
```

Payment and allocation (§2.5):

```
Payment                                         PaymentAllocation
───────────────────────────────                 ───────────────────────────────
id                                              id
payer_club_id      → club                       payment_id     → payment
payee_user_id      → app_user                   claim_id       → expense_claim
payee_name, iban   snapshot when issued         amount_cents   int
(amount = Σ allocations, derived)                UNIQUE(payment_id, claim_id)
status             PaymentStatus
method             transfer | cash | sepa_file
reference          str  (Verwendungszweck)
issued_by_user_id  → app_user | None
issued_on          date | None
settled_on         date | None
failure_reason     str | None (SEPA R-code or free text)
```

One payment settles any number of claims **of one payee for one paying club**. Both are
checked when allocating, and a claim can be settled over several payments (partial
payment, or a new payment after a failed one). The allocation table is what makes both
possible, as ERPNext's payment references do. Approved amounts are never exceeded: the
service refuses an allocation that would push settled plus open allocations past the
claim's approved total.

**Money is integer cents, currency fixed to EUR.** Never `float`, never `Numeric` read
into floats. A currency column waits until a non-EUR claim exists.

**Totals are derived:** `claimed = Σ amount_cents`,
`approved = Σ coalesce(approved_cents, amount_cents)` over items. They are not stored,
the same as points.

**Car items:** `amount_cents = distance_km × rate_cents`, computed by the service on
save. The rate comes from the policy and is frozen on the item at submit. A later rate
change does not reprice claims already filed.

**The payer is the event's host club, recorded when the claim is submitted**
(`payer_club_id`). The permission check is still `can(TREASURER, on=claim.event)`. The
snapshot exists for the books: if the host club changes after a claim was submitted, the
claim stays with the club it was addressed to, and the treasurer list shows the mismatch
instead of moving money silently.

**Documents: uploading proof is part of the claim.** Receipts, hotel invoices, train
tickets, a parking slip: any number per claim, in a table of their own rather than one
path per item, because one hotel invoice often covers several items and one item can
need two papers (outbound and return ticket).

```
ExpenseDocument
───────────────────────────────
id
claim_id           → expense_claim   (required)
item_id            → expense_item    (nullable: a document for the whole claim)
stored_name        str   random, under uploads/expenses/ — never the original name
original_name      str   shown in the list, never used as a path
content_type       str   application/pdf | image/jpeg | image/png
size_bytes         int   ≤ 10 MB
uploaded_by_user_id → app_user
created_at         (TimestampMixin)
```

- **Who uploads, and when:** the claimant, while the claim is `draft` or `returned`.
  Deleting is possible in the same states. From `submitted` on, the documents are
  frozen together with the amounts, because they are what was approved. A `returned`
  claim is where "please add the hotel invoice" gets answered.
- **Required where a cost needs proof:** the policy names the kinds that need one
  (`"document_required": ["travel_public", "accommodation", "other"]`). Car mileage and
  a flat per-diem need none. `submit` refuses a claim with an item of such a kind and no
  document attached to it (or to the claim), with
  `/errors/expense-document-missing` listing the item ids. The UI must say *which* item
  needs one.
- **Who reads:** the claimant and `treasurer` on the claim's event, nobody else, through
  one serving endpoint (`GET /api/expenses/documents/{id}`) that checks access and logs
  every look in `AuditLog`. These are the same rules as the waiver scan, the most
  sensitive files on the site. A receipt carries addresses, card numbers and hotel
  names.
- **Checked on upload:** the type is checked by its content, not by the file name or the
  declared type. Size is capped at 10 MB. Images are stored as uploaded, not
  re-encoded, because a receipt must stay legible.
- **Deleted with the claim's personal data:** when the claimant deletes their account
  (Z-7), the documents of claims that are closed (fully paid, `rejected`, `withdrawn`) are
  kept as long as bookkeeping rules require (German law requires 10 years for
  accounting records). This is a retention rule to confirm (Q5), not something to
  decide in code.

**IBAN** is personal financial data. It is snapshotted on the claim, because a payout
must go to the account the claimant named when submitting, not the one on their profile
today. It is shown only to the claimant and the treasurer, and deleted (nulled) with the
account under Z-7 once the claim is fully paid or otherwise closed.

### 3.3 Policy: rates belong to the paying club, as JSON

Same reasoning as `Series.scoring`: rates differ between clubs and change between
years, and nothing queries them. One JSON column `Club.expense_policy`, plus a site
default in settings for a club that has set none:

```json
{
  "km_rate_cents": 30,
  "per_diem_cents": 1400,
  "accommodation_cap_cents": 12000,
  "claim_deadline_days": 60,
  "eligible": ["race_officer", "jury", "manager"],
  "kinds": ["travel_car", "travel_public", "accommodation", "per_diem", "other"],
  "document_required": ["travel_public", "accommodation", "other"]
}
```

`app/services/expenses.py::policy_for(event)` reads the host club's policy and falls
back to the site default, tolerating anything unexpected the way `PrintSettings` does.

### 3.4 Who may file a claim on an event

The claimant must hold one of the policy's `eligible` relations **directly** on the
event or on its series, e.g. `user:race_officer:event:7` or `user:jury:series:2`. A site
editor "inherits" `manager` on every event, but that does not entitle them to travel
costs for all of them. So this check is `holds` (the tuple itself), deliberately not
`can`. The event's treasurer cannot approve a claim they filed themselves (§2.5).

### 3.5 What is deliberately not modelled yet

- **Entry fees / invoices to clubs**, i.e. money flowing *in*. Different direction,
  different documents. If it comes, it gets its own table, not a sign flip on claims.
- **Budgets per event** ("max €2,000 travel for matchday 3"). Derivable later as a sum
  over approved claims against a number in the policy.
- **A per-event rate override.** The club's policy applies to all its events until a
  club asks for different rates at one of them.
- **SEPA XML export and bank-statement import.** A CSV of `issued` payments (payee,
  IBAN, amount, reference) is the first step, and the treasurer sets `settled` or
  `failed` by hand. pain.001 export and pain.002/camt import come if a treasurer asks for
  them; the states above already have room for both.
- **Two-step approval** (event manager confirms the trip happened, treasurer releases the
  money). See Q2; the payment step already gives a second pair of eyes if a club wants
  `separate_payer`.

---

## 4. Order of work (per CLAUDE.md: story → test → code)

1. ✓ Stories in `docs/userstories/treasurer.md` (letter `F`): **F-1** the treasurer
   relation, **F-2** file a claim, **F-3** decide, **F-4** pay and export, **F-5**
   documents. Still to do: extend **VA-8** with `phase`, `entries_close_on` and
   `results_official_at`, and **A-9** with `withdrawn`.
2. ✓ `treasurer` in `MODEL`, tested by
   `api/tests/stories/test_treasurer.py::TestTreasurerRelation` (Story F-1).
3. ✓ Models `ExpenseClaim`, `ExpenseItem`, `ExpenseDocument`, `Payment`,
   `PaymentAllocation` (`app/models/finance.py`) and `Club.expense_policy`, migration
   regenerated; tested by `api/tests/stories/test_expenses.py`. Still to do: the new event
   columns (`entries_close_on`, `results_official_at`) with the VA-8 extension.
4. `app/services/expenses.py` (claim transitions, four-eyes check, rate and payer
   snapshot) and `app/services/payments.py` (payment transitions, allocation limits,
   the computed payment state). Routers, then `gen-api-client.sh`.
5. Frontend: "My claims" on the account page, a "Claims" tab on the event for whoever
   holds `treasurer` on it.

---

## 5. Open questions

- **Q1.** Should the series' and the site's admin see an event's claims? This is the
  current rule (admin is everything within, and `treasurer` includes `admin`). The
  alternative is to limit the event's `treasurer` to `[user] or treasurer from
  host_club`, so that only the paying club sees its money.
- **Q2.** Four eyes: is "the claimant can neither approve nor pay" enough, with
  `separate_payer` (approver ≠ payer) as a per-club option? Or should the event manager
  also confirm the trip happened before the treasurer approves? That would add a
  `confirmed` status between `submitted` and `approved`.
- **Q3.** Do sailors of the host club or the visiting crews claim too, or only officials
  (race officer, jury, umpires, the event's manager)?
- **Q4.** Per-diem rules: a flat amount per day from the policy, or the German statutory
  tiers (8 h / 24 h, deductions when meals are provided)? Flat is much simpler, and the
  tiers can be a later policy variant.
- **Q5.** Retention of expense documents: kept 10 years after payment (German
  bookkeeping rules for the paying club), even when the claimant deletes their account?
  The club is the one keeping the books, so the club may prefer to download and archive
  them itself, and the site deletes after payment plus a grace period.

---

## 6. Sources for the claim/payment split (researched 2026-10-04)

- Odoo 18 `hr.expense.sheet` (`state`, `approval_state`, `payment_state`):
  <https://raw.githubusercontent.com/odoo/odoo/18.0/addons/hr_expense/models/hr_expense_sheet.py>
- Odoo 18 `account.payment` (draft, in_process, paid, canceled, rejected):
  <https://raw.githubusercontent.com/odoo/odoo/18.0/addons/account/models/account_payment.py>
- ERPNext Expense Claim (`approval_status` separate from `status`):
  <https://raw.githubusercontent.com/frappe/hrms/develop/hrms/hr/doctype/expense_claim/expense_claim.json>
- ERPNext Payment Entry (one payment, several references, partial allocation):
  <https://docs.frappe.io/erpnext/user/manual/en/payment-entry>
- SAP Concur approval vs. payment status:
  <https://docs.workato.com/en/connectors/concur/triggers/new-expense-report.html>
- Expensify report statuses (one combined axis):
  <https://help.expensify.com/articles/new-expensify/reports-and-expenses/Understanding-Report-Statuses-and-Actions>
- Stripe Payout (pending, in_transit, paid, failed, canceled; `reversed_by`):
  <https://docs.stripe.com/api/payouts/object>
- SEPA pain.002 statuses and R-transactions:
  <https://www.cobase.com/insight-hub/pain.002-status-message-guide>,
  <https://europeanpaymentscouncil.eu/sites/default/files/kb/file/2024-11/EPC135-18%20v6.0%20Guidance%20on%20Reason%20Codes%20for%20SCT%20R-transactions.pdf>
- Reversal instead of edit: <https://martinfowler.com/eaaDev/ReversalAdjustment.html>
- German club finance rules ("sachlich und rechnerisch richtig", four eyes), e.g.
  <https://tu-dresden.de/bu/bauingenieurwesen/iwd/ressourcen/dateien/verein/Finanzordnung-Foerderverein_2022-05.pdf>
  (taken from search results; the individual documents were not read in full).
