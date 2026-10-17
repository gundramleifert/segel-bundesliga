---
id: payment-runs
type: guide
order: 190
audience: [treasurer]
stories: [F-4, F-7]
journey: null
route: null
tags: [sepa, pain.001, bank transfer, excel, sammelüberweisung, kassenprüfung, buchhaltung]
title: "Pay through the club's bank"
---

## Pay through the club's bank

The approved claims your club owes become one SEPA file for the club's online banking.
The site never connects to the bank and stores no bank login. Only the club's
*Organizer*, *Treasurer* and *Admin* work here: the club's page in *My space*, tab
*Money*.

### The club's account {#payment-runs-bank}

Under *The club's account*, enter *Account holder*, *IBAN* and, optionally, *BIC* (filled
in from the IBAN), then *Save*. The transfers leave from this account. Only the club's
organizer and treasurer see it — not its members.

### Create the SEPA file {#payment-runs-create}

Starting state: claims are listed under *Approved, to pay*.

1. Under *Pay by SEPA file*, every claim is ticked; untick those to leave out.
2. Check the *Execution date* (default today).
3. Press *Create SEPA file*. The file (pain.001.001.09, `.xml`) downloads.
4. Upload it in the club's online banking as a collective transfer and confirm it with
   one TAN.

Each payee gets one transfer naming all their claims, which now read *In payment* and
leave the list to pay. Refused: no club account saved; your own claim among them;
nothing to pay.

### Booked or returned {#payment-runs-settle}

The run stays on the page as *At the bank: …* with its *Message id*.

1. A transfer the bank sent back: *Returned…*, a *Reason*, *Mark as returned*. Its
   claims are open again for the next file.
2. When the transfers show on the statement: *Booked by the bank*. The claims read
   *Paid*.

> **Note:** Mark returned transfers before *Booked by the bank* — after that, the run
> leaves the page.

*SEPA file (.xml)* downloads the same file again, with the same message id, so the bank
refuses it if it was already uploaded.

### Spreadsheets {#payment-runs-exports}

| For | Press | Contents |
|---|---|---|
| **one run** | *Excel (.xlsx)* | one row per claim with payee, IBAN, BIC, amount, reference, event or club, execution date and status — also for a bank that takes no XML |
| **one year** | under *Books*, the *Year*, then *Download claims (Excel)* | every claim the club paid or owes, submitted that year, one row per item, with claimed and approved amounts, decision and payment state, for the cash audit; drafts are not in it |

[Open my space](/me)
