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
| *Redaktion* | die Seite | Vereine und ihre Meldung zu Serien. Organisation jeder Veranstaltung. Keine Ergebnisse, kein Geld. |
| *Wettfahrtleitung* (Geschäftsstelle) | die Seite | Wettfahrtleitung und Organisation jeder Veranstaltung. |
| *Verwaltung* (*Vereinsverwaltung*) | einen Verein | Wer zum Verein gehört und wer ihn organisiert; der Stander. Alles, was die Organisation tut. Verwaltung jeder Veranstaltung, die der Verein ausrichtet. |
| *Organisation* (*Teammanager*) | einen Verein | Wer segelt: Meldungen, Kader, Crews, Segler, Erziehungsberechtigte, Haftungsausschlüsse. Das Geld des Vereins, mit dem Kassenwart. Organisation jeder Veranstaltung, die der Verein ausrichtet. |
| *Kassenwart* | einen Verein | Zahlt die Abrechnungen des Vereins und jeder Veranstaltung, die er ausrichtet. |
| *Mitglied* | einen Verein | Gehört zum Verein. Sonst nichts. |
| *Verwaltung* | eine Serie | Alles an der Serie und ihren Veranstaltungen, Personen eingeschlossen. |
| *Organisation* (*Serienleitung*) | eine Serie | Ihre Vereine, Termine, Kadergröße, Veröffentlichung. Organisation jeder Veranstaltung der Serie. |
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
| Vereine anlegen, bearbeiten, zu einer Serie melden | ✓ | ✓⁹ | — | — | — | — | — | — | — | — | — |
| Stander eines Vereins ändern | ✓ | ✓ | — | — | — | — | — | eigene | — | — | — |
| Mitglieder, Organisation, Kassenwart eintragen | ✓ | — | — | — | — | — | — | eigene | — | — | — |
| Mitgliederliste eines Vereins sehen | ✓ | ✓ | — | — | — | — | — | eigene | eigene | — | eigene |
| Konten anlegen und deaktivieren | ✓⁹ | — | — | — | — | — | — | — | — | — | — |
| Eine Serie anlegen | ✓ | — | — | — | — | — | — | — | — | — | — |
| Serie bearbeiten, veröffentlichen, ihre Vereine festlegen | ✓ | — | — | eigene⁹ | — | — | — | — | — | — | — |
| Für eine Serie oder Veranstaltung melden | ✓⁹ | — | — | — | — | — | — | eigene⁹ | eigene⁹ | — | — |
| Meldung annehmen oder ablehnen | ✓⁹ | Veranst.⁹ | Veranst.⁹ | Serie⁹ | eigene⁹ | — | — | ausgerichtet⁹ | ausgerichtet⁹ | — | — |
| Veranstaltung anlegen | ✓ | ✓¹⁰ | ✓⁹ | Serie¹⁰ | — | — | — | ausgerichtet⁹ | ausgerichtet⁹ | — | — |
| Veranstaltung bearbeiten, veröffentlichen, ihre Vereine festlegen | ✓ | ✓ | ✓⁹ | Serie | eigene | — | — | ausgerichtet⁹ | ausgerichtet⁹ | — | — |
| Personen einer Veranstaltung benennen | ✓ | — | — | —¹ | — | — | — | ausgerichtet⁹ | — | — | — |
| Pairing-Liste auslosen | ✓ | — | — | — | — | — | — | — | — | — | — |
| Veranstaltung starten, beenden, absagen, wieder öffnen | ✓ | ✓ | ✓⁹ | Serie | eigene | eigene⁹ | — | ausgerichtet⁹ | ausgerichtet⁹ | — | — |
| Wettfahrten durchführen, Ergebnisse erfassen und korrigieren | ✓ | — | ✓ | —¹ | — | eigene | — | ausgerichtet⁹ | — | — | — |
| Segler suchen und anlegen | ✓ | ✓ | — | — | — | — | — | ✓⁹ | ✓⁹ | — | — |
| Angaben eines Seglers ändern | ✓⁹ | ✓⁹ | — | — | — | — | — | Kader²˒⁹ | Kader²˒⁹ | — | selbst |
| Kader melden | ✓ | — | — | — | — | — | — | eigene | eigene | — | — |
| Crew für einen Spieltag aufstellen | ✓⁹ | ✓⁹ | ✓⁹ | Serie⁹ | eigene⁹ | eigene⁹ | — | eigene, ausgerichtet⁹ | eigene, ausgerichtet⁹ | — | — |
| Erziehungsberechtigte verknüpfen | ✓⁹ | — | — | — | — | — | — | eigene | eigene | — | — |
| Haftungsausschluss für einen Segler bestätigen | ✓⁹ | ✓⁹ | — | — | — | — | — | Kader⁹ | Kader⁹ | — | selbst³ |
| Unterschriebenes Formular sehen | ✓ | ✓ | ✓ | Serie⁴ | eigene⁴ | eigene⁴ | — | Kader, ausgerichtet⁴ | Kader, ausgerichtet⁴ | — | selbst |
| Check-in-Liste einer Veranstaltung sehen | ✓ | ✓ | ✓⁹ | Serie | eigene | eigene⁹ | — | ausgerichtet⁹ | ausgerichtet⁹ | — | — |
| Übersicht der Haftungsausschlüsse des Vereins sehen | ✓⁹ | — | — | — | — | — | — | eigene | eigene | — | — |
| Dokumente einer Person sehen | ✓ | ✓⁵ | ✓⁵ | Serie⁵ | eigene⁵ | — | — | eigene⁶ | eigene⁶ | — | selbst |
| Kosten abrechnen⁷ | — | — | — | Serie | eigene | eigene | eigene | — | — | — | eigene |
| Über eine Abrechnung entscheiden und sie zahlen⁸ | ✓⁹ | — | — | —¹ | eigene | — | — | eigene, ausgerichtet | eigene, ausgerichtet | eigene, ausgerichtet | — |
| Vereinskonto, SEPA-Datei, Buchhaltung | ✓⁹ | — | — | — | — | — | — | eigene | eigene | eigene | — |
| Neuen Wortlaut des Haftungsausschlusses veröffentlichen | ✓⁹ | — | — | — | — | — | — | — | — | — | — |

