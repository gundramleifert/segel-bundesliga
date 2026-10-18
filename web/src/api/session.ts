/** The access token of the running session.
 *
 * Deliberately a module, not a React context: the API client isn't part of the component
 * tree and shouldn't become one.
 */
const STORAGE_KEY = "sbl.token";

// Storage can be blocked (private window, site data disabled): then nobody is signed in
// on load, and a sign-in holds until reload rather than taking the whole app down.
let token: string | null = (() => {
  try {
    return localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
})();
const listeners = new Set<() => void>();

export function getToken(): string | null {
  return token;
}

export function setToken(next: string | null): void {
  token = next;
  try {
    if (next) localStorage.setItem(STORAGE_KEY, next);
    else localStorage.removeItem(STORAGE_KEY);
  } catch {
    // Not remembered; holds until reload.
  }
  listeners.forEach((fn) => fn());
}

export function onTokenChange(fn: () => void): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}
