# Segel-Bundesliga

Web-Plattform für die Deutsche Segel-Bundesliga mit PairingList-Optimizer, User Management und Content-System.

## Features

- **PairingList Optimizer** - Optimierung von Segelregatta-Paarungen mit Echtzeit-Fortschrittsanzeige
- **User Management** - Über Zitadel (Self-Hosted Identity Provider) mit OAuth2 (Google, GitHub)
- **Blog/Pages** - Öffentliche und interne Inhalte mit Bild-Upload
- **i18n** - Deutsch und Englisch

## Tech Stack

| Komponente | Technologie |
|------------|-------------|
| Backend | Spring Boot 3.2, Java 21 |
| Frontend | React 18, Vite, TailwindCSS, Zustand |
| Datenbank | PostgreSQL 16 |
| Auth | Zitadel (OIDC/OAuth2) |
| File Storage | MinIO (S3-kompatibel) |
| Testing | JUnit 5, Vitest, Playwright |
| Build | Gradle 8.5 (Kotlin DSL) |

## Projektstruktur

```
segel-bundesliga/
├── backend/                 # Spring Boot API
│   └── src/main/java/de/segelbundesliga/
│       ├── config/          # Security, MinIO Config
│       └── service/         # Business Logic
├── frontend/                # React + Vite + TailwindCSS
│   └── src/
├── optimizer/               # PairingList Optimizer (Java Library)
│   └── src/main/java/gundramleifert/pairing_list/
│       ├── configs/         # Schedule, Optimization, Display Config
│       ├── cost_calculators/
│       └── types/           # Flight, Race, Schedule, etc.
├── e2e/                     # Playwright E2E Tests
├── docker/                  # Docker Compose & Dockerfiles
└── docs/                    # Dokumentation
```

## Schnellstart

### Voraussetzungen

- Java 21 (z.B. Amazon Corretto, Eclipse Temurin)
- Node.js 20+
- Docker & Docker Compose

### 1. Development Services starten

```bash
cd docker
docker compose -f docker-compose.dev.yml up -d
```

Dies startet:
- PostgreSQL (Port 5432)
- Zitadel (Port 8081)
- MinIO (Port 9000, Console: 9001)
- Mailhog (Port 8025)

### 2. Backend starten

```bash
./gradlew :backend:bootRun
```

### 3. Frontend starten

```bash
cd frontend
npm install
npm run dev
```

### URLs (Development)

| Service | URL | Credentials |
|---------|-----|-------------|
| Frontend | http://localhost:3000 | - |
| Backend API | http://localhost:8080 | - |
| Zitadel Admin | http://localhost:8081 | admin / Admin123! |
| MinIO Console | http://localhost:9001 | minioadmin / minioadmin |
| Mailhog | http://localhost:8025 | - |
| H2 Console (dev) | http://localhost:8080/h2-console | sa / (leer) |

## Zitadel Einrichtung

Nach dem ersten Start von Zitadel:

1. **Login** unter http://localhost:8081 mit `admin` / `Admin123!`
2. **Projekt anlegen**: "Segel-Bundesliga"
3. **Application anlegen**:
   - Type: Web
   - Auth Method: PKCE
   - Redirect URIs: `http://localhost:3000/callback`
4. **Client ID kopieren** und in Frontend-Konfiguration eintragen
5. **Optional**: Google/GitHub als Identity Provider hinzufügen

## Build & Test

```bash
# Vollständiger Build
./gradlew build

# Nur Backend
./gradlew :backend:bootJar

# Nur Optimizer
./gradlew :optimizer:jar

# Frontend Build
cd frontend && npm run build

# Tests
./gradlew test                    # Backend + Optimizer
cd frontend && npm test           # Frontend Unit Tests
cd e2e && npm test                # E2E Tests (Playwright)
```

## Produktion

### 1. Environment konfigurieren

```bash
cd docker
cp .env.example .env
# Werte in .env anpassen!
```

### 2. Docker Compose starten

```bash
docker compose up -d
```

### Backup

**PostgreSQL:**
```bash
docker exec -t postgres pg_dumpall -c -U postgres > backup.sql
```

**MinIO (File Storage):**
```bash
docker run --rm -v minio_data:/data -v $(pwd):/backup alpine \
    tar cvf /backup/minio-backup.tar /data
```

## Architektur

### Module

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Frontend   │────▶│   Backend   │────▶│  Optimizer  │
│   (React)   │     │(Spring Boot)│     │   (Java)    │
└─────────────┘     └─────────────┘     └─────────────┘
       │                   │
       │                   ▼
       │            ┌─────────────┐
       │            │ PostgreSQL  │
       │            └─────────────┘
       │                   │
       ▼                   ▼
┌─────────────┐     ┌─────────────┐
│   Zitadel   │     │    MinIO    │
│   (Auth)    │     │  (Storage)  │
└─────────────┘     └─────────────┘
```

### Authentifizierung

- Frontend authentifiziert über Zitadel (OIDC)
- Backend validiert JWT-Tokens von Zitadel
- Rollen werden in Zitadel verwaltet

### File Storage

- Bilder und Dateien werden in MinIO gespeichert
- S3-kompatible API
- Presigned URLs für direkten Browser-Zugriff

### PairingList Optimizer

Der Optimizer ist als separate Java-Library implementiert und wird vom Backend als Dependency eingebunden:

```java
// Backend nutzt Optimizer
implementation(project(":optimizer"))
```

Konfigurationen:
- **ScheduleConfig** - Teams, Boote, Flights
- **OptimizationConfig** - Algorithmus-Parameter
- **DisplayConfig** - Visualisierungs-Einstellungen

## API Endpunkte

### Öffentlich (kein Auth)
- `GET /api/public/**`
- `GET /api/posts/**`
- `GET /api/pages/**`

### Geschützt (Auth erforderlich)
- `POST/PUT/DELETE /api/posts/**`
- `POST/PUT/DELETE /api/pages/**`
- `/api/tournaments/**`
- `/api/optimization/**`

### Admin
- `/api/admin/**`

## Environment Variables

| Variable | Beschreibung | Default |
|----------|--------------|---------|
| `DB_PASSWORD` | PostgreSQL Root-Passwort | postgres |
| `ZITADEL_DOMAIN` | Zitadel Domain | localhost |
| `ZITADEL_MASTERKEY` | Zitadel Master Key (min. 32 Zeichen) | - |
| `ZITADEL_ADMIN_PASSWORD` | Zitadel Admin-Passwort | Admin123! |
| `ZITADEL_CLIENT_ID` | OAuth Client ID | - |
| `MINIO_ROOT_USER` | MinIO Benutzername | minioadmin |
| `MINIO_ROOT_PASSWORD` | MinIO Passwort | minioadmin |

## Lizenz

[MIT](LICENSE)
