---
id: admin-series
type: guide
order: 210
audience: [administration]
stories: [A-6, VA-8, A-14]
journey: null
route: /office/series/new
tags: [series, serie, year, jahrgang, publish, veröffentlichen, draft, entwurf, squad size, kadergröße]
title: Eine Serie anlegen und veröffentlichen
---
## Eine Serie anlegen und veröffentlichen

Eine Serie ist eine Reihe von Veranstaltungen, die gemeinsam gewertet werden; ihr Name
trägt den Jahrgang ([Begriffe](#terms-competition)). Anlegen kann sie nur die Verwaltung
der Seite.

### Eine Serie anlegen {#admin-series-create}

1. [*Ligabüro* › *Serien*](place:admin.series): [*Neue Serie*](place:admin.new-series) ①.
2. *Name*: mindestens drei Zeichen. *Jahrgang*, *Beginn* und *Ende* sind optional.
3. Die *Teilnehmende Vereine* anhaken; sie sind von Anfang an dabei.
4. *Serie anlegen*.

Die Serie ist ein *Entwurf*. *Vereine ändern* ② in ihrer Zeile öffnet den Rest ihrer
Einrichtung:

- die Vereine — [einen Verein in eine Serie eintragen](#admin-clubs-series);
- *Kader mindestens* und *Kader höchstens*, dann *Kadergröße speichern*: Das Höchstmaß
  gilt beim Speichern eines Kaders, das Mindestmaß wird als Ziel angezeigt;
- *Beschreibung*, in Markdown, auf der öffentlichen Tabellenseite —
  *Beschreibung speichern*;
- *Personen* — [die Organisation der Serie](#admin-series-manager).

Ihre Organisation findet alles außer *Personen*, dazu die Termine, im eigenen Kontext der Serie
([ihre Organisation](#admin-series-manager)). Ein Name, dessen Adresse
eine andere Serie schon hat, wird abgelehnt. Name und Jahrgang ändert nach dem Anlegen
keine Seite.

![Der Bereich Serien: *Neue Serie* ①, in jeder Zeile *Vereine ändern* ② und *Veröffentlichen* bzw. *Zurückziehen* ③](shot:help-admin-series)

### Eine Serie veröffentlichen {#admin-series-publish}

- **Entwurf:** Die Serie und ihre Veranstaltungen sind öffentlich verborgen; ihre Seite
  antwortet mit „nicht gefunden“, und ihre Vereine werden über sie nicht aufgeführt.
- *Veröffentlichen* ③ — das Abzeichen wird *Öffentlich*. Das sperrt nichts; jede
  Veranstaltung wird weiter einzeln veröffentlicht
  ([eine Veranstaltung veröffentlichen](#run-event-publish)).
- *Zurückziehen* — zurück zum *Entwurf*; Tabellen und Veranstaltungen bleiben.
- Ihre Organisation: [*die Serie* › *Termine & Veröffentlichung*](place:series.dates).

### Vergangene Saisons und Manage2Sail {#admin-series-import}

Dafür gibt es keine Seite: Wer den Server betreibt, importiert vergangene Saisons aus SAP
Sailing und die Meldeliste und die Dokumente der Bekanntmachungstafel einer Veranstaltung
aus Manage2Sail. Ein Verein wird an seinem *Kürzel* erkannt; ein unbekannter wird angelegt.
Segler werden nicht importiert. Importierte Serien und Veranstaltungen kommen als Entwurf
an, wenn der Import sie nicht veröffentlicht — [veröffentlichen](#admin-series-publish) Sie
sie selbst. Die Punkte werden hier berechnet, und ein Ergebnis, das die Wettfahrtleitung
erfasst hat, wird nie überschrieben.

### Einer Serie ihre Organisation geben {#admin-series-manager}

Die Person hat ein Konto ([woher Konten kommen](#admin-accounts-create)).

1. In der Zeile der Serie *Vereine ändern*.
2. Unter *Personen*: *E-Mail eines bestehenden Kontos*, *Als* *Organisation*,
   *Hinzufügen*.

Die Organisation findet die Serie im Kontextwechsler, unter *Organisieren* und *Serie*:

| Bereich | Was die Organisation dort tut |
|---|---|
| [*Vereine & Meldungen*](place:series.organize) | setzt die Vereine unter *Gemeldete Vereine*; entscheidet, was unter *Anmeldungen zu entscheiden* steht |
| [*Termine & Veröffentlichung*](place:series.dates) | *Erster Tag*, *Letzter Tag*; *Veröffentlichen*, *Zurückziehen*; *Beschreibung* |
| [*Kadergröße & Wertung*](place:series.scoring) | *Kader mindestens*, *Kader höchstens*; für die Wertung gibt es keine Seite |
| [*Veranstaltungen*](place:series.events) | jeder Spieltag, auch Entwürfe; jeder öffnet den Kontext der Veranstaltung, wo sie ihn organisiert. Ein neuer Spieltag: [*Neue Veranstaltung*](place:admin.new-event) ([eine Veranstaltung anlegen](#create-event-wizard)) |
| *Wettfahrtleitung & Jury* | sichtbar, aber Personen benennt dort nur die *Verwaltung* der Serie |

| Rolle in einer Serie | |
|---|---|
| *Wettfahrtleitung*, *Jury* | diese Rolle bei jeder ihrer Veranstaltungen |
| *Verwaltung* | jede Rolle; benennt die Personen der Serie — auch unter *Wettfahrtleitung & Jury* |

✕ *Entfernen* nimmt eine Rolle weg. Siehe [Rollen](#roles-list).

[Eine Serie anlegen](place:admin.new-series)
