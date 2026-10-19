---
id: run-event
type: guide
order: 120
audience: [event-organizer]
stories: [VA-8, VA-7, B-3, VA-12]
journey: null
route: /admin
tags: [readiness, draw, seed, publish, start, frozen, print, pdf, people, auslosung, pairing-liste, veröffentlichen, helfer]
title: "Eine Veranstaltung vorbereiten und starten"
---
## Eine Veranstaltung vorbereiten und starten

*Verwaltung*, Reiter *Veranstaltungen*, *Bearbeiten*. Jeder Block speichert für sich,
auch bei einer unvollständigen Veranstaltung.

### Was noch fehlt {#run-event-readiness}

*Es fehlt noch* listet, was Auslosung und Start blockiert; blockiert nichts:
*Bereit: diese Veranstaltung kann ausgelost und gestartet werden.*

| Es steht dort | Was zu tun ist |
|---|---|
| die gemeldeten Vereine passen nicht zum Zuschnitt | unter *Gemeldete Vereine: … von …* Vereine an- oder abwählen, dann *… Vereine melden* ② |
| noch kein Datum | *Beginn* setzen, *Datum speichern* ① |
| keine vorberechnete Liste für diesen Zuschnitt, oder die Boote passen nicht | das Panel kann Zuschnitt und Boote nicht ändern — wenden Sie sich an die Geschäftsstelle |

![Das Panel: was noch fehlt, *Datum speichern* ①, die Vereine und *… Vereine melden* ②, die Auslosung ③](shot:help-event-readiness)

### Die Pairing-Liste auslosen {#run-event-draw}

Heute lost nur die Verwaltung der Geschäftsstelle aus: Ist *Es fehlt noch* leer, bitten
Sie sie darum. Die Organisation der Veranstaltung sieht *Auslosen* ③, erhält aber einen
Berechtigungsfehler.

- Der *Los-Seed* mischt die Startpositionen der vorberechneten Liste; derselbe Seed
  ergibt dieselbe Auslosung, später nachweisbar.
- *Neu auslosen* ersetzt die Liste, bis die erste Wettfahrt beginnt.

### Veröffentlichen {#run-event-publish}

- *Veröffentlichen* (unter *Veröffentlichung und Start*): Die Veranstaltung erscheint auf
  der öffentlichen Seite, wo es sie vorher nicht gab. Sperrt nichts, setzt nichts
  Vollständiges voraus.
- *Zurückziehen*: wieder ein Entwurf; Pairing-Liste und Ergebnisse bleiben.
- Eine unveröffentlichte Serie verbirgt ihre Veranstaltungen
  ([Zustände einer Veranstaltung](#terms-event-states)).

### Wie die Liste gedruckt wird {#run-event-print}

*Wie es gedruckt wird*: *Schriftgröße* (leer heißt *automatisch*), *Querformat*,
*Eine Seite je Team*, dann *Druckeinstellungen speichern*. Das PDF liegt an der
öffentlichen Pairing-Liste einer veröffentlichten Veranstaltung, wenn diese Installation
drucken kann; sonst kein Link.

### Starten {#run-event-start}

*Veranstaltung starten* braucht ein leeres *Es fehlt noch* und eine Pairing-Liste; bis
dahin ist der Knopf gesperrt und sagt, warum. Ein Datum startet nie eine Veranstaltung.
Auch die Wettfahrtleitung der Veranstaltung darf starten. Danach: *Läuft*, und
*Wettfahrtleitung* führt zum [Bildschirm der Wettfahrtleitung](#race-control-start).

### Nach der ersten Wettfahrt {#run-event-frozen}

Sobald eine Wettfahrt gestartet ist (auch eine später zurückgerufene) oder ein Ergebnis
erfasst ist, zeigt das Panel *Es wird gesegelt …*.

| Steht fest | Bleibt änderbar |
|---|---|
| Zuschnitt, Serie und Act, Vereine, Boote, Pairing-Liste | Datum, Veröffentlichung, Druckeinstellungen, Ergebnisse — eine Protestentscheidung Monate später landet trotzdem |

### Personen der Veranstaltung {#run-event-helpers}

*Personen*: *E-Mail eines bestehenden Kontos*, *Als* (*Wettfahrtleitung*, *Jury*,
*Helfer* …), *Hinzufügen*; ✕ entfernt.

| | |
|---|---|
| *Helfer* (RIB, Steg, Boote) | haben keine Befugnis über die Veranstaltung, dürfen aber [eine Abrechnung einreichen](#file-a-claim-where); ihre Organisation darf ihre Dokumente sehen |
| wer hier schreibt | auf der Website die Verwaltung der Veranstaltung selbst, die Verwaltung ihrer Serie und die Geschäftsstelle; wer nur Organisation ist, sieht einen Fehler, und die Verwaltung des Ausrichters erreicht diesen Bereich nicht — wenden Sie sich an eine dieser Stellen |

[Verwaltung öffnen](/admin)
