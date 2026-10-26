---
id: roles
type: doc
order: 20
audience: [sailor, club, event-organizer, race-committee, treasurer, administration]
stories: [Z-2, Z-5, A-8, F-1, F-3, VA-12]
journey: null
route: /help/roles
tags: [roles, permissions, access, rollen, rechte, zugriff, geschäftsstelle, redaktion, wettfahrtleitung, teammanager, kassenwart, vereinsverwaltung, veranstaltungsleitung, serienleitung]
title: "Rollen"
---

## Rollen

### Wer welche Rolle hat {#roles-list}

Eine Rolle gilt für die ganze Seite, einen Verein, eine Serie oder eine Veranstaltung.
Sie wirkt ab dem nächsten Klick.

| Rolle | Gilt für | Kurz |
|---|---|---|
| *Verwaltung* (Geschäftsstelle) | die Seite | Alles überall, Personen eingeschlossen. Serien, Konten, Pairing-Listen, Wortlaut des Haftungsausschlusses. |
| *Redaktion* | die Seite, eine Serie oder eine Veranstaltung | News, Pressemitteilungen und Bilder — die der Seite über alles, die einer Serie oder Veranstaltung über diese Regatta. Organisiert nichts: keine Vereine, Veranstaltungen, Ergebnisse, kein Geld. |
| *Wettfahrtleitung* (Geschäftsstelle) | die Seite | Wettfahrtleitung und Organisation jeder Veranstaltung. |
| *Verwaltung* (*Vereinsverwaltung*) | einen Verein | Wer zum Verein gehört und wer ihn organisiert; der Stander. Alles, was die Organisation tut. Verwaltung jeder Veranstaltung, die der Verein ausrichtet. |
| *Organisation* (*Teammanager*) | einen Verein | Wer segelt: Meldungen, Kader, Crews, Segler, Erziehungsberechtigte, Haftungsausschlüsse. Das Geld des Vereins, mit dem Kassenwart. Organisation jeder Veranstaltung, die der Verein ausrichtet. |
| *Kassenwart* | einen Verein | Zahlt die Abrechnungen des Vereins und jeder Veranstaltung, die er ausrichtet. |
| *Mitglied* | einen Verein | Gehört zum Verein. Sonst nichts. |
| *Verwaltung* | eine Serie | Alles an der Serie und ihren Veranstaltungen, Personen eingeschlossen. |
| *Organisation* (*Serienleitung*) | eine Serie | Ihre Vereine, Meldungen, Termine, Kadergröße, Veröffentlichung; legt ihre Spieltage an. Organisation jeder Veranstaltung der Serie. |
| *Wettfahrtleitung*, *Jury* | eine Serie | Diese Rolle bei jeder Veranstaltung der Serie. |
| *Verwaltung* | eine Veranstaltung | Alles an der Veranstaltung, Personen eingeschlossen. |
| *Organisation* (*Veranstaltungsleitung*) | eine Veranstaltung | Konfiguration, Vereine, Veröffentlichung, Start und Abschluss. |
| *Wettfahrtleitung* | eine Veranstaltung | Führt die Wettfahrten durch, erfasst die Ergebnisse. |
| *Jury*, *Helfer* | eine Veranstaltung | Arbeiten am Tag mit, ohne Rechte an ihr. Können ihre Kosten abrechnen. |
| *Kassenwart* | eine Veranstaltung | Zahlt die Abrechnungen der Veranstaltung. |
| *Segler* | einen Kader oder eine Crew | Eigenes Profil und eigener Haftungsausschluss. |
| *Erziehungsberechtigte* | einen Segler unter 18 | Nehmen den Haftungsausschluss des Kindes an. |
| Gast | — | Liest jede öffentliche Seite. |

Zu Organisation und Verwaltung einer Veranstaltung gehören die ihrer Serie und ihres
Ausrichters, zu ihrer Wettfahrtleitung die ihrer Serie.

### Wer was darf {#roles-matrix}

