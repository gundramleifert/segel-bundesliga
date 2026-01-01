#!/bin/bash
# ============================================================
# Setup-Script für Segel-Bundesliga Web-Projekt
# Mono-Repo mit Gradle Multi-Project Build
# Führe aus: chmod +x setup.sh && ./setup.sh
# ============================================================

set -e

PROJECT_NAME="segel-bundesliga"
echo "🚀 Erstelle Mono-Repo: $PROJECT_NAME"

mkdir -p $PROJECT_NAME
cd $PROJECT_NAME

# ============================================================
# 1. Verzeichnisstruktur
# ============================================================

mkdir -p backend
mkdir -p frontend
mkdir -p optimizer
mkdir -p docker
mkdir -p e2e
mkdir -p docs

# ============================================================
# 2. Root Gradle Build (settings.gradle.kts)
# ============================================================

cat > settings.gradle.kts << 'EOF'
rootProject.name = "segel-bundesliga"

include("backend")
include("optimizer")
// frontend wird separat mit npm verwaltet
EOF

# ============================================================
# 3. Root build.gradle.kts
# ============================================================

cat > build.gradle.kts << 'EOF'
plugins {
    id("java")
    id("idea")
}

allprojects {
    group = "de.segelbundesliga"
    version = "0.1.0-SNAPSHOT"

    repositories {
        mavenCentral()
    }
}

subprojects {
    apply(plugin = "java")

    java {
        sourceCompatibility = JavaVersion.VERSION_21
        targetCompatibility = JavaVersion.VERSION_21
    }

    tasks.withType<Test> {
        useJUnitPlatform()
    }
}
EOF

# ============================================================
# 4. Optimizer Modul (PairingList)
# ============================================================

cat > optimizer/build.gradle.kts << 'EOF'
plugins {
    id("java-library")
}

dependencies {
    // YAML parsing
    implementation("org.yaml:snakeyaml:2.2")

    // Logging
    implementation("org.slf4j:slf4j-api:2.0.9")

    // Testing
    testImplementation("org.junit.jupiter:junit-jupiter:5.10.1")
    testRuntimeOnly("org.junit.platform:junit-platform-launcher")
}
EOF

mkdir -p optimizer/src/main/java/de/segelbundesliga/optimizer
mkdir -p optimizer/src/test/java/de/segelbundesliga/optimizer

cat > optimizer/src/main/java/de/segelbundesliga/optimizer/PairingListOptimizer.java << 'EOF'
package de.segelbundesliga.optimizer;

/**
 * PairingList Optimizer - Kernlogik für die Optimierung von Segelregatta-Paarungen.
 *
 * TODO: Code aus https://github.com/gundramleifert/PairingList hierher migrieren
 */
public class PairingListOptimizer {

    public interface ProgressCallback {
        void onPhaseStarted(int phase, int totalPhases, String phaseName);
        void onIterationProgress(int iteration, int totalIterations, double bestScore);
        void onCompleted(OptimizationResult result);
        void onFailed(String errorMessage);
    }

    public record OptimizationConfig(
        int flights,
        int teams,
        int boats,
        long seed,
        int mmLoops,
        int buLoops
    ) {}

    public record OptimizationResult(
        String scheduleYaml,
        int savedShuttles,
        int boatChanges,
        long computationTimeMs
    ) {}

    public void optimize(OptimizationConfig config, ProgressCallback callback) {
        // TODO: Implementierung aus PairingList-Repo übernehmen
        throw new UnsupportedOperationException("Not yet implemented");
    }
}
EOF

# ============================================================
# 5. Backend Modul (JHipster-generiert)
# ============================================================

cat > backend/build.gradle.kts << 'EOF'
plugins {
    id("java")
    id("org.springframework.boot") version "3.2.1"
    id("io.spring.dependency-management") version "1.1.4"
}

