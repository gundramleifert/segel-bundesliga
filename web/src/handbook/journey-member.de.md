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

- **Anfang:** eine Person ohne Konto und ohne Segler-Datensatz, bei einem Verein, der bereits
  Vereinsverwaltung und Teammanager hat.
- **Ende:** Die Person ist Mitglied, angemeldet bei ihrem eigenen Segler-Datensatz und kann
  ihn selbst korrigieren — ohne dass die Geschäftsstelle etwas tun muss.

| Schritt | Wer | Was danach gilt | Wie |
|---|---|---|---|
| J-3.2 | Neuer Segler | ein Konto existiert, ein Code ist per E-Mail unterwegs | [Registrieren](#account-register) |
| J-3.3 | Neuer Segler | die Adresse ist bestätigt; das Konto gehört noch zu keinem Verein und hat keine Rolle | [Registrieren](#account-register) |
| J-3.5 | Vereinsverwaltung | die Person ist Mitglied des Vereins — sofort, ohne dass jemand zustimmen muss | [Mitglieder hinzufügen](#club-members-add) |
| J-3.6 | Mitglied | *Mein Bereich* zeigt den Verein als Karte, markiert mit *Mitglied* | [Mein Verein in meinem Bereich](#my-space-club) |
| J-3.7 | Mitglied | die Mitgliederliste zeigt die Leute des Vereins mit Namen, ohne E-Mail-Adressen | [Mein Verein in meinem Bereich](#my-space-club) |
| J-3.8 | Teammanager | der Teammanager bittet die Geschäftsstelle, die einen Segler-Datensatz mit E-Mail-Adresse und Geburtsdatum der Person anlegt | [Segler](#squad-and-lineup-sailors) |
| J-3.9 | Mitglied | der Segler-Datensatz gehört dem Mitglied — verbunden über die bestätigte Adresse — und trägt den Namen und das Geburtsdatum, die es korrigiert hat | [Mein Segler-Profil](#profile-sailor) |

Mitgliedschaft und Segler-Datensatz sind zweierlei: Der Beitritt erzeugt keinen
Segler-Datensatz, und der Datensatz findet sein Konto nur über dieselbe, bestätigte
E-Mail-Adresse.

### Wenn … {#journey-member-variations}

- **Hinzugefügt, bevor ein Konto existiert (J-3.1):** Niemand wird hinzugefügt — die
  Person registriert sich zuerst, dann fügt die Vereinsverwaltung sie erneut hinzu.
  [Mitglieder hinzufügen](#club-members-add)
- **Passwort statt jedes Mal eines Codes (J-3.4):** nach der Bestätigung der Adresse eines
  setzen und sich damit anmelden. [Passwort](#account-password)
- **Das Mitglied tritt aus (J-3.10):** Es beendet seine Mitgliedschaft jederzeit selbst; der
  Verein verschwindet aus *Mein Bereich*, der Segler-Datensatz bleibt.
  [Verein verlassen](#my-space-leave)
