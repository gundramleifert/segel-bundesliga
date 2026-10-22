---
id: roles
type: doc
order: 20
audience: [sailor, club, event-organizer, race-committee, treasurer, administration]
stories: [Z-2, Z-5, A-8, F-1, F-3, VA-12]
journey: null
route: /help/roles
tags: [roles, permissions, access, rollen, rechte, zugriff, geschäftsstelle, redaktion, wettfahrtleitung, teammanager, kassenwart, vereinsverwaltung, veranstaltungsleitung, serienleitung]
title: "Roles"
---

## Roles

### Who holds which role {#roles-list}

A role is held on the whole site, one club, one series or one event. It takes effect at
the next click.

| Role | Held on | In short |
|---|---|---|
| *Admin* (league office) | the site | Everything everywhere, people included. Series, accounts, pairing lists, waiver wording. |
| *Editor* | the site | Clubs and their entry into series. Organizer of every event. News, press releases and the pictures. No results, no money. |
| *Race officer* (league) | the site | Race officer and organizer of every event. |
| *Admin* (*Club admin*) | a club | Who is in the club and who organizes it; the crest. Everything an organizer does. Admin of every event the club hosts. |
| *Organizer* (*Team manager*) | a club | Who sails: applications, squads, crews, sailors, guardians, waivers. The club's money, with the treasurer. Organizer of every event the club hosts. |
| *Treasurer* | a club | Pays the club's claims and those of every event it hosts. |
| *Member* | a club | Belongs to the club. Nothing more. |
| *Admin* | a series | Everything on the series and its events, people included. |
| *Organizer* (*Series manager*) | a series | Its clubs, dates, squad size, publication. Organizer of every event in it. |
| *Race officer*, *Jury* | a series | That role at every event in it. |
| *Admin* | an event | Everything on the event, people included. |
| *Organizer* (*Event manager*) | an event | Setup, clubs, publication, start and close. |
| *Race officer* | an event | Runs the races, enters the results. |
| *Jury*, *Helper* | an event | Work the day, with no rights on it. May claim their costs. |
| *Treasurer* | an event | Pays the event's claims. |
| *Sailor* | a squad or crew | Own profile and waiver. |
| *Guardian* | a sailor under 18 | Accepts the child's waiver. |
| Guest | — | Reads every public page. |

An event's organizers and admins include those of its series and its host club; its race
officers, those of its series.

### Who may do what {#roles-matrix}

✓ all · *own* your club, series or event · *series* your series' events · *hosted* your
club's hosted events · *squad* your club's squad sailors · *self* yourself · — no.

