# MISSION.md

Web-Plattform für die Segel-Bundesliga (German Sailing Federal League)

## Ursprüngliche Anforderungen

- Usermanagement (User müssen durch Administrator freigegeben werden)
- Möglichkeit, Posts auf der Webseite zu machen
- Möglichkeit, interne und öffentliche Seiten zu haben
- Möglichkeit, Sponsoren oder ähnliches darzustellen
- Möglichkeit, https://github.com/gundramleifert/PairingList so zu ändern, dass es über eine UI genutzt werden kann (inkl. Persistenz)
- Backend: Java (Spring Boot 3.2, Java 21)

---

## Projektstatus (Stand: Januar 2026)

### ✅ Vollständig implementiert

#### Backend (Spring Boot 3.2 + Java 21)

| Bereich | Status | Details |
|---------|--------|---------|
| **Authentifizierung** | ✅ | Zitadel OIDC/JWT, Rollen-basierte Zugriffskontrolle |
| **Turnier-Verwaltung** | ✅ | CRUD, Teams, Boote, Ownership-Validierung |
| **Blog-System** | ✅ | Zweisprachig (DE/EN), Publish-Workflow, Bild-Upload |
| **CMS-Seiten** | ✅ | Menü-Sortierung, Sichtbarkeit, Standard-Seiten |
| **Sponsoren** | ✅ | CRUD, Logo-Upload, aktiv/inaktiv |
| **Datei-Storage** | ✅ | MinIO (S3-kompatibel), Presigned URLs |
| **Optimizer-Integration** | ✅ | SSE-Streaming, 2-Phasen-Optimierung |
| **Datenbank** | ✅ | PostgreSQL 16, Liquibase Migrations (6 Changesets) |

**Entities:** Tournament, Post, Page, Sponsor, Team, Boat, OptimizationSettings
**API-Endpunkte:** 6 Controller mit vollständiger REST-API

#### Frontend (React 18 + Vite + TailwindCSS)

| Bereich | Status | Details |
|---------|--------|---------|
| **Authentifizierung** | ✅ | OIDC via react-oidc-context, Protected Routes |
| **Startseite** | ✅ | Hero, Feature-Cards, responsive Design |
| **Turnier-Liste** | ✅ | Filterung, Status-Anzeige, Empty States |
| **Turnier-Erstellung** | ✅ | Teams/Boote dynamisch hinzufügen |
| **Turnier-Details** | ✅ | Live-Optimierung mit SSE, Progress-Bar, Event-Log |
| **CMS-Seiten** | ✅ | Öffentliche Seiten-Darstellung |
| **Admin-Panel** | ⚠️ | Nur Seiten-Verwaltung (react-admin) |
| **UI-Komponenten** | ✅ | Shadcn/UI (25+ Komponenten) |

#### Infrastruktur (Docker)

| Service | Status | Port |
|---------|--------|------|
| PostgreSQL 16 | ✅ | 5432 |
| Zitadel (OIDC) | ✅ | 8081 |
| MinIO | ✅ | 9000/9001 |
| Mailhog | ✅ | 1025/8025 |

**Setup-Automatisierung:** `setup_zitadel.py` mit Reset, User-Management, Password-Reset

#### Optimizer (Java Library)

| Komponente | Status |
|------------|--------|
| Match-Matrix-Optimierung | ✅ |
| Boot-Zeitplan-Optimierung | ✅ |
| Genetischer Algorithmus | ✅ |
| Ergebnis-Serialisierung | ✅ |

---

### ⚠️ Teilweise implementiert

| Bereich | Status | Was fehlt |
|---------|--------|-----------|
| **Admin-Panel** | 30% | Posts- und Sponsoren-Verwaltung fehlt |
| **E2E-Tests** | 5% | Nur Smoke-Test vorhanden |
| **Backend-Tests** | 10% | Nur SecurityConfigTest (45 Tests) |
| **i18n** | 20% | Infrastruktur vorhanden, Übersetzungen fehlen |
| **Dokumentation** | 60% | CLAUDE.md gut, API-Doku fehlt |

---

### ❌ Noch nicht implementiert