dependencies {
    // Optimizer als lokale Dependency
    implementation(project(":optimizer"))

    // Spring Boot
    implementation("org.springframework.boot:spring-boot-starter-web")
    implementation("org.springframework.boot:spring-boot-starter-data-jpa")
    implementation("org.springframework.boot:spring-boot-starter-security")
    implementation("org.springframework.boot:spring-boot-starter-validation")
    implementation("org.springframework.boot:spring-boot-starter-websocket")
    implementation("org.springframework.boot:spring-boot-starter-mail")

    // OAuth2
    implementation("org.springframework.boot:spring-boot-starter-oauth2-client")
    implementation("org.springframework.boot:spring-boot-starter-oauth2-resource-server")

    // Database
    runtimeOnly("org.postgresql:postgresql")
    implementation("org.liquibase:liquibase-core")

    // JWT
    implementation("io.jsonwebtoken:jjwt-api:0.12.3")
    runtimeOnly("io.jsonwebtoken:jjwt-impl:0.12.3")
    runtimeOnly("io.jsonwebtoken:jjwt-jackson:0.12.3")

    // MapStruct
    implementation("org.mapstruct:mapstruct:1.5.5.Final")
    annotationProcessor("org.mapstruct:mapstruct-processor:1.5.5.Final")

    // Lombok
    compileOnly("org.projectlombok:lombok")
    annotationProcessor("org.projectlombok:lombok")
    annotationProcessor("org.projectlombok:lombok-mapstruct-binding:0.2.0")

    // Dev
    developmentOnly("org.springframework.boot:spring-boot-devtools")

    // Test
    testImplementation("org.springframework.boot:spring-boot-starter-test")
    testImplementation("org.springframework.security:spring-security-test")
    testRuntimeOnly("com.h2database:h2")
}

tasks.bootRun {
    jvmArgs = listOf("-Dspring.profiles.active=dev")
}
EOF

mkdir -p backend/src/main/java/de/segelbundesliga
mkdir -p backend/src/main/resources
mkdir -p backend/src/test/java/de/segelbundesliga

cat > backend/src/main/java/de/segelbundesliga/SegelBundesligaApplication.java << 'EOF'
package de.segelbundesliga;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
public class SegelBundesligaApplication {
    public static void main(String[] args) {
        SpringApplication.run(SegelBundesligaApplication.class, args);
    }
}
EOF

cat > backend/src/main/resources/application.yml << 'EOF'
spring:
  application:
    name: segel-bundesliga
  profiles:
    active: dev

  datasource:
    url: jdbc:postgresql://localhost:5432/segelbundesliga
    username: postgres
    password: postgres

  jpa:
    hibernate:
      ddl-auto: validate
    open-in-view: false

  liquibase:
    change-log: classpath:db/changelog/db.changelog-master.xml

  mail:
    host: ${MAIL_HOST:localhost}
    port: ${MAIL_PORT:1025}
    username: ${MAIL_USERNAME:}
    password: ${MAIL_PASSWORD:}

server:
  port: 8080

# JWT Configuration
application:
  security:
    jwt:
      secret: ${JWT_SECRET:your-256-bit-secret-key-here-for-development-only}
      token-validity-in-seconds: 86400
      token-validity-in-seconds-for-remember-me: 2592000
EOF

cat > backend/src/main/resources/application-dev.yml << 'EOF'
spring:
  datasource:
    url: jdbc:h2:mem:segelbundesliga;DB_CLOSE_DELAY=-1
    driver-class-name: org.h2.Driver
    username: sa
    password:

  h2:
    console:
      enabled: true
      path: /h2-console

  jpa:
    hibernate:
      ddl-auto: create-drop
    show-sql: true

  liquibase:
    enabled: false

logging:
  level:
    de.segelbundesliga: DEBUG
    org.springframework.security: DEBUG
EOF

# ============================================================
# 6. Frontend (React + Vite)
# ============================================================