| Action | League admin | Editor | League race officer | Series organizer | Event organizer | Race officer | Jury, helper | Club admin | Team manager | Treasurer | Member, sailor |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Create clubs, edit them, enter them in a series | ✓ | ✓⁹ | — | — | — | — | — | — | — | — | — |
| Change a club's crest | ✓ | ✓ | — | — | — | — | — | own | — | — | — |
| Write news and press releases, keep the pictures | ✓ | ✓ | — | — | — | — | — | — | — | — | — |
| Add members, organizers, treasurer | ✓ | — | — | — | — | — | — | own | — | — | — |
| See a club's member list | ✓ | ✓ | — | — | — | — | — | own | own | — | own |
| Create and deactivate accounts | ✓⁹ | — | — | — | — | — | — | — | — | — | — |
| Create a series | ✓ | — | — | — | — | — | — | — | — | — | — |
| Edit, publish a series, set its clubs | ✓ | — | — | own⁹ | — | — | — | — | — | — | — |
| Apply for a series or event | ✓⁹ | — | — | — | — | — | — | own⁹ | own⁹ | — | — |
| Accept or reject an application | ✓⁹ | events⁹ | events⁹ | series⁹ | own⁹ | — | — | hosted⁹ | hosted⁹ | — | — |
| Create an event | ✓ | ✓¹⁰ | ✓⁹ | series¹⁰ | — | — | — | hosted⁹ | hosted⁹ | — | — |
| Edit, publish an event, set its clubs | ✓ | ✓ | ✓⁹ | series | own | — | — | hosted⁹ | hosted⁹ | — | — |
| Name an event's people | ✓ | — | — | —¹ | — | — | — | hosted⁹ | — | — | — |
| Draw the pairing list | ✓ | — | — | — | — | — | — | — | — | — | — |
| Start, close, call off, reopen an event | ✓ | ✓ | ✓⁹ | series | own | own⁹ | — | hosted⁹ | hosted⁹ | — | — |
| Run races, enter and correct results | ✓ | — | ✓ | —¹ | — | own | — | hosted⁹ | — | — | — |
| Find and create sailors | ✓ | ✓ | — | — | — | — | — | ✓⁹ | ✓⁹ | — | — |
| Change a sailor's details | ✓⁹ | ✓⁹ | — | — | — | — | — | squad²˒⁹ | squad²˒⁹ | — | self |
| Register the squad | ✓ | — | — | — | — | — | — | own | own | — | — |
| Name the crew for a matchday | ✓⁹ | ✓⁹ | ✓⁹ | series⁹ | own⁹ | own⁹ | — | own, hosted⁹ | own, hosted⁹ | — | — |
| Link a guardian | ✓⁹ | — | — | — | — | — | — | own | own | — | — |
| Confirm a waiver for a sailor | ✓⁹ | ✓⁹ | — | — | — | — | — | squad⁹ | squad⁹ | — | self³ |
| See a signed waiver form | ✓ | ✓ | ✓ | series⁴ | own⁴ | own⁴ | — | squad, hosted⁴ | squad, hosted⁴ | — | self |
| See an event's check-in list | ✓ | ✓ | ✓⁹ | series | own | own⁹ | — | hosted⁹ | hosted⁹ | — | — |
| See the club's waiver overview | ✓⁹ | — | — | — | — | — | — | own | own | — | — |
| See a person's documents | ✓ | ✓⁵ | ✓⁵ | series⁵ | own⁵ | — | — | own⁶ | own⁶ | — | self |
| File an expense claim⁷ | — | — | — | series | own | own | own | — | — | — | own |
| Decide and pay a claim⁸ | ✓⁹ | — | — | —¹ | own | — | — | own, hosted | own, hosted | own, hosted | — |
| Club account, SEPA file, books | ✓⁹ | — | — | — | — | — | — | own | own | own | — |
| Publish a new waiver wording | ✓⁹ | — | — | — | — | — | — | — | — | — | — |

1. A series' *Admin* may, for its events — except running races and deciding claims:
   race control, the results tab and the claims screens do not let them in yet (⁹).
2. Or in nobody's squad yet.
3. And a linked guardian, for a child under 18.
4. Only forms signed for that event alone, not those for a whole series.
5. Of the people named on that event.
6. Of club members, and of people named on a hosted event.
7. A role held by name on the event or its series, or club membership. League office
   roles never count.
8. Never your own. Only an organizer named on the event itself, not an editor, a league
   race officer or a series organizer.
9. Allowed, but no screen offers it yet (or only part of it) — ask the league office.
10. On screen only with the league office's admin: the event form loads *Teams and boats*
    only for them. Ask the league office to create the event.

### How you get a role {#roles-getting}

- **An account first.** Signing in does not create one. You create it yourself with
  *Create an account*; neither your club nor the league office can do it for you.
- **League office roles:** its admin grants them under [*Accounts*](place:admin.accounts).
- **Club:** the club's admin adds people on the [*Members* tab](place:club.members), by an existing account's
  email. One *Admin* must always remain.
- **Series, event:** its admin, in the *People* panel. For an event, on screen that is the
  event's own admin, the series' admin or the league office — never the event's organizer;
  the host club's admin has no access to that panel and asks one of them.
- **Guardian:** the child's club links the parent's account under *Guardians*.
- **Photographer:** no role and no account — the editor sends an
  [upload link](#news-and-press-pictures).
- **Sailor:** a club puts you in its squad. Your account finds your record by the email
  address.
- **Ending a role:** a member leaves with *Leave the club*. Other roles are removed by
  whoever can grant them.

[Open my space](place:space)
