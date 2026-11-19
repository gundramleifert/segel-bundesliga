/** What `/environment.js` (index.html) says about this installation, set when its web
 *  container starts — not built in: production runs the very images staging ran
 *  (docs/deploy-server.md). Empty in development. */
const from = window as Window & { sblEnvironment?: string; sblVersion?: string; sblCommit?: string };

/** The installation's name — `SBL_ENVIRONMENT`, e.g. "staging"; empty in production. */
export const environment: string = from.sblEnvironment?.trim() ?? "";

/** The release it runs — the tag without its "v" ("0.1.0", "0.1.0-rc.6") — and its commit,
 *  short; both empty where no deploy wrote them. */
export const version: string = from.sblVersion?.trim().replace(/^v/, "") ?? "";
export const commit: string = from.sblCommit?.trim().slice(0, 7) ?? "";
