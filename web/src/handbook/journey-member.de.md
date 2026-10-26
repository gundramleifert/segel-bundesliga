---
id: journey-member
type: journey
order: 30
audience: [club, sailor]
stories: [V-9, Z-4, Z-9, Z-5, Z-8, V-10, V-4, S-2]
journey: J-3
route: null
tags: [join, member, register, mitglied, konto, registrieren, segler, sailor record]
title: Ein Segler tritt seinem Verein bei
---

## Ein Segler tritt seinem Verein bei

Wer: der neue Segler, die Vereinsverwaltung, der Teammanager.

- **Anfang:** eine Person ohne Konto, nirgends erfasst, bei einem Verein, der bereits
  Vereinsverwaltung und Teammanager hat.
- **Ende:** Die Person ist Mitglied, angemeldet bei ihrem eigenen Personendatensatz und kann
  ihn selbst korrigieren — ohne dass die Geschäftsstelle etwas tun muss — und kann den
  Verein selbst verlassen.

| Schritt | Wer | Was danach gilt | Wie |
|---|---|---|---|
| J-3.2 | Neuer Segler | ein Konto existiert, ein Code ist per E-Mail unterwegs | [Registrieren](#account-register) |
| J-3.3 | Neuer Segler | die Adresse ist bestätigt; das Konto hat seinen eigenen Personendatensatz, gehört noch zu keinem Verein und hat keine Rolle | [Registrieren](#account-register) |
| J-3.5 | Vereinsverwaltung | die Person ist Mitglied des Vereins — sofort, ohne dass jemand zustimmen muss, da sie in keinem anderen Verein ist | [Mitglieder hinzufügen](#club-members-add) |
| J-3.6 | Mitglied | der Verein steht im Kontextwechsler von *Mein Bereich*, markiert mit *Mitglied*; der Personendatensatz hat noch kein Geburtsdatum | [Mein Verein in meinem Bereich](#my-space-club) |
| J-3.7 | Mitglied | [*Ihr Verein* › *Personen*](place:club.people) zeigt die Mitglieder des Vereins mit Namen, ohne E-Mail-Adressen | [Mein Verein in meinem Bereich](#my-space-club) |
| J-3.8 | Teammanager | der Teammanager ergänzt den Personendatensatz unter [*Ihr Verein* › *Personen*](place:club.people) um das Geburtsdatum | [Segler](#squad-and-lineup-sailors) |
| J-3.9 | Mitglied | der Datensatz gehört dem Mitglied und trägt den Namen und das Geburtsdatum, die es korrigiert hat | [Mein Segler-Profil](#profile-sailor) |

Ab der bestätigten Registrierung gibt es einen Personendatensatz: Der Verein nimmt diese
Person auf, der Teammanager ergänzt sie, das Mitglied korrigiert sie — niemand legt einen
zweiten an.

### Wenn … {#journey-member-variations}

- **Hinzugefügt, bevor ein Konto existiert (J-3.1):** Unter der Adresse ist niemand
  erfasst, also wird niemand hinzugefügt — die Person registriert sich zuerst, dann fügt die Vereinsverwaltung sie erneut hinzu.
  [Mitglieder hinzufügen](#club-members-add)
- **Passwort statt jedes Mal eines Codes (J-3.4):** nach der Bestätigung der Adresse eines
  setzen und sich damit anmelden. [Passwort](#account-password)
- **Das Mitglied tritt aus (J-3.10):** Es beendet seine Mitgliedschaft jederzeit selbst; der
  Verein verschwindet aus dem Kontextwechsler von *Mein Bereich*, der Personendatensatz bleibt.
  [Verein verlassen](#my-space-leave)
