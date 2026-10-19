---
id: payment-runs
type: guide
order: 190
audience: [treasurer]
stories: [F-4, F-7]
journey: null
route: null
tags: [sepa, pain.001, bank transfer, excel, sammelüberweisung, kassenprüfung, buchhaltung]
title: "Über die Bank des Vereins zahlen"
---

## Über die Bank des Vereins zahlen

Die genehmigten Abrechnungen, die Ihr Verein schuldet, werden eine SEPA-Datei für das
Online-Banking des Vereins. Die Website verbindet sich nie mit der Bank und speichert
keinen Bank-Zugang. Hier arbeiten nur *Organisation*, *Kassenwart* und *Verwaltung* des
Vereins: auf seiner Seite in *Mein Bereich*, Reiter *Finanzen*.

### Das Konto des Vereins {#payment-runs-bank}

Unter *Konto des Vereins* *Kontoinhaber*, *IBAN* und optional *BIC* (wird aus der IBAN
ergänzt) eintragen, dann *Speichern*. Von diesem Konto gehen die Überweisungen ab. Nur
Organisation und Kassenwart des Vereins sehen es – nicht seine Mitglieder.

### Die SEPA-Datei erstellen {#payment-runs-create}

Ausgangslage: Unter *Freigegeben, zu zahlen* stehen Abrechnungen.

1. Unter *Per SEPA-Datei zahlen* ist jede Abrechnung angehakt ①; Haken bei denen
   entfernen, die nicht mit sollen.
2. Das *Ausführungsdatum* ② prüfen (Vorgabe: heute).
3. *SEPA-Datei erstellen* ③ drücken. Die Datei (pain.001.001.09, `.xml`) wird
   heruntergeladen.
4. Im Online-Banking des Vereins als Sammelüberweisung hochladen und mit einer TAN
   freigeben.

![Per SEPA-Datei zahlen: eine angehakte Abrechnung ①, das *Ausführungsdatum* ②, *SEPA-Datei erstellen* ③](shot:help-payment-sepa)

Jeder Empfänger bekommt eine Überweisung, die alle seine Abrechnungen nennt; diese
stehen nun auf *In Zahlung* und verlassen die Liste der zu zahlenden.
Abgelehnt wird: kein Vereinskonto gespeichert; eine eigene Abrechnung darunter; nichts zu
zahlen.

### Gebucht oder zurückgegeben {#payment-runs-settle}

Der Zahlungslauf bleibt als *Bei der Bank: …* mit seiner *Nachrichten-ID* auf der Seite.

1. Eine Überweisung, die die Bank zurückgegeben hat: *Zurückgegeben…*, einen *Grund*,
   *Als zurückgegeben markieren*. Ihre Abrechnungen sind wieder offen für die nächste
   Datei.
2. Sobald die Überweisungen auf dem Kontoauszug stehen: *Von der Bank gebucht*. Die
   Abrechnungen stehen auf *Gezahlt*.

> **Hinweis:** Zurückgegebene Überweisungen vor *Von der Bank gebucht* markieren – danach
> verschwindet der Zahlungslauf von der Seite.

*SEPA-Datei (.xml)* lädt dieselbe Datei mit derselben Nachrichten-ID erneut herunter;
wurde sie schon hochgeladen, lehnt die Bank sie ab.

### Tabellen {#payment-runs-exports}

| Für | Drücken | Inhalt |
|---|---|---|
| **einen Zahlungslauf** | *Excel (.xlsx)* | eine Zeile je Abrechnung mit Empfänger, IBAN, BIC, Betrag, Verwendungszweck, Veranstaltung oder Verein, Ausführungsdatum und Status – auch für eine Bank, die kein XML annimmt |
| **ein Jahr** | unter *Buchhaltung* das *Jahr*, dann *Abrechnungen herunterladen (Excel)* | jede Abrechnung, die der Verein gezahlt hat oder schuldet, in dem Jahr eingereicht, eine Zeile je Position, mit beantragtem und genehmigtem Betrag, Entscheidung und Zahlungsstand, für die Kassenprüfung; Entwürfe sind nicht enthalten |

[Mein Bereich öffnen](/me)
