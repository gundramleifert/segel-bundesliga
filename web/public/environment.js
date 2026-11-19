// Which installation this is: replaced at runtime by the web container's Caddy with
// SBL_ENVIRONMENT (deploy/compose/Caddyfile), so one image serves staging and production.
// Empty here, in development and wherever nothing replaces it: no marker.
window.sblEnvironment = "";
