import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import type { Need } from "../../api/types";
import { needPath, refKey, type ContextRef } from "../../lib/workspace";

/** Story Z-10 (§4): what waits for me in one context, each line a link to the section
 *  that clears it — never to a page that merely explains. Worded by the page from the
 *  code (`needs.<code>`), ordered as the API sends them: by severity, then by date.
 *  Severity orders and marks; it never shouts — *now* gets the warning dot, the rest a
 *  quiet one. Clearing a to-do there makes it disappear: every such mutation invalidates
 *  `/api/me/contexts`. */
export function TodoList({ context, needs, testId }: { context: ContextRef; needs: readonly Need[]; testId: string }) {
  const { t } = useTranslation("space");
  if (!needs.length) return null;
  return (
    <ul className="flex flex-col gap-1.5" data-testid={testId}>
      {needs.map((need) => (
        <li key={`${need.code}-${need.section}`} className="flex items-baseline gap-2 text-sm">
          <span aria-hidden className={need.severity === "now" ? "text-warning" : "text-faint"}>
            ●
          </span>
          <Link
            to={needPath(context, need)}
            data-testid={`${testId}-${need.code}`}
            data-severity={need.severity}
            className="text-foreground underline-offset-2 hover:underline"
          >
            {t(`needs.${need.code}`, { count: need.count })}
          </Link>
        </li>
      ))}
    </ul>
  );
}

/** `me-todo-club-7` — the test id of a context's to-do list on the landing page. */
export function todoTestId(prefix: string, ref: ContextRef): string {
  return `${prefix}-${refKey(ref).replace(":", "-")}`;
}
