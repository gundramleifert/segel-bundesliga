import { Card } from "@heroui/react";
import {
  cloneElement,
  isValidElement,
  useId,
  useState,
  type ReactElement,
  type ReactNode,
} from "react";
import { useTranslation } from "react-i18next";

import { Fehler } from "../components/Bausteine";

/** Small pieces shared by every admin form.
 *
 * Deliberately plain form elements instead of HeroUI inputs: the forms here are a tool,
 * not a showcase page, and a plain <input> behaves more predictably in a form than a
 * component with its own state management.
 */

export function Abschnitt({
  titel,
  hinweis,
  children,
}: {
  titel: string;
  hinweis?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section>
      <h2 className="mb-1 text-lg font-semibold">{titel}</h2>
      {hinweis && <p className="mb-3 text-sm text-slate-600">{hinweis}</p>}
      <Card>
        <Card.Content className="grid gap-4 py-4">{children}</Card.Content>
      </Card>
    </section>
  );
}

export function Feld({
  label,
  hinweis,
  children,
}: {
  label: string;
  hinweis?: string;
  children: ReactNode;
}) {
  // The label is associated via htmlFor, not by wrapping the control. Wrapping a
  // <input type="date"> (or any input with a native popup) in a <label> makes every
  // click on the field bubble back to the label and re-toggle the picker — it opens
  // and instantly closes, so a date can never be picked and the form stays un-submittable.
  const id = useId();
  const control = isValidElement(children)
    ? cloneElement(children as ReactElement<{ id?: string }>, { id })
    : children;

  return (
    <div className="text-sm">
      <label htmlFor={id} className="font-medium text-slate-700">
        {label}
      </label>
      {hinweis && <span className="ml-2 text-slate-500">{hinweis}</span>}
      <div className="mt-1">{control}</div>
    </div>
  );
}

export function Meldung({
  erfolg,
  fehler,
}: {
  erfolg?: string | null;
  fehler?: string | null;
}) {
  if (fehler) return <Fehler text={fehler} />;
  if (erfolg) {
    return (
      <p
        role="status"
        className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-2 text-sm text-emerald-800"
      >
        {erfolg}
      </p>
    );
  }
  return null;
}

/** Two-pane transfer list for choosing which clubs participate.
 *
 * Left: not (yet) selected, with a filter — useful once there are more than a handful of
 * clubs to scan. Right: selected. Clicking an entry moves it across; there's no separate
 * "add"/"remove" button, the click target already says what it does.
 */
export function VereinsAuswahl({
  vereine,
  gewaehlt,
  umschalten,
  id,
}: {
  vereine: { id: number; name: string; short_name: string }[];
  gewaehlt: Set<number>;
  umschalten: (id: number) => void;
  id?: string;
}) {
  const { t } = useTranslation();
  const [filter, setFilter] = useState("");

  const term = filter.trim().toLowerCase();
  const matches = (verein: { name: string; short_name: string }) =>
    !term ||
    verein.name.toLowerCase().includes(term) ||
    verein.short_name.toLowerCase().includes(term);

  const available = vereine.filter((v) => !gewaehlt.has(v.id) && matches(v));
  const selected = vereine.filter((v) => gewaehlt.has(v.id));

  return (
    <div id={id} className="grid gap-3 sm:grid-cols-2">
      <div className="rounded-md border border-slate-200">
        <div className="border-b border-slate-200 p-2">
          <input
            type="search"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder={t("common:transferList.filterPlaceholder")}
            aria-label={t("common:transferList.filterPlaceholder")}
            className="w-full rounded border border-slate-300 px-2 py-1 text-sm outline-none focus:border-marke-500 focus:ring-1 focus:ring-marke-200"
          />
        </div>
        <p className="px-2 pt-2 text-xs font-medium uppercase tracking-wide text-slate-500">
          {t("common:transferList.available", { count: available.length })}
        </p>
        <ul className="max-h-56 overflow-y-auto p-1">
          {available.map((verein) => (
            <li key={verein.id}>
              <button
                type="button"
                onClick={() => umschalten(verein.id)}
                className="flex w-full items-center gap-2 rounded px-2 py-1 text-left text-sm hover:bg-slate-50"
              >
                <span aria-hidden className="text-slate-400">
                  +
                </span>
                <span className="flex-1 truncate">{verein.name}</span>
                <span className="text-slate-400">{verein.short_name}</span>
              </button>
            </li>
          ))}
          {!available.length && (
            <li className="px-2 py-3 text-center text-sm text-slate-400">
              {t("common:transferList.noneAvailable")}
            </li>
          )}
        </ul>
      </div>

      <div className="rounded-md border border-slate-200">
        <p className="border-b border-slate-200 px-2 py-2 text-xs font-medium uppercase tracking-wide text-slate-500">
          {t("common:transferList.selected", { count: selected.length })}
        </p>
        <ul className="max-h-56 overflow-y-auto p-1">
          {selected.map((verein) => (
            <li key={verein.id}>
              <button
                type="button"
                onClick={() => umschalten(verein.id)}
                className="flex w-full items-center gap-2 rounded px-2 py-1 text-left text-sm hover:bg-slate-50"
              >
                <span className="flex-1 truncate">{verein.name}</span>
                <span className="text-slate-400">{verein.short_name}</span>
                <span aria-hidden className="text-slate-400">
                  ×
                </span>
              </button>
            </li>
          ))}
          {!selected.length && (
            <li className="px-2 py-3 text-center text-sm text-slate-400">
              {t("common:transferList.noneSelected")}
            </li>
          )}
        </ul>
      </div>
    </div>
  );
}