cat > frontend/package.json << 'EOF'
{
  "name": "segel-bundesliga-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview",
    "lint": "eslint . --ext ts,tsx --report-unused-disable-directives --max-warnings 0",
    "test": "vitest",
    "test:e2e": "playwright test"
  },
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-router-dom": "^6.21.1",
    "@tanstack/react-query": "^5.17.0",
    "axios": "^1.6.3",
    "@stomp/stompjs": "^7.0.0",
    "sockjs-client": "^1.6.1",
    "i18next": "^23.7.11",
    "react-i18next": "^14.0.0",
    "zustand": "^4.4.7"
  },
  "devDependencies": {
    "@types/react": "^18.2.46",
    "@types/react-dom": "^18.2.18",
    "@types/sockjs-client": "^1.5.4",
    "@typescript-eslint/eslint-plugin": "^6.16.0",
    "@typescript-eslint/parser": "^6.16.0",
    "@vitejs/plugin-react": "^4.2.1",
    "autoprefixer": "^10.4.16",
    "eslint": "^8.56.0",
    "eslint-plugin-react-hooks": "^4.6.0",
    "eslint-plugin-react-refresh": "^0.4.5",
    "postcss": "^8.4.32",
    "tailwindcss": "^3.4.0",
    "typescript": "^5.3.3",
    "vite": "^5.0.10",
    "vitest": "^1.1.1",
    "@playwright/test": "^1.40.1"
  }
}
EOF

cat > frontend/vite.config.ts << 'EOF'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8080',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://localhost:8080',
        ws: true,
      },
    },
  },
})
EOF

cat > frontend/tsconfig.json << 'EOF'
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true
  },
  "include": ["src"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
EOF

cat > frontend/tsconfig.node.json << 'EOF'
{
  "compilerOptions": {
    "composite": true,
    "skipLibCheck": true,
    "module": "ESNext",
    "moduleResolution": "bundler",
    "allowSyntheticDefaultImports": true
  },
  "include": ["vite.config.ts"]
}
EOF

cat > frontend/tailwind.config.js << 'EOF'
/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {},
  },
  plugins: [],
}
EOF

cat > frontend/postcss.config.js << 'EOF'
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
}
EOF

mkdir -p frontend/src

cat > frontend/index.html << 'EOF'
<!DOCTYPE html>
<html lang="de">
  <head>
    <meta charset="UTF-8" />
    <link rel="icon" type="image/svg+xml" href="/vite.svg" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Segel-Bundesliga</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
EOF

cat > frontend/src/main.tsx << 'EOF'
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
EOF

cat > frontend/src/App.tsx << 'EOF'
function App() {
  return (
    <div className="min-h-screen bg-gray-100">
      <header className="bg-blue-600 text-white p-4">
        <h1 className="text-2xl font-bold" data-testid="app-title">
          Segel-Bundesliga
        </h1>
      </header>
      <main className="container mx-auto p-4">
        <p data-testid="welcome-message">
          Willkommen zur Segel-Bundesliga Plattform
        </p>
      </main>
    </div>
  )
}

export default App
EOF

cat > frontend/src/index.css << 'EOF'
@tailwind base;
@tailwind components;
@tailwind utilities;
EOF

# ============================================================
# 7. E2E Tests (Playwright)
# ============================================================

cat > e2e/package.json << 'EOF'
{
  "name": "segel-bundesliga-e2e",
  "private": true,
  "scripts": {
    "test": "playwright test",
    "test:ui": "playwright test --ui",
    "test:headed": "playwright test --headed"
  },
  "devDependencies": {
    "@playwright/test": "^1.40.1"
  }
}
EOF

cat > e2e/playwright.config.ts << 'EOF'
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: 'html',

  use: {
    baseURL: 'http://localhost:3000',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },

  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'firefox',
      use: { ...devices['Desktop Firefox'] },
    },
    {
      name: 'webkit',
      use: { ...devices['Desktop Safari'] },
    },
  ],

  webServer: [
    {
      command: 'cd ../backend && ./gradlew bootRun',
      url: 'http://localhost:8080/actuator/health',
      reuseExistingServer: !process.env.CI,
      timeout: 120000,
    },
    {
      command: 'cd ../frontend && npm run dev',
      url: 'http://localhost:3000',
      reuseExistingServer: !process.env.CI,
    },
  ],
});
EOF

mkdir -p e2e/tests

