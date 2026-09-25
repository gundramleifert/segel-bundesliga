/** The club this browser last showed on `/club` — a per-browser convenience, nothing more.
 *
 * `?club=` is the source of truth for which club is shown; this only fills in for a bare
 * `/club` and tells the navigation's "Our club" dropdown what to preselect when the page
 * open is not a club screen. An account has no home club (Story Z-2: a person's clubs are
 * their `member`/`manager`/`admin` grants), so the choice is not the server's to keep.
 * Storage may be missing or throw (private window, blocked site data), hence the guards:
 * without it the screen simply falls back to its own default.
 */
const KEY = "sbl.lastClub";

export function readLastClub(): string | null {
  try {
    return window.localStorage.getItem(KEY);
  } catch {
    return null;
  }
}

export function writeLastClub(clubId: number): void {
  try {
    window.localStorage.setItem(KEY, String(clubId));
  } catch {
    // Not remembered, then — the URL still says which club is open.
  }
}
