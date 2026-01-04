# E2E Test User Stories

Dieses Dokument beschreibt die User Stories, die durch E2E-Tests abgedeckt werden.

---

## 1. Authentifizierung

### US-AUTH-01: Login
**Als** Benutzer
**möchte ich** mich über Zitadel einloggen können
**damit** ich auf geschützte Funktionen zugreifen kann

**Akzeptanzkriterien:**
- [ ] Login-Button auf der Startseite sichtbar
- [ ] Weiterleitung zu Zitadel nach Klick
- [ ] Erfolgreiche Anmeldung mit gültigen Credentials
- [ ] Rückleitung zur App nach Login
- [ ] Benutzername in der Navigation sichtbar

**Test:** `AuthenticationTest.userCanLogin()`

---

### US-AUTH-02: Logout
**Als** eingeloggter Benutzer
**möchte ich** mich ausloggen können
**damit** meine Sitzung beendet wird

**Akzeptanzkriterien:**
- [ ] User-Menü öffnet sich bei Klick auf Avatar
- [ ] Logout-Button im Menü sichtbar
- [ ] Nach Logout erscheint Login-Button wieder
- [ ] Geschützte Seiten sind nicht mehr erreichbar

**Test:** `AuthenticationTest.userCanLogout()`

---

## 2. Turnier-Verwaltung

### US-TOUR-01: Turnier erstellen
**Als** eingeloggter Benutzer
**möchte ich** ein neues Turnier erstellen können
**damit** ich eine Regatta planen kann

**Akzeptanzkriterien:**
- [ ] Navigation zur Erstellungsseite möglich
- [ ] Pflichtfelder werden validiert (Name)
- [ ] Teams können hinzugefügt werden
- [ ] Boote können hinzugefügt werden
- [ ] Turnier wird gespeichert und Detail-Seite angezeigt

**Tests:**
- `TournamentTest.canNavigateToCreateTournament()`
- `TournamentTest.canCreateTournamentWithTeamsAndBoats()`
- `TournamentTest.formValidationRequiresName()`

---

### US-TOUR-02: Turnier anzeigen
**Als** eingeloggter Benutzer
**möchte ich** meine Turniere einsehen können
**damit** ich den Status und die Konfiguration überprüfen kann

**Akzeptanzkriterien:**
- [ ] Turnier-Details werden korrekt angezeigt
- [ ] Teams und Boote sind sichtbar
- [ ] Optimierungs-Sektion ist vorhanden

**Tests:**
- `TournamentTest.createdTournamentCanBeAccessedByUrl()`
- `TournamentTest.canViewTournamentDetails()`
- `TournamentTest.tournamentShowsCorrectConfiguration()`

---

### US-TOUR-03: Turnier bearbeiten
**Als** eingeloggter Benutzer
**möchte ich** Teams und Boote vor dem Speichern anpassen können
**damit** ich die Konfiguration korrigieren kann

**Akzeptanzkriterien:**
- [ ] Teams können entfernt werden
- [ ] Boote können entfernt werden

**Tests:**
- `TournamentTest.canRemoveTeamsBeforeSaving()`
- `TournamentTest.canRemoveBoatsBeforeSaving()`

---

### US-TOUR-04: Turnier löschen
**Als** eingeloggter Benutzer
**möchte ich** ein Turnier löschen können
**damit** ich nicht mehr benötigte Turniere entfernen kann

**Akzeptanzkriterien:**
- [ ] Bestätigungs-Dialog erscheint
- [ ] Nach Bestätigung wird Turnier gelöscht
- [ ] Weiterleitung zur Turnier-Liste

**Test:** `TournamentTest.canDeleteTournament()`

---

## 3. Optimierung

### US-OPT-01: Optimierung starten
**Als** eingeloggter Benutzer
**möchte ich** die Optimierung für ein konfiguriertes Turnier starten können
**damit** ein optimaler Spielplan erstellt wird

**Akzeptanzkriterien:**
- [ ] Start-Button ist bei gültiger Konfiguration sichtbar
- [ ] Warnung bei fehlender Konfiguration
- [ ] Optimierung startet nach Klick

**Tests:**
- `OptimizationTest.optimizationShowsStartButton()`
- `OptimizationTest.canStartOptimization()`
- `OptimizationTest.tournamentWithoutConfigShowsWarning()`

---

### US-OPT-02: Optimierungs-Fortschritt
**Als** eingeloggter Benutzer
**möchte ich** den Fortschritt der Optimierung sehen
**damit** ich weiß, wie lange es noch dauert