cat > e2e/tests/smoke.spec.ts << 'EOF'
import { test, expect } from '@playwright/test';

test.describe('Smoke Tests', () => {
  test('homepage loads successfully', async ({ page }) => {
    await page.goto('/');

    await expect(page.getByTestId('app-title')).toBeVisible();
    await expect(page.getByTestId('welcome-message')).toBeVisible();
  });
});
EOF

# ============================================================
# 8. Docker Compose
# ============================================================

cat > docker/docker-compose.yml << 'EOF'
version: "3.8"

services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: segelbundesliga
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: ${DB_PASSWORD:-postgres}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5

  mailhog:
    image: mailhog/mailhog
    ports:
      - "1025:1025"
      - "8025:8025"

  backend:
    build:
      context: ..
      dockerfile: docker/Dockerfile.backend
    environment:
      SPRING_PROFILES_ACTIVE: docker
      SPRING_DATASOURCE_URL: jdbc:postgresql://postgres:5432/segelbundesliga
      SPRING_DATASOURCE_USERNAME: postgres
      SPRING_DATASOURCE_PASSWORD: ${DB_PASSWORD:-postgres}
    ports:
      - "8080:8080"
    depends_on:
      postgres:
        condition: service_healthy

  frontend:
    build:
      context: ../frontend
      dockerfile: ../docker/Dockerfile.frontend
    ports:
      - "3000:80"
    depends_on:
      - backend

volumes:
  postgres_data:
EOF

cat > docker/docker-compose.dev.yml << 'EOF'
version: "3.8"

services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: segelbundesliga
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    ports:
      - "5432:5432"

  mailhog:
    image: mailhog/mailhog
    ports:
      - "1025:1025"
      - "8025:8025"
EOF

cat > docker/Dockerfile.backend << 'EOF'
FROM eclipse-temurin:21-jdk-alpine AS builder

WORKDIR /app
COPY gradlew .
COPY gradle gradle
COPY build.gradle.kts .
COPY settings.gradle.kts .
COPY backend backend
COPY optimizer optimizer

RUN chmod +x gradlew
RUN ./gradlew :backend:bootJar --no-daemon

FROM eclipse-temurin:21-jre-alpine

