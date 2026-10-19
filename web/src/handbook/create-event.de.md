---
id: create-event
type: guide
order: 110
audience: [event-organizer]
stories: [VA-6, A-2]
journey: null
route: /admin/events/new
tags: [new event, matchday, act, boats, colors, wizard, veranstaltung anlegen, spieltag, boote, zuschnitt]
title: "Eine Veranstaltung anlegen"
---
## Eine Veranstaltung anlegen

Anlegen dürfen: die Geschäftsstelle, die Organisation der Serie und die Organisation des
Ausrichters (nur mit dem eigenen Verein als Ausrichter).

> **Hinweis:** *Teams und Boote* lädt derzeit nur für die Verwaltung der Geschäftsstelle;
> ohne die Liste lässt sich die Veranstaltung nicht speichern. Zeigt das Feld einen
> Fehler, bitten Sie die Geschäftsstelle, die Veranstaltung anzulegen.

### Die drei Schritte {#create-event-wizard}

1. *Verwaltung*, Reiter *Veranstaltungen*: *＋ Neue Veranstaltung*.
2. *Allgemeines*: Pflicht ist nur *Name* ① (mindestens drei Zeichen). *Veranstaltung
   anlegen* ② speichert einen Entwurf, den sonst niemand sieht.
3. *Vereine*: die Teilnehmer ankreuzen, dann *… Vereine eintragen und weiter*. In einer
   Serie können nur ihre gemeldeten Vereine antreten, schon angekreuzt; ohne Serie jeder
   Verein.
4. *Pairing-Liste*: [die Auslosung](#run-event-draw).
5. Der letzte Bildschirm: *Bereit für die Veranstaltung 🚀* oder
   *Gespeichert — noch nicht bereit* mit dem, was fehlt; dazu *Veröffentlichen*.

Schritte 2 und 3 haben *Vorerst überspringen*; den Rest ergänzen Sie im Panel der
Veranstaltung ([was noch fehlt](#run-event-readiness)).

![Der erste Schritt: *Name* ①, Daten, Serie, Ausrichter, Zuschnitt und Boote, *Veranstaltung anlegen* ②](shot:help-event-wizard)

### Zuschnitt, Serie und Daten {#create-event-config}

| Feld | |
|---|---|
| *Teams und Boote* | nur Zuschnitte mit vorberechneter Pairing-Liste; ein anderer muss erst ergänzt werden — das Formular nennt, wer das tut |
| *Flights* | 1 bis zur Länge dieser Liste; ein kürzerer Tag segelt ihre ersten Flights. Darunter: Wettfahrten je Flight (Teams ÷ Boote, aufgerundet) und die Gesamtzahl |
| *Serie* | leer: die Veranstaltung steht für sich, in keiner Serienwertung; gesetzt: sie wird von selbst der nächste Act |
| *Beginn* | darf leer bleiben, aber ohne Datum kein Auslosen und kein Start |
| *Ende* | leer: eintägig; ein Ende vor dem Beginn wird abgelehnt |
| *Ausrichter* | darf auf *- noch offen -* bleiben |

Zuschnitt, Serie und Vereine stehen fest, sobald die erste Wettfahrt startet
([nach der ersten Wettfahrt](#run-event-frozen)).

### Boote {#create-event-boats}

- Eine Zeile je Boot, in den Ligafarben, benannt *Boot 1*, *Boot 2* … — sein Ruf auf dem
  Wasser.
- *Farbe*: eine benannte Farbe, der Farbwähler oder Text wie `#ff69b4`; Farbwähler oder
  Text schalten die Liste auf *Eigene …*.
- Jedes Boot braucht einen *Name*, sonst bleibt *Veranstaltung anlegen* gesperrt.
- Boote gehören zur Veranstaltung: Eine neue Auslosung ändert, wer welches Boot segelt,
  nicht die Boote. Das Panel kann Boote nicht bearbeiten — prüfen Sie sie hier.

[Veranstaltung anlegen](/admin/events/new)