✓ alle · *eigene* Ihr Verein, Ihre Serie, Ihre Veranstaltung · *Serie* die
Veranstaltungen Ihrer Serie · *ausgerichtet* die Veranstaltungen, die Ihr Verein
ausrichtet · *Kader* Segler in den Kadern Ihres Vereins · *selbst* Sie selbst · — nein.

| Aktion | Verwaltung der Geschäftsstelle | Redaktion | Wettfahrtleitung der Geschäftsstelle | Serienleitung | Veranstaltungsleitung | Wettfahrtleitung | Jury, Helfer | Vereinsverwaltung | Teammanager | Kassenwart | Mitglied, Segler |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Vereine anlegen, bearbeiten, zu einer Serie melden | ✓ | — | — | — | — | — | — | — | — | — | — |
| Stander eines Vereins ändern | ✓ | — | — | — | — | — | — | eigene | — | — | — |
| News und Pressemitteilungen schreiben, die Bilder pflegen | ✓ | ✓ | — | — | — | — | — | — | — | — | — |
| Mitglieder, Organisation, Kassenwart eintragen | ✓ | — | — | — | — | — | — | eigene | — | — | — |
| Mitgliederliste eines Vereins sehen | ✓ | — | — | — | — | — | — | eigene | eigene | — | eigene |
| Konten anlegen und deaktivieren | ✓⁹ | — | — | — | — | — | — | — | — | — | — |
| Eine Serie anlegen | ✓ | — | — | — | — | — | — | — | — | — | — |
| Serie bearbeiten, veröffentlichen, ihre Vereine festlegen | ✓ | — | — | eigene | — | — | — | — | — | — | — |
| Für eine Serie oder Veranstaltung melden | ✓⁹ | — | — | — | — | — | — | eigene⁹ | eigene⁹ | — | — |
| Meldung annehmen oder ablehnen | ✓⁹ | — | Veranst.⁹ | eigene, Serie⁹ | eigene⁹ | — | — | ausgerichtet⁹ | ausgerichtet⁹ | — | — |
| Veranstaltung anlegen | ✓ | — | ✓ | Serie | — | — | — | ausgerichtet | ausgerichtet | — | — |
| Veranstaltung bearbeiten, veröffentlichen, ihre Vereine festlegen | ✓ | — | ✓ | Serie | eigene | — | — | ausgerichtet | ausgerichtet | — | — |
| Personen einer Veranstaltung benennen | ✓ | — | — | —¹ | — | — | — | ausgerichtet | — | — | — |
| Pairing-Liste auslosen | ✓ | — | — | — | — | — | — | — | — | — | — |
| Veranstaltung starten, beenden, absagen, wieder öffnen | ✓ | — | ✓ | Serie | eigene | eigene | — | ausgerichtet | ausgerichtet | — | — |
| Wettfahrten durchführen, Ergebnisse erfassen und korrigieren | ✓ | — | ✓ | —¹ | — | eigene | — | ausgerichtet | — | — | — |
| Segler suchen und anlegen | ✓ | — | — | — | — | — | — | eigene | eigene | — | — |
| Angaben eines Seglers ändern | ✓⁹ | — | — | — | — | — | — | Kader²˒⁹ | Kader²˒⁹ | — | selbst |
| Kader melden | ✓ | — | — | — | — | — | — | eigene | eigene | — | — |
| Crew für einen Spieltag aufstellen | ✓⁹ | — | ✓⁹ | Serie⁹ | eigene⁹ | eigene⁹ | — | eigene, ausgerichtet⁹ | eigene, ausgerichtet⁹ | — | — |
| Erziehungsberechtigte verknüpfen | ✓⁹ | — | — | — | — | — | — | eigene | eigene | — | — |
| Haftungsausschluss für einen Segler bestätigen | ✓⁹ | — | — | — | — | — | — | Kader⁹ | Kader⁹ | — | selbst³ |
| Unterschriebenes Formular sehen | ✓ | — | ✓ | Serie⁴ | eigene⁴ | eigene⁴ | — | Kader, ausgerichtet⁴ | Kader, ausgerichtet⁴ | — | selbst |
| Check-in-Liste einer Veranstaltung sehen | ✓ | — | ✓ | Serie | eigene | eigene | — | ausgerichtet | ausgerichtet | — | — |
| Übersicht der Haftungsausschlüsse des Vereins sehen | ✓⁹ | — | — | — | — | — | — | eigene | eigene | — | — |
| Dokumente einer Person sehen | ✓ | — | ✓⁵ | Serie⁵ | eigene⁵ | — | — | eigene⁶ | eigene⁶ | — | selbst |
| Kosten abrechnen⁷ | — | — | — | Serie | eigene | eigene | eigene | — | — | — | eigene |
| Über eine Abrechnung entscheiden und sie zahlen⁸ | ✓⁹ | — | — | —¹ | eigene | — | — | eigene, ausgerichtet | eigene, ausgerichtet | eigene, ausgerichtet | — |
| Vereinskonto, SEPA-Datei, Buchhaltung | ✓⁹ | — | — | — | — | — | — | eigene | eigene | eigene | — |
| Neuen Wortlaut des Haftungsausschlusses veröffentlichen | ✓⁹ | — | — | — | — | — | — | — | — | — | — |

