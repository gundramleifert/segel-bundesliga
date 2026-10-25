---
id: admin-accounts
type: guide
order: 220
audience: [administration]
stories: [Z-2, A-8, Z-6, A-11, A-13]
journey: null
route: null
tags: [account, konto, access, zugriff, role, rolle, grant, revoke, password, search, suche]
title: Konten und wer was darf
---

## Konten und wer was darf

Das *Ligabüro* hat einen Bereich je Aufgabe; eine Rolle sieht nur die Bereiche, die sie
nutzen darf. *Konten* gehört allein der Verwaltung der Seite.

![Die Bereiche des Ligabüros, in der Reihenfolge, in der eine Saison eingerichtet wird](shot:help-admin-tabs)

### Woher Konten kommen {#admin-accounts-create}

- Eine Person registriert sich auf [ihrer Kontoseite](/account) und bestätigt den
  zugeschickten Code ([registrieren](#account-register)).
- Eine Anmeldung mit unbekannter Adresse legt nichts an; sie wird abgelehnt, mit Verweis
  auf die Geschäftsstelle.
- *Konten* legt keine Konten an, und jede Rolle braucht eines: Eine unbekannte Adresse
  wird abgelehnt.

### Zugriff vergeben {#admin-accounts-grant}

1. [*Konten*](place:admin.accounts): die Person nach Name oder E-Mail suchen.
2. Spalte *Zugriff*: *＋ Zugriff vergeben*.
3. *Für* (*Gesamte Seite*, *Einen Verein*, *Eine Serie*, *Eine Veranstaltung*), *Als*,
   *Welche*.
4. *Vergeben*. Die neue Zeile zeigt die Rolle und wo sie gilt.

- **Die erste Verwaltung eines Vereins kommt von Ihnen:** *Einen Verein*, *Verwaltung*.
  Danach benennt sie Mitglieder und Organisation des Vereins selbst
  ([Vereinsmitglieder](#club-members-add)).
- Rollen auf der *Gesamte Seite* — *Verwaltung*, *Redaktion*, *Wettfahrtleitung* — werden
  nur hier vergeben.
- Ebenso im Feld *Personen* einer Serie ([Organisation der Serie](#admin-series-manager))
  und unter *die Veranstaltung* › [*Personen*](place:event.people) — aus
  [*Veranstaltungen*](place:admin.events) mit *In Mein Bereich öffnen*.
- Abgelehnt: eine Rolle, die die Person dort schon hat. Was jede Rolle darf:
  [Rollen](#roles-list). Änderungen gelten sofort, ohne neue Anmeldung.

### Zugriff entziehen {#admin-accounts-remove}

- ✕ *Entziehen* entfernt genau diese Zeile; die übrigen Rollen der Person bleiben.
- Abgelehnt: Ihre eigene *Verwaltung* der Seite (das muss eine andere Verwaltung tun);
  die letzte *Verwaltung* eines Vereins, auch wenn noch eine *Organisation* bleibt —
  „Dieser Verein braucht weiterhin mindestens eine Person in der Verwaltung.“ (zuerst eine
  weitere *Verwaltung* benennen).
- *Passwort löschen*, wo das Konto eines hat: Die Person meldet sich mit einem Code an
  und setzt ein neues.
- Kein Knopf entfernt oder sperrt ein Konto; eines ohne Rollen meldet sich weiter an.

### Ein Konto unter Hunderten finden {#admin-accounts-lists}

| | |
|---|---|
| Seiten | *Konten*, *Segler* und die Liste unter *Veranstaltungen*: 25 Zeilen je Seite, *Zurück* und *Weiter* |
| Suche | überall in Name oder Adresse (Veranstaltungen: Titel, Revier, Ausrichter), gleich in welcher Schreibung |
| Sortierung | *Name* oder *E-Mail* sortiert *Konten* oder *Segler*; nochmals kehrt um |
| Adresse | enthält Seite, Sortierung und Suche: Neu laden behält sie; ein geschickter Link zeigt genau diese Liste |
| *Vereine*, *Serien* | alle Zeilen auf einmal, ohne Suche |

[Ligabüro öffnen](place:admin.accounts)
