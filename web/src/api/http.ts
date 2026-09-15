/** The one place a request leaves the browser.
 *
 * `orval` generates every endpoint call (see `orval.config.ts`) and routes all of them
 * through this function, so the three things that must be true of *every* request live
 * here and nowhere else: the bearer token is attached, a failure becomes an `ApiError`
 * carrying its RFC 9457 problem code, and a 204 does not get parsed as JSON.
 */
import i18n from "../i18n";
import { type ProblemDetail, describeProblem, isProblem, problemCode } from "./problems";
import { getToken } from "./session";

export class ApiError extends Error {
  // No constructor shorthand: this project builds with `erasableSyntaxOnly`.
  status: number;
  /** The RFC 9457 problem code, e.g. `waiver-already-confirmed` — null for non-typed errors. */
  code: string | null;
  /** The full problem body, for reading extension members. */
  problem: ProblemDetail | null;

  constructor(
    status: number,
    message: string,
    options: { code?: string | null; problem?: ProblemDetail | null } = {},
  ) {
    super(message);
    this.status = status;
    this.code = options.code ?? null;
    this.problem = options.problem ?? null;
  }
}

/** Turns a failed response into an {@link ApiError}.
 *
 * The backend answers with RFC 9457 `application/problem+json`: the `type` carries a
 * stable code the UI maps to a translation (see `./problems`). A non-problem body (an
 * old deployment, a proxy error page) still yields a readable message.
 */
export async function apiError(response: Response): Promise<ApiError> {
  let body: unknown;
  try {
    body = await response.json();
  } catch {
    // Response wasn't JSON — fall through to the generic message.
  }
  if (isProblem(body)) {
    return new ApiError(response.status, describeProblem(body), {
      code: problemCode(body),
      problem: body,
    });
  }
  return new ApiError(
    response.status,
    i18n.t("common:errors.requestFailed", { status: response.status }),
  );
}

/** What a generated hook's `error` is typed as.
 *
 * orval reads this name out of the mutator module and uses it for every `TError`. Without
 * it each hook would claim `HTTPValidationError` — the only failure FastAPI documents in
 * the schema — and a screen reading `error.code` would not compile even though that is
 * exactly what arrives: `http` throws {@link ApiError} and nothing else.
 */
export type ErrorType<_E> = ApiError;

/** The request-body type orval uses. Ours is the plain body, unwrapped. */
export type BodyType<Body> = Body;

export async function http<T>(url: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");

  // A FormData body must **not** carry `application/json`, and must not carry a
  // hand-written multipart type either: only the browser knows the boundary it is about
  // to use. orval sets the JSON content type for JSON bodies itself, so the job here is
  // to make sure nothing else has, not to add one.
  if (init.body instanceof FormData) headers.delete("Content-Type");

  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const response = await fetch(url, { ...init, headers });
  if (!response.ok) throw await apiError(response);

  // 204 and an empty body: `response.json()` throws on both, and several endpoints here
  // answer exactly that way (deleting a crest, deleting a photo).
  if (response.status === 204 || response.headers.get("Content-Length") === "0") {
    return undefined as T;
  }
  const text = await response.text();
  return (text ? JSON.parse(text) : undefined) as T;
}