1. Die *Verwaltung* einer Serie darf es, für ihre Veranstaltungen.
2. Oder in noch keinem Kader.
3. Und verknüpfte Erziehungsberechtigte, für ein Kind unter 18.
4. Nur Formulare für genau diese Veranstaltung, nicht die für eine ganze Serie.
5. Der Personen, die bei dieser Veranstaltung benannt sind.
6. Der Vereinsmitglieder und der Personen, die bei einer ausgerichteten Veranstaltung
   benannt sind.
7. Eine Rolle, namentlich bei der Veranstaltung oder ihrer Serie vergeben, oder die
   Mitgliedschaft im Verein. Rollen der Geschäftsstelle zählen nie.
8. Nie die eigene. Nur eine Organisation, die bei der Veranstaltung selbst benannt ist,
   nicht Redaktion, Wettfahrtleitung der Geschäftsstelle oder Serienleitung.
9. Erlaubt, aber noch auf keiner Seite (oder nur teilweise) bedienbar — fragen Sie die
   Geschäftsstelle.

### Wie Sie eine Rolle bekommen {#roles-getting}

- **Zuerst ein Konto.** Die Anmeldung legt keines an. Sie legen es selbst mit *Konto
  anlegen* an; weder Ihr Verein noch die Geschäftsstelle kann das für Sie tun.
- **Rollen der Geschäftsstelle:** vergibt deren Verwaltung unter [*Konten*](place:admin.accounts).
- **Verein:** Die Vereinsverwaltung trägt Personen unter [*der Verein* ›
  *Mitglieder*](place:club.people) ein, mit der E-Mail-Adresse eines bestehenden Kontos.
  Eine *Verwaltung* muss immer bleiben.
- **Serie, Veranstaltung:** deren Verwaltung oder die Geschäftsstelle — unter *die Serie* ›
  *Wettfahrtleitung & Jury*, unter *die Veranstaltung* › [*Personen*](place:event.people).
  Zur Verwaltung einer Veranstaltung gehören die ihrer Serie und ihres Ausrichters; ihre
  Organisation allein kann niemanden benennen.
- **Erziehungsberechtigte:** Der Verein des Kindes verknüpft das Konto des Elternteils
  unter [*der Verein* › *Minderjährige & Erziehungsberechtigte*](place:club.minors).
- **Fotograf:** keine Rolle und kein Konto — die Redaktion schickt einen
  [Upload-Link](#news-and-press-pictures).
- **Segler:** Ein Verein nimmt Sie in seinen Kader auf. Ihr Konto findet Ihren Datensatz
  über die E-Mail-Adresse.
- **Eine Rolle beenden:** Ein Mitglied tritt mit *Verein verlassen* aus. Andere Rollen
  entfernt, wer sie vergeben kann.

[Mein Bereich öffnen](place:space)
