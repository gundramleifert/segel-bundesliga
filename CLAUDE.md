# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Web-Plattform für die Segel-Bundesliga (German Sailing Federal League) mit:
- PairingList Optimizer mit Echtzeit-UI (WebSocket)
- User Management via Zitadel (Self-Hosted OIDC)
- Blog/Pages mit Bild-Upload (MinIO)
- Sponsoren-Verwaltung
- i18n: DE + EN

## Tech Stack

| Komponente | Technologie |
|------------|-------------|
| Backend | Spring Boot 3.2, Java 21 |
| Frontend | React 18, Vite, TailwindCSS, Zustand, React Query |
| Optimizer | Java Library (gundramleifert.pairing_list) |
| Auth | Zitadel (OIDC/OAuth2) |
| Database | PostgreSQL 16 |
| File Storage | MinIO (S3-kompatibel) |
| Testing | JUnit 5, Vitest, Playwright |
| Build | Gradle 8.5 (Kotlin DSL) |

## Project Structure

```
./
├── backend/                    # Spring Boot API
│   └── src/main/java/de/segelbundesliga/
│       ├── config/             # SecurityConfig, MinioConfig
│       ├── domain/             # Entity-Klassen
│       ├── dto/                # Data Transfer Objects
│       ├── repository/         # JPA Repositories
│       ├── service/            # Business Logic
│       └── web/                # REST Controller
├── frontend/                   # React + Vite
├── optimizer/                  # PairingList Java Library
│   └── src/main/java/gundramleifert/pairing_list/
├── e2e/                        # Playwright E2E Tests
├── docker/                     # Docker Compose files
├── build.gradle.kts            # Root Gradle build
├── settings.gradle.kts         # Multi-project config
├── CLAUDE.md                   # Claude Code Guidance
└── MISSION.md                  # Original Requirements
```

## Commands

### Development
```bash
# Start all services (PostgreSQL, Zitadel, MinIO, Mailhog)
cd docker && docker compose -f docker-compose.dev.yml up -d

# Backend
./gradlew :backend:bootRun

# Frontend
cd frontend && npm install && npm run dev
```

### Build
```bash
./gradlew build                 # Full build
./gradlew :backend:bootJar      # Backend JAR
./gradlew :optimizer:jar        # Optimizer JAR
cd frontend && npm run build    # Frontend
```

### Testing
```bash
./gradlew test                                    # Backend + Optimizer
./gradlew :backend:test --tests "*.SomeTest"     # Single test
cd frontend && npm test                           # Frontend
cd e2e && npm test                                # E2E (Playwright)
```

### Docker Production
```bash
cd docker
cp .env.example .env   # Configure!
docker compose up -d
```

## URLs (Development)

| Service | URL | Credentials |
|---------|-----|-------------|
| Frontend | http://localhost:3000 | - |
| Backend | http://localhost:8080 | - |
| Zitadel Console | http://localhost:8081/ui/console | testuser / test1234 |
| MinIO | http://localhost:9001 | minioadmin / minioadmin |
| Mailhog | http://localhost:8025 | - |

## Zitadel Setup

### Erstmaliges Setup
```bash
cd docker

# 1. Services starten
docker compose -f docker-compose.dev.yml up -d

# 2. Warten bis Zitadel bereit ist (ca. 30 Sekunden)
curl http://localhost:8081/debug/healthz  # sollte "ok" zurückgeben

# 3. Setup-Script ausführen (mit uv)
uv run python setup_zitadel.py
```

Das Setup-Script konfiguriert automatisch:
- Projekt "segel-bundesliga" mit allen Rollen
- Frontend OIDC-Applikation
- Vereinfachte Passwort-Policy (min. 8 Zeichen, keine Sonderzeichen)
- Deaktivierte 2FA-Anforderung
- Test-User für E2E-Tests
- Aktualisiert `frontend/.env.local` mit der neuen Client-ID

### Setup-Script Befehle
```bash
cd docker

# Vollständiges Setup (nach Neustart)
uv run python setup_zitadel.py

# Komplett-Reset (stoppt Services, löscht Daten, startet neu, führt Setup aus)
uv run python setup_zitadel.py --reset

# Nur Frontend-Config synchronisieren
uv run python setup_zitadel.py --sync-frontend

# Neuen Benutzer anlegen
uv run python setup_zitadel.py --add-user USERNAME PASSWORD

# Passwort zurücksetzen
uv run python setup_zitadel.py --reset-password USERNAME NEW_PASSWORD

# Alle Benutzer auflisten
uv run python setup_zitadel.py --list-users
```

