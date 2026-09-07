/** RFC 9457 *Problem Details* — turning a typed API error into a translated message.
 *
 * The backend never sends a localized sentence as the contract. It sends a stable
 * `type` like `/errors/guardian-confirmation-needed`; this module maps the last segment
 * (the "code") to a key in the `errors` i18n namespace. Extension members on the body
 * (`required_version`, `sailor_id`, …) are passed to the translation as interpolation
 * values, so `errors.json` can write `"{{required_version}}"`.
 *
 * See `docs/concepts.md` → "Errors".
 */
import i18n from "../i18n";

export interface ProblemDetail {
  type: string;
  title: string;
  status: number;
  detail?: unknown;
  instance?: string;
  [member: string]: unknown;
}

/** True when a parsed response body is an RFC 9457 problem. */
export function isProblem(body: unknown): body is ProblemDetail {
  return (
    typeof body === "object" &&
    body !== null &&
    typeof (body as ProblemDetail).type === "string" &&
    typeof (body as ProblemDetail).status === "number"
  );
}

/** `/errors/waiver-already-confirmed` → `waiver-already-confirmed`. */
export function problemCode(problem: ProblemDetail): string | null {
  const match = /\/errors\/([a-z0-9-]+)$/.exec(problem.type);
  return match ? match[1] : null;
}

const RESERVED = new Set(["type", "title", "status", "detail", "instance"]);

/** The message to show a user for a problem: the translation for its code, or a fallback. */
export function describeProblem(problem: ProblemDetail): string {
  const code = problemCode(problem);
  const values: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(problem)) {
    if (!RESERVED.has(key)) values[key] = value;
  }
  // A per-field validation list arrives under `detail` as an array — summarise it.
  const validationDetail = Array.isArray(problem.detail)
    ? problem.detail
        .map((entry: { loc?: unknown[]; msg?: string }) => {
          const field = Array.isArray(entry.loc) ? entry.loc.slice(1).join(".") : "";
          return field ? `${field}: ${entry.msg}` : entry.msg;
        })
        .join(" · ")
    : undefined;

  const fallback =
    validationDetail ??
    (typeof problem.detail === "string" ? problem.detail : undefined) ??
    problem.title ??
    i18n.t("errors:unknown");

  if (!code) return fallback;
  // A known code wins; an unknown one falls back to the server's English title.
  return i18n.t(`errors:${code}`, { ...values, defaultValue: fallback });
}
