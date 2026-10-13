# Taking money online — implementation plan

Status: **plan, nothing built** (written 2026-10-13 from a discussion of options A–E:
GiroCode, statement import, payment provider, PayPal, direct debit — option C chosen).
Stories come first (`CLAUDE.md`, "How to update the docs"): this file is what the stories
are written *from*. Once a story exists, it is the truth and this file only says why the
order is what it is.

Two money flows, and they are not symmetrical:

| Flow | Example | Today | This plan |
|---|---|---|---|
| **In** — a person or a club pays a club | boat charter, entry fee, training camp | ❌ nothing | online through a provider, transfer as fallback |
| **Out** — a club pays back a person | a helper's train ticket, a jury member's hotel | ● F-2…F-8: claim, receipts, approval, SEPA file, GiroCode | stays on the bank file, see §6 |

---

## 1. Decisions this plan rests on

1. **The money goes straight to the club that is owed it, never through the association.**
   Each club connects its *own* provider account (Stripe Connect *standard* accounts, or
   Mollie Connect with OAuth); a payment is a **direct charge** on that account. Collecting
   other clubs' money on the DSL's account and passing it on would be a payment service in
   the sense of the ZAG (*Finanztransfergeschäft*) and would put the association in the
   middle of every refund and chargeback. With direct charges the provider holds the
   licence and the club holds its customer relationship. The DSL e.V. is just one more
   club that connects an account.
2. **Hosted checkout, never a card form of our own.** The payer is sent to the
   provider's page and comes back. No card or bank data reaches our server (PCI SAQ-A), and
   payment methods (card, Apple/Google Pay, PayPal, SEPA direct debit, later Wero) are
   switched on in the club's provider dashboard, not in our code.
3. **"Paid" comes from the webhook, never from the return URL.** The return page only
   shows the state; the signed webhook writes it. It is idempotent (the provider's event
   id is stored), and it refetches the object from the provider instead of trusting the
   payload. Live update after the commit through `app/live.py`, as everywhere else.
4. **A transfer is always possible.** Every receivable also shows the club's IBAN, an
   unambiguous reference and a GiroCode (`segno`, as in F-8, with the club as recipient).
   A club without a provider account still gets everything except the button. Clubs
   paying clubs (the charter) will often take this path.
5. **Paid is computed, never stored**, as for claims (`PLAN_DATA_MODEL.md` §2.5): a
   receivable's state is derived from its incoming payments. A refunded or charged-back
   payment stops counting. The receivable never "reopens" by hand.
6. **Surcharges are not allowed.** The EU ban on surcharges (PSD2, § 270a BGB) forbids
   adding the card fee to the price. The club sets its prices knowing the fee. The site
   shows the club its fees in the books (§5) and never adds a "+ fee" line for the payer.
7. **One provider, behind a small Protocol** (`app/payments/provider.py`), with a
   `FakeProvider` for tests and the e2e stack. This mirrors `app/tracking/`: the choice is
   made in one place. We do not build two real adapters up front.

### Stripe or Mollie (decision D1, before phase 2)

| | Stripe | Mollie |
|---|---|---|
| Club onboarding | Connect standard account; the club owns a full Stripe account | Connect for Platforms, OAuth to the club's own Mollie account |
| Fees (standard, EU cards / SEPA DD) | ~1.5 % + 0.25 € / ~0.35 € | ~1.8 % + 0.25 € / ~0.35 € |
| PayPal | yes, as a Stripe method | yes |
| Developer tooling | Python SDK, test mode, CLI webhook forwarding, test clocks | good, but thinner |
| Seat | US/IE | NL, German-language support |

Fees are list prices from public sources; check them in the account before deciding.
**Recommendation: Stripe**, because testability decides how cheaply we can build and keep
this green. Mollie remains a second adapter if clubs ask for it.

### All providers compared (2026-10-13)

●● very good · ● good · ◐ fair · ○ poor. Prices are list prices, partly from third-party
comparison sites that disagree with each other. Check the official price pages before
deciding.

