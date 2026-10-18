import type { ReactNode } from "react";

import type { ReadinessReason } from "../../../api/types";
import i18n from "../../../i18n";

/** One readiness reason as a sentence.
 *
 * The backend sends a code plus the numbers involved and deliberately no English text, so
 * the wording lives in the `errors` namespace — the same key the matching API error uses.
 * A code this build doesn't know yet still reads as something rather than vanishing.
 */
function reasonText(reason: ReadinessReason): string {
  return i18n.t(`errors:${reason.code}`, {
    ...reason.details,
    defaultValue: reason.code,
  });
}

/** What still keeps an event from its draw and its start (Story VA-8) — the list of reasons
 *  `GET …/readiness` answers with, the same ones the draw and the start refuse with, so the
 *  screen can never promise what the server then rejects (`app/services/event_readiness.py`).
 *
 *  Three screens show it — the wizard's draw step, its closing screen, and the manage
 *  panel — which is why it is one piece. Render the reasons, never branch on one code: a
 *  refusal carries a single reason's code *or* `event-not-ready` with all of them
 *  (docs/gotchas). `children` are further items of the same list (the closing screen's
 *  "no pairing list yet"). */
export function ReadinessReasons({
  reasons,
  testId,
  reasonTestId,
  className = "",
  children,
}: {
  reasons: ReadinessReason[];
  testId: string;
  /** Each item is `${reasonTestId}-${code}`. */
  reasonTestId: string;
  className?: string;
  children?: ReactNode;
}) {
  return (
    <ul data-testid={testId} className={`mt-1 grid grid-cols-[minmax(0,1fr)] gap-1 ${className}`}>
      {reasons.map((reason) => (
        <li key={reason.code} data-testid={`${reasonTestId}-${reason.code}`}>
          · {reasonText(reason)}
        </li>
      ))}
      {children}
    </ul>
  );
}
