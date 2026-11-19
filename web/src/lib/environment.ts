/** The installation's name — `SBL_ENVIRONMENT` of the web container, e.g. "staging"; empty
 *  in production and development. Read at runtime from `/environment.js` (index.html), not
 *  built in: production runs the very images staging ran (docs/deploy-server.md). */
export const environment: string =
  (window as Window & { sblEnvironment?: string }).sblEnvironment?.trim() ?? "";
