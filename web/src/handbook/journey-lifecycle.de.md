---
id: journey-lifecycle
type: journey
order: 10
audience: [administration, event-organizer, race-committee]
stories: [A-1, A-6, VA-8, VA-6, VA-7, B-3, WL-2, B-1, VA-10, VA-9]
journey: J-1
route: null
tags: [lifecycle, season, matchday, spieltag, serie, veranstaltung, auslosung, wertung]
title: Von der leeren Serie zum gewerteten Spieltag
---

## Von der leeren Serie zum gewerteten Spieltag

Wer: die Geschäftsstelle, die Veranstaltungsleitung, die Wettfahrtleitung, die Jury, ein
Besucher.

Von nichts — keine Vereine, Serie oder Veranstaltung — zu einer beendeten Veranstaltung,
deren Punkte sich noch ändern, wenn nach der letzten Wettfahrt ein Protest entschieden wird.

| Schritt | Wer | Was danach gilt | Wie |
|---|---|---|---|
| J-1.1 | Geschäftsstelle | die Vereine existieren; öffentlich ist noch keiner zu sehen | [Vereine anlegen](#admin-clubs-create) |
| J-1.2 | Geschäftsstelle | die Serie existiert mit ihren Vereinen, als Entwurf, den sonst niemand sieht | [Serie anlegen](#admin-series-create) |
| J-1.3 | Geschäftsstelle | die Serie ist veröffentlicht und gelistet | [Serie veröffentlichen](#admin-series-publish) |
| J-1.4 | Veranstaltungsleitung | die Veranstaltung existiert mit Titel und Booten; die für die Serie gemeldeten Vereine sind ihre Teilnehmer — das Formular speichert heute nur für die Verwaltung der Geschäftsstelle, die Veranstaltungsleitung bittet also gegebenenfalls dort darum | [Veranstaltung anlegen](#create-event-wizard) |
| J-1.5 | Veranstaltungsleitung | *Es fehlt noch* nennt, was der Veranstaltung fehlt — hier Teamzahl und Datum | [Bereitschaft](#run-event-readiness) |
| J-1.16 | Veranstaltungsleitung | Teamzahl und Datum sind gesetzt; es fehlt nichts mehr | [Konfiguration](#create-event-config) |
| J-1.6 | Geschäftsstelle | die Pairing-Liste ist ausgelost; erneutes Auslosen ersetzt sie, solange nichts gesegelt ist | [Auslosen](#run-event-draw) |
| J-1.7 | Veranstaltungsleitung | die Veranstaltung steht im öffentlichen Kalender | [Veröffentlichen](#run-event-publish) |
| J-1.8 | Besucher | die Pairing-Liste lässt sich drucken — wo der Server nicht drucken kann, wird der Download nicht angeboten | die öffentliche Website |
| J-1.9 | Veranstaltungsleitung | die Veranstaltung *läuft* | [Veranstaltung starten](#run-event-start) |
| J-1.10 | Wettfahrtleitung | jede Wettfahrt hat ihre Ergebnisse; die Punkte ergeben sich daraus | [Ergebnisse eintragen](#results-entry-enter) |
| J-1.11 | Besucher | die Serientabelle enthält den Act, jeden Verein mit seiner Platzierung | die öffentliche Website |
| J-1.12 | Veranstaltungsleitung | Zuschnitt, Vereine, Boote und Pairing-Liste sind eingefroren; der Titel lässt sich noch korrigieren | [Eingefroren nach der ersten Wettfahrt](#run-event-frozen) |
| J-1.13 | Jury, dann Wettfahrtleitung | die Jury disqualifiziert Monate später einen Sieger, und die Wettfahrtleitung trägt die Entscheidung ein; Punkte und Tabellen folgen sofort | [Ergebnis korrigieren](#results-entry-correct) |
| J-1.14 | Wettfahrtleitung, über die Veranstaltungsleitung | die Wettfahrtleitung erklärt die Wettfahrten für beendet, die Veranstaltungsleitung schließt die Veranstaltung ab: sie ist *beendet*; Ergebnisse bleiben korrigierbar | [Wettfahrten sind beendet](#close-event-finish) |

Heute kann nur die Verwaltung der Geschäftsstelle eine Pairing-Liste auslosen (J-1.6); die
Veranstaltungsleitung bittet die Geschäftsstelle darum.

### Wenn … {#journey-lifecycle-variations}

- **Auslosen, bevor die Veranstaltung bereit ist (J-1.15):** Abgelehnt mit den Gründen,
  die *Es fehlt noch* nennt. Beheben Sie sie (J-1.16) und losen Sie erneut aus.
  [Bereitschaft](#run-event-readiness)
