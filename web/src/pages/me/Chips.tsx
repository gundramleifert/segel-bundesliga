import { useTranslation } from "react-i18next";

import type { Need } from "../../api/types";

/** What I am there, one chip each — *sailor* among them when I sail there. */
export function RelationChips({ relations, testId }: { relations: string[]; testId: string }) {
  const { t } = useTranslation("space");
  return (
    <ul className="flex flex-wrap gap-1.5" data-testid={testId}>
      {relations.map((relation) => (
        <li
          key={relation}
          data-testid={`${testId}-${relation}`}
          className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs text-slate-700 ring-1 ring-inset ring-slate-200"
        >
          {t(`relations.${relation}`, { defaultValue: relation })}
        </li>
      ))}
    </ul>
  );
}

/** What waits for me there, in words — nothing at all when nothing does. */
export function NeedsLine({ needs, testId }: { needs: Need[]; testId: string }) {
  const { t } = useTranslation("space");
  if (!needs.length) return null;
  return (
    <ul className="flex flex-col gap-1 text-sm text-amber-800" data-testid={testId}>
      {needs.map((need) => (
        <li key={need.code} data-testid={`${testId}-${need.code}`} className="flex items-baseline gap-1.5">
          <span aria-hidden className="text-amber-500">
            ●
          </span>
          {t(`needs.${need.code}`, { count: need.count })}
        </li>
      ))}
    </ul>
  );
}