### Bei Problemen (Komplett-Reset)

Am einfachsten mit dem automatischen Reset-Befehl:
```bash
cd docker
uv run python setup_zitadel.py --reset
```

Falls Permission-Fehler beim Löschen von `zitadel-data/`:
```bash
cd docker
sudo rm -rf zitadel-data/*
uv run python setup_zitadel.py --reset
```

Nach dem Reset: **Frontend neu starten!**
```bash
cd ../frontend && npm run dev
```

### Troubleshooting

| Problem | Ursache | Lösung |
|---------|---------|--------|
| Login leitet zurück ohne Fehlermeldung | Passwort-Policy oder 2FA-Problem | `uv run python setup_zitadel.py --reset` |
| "App not found" Fehler | Frontend hat alte Client-ID | `uv run python setup_zitadel.py --sync-frontend`, dann Frontend neustarten |
| Passwort-Änderung erforderlich | User hat `passwordChangeRequired` Flag | `uv run python setup_zitadel.py --reset-password USERNAME PASSWORD` |
| Zitadel komplett kaputt | Datenbank-Probleme | `uv run python setup_zitadel.py --reset` |
| Zitadel-UI auf Deutsch | Browser-Sprache ist DE | Kein Problem - E2E-Tests verwenden deutsche Labels ("Loginname", "Passwort", "Weiter") |
| E2E-Test findet Login-Feld nicht | Falscher Selector | Prüfen ob `getByRole` mit deutschem Label verwendet wird |

### Generierte Dateien
- `docker/zitadel-data/admin.pat` - Personal Access Token für API-Zugriff
- `docker/zitadel.env` - Environment-Variablen für Backend
- `frontend/.env.local` - Frontend Zitadel-Konfiguration (wird automatisch aktualisiert)

### Test-Benutzer (nach Setup)

| Username | Password | Beschreibung |
|----------|----------|--------------|
| admin | test1234 | Admin-Benutzer |
| testuser | test1234 | E2E-Test-Benutzer |

### Konfigurierte Rollen
| Rolle | Beschreibung |
|-------|--------------|
| ADMIN | Vollzugriff |
| BLOG_WRITE | Blog-Posts erstellen/bearbeiten |
| BLOG_PUBLISH | Blog-Posts veröffentlichen |
| SPONSOR_MANAGE | Sponsoren verwalten |
| PAIRING_EXECUTE | Optimierungen ausführen |
| PAIRING_VIEW | Optimierungsergebnisse ansehen |
| INTERNAL_ACCESS | Interne Inhalte sehen |

## Architecture Notes

### Authentication (Zitadel)
- Backend: `SecurityConfig.java` validates JWT from Zitadel
- Roles stored in JWT claim `urn:zitadel:iam:org:project:{projectId}:roles`
- Custom `ZitadelGrantedAuthoritiesConverter` extracts roles from project-specific claim
- No local User entity needed - Zitadel handles everything

### File Storage (MinIO)
- `StorageService.java` handles uploads/downloads
- Files stored in bucket `segel-bundesliga`
- Presigned URLs for browser access (60 min default)
- Config in `application.yml` under `minio.*`

### Optimizer Integration
- `optimizer` module is pure Java, no Spring dependencies
- Backend imports via `implementation(project(":optimizer"))`
- Key classes:
  - `Optimizer.java` - Main entry point
  - `configs/ScheduleConfig.java` - Tournament setup
  - `configs/OptimizationConfig.java` - Algorithm params
  - `types/Schedule.java` - Result structure

### SSE für Optimierungs-Fortschritt
```
GET /api/optimization/{id}/progress  (text/event-stream)
```
Events:
- `started` - Optimierung gestartet
- `phase_started` - Phase (MATCH_MATRIX, BOAT_SCHEDULE) begonnen
- `progress` - Fortschritts-Update mit Score
- `phase_completed` - Phase abgeschlossen
- `completed` - Optimierung erfolgreich beendet
- `failed` - Fehler aufgetreten

Frontend-Beispiel:
```javascript
const eventSource = new EventSource(`/api/optimization/${id}/progress`);
eventSource.addEventListener('progress', (e) => {
  const data = JSON.parse(e.data);
  console.log(`Score: ${data.bestScore}`);
});
```

