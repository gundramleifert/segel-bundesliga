import { apiError } from "../api/http";
import { getToken } from "../api/session";

/** Files that need the bearer token.
 *
 * A plain `<a href>` or `<img src>` never sends the Authorization header, and the files
 * that matter here — a sailor's photo when they are a minor, the waiver form with a date of
 * birth on it, the guardian's signed scan — are served only to a signed-in, connected
 * account (Stories S-1, S-2). So the bytes are fetched with the token and handed to the
 * browser as an object URL. Written once the third page needed it.
 */
export async function fetchFileUrl(url: string): Promise<string> {
  const token = getToken();
  const response = await fetch(url, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  // The same `ApiError` every generated call throws, so `errorText` translates its code.
  if (!response.ok) throw await apiError(response);
  return URL.createObjectURL(await response.blob());
}

/** Saves an authenticated file under `filename`. */
export async function downloadFile(url: string, filename: string): Promise<void> {
  const objectUrl = await fetchFileUrl(url);
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = filename;
  anchor.rel = "noopener";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  // Revoke after the click has been handled — revoking synchronously cancels the save.
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 10_000);
}

/** Opens an authenticated file in a new tab. */
export async function openFile(url: string): Promise<void> {
  const objectUrl = await fetchFileUrl(url);
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.target = "_blank";
  anchor.rel = "noopener";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 60_000);
}
