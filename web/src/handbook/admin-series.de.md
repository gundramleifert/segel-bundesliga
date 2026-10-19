---
id: admin-series
type: guide
order: 210
audience: [administration]
stories: [A-6, VA-8]
journey: null
route: /admin/series/new
tags: [series, serie, year, jahrgang, publish, veröffentlichen, draft, entwurf, squad size, kadergröße]
title: Eine Serie anlegen und veröffentlichen
---
## Eine Serie anlegen und veröffentlichen

Eine Serie ist eine Reihe von Veranstaltungen, die gemeinsam gewertet werden; ihr Name
trägt den Jahrgang ([Begriffe](#terms-competition)). Anlegen kann sie nur die Verwaltung
der Seite; im Reiter *Serien* der Redaktion steht nur *Serien legt die Geschäftsstelle
an.*

### Eine Serie anlegen {#admin-series-create}

1. [*Verwaltung*, Reiter *Serien*](place:admin.series): [*Neue Serie*](place:admin.new-series) ①.
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

Ein Name, dessen Adresse eine andere Serie schon hat, wird abgelehnt. Name, Jahrgang und
Daten lassen sich nach dem Anlegen auf keiner Seite mehr ändern — erlaubt wäre es, eine
Bedienung dafür gibt es noch nicht.

![Der Reiter Serien: *Neue Serie* ①, in jeder Zeile *Vereine ändern* ② und *Veröffentlichen* bzw. *Zurückziehen* ③](shot:help-admin-series)

### Eine Serie veröffentlichen {#admin-series-publish}

- **Entwurf:** Die Serie und ihre Veranstaltungen sind öffentlich verborgen; ihre Seite
  antwortet mit „nicht gefunden“, und ihre Vereine werden über sie nicht aufgeführt.
- *Veröffentlichen* ③ — das Abzeichen wird *Öffentlich*. Das sperrt nichts; jede
  Veranstaltung wird weiter einzeln veröffentlicht
  ([eine Veranstaltung veröffentlichen](#run-event-publish)).
- *Zurückziehen* — zurück zum *Entwurf*; Tabellen und Veranstaltungen bleiben.

### Einer Serie ihre Organisation geben {#admin-series-manager}

Die Person hat ein Konto ([woher Konten kommen](#admin-accounts-create)).

1. In der Zeile der Serie *Vereine ändern*.
2. Unter *Personen*: *E-Mail eines bestehenden Kontos*, *Als* *Organisation*,
   *Hinzufügen*.

| | |
|---|---|
| Reiter *Serien* | nur der Hinweis, dass Serien von der Geschäftsstelle angelegt werden. Die Organisation darf Vereine, Kadergröße, Beschreibung und Veröffentlichung ihrer Serie ändern, hat dort aber keine Bedienelemente — sie wendet sich an die Geschäftsstelle (Name, Jahrgang und Daten ändert nach dem Anlegen keine Seite) |
| Reiter *Veranstaltungen* | sie organisiert die Veranstaltungen der Serie; anlegen lässt sich eine heute nur mit der Verwaltung der Geschäftsstelle, sie fragt also dort ([eine Veranstaltung anlegen](#create-event-wizard)) |
| *Wettfahrtleitung*, *Jury* | einer Serie: diese Rolle bei jeder ihrer Veranstaltungen |
| *Verwaltung* | jede Rolle; benennt die Personen der Serie |

✕ *Entfernen* nimmt eine Rolle weg. Siehe [Rollen](#roles-list).

[Eine Serie anlegen](place:admin.new-series)