### Security Endpoints
```
Public:     GET /api/public/**, /api/posts/**, /api/pages/**, /api/sponsors/**
Protected:  POST/PUT/DELETE /api/**, /api/tournaments/**, /api/optimization/**
Admin:      /api/admin/**
```

## Key Files

| File | Purpose |
|------|---------|
| `backend/src/main/java/.../config/SecurityConfig.java` | OIDC/JWT config |
| `backend/src/main/java/.../config/MinioConfig.java` | MinIO client bean |
| `backend/src/main/java/.../domain/*.java` | Entity-Klassen (Tournament, Post, Page, Sponsor) |
| `backend/src/main/java/.../dto/*.java` | DTOs mit Create/Update/Response/ListItem |
| `backend/src/main/java/.../service/*.java` | Business Logic Services |
| `backend/src/main/java/.../web/*.java` | REST Controller |
| `backend/src/main/java/.../service/StorageService.java` | File upload/download |
| `backend/src/main/resources/application.yml` | Main config |
| `backend/src/main/resources/db/changelog/*.xml` | Liquibase Migrations |
| `optimizer/src/main/java/.../Optimizer.java` | PairingList entry point |
| `docker/docker-compose.dev.yml` | Dev environment |
| `docker/docker-compose.yml` | Production setup |
| `docker/setup_zitadel.py` | Automatisches Zitadel-Setup |
| `docker/zitadel.env` | Generierte Zitadel-Konfiguration |

### API Endpoints

| Resource | Endpoints |
|----------|-----------|
| Tournaments | `GET/POST /api/tournaments`, `GET/PUT/DELETE /api/tournaments/{id}`, `GET /api/tournaments/my` |
| Posts | `GET /api/posts/public`, `GET /api/posts/public/{slug}`, CRUD `/api/posts`, `PUT /{id}/publish` |
| Pages | `GET /api/pages/public`, `GET /api/pages/menu`, CRUD `/api/pages` |
| Sponsors | `GET /api/sponsors/public`, CRUD `/api/sponsors`, `POST /{id}/logo` |
| Optimization | `POST /{id}/start`, `GET /{id}/progress` (SSE), `POST /{id}/cancel`, `GET /{id}/result`, `GET /{id}/status` |

## Test-ID Convention (Playwright)

All interactive UI components use `data-testid`:
```
{bereich}-{element}-{typ}
Examples: login-email-input, tournament-create-button, optimization-progress-bar
```

## Frontend Routen

| Route | Beschreibung | Auth |
|-------|--------------|------|
| `/` | Startseite | - |
| `/tournaments` | Turnierübersicht | Login |
| `/tournaments/new` | Neues Turnier | Login |
| `/tournaments/:id` | Turnier-Details | Login |
| `/seite/:slug` | Statische Seiten (Impressum, etc.) | - |
| `/admin/*` | Admin-Panel (react-admin) | Login + ADMIN |

### Standard-Seiten (via CMS)

| Slug | Titel | Beschreibung |
|------|-------|--------------|
| `ueber-uns` | Über uns | Projektbeschreibung |
| `kontakt` | Kontakt | Kontaktinformationen |
| `impressum` | Impressum | Rechtliche Angaben |
| `datenschutz` | Datenschutz | Datenschutzerklärung |
| `agb` | AGB | Allgemeine Geschäftsbedingungen |

### Admin-Panel

Das Admin-Panel unter `/admin` nutzt [react-admin](https://marmelab.com/react-admin/) und ermöglicht:
- Seiten verwalten (CRUD für statische Seiten)
- Erfordert ADMIN-Rolle in Zitadel

## TODO

- [x] Entity-Klassen (Tournament, Post, Page, Sponsor)
- [x] Liquibase Migrations
- [x] DTOs, Services, Controller (CRUD)
- [x] OptimizerService mit SSE für Echtzeit-Fortschritt
- [x] Zitadel Setup-Automatisierung (setup_zitadel.py)
- [x] Backend SecurityConfig mit Zitadel JWT-Integration
- [x] Frontend Auth Integration (Zitadel OIDC)
- [x] Frontend Optimization UI mit SSE
- [x] Standard-Seiten mit Footer und Admin-UI
- [x] E2E Login-Tests (AuthenticationTest mit deutschen Labels)
- [ ] Weitere E2E Tests (Turniere, Blog, Admin)
