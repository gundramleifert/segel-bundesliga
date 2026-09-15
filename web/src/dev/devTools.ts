/** Whether the development tools — the role switcher — are part of this build.
 *
 * True in the Vite dev server, and in a build that was told to include them:
 * `VITE_DEV_TOOLS=true`, which `vite.config.ts` sets itself when Render builds the public
 * **test** instance (the service named `sbl-web`), whose backend runs with
 * `SBL_DEV_LOGIN=true` anyway. It stays false in any build that does not ask for it, which
 * is what keeps a real deployment free of a panel that signs anyone in as an administrator.
 *
 * It exists as one constant because **two** places depend on it and must never disagree:
 * the switcher itself, and the clearance at the foot of the page that keeps its fixed
 * panel off whatever is down there. They were once gated on different conditions, and the
 * switcher ended up sitting on top of the legal links that § 5 DDG requires to be
 * reachable — a bug you cannot see in a dev build, because there the two agreed.
 */
export const DEV_TOOLS =
  import.meta.env.DEV || import.meta.env.VITE_DEV_TOOLS === "true";