1. Die *Verwaltung* einer Serie darf es, für ihre Veranstaltungen — außer Wettfahrten
   durchführen und über Abrechnungen entscheiden: Die Wettfahrtleitung, der Ergebnis-Tab
   und die Abrechnungsseiten lassen sie noch nicht zu (⁹).
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
10. Auf der Website nur mit der Verwaltung der Geschäftsstelle: Das Formular lädt *Teams
    und Boote* nur für sie. Bitten Sie die Geschäftsstelle, die Veranstaltung anzulegen.

### Wie Sie eine Rolle bekommen {#roles-getting}

- **Zuerst ein Konto.** Die Anmeldung legt keines an. Sie legen es selbst mit *Konto
  anlegen* an; weder Ihr Verein noch die Geschäftsstelle kann das für Sie tun.
- **Rollen der Geschäftsstelle:** vergibt deren Verwaltung unter [*Konten*](place:admin.accounts).
- **Verein:** Die Vereinsverwaltung trägt Personen im [Tab *Mitglieder*](place:club.members) ein, mit der
  E-Mail-Adresse eines bestehenden Kontos. Eine *Verwaltung* muss immer bleiben.
- **Serie, Veranstaltung:** deren Verwaltung, im Bereich *Personen*. Bei einer
  Veranstaltung ist das auf der Website die Verwaltung der Veranstaltung selbst, der Serie
  oder der Geschäftsstelle — nie die Veranstaltungsleitung; die Verwaltung des Ausrichters
  erreicht diesen Bereich nicht und wendet sich an eine dieser Stellen.
- **Erziehungsberechtigte:** Der Verein des Kindes verknüpft das Konto des Elternteils
  unter *Erziehungsberechtigte*.
- **Segler:** Ein Verein nimmt Sie in seinen Kader auf. Ihr Konto findet Ihren Datensatz
  über die E-Mail-Adresse.
- **Eine Rolle beenden:** Ein Mitglied tritt mit *Verein verlassen* aus. Andere Rollen
  entfernt, wer sie vergeben kann.

[Mein Bereich öffnen](place:space)