| Bereich | Priorität | Beschreibung |
|---------|-----------|--------------|
| **Test-Abdeckung** | HOCH | Service-Layer, Integration, Komponenten |
| **Admin: Posts** | HOCH | Blog-Verwaltung im Admin-Panel |
| **Admin: Sponsoren** | HOCH | Sponsoren-Verwaltung im Admin-Panel |
| **API-Dokumentation** | MITTEL | OpenAPI/Swagger |
| **CI/CD** | MITTEL | GitHub Actions für Tests und Deployment |
| **E-Mail-Benachrichtigungen** | MITTEL | Mail-Starter vorhanden, nicht integriert |
| **Erweiterte Optimierungs-UI** | NIEDRIG | Algorithmus-Parameter im Frontend |
| **Performance-Optimierung** | NIEDRIG | Caching, Pagination |
| **Offline-Support** | NIEDRIG | PWA-Features |

---

## Nächste Schritte (Priorisiert)

### Phase 1: Admin-Panel vervollständigen
1. Posts-Resource in react-admin hinzufügen
2. Sponsoren-Resource in react-admin hinzufügen
3. Bild-Upload in Admin-Formularen integrieren

### Phase 2: Test-Abdeckung erhöhen
1. Service-Layer Unit-Tests (TournamentService, PostService, etc.)
2. Integration-Tests für Optimizer-Flow
3. Frontend-Komponenten-Tests (Vitest)
4. E2E-Tests erweitern (Login, Turnier-CRUD, Optimierung)

### Phase 3: Dokumentation & Qualität
1. OpenAPI/Swagger für REST-API
2. CI/CD-Pipeline (GitHub Actions)
3. Error-Handling verbessern
4. Toast-Benachrichtigungen im Frontend

### Phase 4: Features
1. E-Mail-Benachrichtigungen aktivieren
2. Turnier-Export/Import
3. Vollständige i18n (EN-Übersetzungen)

---

## Technologie-Stack

| Komponente | Technologie | Version |
|------------|-------------|---------|
| Backend | Spring Boot | 3.2.1 |
| Java | OpenJDK | 21 |
| Frontend | React | 18.2.0 |
| Build (FE) | Vite | 5.x |
| Styling | TailwindCSS | 3.4.0 |
| State | Zustand | 4.4.7 |
| Data Fetching | TanStack Query | 5.17.0 |
| Admin | react-admin | 5.13.4 |
| Auth | Zitadel | 2.64.1 |
| Database | PostgreSQL | 16 |
| Migrations | Liquibase | - |
| Storage | MinIO | 8.5.7 |
| Build (BE) | Gradle (Kotlin DSL) | 8.5 |
| Testing (E2E) | Playwright | - |

---

## Architektur-Übersicht

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (React)                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐ │
│  │   Home   │  │ Turniere │  │  Seiten  │  │   Admin Panel    │ │
│  └──────────┘  └──────────┘  └──────────┘  └──────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼ REST/SSE
┌─────────────────────────────────────────────────────────────────┐
│                      Backend (Spring Boot)                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │  Controller  │  │   Services   │  │    Repositories      │   │
│  └──────────────┘  └──────────────┘  └──────────────────────┘   │
│          │                │                    │                 │
│          ▼                ▼                    ▼                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │   Optimizer  │  │   Zitadel    │  │     PostgreSQL       │   │
│  │   (Library)  │  │   (OIDC)     │  │                      │   │
│  └──────────────┘  └──────────────┘  └──────────────────────┘   │
│                                              │                   │
│                                              ▼                   │
│                                      ┌──────────────┐           │
│                                      │    MinIO     │           │
│                                      │  (Storage)   │           │
│                                      └──────────────┘           │
└─────────────────────────────────────────────────────────────────┘
```

---

## Metriken

| Metrik | Wert |
|--------|------|
| Backend LOC | ~3.500 |
| Frontend LOC | ~4.000 |
| Optimizer LOC | ~2.000 |
| API-Endpunkte | 30+ |
| DB-Tabellen | 6 |
| UI-Komponenten | 25+ |
| Test-Coverage | ~15% (geschätzt) |
