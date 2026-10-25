---
id: run-event
type: guide
order: 120
audience: [event-organizer]
stories: [VA-8, VA-7, B-3, VA-12, VA-13]
journey: null
route: /office/events
tags: [readiness, draw, seed, publish, start, frozen, print, pdf, people, auslosung, pairing-liste, veröffentlichen, helfer]
title: "Eine Veranstaltung vorbereiten und starten"
---
## Eine Veranstaltung vorbereiten und starten

Alles liegt im eigenen Kontext der Veranstaltung in Mein Bereich — die Geschäftsstelle
öffnet ihn über [*Ligabüro* › *Veranstaltungen*](place:admin.events). Jeder Bereich
speichert für sich, auch bei einer unvollständigen Veranstaltung.

### Was noch fehlt {#run-event-readiness}

*Es fehlt noch* listet, was Auslosung und Start blockiert — in
[*die Veranstaltung* › *Veröffentlichung*](place:event.publication) und auf der
*Übersicht* einer geplanten Veranstaltung. Blockiert nichts: *Bereit: diese Veranstaltung kann ausgelost und gestartet werden.*

| Es steht dort | Was zu tun ist |
|---|---|
| die gemeldeten Vereine passen nicht zum Zuschnitt | [*die Veranstaltung* › *Vereine*](place:event.clubs): unter *Gemeldete Teams: … von …* Vereine an- oder abwählen, dann *… Vereine melden* |
| noch kein Datum | [*die Veranstaltung* › *Allgemein*](place:event.organize): *Beginn* setzen, *Datum speichern* |
| keine vorberechnete Liste für diesen Zuschnitt, oder die Boote passen nicht | *Allgemein*: andere *Teams und Boote* wählen, dann *Speichern*; Farben und Namen stehen unter *Boote* |

Ein Verein mit mehreren Teams: *Teams pro Verein* erhöhen (*Allgemein* oder *Vereine*),
dann für den Verein *Teams von …* wählen. Seine Teams, `ASVW`, `ASVW 2`, …, werden alle
aus seinem einen Kader aufgestellt.

![Die *Veröffentlichung* der Veranstaltung: ob sie bereit ist, und *Veröffentlichen* oder *Zurückziehen*](shot:help-event-readiness)

### Die Pairing-Liste auslosen {#run-event-draw}

[*die Veranstaltung* › *Pairing-Liste*](place:event.pairing) zeigt *Auslosen*, aber
heute darf nur die Verwaltung der Geschäftsstelle auslosen; andere erhalten einen
Berechtigungsfehler. Bitten Sie sie darum, sobald *Es fehlt noch* leer ist.

- Der *Los-Seed* mischt die Startpositionen; derselbe Seed ergibt dieselbe Auslosung,
  später nachweisbar.
- *Neu auslosen* ersetzt die Liste, bis die erste Wettfahrt beginnt.

### Veröffentlichen {#run-event-publish}

- *Veröffentlichen* (*Veröffentlichung*, unter *Veröffentlichung und Start*): Die
  Veranstaltung erscheint auf der öffentlichen Seite. Sperrt nichts, setzt nichts
  Vollständiges voraus.
- *Zurückziehen*: wieder ein Entwurf; Pairing-Liste und Ergebnisse bleiben.
- Eine unveröffentlichte Serie verbirgt ihre Veranstaltungen
  ([Zustände einer Veranstaltung](#terms-event-states)).

### Wie die Liste gedruckt wird {#run-event-print}

*Wie es gedruckt wird*, unter der Auslosung: *Schriftgröße* (leer heißt *automatisch*),
*Querformat*, *Eine Seite je Team*, dann *Druckeinstellungen speichern*. Die öffentliche
Pairing-Liste einer veröffentlichten Veranstaltung trägt das PDF, wenn diese Installation
drucken kann.

### Starten {#run-event-start}

*Veranstaltung starten* steht in [*die Veranstaltung* › *Wettfahrtleitung*](place:event.race),
für ihre Organisation und ihre Wettfahrtleitung. Der Knopf braucht ein leeres *Es fehlt
noch* und eine Pairing-Liste; bis dahin ist er gesperrt und sagt, warum. Ein Datum startet
nie eine Veranstaltung. Danach führt *Wettfahrtleitung öffnen* zum
[Bildschirm der Wettfahrtleitung](#race-control-start).

### Nach der ersten Wettfahrt {#run-event-frozen}

Bis dahin ändern *Allgemein* und *Boote* alles, was beim Anlegen gesetzt wurde; ein neuer
Zuschnitt verwirft eine ausgeloste Pairing-Liste. Eine gestartete Wettfahrt (auch eine
später zurückgerufene) oder ein Ergebnis legt die Konfiguration fest; *Veröffentlichung*
zeigt dann *Es wird gesegelt …*.

| Steht fest | Bleibt änderbar |
|---|---|
| Zuschnitt, Serie und Act, Teams pro Verein, Vereine, Boote, Pairing-Liste | Titel, Ausrichter, Revier, Datum, Veröffentlichung, Druckeinstellungen, Ergebnisse — eine Protestentscheidung Monate später landet trotzdem |

### Personen der Veranstaltung {#run-event-helpers}

[*die Veranstaltung* › *Personen*](place:event.people): *E-Mail eines bestehenden Kontos*,
*Als* (*Wettfahrtleitung*, *Jury*, *Helfer* …), *Hinzufügen*; ✕ entfernt.

| | |
|---|---|
| *Helfer* (RIB, Steg, Boote) | haben keine Befugnis über die Veranstaltung, dürfen aber [eine Abrechnung einreichen](#file-a-claim-where); ihre Organisation darf ihre Dokumente sehen |
| wer hier schreibt | die Verwaltung der Veranstaltung, ihrer Serie oder ihres Ausrichters und die Geschäftsstelle; wer nur Organisation ist, sieht den Bereich, erhält aber einen Fehler — wenden Sie sich an eine dieser Stellen |

[Veranstaltung in Mein Bereich öffnen](place:event.overview)