| Criterion | Stripe | Mollie | PayPal (direct) | Unzer | Payone | SumUp |
|---|---|---|---|---|---|---|
| Known to German payers | ◐ brand barely visible in checkout | ◐ same | ●● best-known online method | ○ | ◐ through the Sparkassen | ● known from card terminals |
| Payment methods | card, Apple/Google Pay, SEPA DD, PayPal, Klarna; Wero open | the same plus Wero (EPI member, DE start 2026) | PayPal, card, DD through PayPal | very many, incl. Wero | card, girocard, DD | card, payment links |
| Usability for the payer | ●● | ●● | ●● log in and done | ● | ◐ | ● |
| Usability for the club | ● online onboarding ~15 min, dashboard partly English | ●● German, lean, German support | ● familiar; account freezes reported | ◐ offer on request | ○ contract, 24 months | ●● very simple |
| Card fee (EEA) | **1.5 % + 0.25 €** | ~1.8 % + 0.25 € | 2.49–2.99 % + 0.35–0.39 € (non-profit rate on application) | ~1.4–1.5 % + 0.20 €, negotiated | 1.9 % credit card, often plus a monthly flat fee | 2.5 % online (or 19 €/month + ~0.8–1 %) |
| SEPA direct debit | 0.35 € | 0.35 € | – | on request | on request | – |
| Monthly fee / term | none | none | none | individual | yes, 24–36 months | none or subscription |
| **Platform model** (each club its own account, we initiate the payment) | ●● Connect standard accounts | ● Connect for Platforms (OAuth); split payments on request | ◐ partner contract only | ○ | ○ | ○ |
| Development and testing | ●● test mode, CLI webhook forwarding, Python SDK | ● good API, fewer test tools | ◐ | ◐ | ○ | ◐ |
| Paying out to third parties (claims) | ○ Global Payouts in private preview in DE | ○ no | ◐ Payouts API, only to PayPal accounts, after approval | ○ | ○ | ○ |
| Seat / data protection | US/IE | NL (EU) | US/LU | DE | DE | DE/UK |
| Risk of account freeze / reserve | ◐ | ◐ | ○ often reported | ● | ● | ◐ |

What the fees mean for two typical payments:

| Payment | Stripe | Mollie | PayPal direct | SEPA DD (Stripe/Mollie) |
|---|---|---|---|---|
| 30 € entry fee | 0.70 € | 0.79 € | 1.13–1.29 € | 0.35 € |
| 450 € boat charter | 7.00 € | 8.35 € | 11.56–13.85 € | 0.35 € |

**PayPal, Unzer, Payone, SumUp** were compared too. None of them has a
platform model a small site can join without a partner contract, which rules them out as
*the* provider (§1, decision 1). PayPal is the best-known brand with German payers (EHI
2025: 28.5 % of online sales), so it is offered **as a payment method inside** Stripe or
Mollie, not as its own integration. SumUp remains an option for card payments **on site**
at a regatta. That is outside this plan.

---

## 2. What is built, phase by phase

Every phase gives something usable on its own. Phase 1 needs no provider at all.

### Phase 1 — Receivables, paid by transfer (no provider)

The data model and both screens. Afterwards a club can bill, people can see what they
owe, and the treasurer ticks payments off by hand.

- **F-9 Bill someone.** A club's manager or treasurer (or an event's, for an event the
  club hosts) creates a receivable: payee club, payer (a person *or* a club), title,
  amount, optional event, optional due date. One at a time, or **for every participant
  of an event** (charter per team, `Team.event_id`), which is the main use case.
- **S-8 What I owe.** A card in my space (`/api/me/contexts` gets a code
  `receivables_open` with a count) lists what I owe, and what my club owes if I am its
  manager or treasurer. For each item: the amount, the club's IBAN, the reference
  (`R-<id>`) and the GiroCode.
- **F-10 Record a transfer received.** "Received" on a receivable writes an incoming
  payment (`method = transfer`) with the date. The same four-eyes rule as F-4 applies:
  nobody records a payment to their own receivable.

### Phase 2 — Connect a club, pay online

- **F-11 Connect the club's payment account.** The club's admin or treasurer starts the
  provider's onboarding from the club page and comes back. We store the account id and
  whether it may take charges (`charges_enabled`, updated by the `account.updated`
  webhook). No secret is stored per club: the platform key acts *on behalf of* the
  account.
- **S-8 (extended) Pay online.** "Pay" creates a checkout session on the club's account
  for exactly the open amount, with the reference as metadata, and sends the payer there.
  The webhook writes the incoming payment, including the provider's fee and payment id.
  The page flips to "paid" over SSE.
