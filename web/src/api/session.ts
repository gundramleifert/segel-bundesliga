/** The access token of the running session.
 *
 * Deliberately a module, not a React context: the API client isn't part of the component
 * tree and shouldn't become one.
 */
const STORAGE_KEY = "sbl.token";

let token: string | null = localStorage.getItem(STORAGE_KEY);
const listeners = new Set<() => void>();

export function getToken(): string | null {
  return token;
}

export function setToken(next: string | null): void {
  token = next;
  if (next) localStorage.setItem(STORAGE_KEY, next);
  else localStorage.removeItem(STORAGE_KEY);
  listeners.forEach((fn) => fn());
}

export function onTokenChange(fn: () => void): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}
