-- Datenbank für Zitadel
CREATE DATABASE zitadel;
CREATE USER zitadel WITH ENCRYPTED PASSWORD 'zitadel';
GRANT ALL PRIVILEGES ON DATABASE zitadel TO zitadel;

-- Zitadel braucht diese Rechte
\c zitadel
GRANT ALL ON SCHEMA public TO zitadel;