- One page that tells a club with no connected account, in its own words, why the button
  is missing.

### Phase 3 — Things you can book yourself

Billing everyone by hand does not scale to "anyone may book a training camp".

- **F-12 An offer.** A club or an event offers something at a price: title, price,
  optional capacity, a booking window, and who may book (`anyone signed in`, `members of
  the club`, `managers of a participating club`). Booking it creates the receivable
  (phase 1) and goes straight to checkout (phase 2). If a capacity is set, a booking
  counts only once paid. An unpaid one is released after 30 minutes (the checkout
  session's expiry).
- On the event page, offers appear for whoever may book them. For a person in no
  context, the offer itself is the way in.

### Phase 4 — Refunds and books

- **F-13 Refund.** The treasurer refunds all or part of a paid receivable through the
  provider (`charge.refunded` → the incoming payment is reduced). A chargeback
  (`charge.dispute.*`) is shown, never hidden. **Cancelling an event (VA-10) refunds
  nothing automatically**, because a cancelled event can be reopened. The treasurer gets
  the list of what was paid for it and decides.
- **F-14 The year's income as a spreadsheet** (`openpyxl`, like F-7): gross, provider
  fee, net, payout to the bank (the provider pays out in batches, and that batch is what
  the bank statement shows), refunds. This is what the *Kassenprüfung* needs. Together
  with F-7's export it gives the club's whole cash book.
- A simple receipt (*Quittung*) as PDF (`reportlab`, as for the waiver form). A formal
  invoice is Q3.

### Phase 5 — only if asked for

- Import of the bank statement (CAMT.053) to tick transfers off automatically. This is
  option B of the discussion, and it only matters once transfers are frequent.
- Membership fees by direct debit (pain.008 with `sepaxml`, creditor id per club).
  Better done in the club's own bank than through a provider at ~0.35 € per debit.

---

## 3. Data model (sketch, `app/models/finance.py`)

```
ClubPaymentAccount   club_id (unique) · provider · account_ref · charges_enabled · connected_by
Offer                payee_club_id · event_id? · title · price_cents · capacity? · opens_at · closes_at · audience
Receivable           payee_club_id · payer_user_id? · payer_club_id? · event_id? · offer_id?
                     title · amount_cents · due_on? · reference (unique) · cancelled_at? · created_by
IncomingPayment      receivable_id · method (online | transfer) · provider? · provider_ref? (unique)
                     amount_cents · fee_cents? · status (pending | succeeded | failed | refunded | disputed)
                     refunded_cents · received_on · recorded_by_user_id?
ProviderEvent        provider · event_id (unique) · received_at          -- webhook idempotency
```

- Exactly one of `payer_user_id` / `payer_club_id` (a CHECK, like `Team`'s two ids).
- A receivable's state (`open`, `partially_paid`, `paid`, `refunded`, `cancelled`) is
  computed from its payments, as `claim_payment_state` is for claims.
- One receivable per payment. Several receivables in one checkout is not built until
  someone asks: allocations are what made the outgoing side complex, and the incoming side
  does not need them.
- **Not** reusing `Payment` with a direction flag: the outgoing payment has a payer club
  and a payee person, the incoming one the opposite, plus a provider. One table with two
  meanings is what `PLAN_DATA_MODEL.md` §2.5 warned against.

## 4. Permissions

No new relation. The existing tuples cover it (`MODEL` in `app/models/auth.py`):

| Action | Who |
|---|---|
| Connect / disconnect the club's provider account | the club's `admin` or `treasurer` (direct tuple, not `can(manager)` — same reasoning as claims) |
| Create a receivable or offer for a club | the club's `manager` or `treasurer` |
| … for an event | the event's `manager` or `treasurer` (the host club's, by the model) |
| Record a transfer, refund | the payee club's / event's `treasurer` or `manager`, never on their own receivable |
| See and pay a receivable | the payer person; for a club payer its `manager` and `treasurer` |
| Book an offer | as its `audience` says |

## 5. Configuration, secrets, testing

- `SBL_PAYMENTS_PROVIDER = off | fake | stripe` (default `off`: phase 1 works, there is
  no button). `SBL_STRIPE_SECRET_KEY`, `SBL_STRIPE_WEBHOOK_SECRET` come from the
  environment, never `.env` in the repo. Staging runs **Stripe test mode**, so a
  stakeholder pays with `4242 4242 4242 4242`.
- **Tests never call the provider** (`CLAUDE.md`): `FakeProvider` in story tests;
  recorded webhook payloads in `api/tests/fixtures/stripe/` for signature, parsing and
  idempotency (the same event twice changes nothing; events arriving in the wrong order
  still end right).
- **e2e** with `fake`: the fake checkout is one page of our own that redirects back and
  fires the webhook. The browser walks booking → paying → "paid" without the network.
- The free Render instance sleeps. A webhook wakes it, and Stripe retries for three days,
  so nothing is lost. The return page polls once in case the webhook is still on its way.

## 6. Paying claims out — why the provider does not do it

The wish "receipts are paid simply" is already mostly met by F-7 (one SEPA file, one TAN
per run) and F-8 (GiroCode per claim). **A payment provider does not make it simpler**:

- Stripe and Mollie pay out only to the account holder's **own** bank account. Paying a
  helper through Connect would require every helper to open an account with KYC first.
- Stripe's *Global Payouts* (paying arbitrary third parties) is in private preview in
  Germany, needs Stripe Treasury, and is aimed at businesses with their own money
  transmitter licence. It is not something a sailing club can sign up for.

So outgoing stays on the bank file, and this plan adds only what makes it faster:

- **Notify the claimant** when their claim is approved and when it is paid (mail, plus
  the my-space code).
- **Offsetting:** if a person both owes the club (phase 1) and is owed by it, the
  treasurer can settle one against the other. This comes later, and only if it happens
  in practice.
- A live bank connection (FinTS/EBICS, or a business-bank API like Qonto/Wise) would be
  the only way to "one click, money gone". It contradicts the decision of 2026-10-07
  (no bank login stored here) and stays `docs/findings.md` material.

## 7. Open questions

| # | Question | Who answers | Blocks |
|---|---|---|---|
| D1 | Stripe or Mollie? (§1) | user | phase 2 |
| Q1 | Is the platform model (direct charges, DSL takes **no** application fee) right, or should the DSL take a fee per payment for running the site? A fee makes the DSL a party to the payment and needs its own tax treatment. | DSL board | phase 2 |
| Q2 | Charter between clubs: is it the host club's *wirtschaftlicher Geschäftsbetrieb* (VAT)? | the clubs' tax advisers | phase 4 receipts |
| Q3 | Do clubs need formal invoices (§ 14 UStG), and from 2027/28 **e-invoices** (XRechnung/ZUGFeRD) for club-to-club charges? If so, a library (e.g. `drafthorse` for ZUGFeRD), not our own format. | tax adviser | phase 4 |
| Q4 | Can a guest without an account book (training camp for non-members), or is signing in required? Plan: signed in, as for the waiver. | user | phase 3 |
| Q5 | What happens to paid bookings when an event is cancelled: always a refund, or the club decides? Plan: the club decides (F-13). | user | phase 4 |

## 8. Sources (checked 2026-10-13)

- Stripe Global Payouts, availability and requirements: <https://docs.stripe.com/global-payouts>,
  <https://stripe.com/blog/global-payouts-a-new-way-to-send-money-directly-to-third-parties>
- Stripe Connect cross-border payouts (connected accounts only): <https://docs.stripe.com/connect/cross-border-payouts>
- Mollie Connect split payments: <https://docs.mollie.com/docs/splitting-payments>
- Mollie list prices (third-party summary, verify in account): <https://www.yagemi.de/blog/e-commerce/mollie-zahlungsanbieter-haendler/>
- Stripe fees in Germany 2026: <https://transaktionsgebuehren.com/blog/stripe-gebuehren-deutschland-2025>
- PayPal merchant fees (official): <https://www.paypal.com/de/business/paypal-business-fees>
- Unzer fees: <https://zahlungskompass.de/anbieter/unzer/>
- SumUp fees 2026: <https://future-payments.de/ratgeber/sumup-gebuehren/>
- SumUp vs Payone: <https://paylindo.de/anbietervergleich/sumup-vs-payone>
- Mollie and Wero: <https://onlinemarktplatz.de/263172/mollie-integriert-wero/>
- EHI Online-Payment 2025 (PayPal 28.5 %): <https://retail-news.de/ehi-studie-paypal-dominanz-online-zahlung/>
