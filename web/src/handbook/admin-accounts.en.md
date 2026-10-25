---
id: admin-accounts
type: guide
order: 220
audience: [administration]
stories: [Z-2, A-8, Z-6, A-11, A-13]
journey: null
route: null
tags: [account, konto, access, zugriff, role, rolle, grant, revoke, password, search, suche]
title: Accounts and who may do what
---

## Accounts and who may do what

The *League office* has a section per area; a role sees only the sections it may use.
*Accounts* is the site admin's alone.

![The league office's sections, in the order a season is set up](shot:help-admin-tabs)

### Where accounts come from {#admin-accounts-create}

- A person registers on [their account page](/account) and confirms the emailed code
  ([register](#account-register)).
- Signing in with an unknown address creates nothing; it is refused, pointing to the
  league office.
- *Accounts* creates no accounts, and every role needs one: an unknown address is refused.

### Grant access {#admin-accounts-grant}

1. [*Accounts*](place:admin.accounts): search the person by name or email.
2. *Access* column: *＋ Grant access*.
3. *On* (*Whole site*, *One club*, *One series*, *One event*), *As*, *Which*.
4. *Grant*. The new line shows the role and where it is held.

- **A club's first admin comes from you:** *One club*, *Admin*. Then the club's admin
  names its own members and organizers ([club members](#club-members-add)).
- Roles on the *Whole site* — *Admin*, *Editor*, *Race officer* — are granted only here.
- Also on the *People* panel of a series ([series manager](#admin-series-manager)), and
  at *the event* › [*People*](place:event.people) — from [*Events*](place:admin.events),
  *Open in My space*.
- Refused: a role the person already holds there. What each role allows:
  [roles](#roles-list). Changes apply at once, without signing in again.

### Take access away {#admin-accounts-remove}

- ✕ *Revoke* removes exactly that line; the person's other roles stay.
- Refused: your own site *Admin* (another admin must revoke it); a club's last *Admin*,
  even while *Managers* remain — "At least one admin must remain for this club." (name
  another *Admin* first).
- *Clear password*, where the account has one: the person signs in with a code and sets
  a new one.
- No button removes or blocks an account; one without roles still signs in.

### Find one account among hundreds {#admin-accounts-lists}

| | |
|---|---|
| Pages | *Accounts*, *Sailors* and the *Events* list: 25 rows a page, *Previous* and *Next* |
| Search | anywhere in name or email (events: title, venue, host club), any case |
| Sort | *Name* or *Email* sorts *Accounts* or *Sailors*; again reverses |
| Address | holds page, sort and search: a reload keeps them; a sent link shows exactly this list |
| *Clubs*, *Series* | every row at once, without a search |

[Open the league office](place:admin.accounts)
