---
id: create-event
type: guide
order: 110
audience: [event-organizer]
stories: [VA-6, A-2, A-10]
journey: null
route: /office/events/new
tags: [new event, matchday, act, boats, colors, wizard, veranstaltung anlegen, spieltag, boote, zuschnitt]
title: "Eine Veranstaltung anlegen"
---
## Eine Veranstaltung anlegen

Anlegen dürfen: die Geschäftsstelle und ihre Wettfahrtleitung jede Veranstaltung; die
Organisation einer Serie deren Acts, mit jedem Verein als Ausrichter; die Organisation
eines Vereins eine Veranstaltung außerhalb einer Serie, die der eigene Verein ausrichtet.
Das Formular bietet nur an, was Sie wählen dürfen — Ihre Serien, die Ausrichter, die Sie
nennen dürfen —, und *＋ Neue Veranstaltung* gibt es nur, wenn Sie eine anlegen dürfen.
Jede Seite des Ligabüros und von Mein Bereich funktioniert auf dem Handy: Eine Tabelle, breiter als der
Bildschirm, lässt sich seitlich schieben, die Seite selbst nicht.

### Die drei Schritte {#create-event-wizard}

1. Die Geschäftsstelle: [*Ligabüro* › *Veranstaltungen*](place:admin.events),
   [*＋ Neue Veranstaltung*](place:admin.new-event). Die Organisation eines Vereins:
   [*Ihr Verein* › *Ausrichten*](place:club.hosting), *+ Neue Veranstaltung*. Die
   Organisation einer Serie: [*Neue Veranstaltung*](place:admin.new-event) von dieser Seite aus.
2. *Allgemeines*: Pflicht ist nur *Name* ① (mindestens drei Zeichen). *Veranstaltung
   anlegen* ② speichert einen Entwurf, den sonst niemand sieht.
3. *Vereine*: die Teilnehmer ankreuzen, dann *… Vereine eintragen und weiter*. In einer
   Serie können nur ihre gemeldeten Vereine antreten, schon angekreuzt; ohne Serie jeder
   Verein.
4. *Pairing-Liste*: [die Auslosung](#run-event-draw).
5. Der letzte Bildschirm: *Bereit für die Veranstaltung 🚀* oder
   *Gespeichert — noch nicht bereit* mit dem, was fehlt; dazu *Veröffentlichen*.

Schritte 2 und 3 haben *Vorerst überspringen*; den Rest ergänzen Sie im eigenen Kontext
der Veranstaltung in Mein Bereich ([was noch fehlt](#run-event-readiness)).

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

Bis zur ersten Wettfahrt lässt sich all das in [*die Veranstaltung* › *Allgemein*](place:event.organize)
ändern; danach stehen Zuschnitt, Serie und Vereine fest ([nach der ersten Wettfahrt](#run-event-frozen)).

### Boote {#create-event-boats}

- Eine Zeile je Boot, in den Ligafarben, benannt *Boot 1*, *Boot 2* … — sein Ruf auf dem
  Wasser.
- *Farbe*: eine benannte Farbe, der Farbwähler oder Text wie `#ff69b4`; Farbwähler oder
  Text schalten die Liste auf *Eigene …*.
- Jedes Boot braucht einen *Name*, sonst bleibt *Veranstaltung anlegen* gesperrt.
- Boote gehören zur Veranstaltung: Eine neue Auslosung ändert, wer welches Boot segelt,
  nicht die Boote. Farben und Namen lassen sich bis zur ersten Wettfahrt unter
  [*die Veranstaltung* › *Boote*](place:event.boats) ändern.

[Veranstaltung anlegen](place:admin.new-event)