**Akzeptanzkriterien:**
- [ ] Progress-Bar wird angezeigt
- [ ] Abbrechen-Button erscheint

**Test:** `OptimizationTest.progressBarAppearsDuringOptimization()`

---

### US-OPT-03: Optimierung abbrechen
**Als** eingeloggter Benutzer
**möchte ich** eine laufende Optimierung abbrechen können
**damit** ich bei Bedarf neu starten kann

**Akzeptanzkriterien:**
- [ ] Abbrechen-Button ist klickbar
- [ ] Optimierung wird gestoppt
- [ ] Start-Button erscheint wieder

**Test:** `OptimizationTest.canCancelOptimization()`

---

### US-OPT-04: Optimierungs-Ergebnis
**Als** eingeloggter Benutzer
**möchte ich** das Optimierungsergebnis einsehen können
**damit** ich den Spielplan nutzen kann

**Akzeptanzkriterien:**
- [ ] Ergebnis-Sektion wird angezeigt
- [ ] Metriken (Gesparte Shuttles, Boot-Wechsel, Rechenzeit) sichtbar
- [ ] JSON-Ergebnis kann expandiert werden

**Tests:**
- `OptimizationTest.optimizationCompletesAndShowsResult()`
- `OptimizationTest.canExpandJsonResult()`

---

## 4. CMS-Seiten

### US-CMS-01: Öffentliche Seiten anzeigen
**Als** Besucher (nicht eingeloggt)
**möchte ich** öffentliche Seiten wie Impressum und Datenschutz aufrufen können
**damit** ich wichtige Informationen lesen kann

**Akzeptanzkriterien:**
- [ ] Standard-Seiten sind über URL erreichbar
- [ ] Titel und Inhalt werden angezeigt
- [ ] Seiten sind ohne Login zugänglich

**Test:** `CmsPageTest.canViewPublicPages()`

---

### US-CMS-02: Navigation über Footer
**Als** Besucher
**möchte ich** über den Footer zu rechtlichen Seiten navigieren können
**damit** ich schnell Impressum und Datenschutz finde

**Akzeptanzkriterien:**
- [ ] Footer enthält Links zu Impressum, Datenschutz, etc.
- [ ] Links führen zu den richtigen Seiten

**Test:** `CmsPageTest.canNavigateViaFooter()`

---

### US-CMS-03: 404-Seite bei unbekannter URL
**Als** Besucher
**möchte ich** eine sinnvolle Fehlermeldung sehen
**wenn** ich eine nicht existierende Seite aufrufe

**Akzeptanzkriterien:**
- [ ] 404-Fehlerseite oder Hinweis wird angezeigt
- [ ] Navigation zurück zur Startseite möglich

**Test:** `CmsPageTest.showsErrorForNonExistentPage()`

---

## Test-Übersicht

| Test-Klasse | Tests | User Stories |
|-------------|-------|--------------|
| `AuthTest` | 3 | US-AUTH-01, US-AUTH-02 |
| `TournamentCrudTest` | 9 | US-TOUR-01 bis US-TOUR-04 |
| `OptimizationFlowTest` | 9 | US-OPT-01 bis US-OPT-04 |
| `CmsPageTest` | 8 | US-CMS-01 bis US-CMS-03 |

**Gesamt:** 29 E2E-Tests

## Einheitliches Test-Schema

Alle Tests verwenden `E2ETestBase` als Basis-Klasse mit:

- **Session-Management:** `PlaywrightThreadFactory` für Thread-sichere Browser-Instanzen
- **Login-State-Reuse:** Storage State wird gespeichert und wiederverwendet
- **Deutsche UI-Unterstützung:** Zitadel-Labels auf Deutsch (Loginname, Passwort, Weiter)
- **Konsistente Helper-Methoden:**
  - `navigateTo(path)` - Navigation
  - `performLogin()` / `performLogout()` - Authentifizierung
  - `waitForTestId()` / `clickTestId()` / `fillTestId()` - Element-Interaktion
  - `acceptNextDialog()` - Dialog-Handling
  - `takeScreenshot()` - Debugging

## Test-ID Konvention

Alle interaktiven UI-Elemente nutzen `data-testid`:
```
{bereich}-{element}-{typ}
```

Beispiele:
- `login-button`
- `tournament-create-button`
- `tournament-name-input`
- `optimization-start-button`
- `optimization-progress-bar`