WORKDIR /app
COPY --from=builder /app/backend/build/libs/*.jar app.jar

EXPOSE 8080

ENTRYPOINT ["java", "-jar", "app.jar"]
EOF

cat > docker/Dockerfile.frontend << 'EOF'
FROM node:20-alpine AS builder

WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
EOF

cat > docker/nginx.conf << 'EOF'
server {
    listen 80;
    server_name localhost;
    root /usr/share/nginx/html;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api {
        proxy_pass http://backend:8080;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }

    location /ws {
        proxy_pass http://backend:8080;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "Upgrade";
        proxy_set_header Host $host;
    }
}
EOF

cat > docker/.env.example << 'EOF'
# Database
DB_PASSWORD=super_sicheres_passwort

# JWT
JWT_SECRET=min-64-zeichen-langer-geheimer-schluessel-fuer-jwt-tokens

# OAuth (vor Go-Live einrichten)
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GITHUB_CLIENT_ID=
GITHUB_CLIENT_SECRET=

# Mail (Brevo SMTP)
MAIL_HOST=smtp-relay.brevo.com
MAIL_PORT=587
MAIL_USERNAME=
MAIL_PASSWORD=
EOF

# ============================================================
# 9. Gradle Wrapper
# ============================================================

cat > gradlew << 'GRADLEW'
#!/bin/sh
# Gradle Wrapper - wird beim ersten Build automatisch heruntergeladen
echo "Downloading Gradle Wrapper..."
GRADLE_VERSION=8.5
WRAPPER_JAR="gradle/wrapper/gradle-wrapper.jar"

mkdir -p gradle/wrapper

if [ ! -f "$WRAPPER_JAR" ]; then
    curl -L -o "$WRAPPER_JAR" "https://services.gradle.org/distributions/gradle-${GRADLE_VERSION}-bin.zip" 2>/dev/null || \
    wget -O "$WRAPPER_JAR" "https://services.gradle.org/distributions/gradle-${GRADLE_VERSION}-bin.zip" 2>/dev/null
fi

exec java -jar "$WRAPPER_JAR" "$@"
GRADLEW

chmod +x gradlew

mkdir -p gradle/wrapper
cat > gradle/wrapper/gradle-wrapper.properties << 'EOF'
distributionBase=GRADLE_USER_HOME
distributionPath=wrapper/dists
distributionUrl=https\://services.gradle.org/distributions/gradle-8.5-bin.zip
networkTimeout=10000
validateDistributionUrl=true
zipStoreBase=GRADLE_USER_HOME
zipStorePath=wrapper/dists
EOF

# ============================================================
# 10. Git & Editor Config
# ============================================================

cat > .gitignore << 'EOF'
# Gradle
.gradle/
build/
!gradle/wrapper/gradle-wrapper.jar

# IDE
.idea/
*.iml
.vscode/
*.swp

# Node
node_modules/
dist/

# Env
.env
.env.local

# OS
.DS_Store
Thumbs.db

# Test
/e2e/test-results/
/e2e/playwright-report/
EOF

cat > .editorconfig << 'EOF'
root = true

[*]
charset = utf-8
end_of_line = lf
insert_final_newline = true
trim_trailing_whitespace = true
indent_style = space
indent_size = 2

[*.{java,kt,kts}]
indent_size = 4

[*.md]
trim_trailing_whitespace = false
EOF

# ============================================================
# 11. README
# ============================================================

cat > README.md << 'EOF'
# Segel-Bundesliga

Web-Plattform für die Deutsche Segel-Bundesliga mit PairingList-Optimizer.

## Projektstruktur (Mono-Repo)

```
├── backend/          # Spring Boot API
├── frontend/         # React + Vite + TailwindCSS
├── optimizer/        # PairingList Optimizer (Java Library)
├── e2e/              # Playwright E2E Tests
├── docker/           # Docker Compose & Dockerfiles
└── docs/             # Dokumentation
```

## Schnellstart

### Voraussetzungen
- Java 21
- Node.js 20+
- Docker & Docker Compose

### Entwicklung starten

```bash
# 1. Datenbank & Mailhog starten
cd docker && docker compose -f docker-compose.dev.yml up -d

# 2. Backend starten (Terminal 1)
./gradlew :backend:bootRun

# 3. Frontend starten (Terminal 2)
cd frontend && npm install && npm run dev
```

- Frontend: http://localhost:3000
- Backend API: http://localhost:8080
- H2 Console (dev): http://localhost:8080/h2-console
- Mailhog: http://localhost:8025

### Tests

```bash
# Backend Tests
./gradlew test

# Frontend Tests
cd frontend && npm test

# E2E Tests
cd e2e && npm install && npm test
```

### Produktion

```bash
# Build
./gradlew :backend:bootJar
cd frontend && npm run build

# Docker
cd docker
cp .env.example .env  # Werte anpassen!
docker compose up -d
```

## Tech Stack

- **Backend:** Spring Boot 3, PostgreSQL, WebSocket
- **Frontend:** React 18, Vite, TailwindCSS, Zustand
- **Auth:** JWT + OAuth2 (Google, GitHub)
- **Testing:** JUnit 5, Vitest, Playwright
- **i18n:** DE + EN
EOF

# ============================================================
# Fertig!
# ============================================================

echo ""
echo "✅ Mono-Repo erstellt in: $(pwd)"
echo ""
echo "Nächste Schritte:"
echo "  1. cd $PROJECT_NAME"
echo "  2. Datenbank starten: cd docker && docker compose -f docker-compose.dev.yml up -d"
echo "  3. Backend starten: ./gradlew :backend:bootRun"
echo "  4. Frontend starten: cd frontend && npm install && npm run dev"
echo ""
echo "URLs:"
echo "  - Frontend: http://localhost:3000"
echo "  - Backend:  http://localhost:8080"
echo "  - Mailhog:  http://localhost:8025"
echo ""
