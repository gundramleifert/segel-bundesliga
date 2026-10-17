import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { useAccount } from "../api/useApi";
import { anchorPath } from "../handbook";
import { Tip } from "./Tip";

/** The "?" beside a heading that opens the help on exactly that thing (Story B-18).
 *
 * Takes a handbook **anchor** — `roles-matrix`, `squad-and-lineup-size` — never a path:
 * which page owns an anchor is the store's business (`web/src/handbook/index.ts`), and
 * the anchors are the part of the help that is promised to stay (the structure lock in
 * `check-docs.py`). An anchor no page has renders nothing, rather than a "?" that lands on
 * an empty page. A guest sees nothing either: the help is for signed-in accounts, and a
 * public screen has to explain itself.
 */
export function HelpLink({ anchor, label }: { anchor: string; label?: string }) {
  const { t } = useTranslation("help");
  const { account } = useAccount();
  const to = anchorPath(anchor);
  if (!to || !account) return null;
  const text = label ?? t("helpLink");

  return (
    <Tip text={text}>
      <Link
        to={to}
        aria-label={text}
        data-testid={`help-link-${anchor}`}
        className="inline-grid size-5 shrink-0 place-items-center rounded-full bg-slate-100 align-middle text-xs font-semibold text-slate-500 hover:bg-brand-50 hover:text-brand-700"
      >
        ?
      </Link>
    </Tip>
  );
}
