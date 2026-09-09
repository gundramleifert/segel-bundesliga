import { Card, Spinner } from "@heroui/react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import type { EventSummary } from "../api/client";
import { ortText, spieltagUntertitel, statusText, zeitraum } from "../lib/format";
import { slugify } from "../lib/testids";

export function Laden({ text, testId }: { text?: string; testId?: string }) {
  const { t } = useTranslation();
  return (
    <div
      data-testid={testId ?? "loading-indicator"}
      className="flex items-center justify-center gap-3 py-16 text-slate-500"
    >
      <Spinner size="sm" />
      <span>{text ?? t("loading")}</span>
    </div>
  );
}

/** Errors are named, not hidden — an empty table says nothing. */
export function Fehler({ text, testId }: { text: string; testId?: string }) {
  return (
    <div
      role="alert"
      data-testid={testId ?? "error-message"}
      className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-red-800"
    >
      {text}
    </div>
  );
}

export function Leer({ children, testId }: { children: ReactNode; testId?: string }) {
  return (
    <p data-testid={testId ?? "empty-state"} className="py-12 text-center text-slate-500">
      {children}
    </p>
  );
}

const STATUS_STIL: Record<string, string> = {
  planned: "bg-slate-100 text-slate-700 ring-slate-200",
  live: "bg-emerald-100 text-emerald-800 ring-emerald-300",
  final: "bg-marke-100 text-marke-800 ring-marke-200",
  cancelled: "bg-red-100 text-red-800 ring-red-200",
};

export function StatusMarke({ status, testId }: { status: string; testId?: string }) {
  return (
    <span
      data-testid={testId ?? `status-badge-${status}`}
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${
        STATUS_STIL[status] ?? STATUS_STIL.planned
      }`}
    >
      {status === "live" && (
        <span className="size-1.5 animate-pulse rounded-full bg-emerald-600" aria-hidden />
      )}
      {statusText(status)}
    </span>
  );
}

/** A matchday as a clickable card.
 *
 * The home page and the events list show the same card — they should behave the same
 * way in both places, so it lives here rather than twice in the pages.
 */
export function SpieltagKarte({ event, testId }: { event: EventSummary; testId?: string }) {
  const untertitel = [spieltagUntertitel(event), ortText(event)].filter(Boolean).join(" · ");

  return (
    <Link
      to={`/events/${event.id}`}
      data-testid={testId ?? `event-card-${event.id}`}
      className="block group"
    >
      <Card className="h-full transition-shadow group-hover:shadow-md">
        <Card.Header>
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-center gap-2.5">
              {event.logo_url && (
                <img src={event.logo_url} alt="" className="size-8 shrink-0 object-contain" />
              )}
              <Card.Title>{event.title}</Card.Title>
            </div>
            <StatusMarke status={event.status} />
          </div>
          <Card.Description>{untertitel}</Card.Description>
        </Card.Header>
        <Card.Content>
          <p className="text-sm text-slate-600">
            {zeitraum(event.starts_on, event.ends_on)}
          </p>
        </Card.Content>
      </Card>
    </Link>
  );
}

/** Results tables are wide (and sometimes tall). They scroll in their own box, bounded to a
 *  sensible viewport height, never the whole page — see `.tabelle-scroll` in `index.css` for
 *  why that box needs an explicit max-height rather than just `overflow-x: auto`.
 *
 * Convention: every `<thead>` placed inside this frame must carry the `tabelle-kopf`
 * class (defined in `index.css`) so its column headers stay pinned to the top of this box
 * while a long table's body scrolls past underneath — `TabellenRahmen` only wraps arbitrary
 * table markup, so it cannot inject that class into a child `<thead>` itself. Keep each
 * header row's existing opaque background (`bg-slate-50` on the `<tr>`, in every table so
 * far) — a sticky header needs one so scrolled-past rows don't show through.
 */
export function TabellenRahmen({
  children,
  testId,
}: {
  children: ReactNode;
  testId?: string;
}) {
  return (
    <div
      data-testid={testId ?? "table-frame"}
      className="tabelle-scroll rounded-xl border border-slate-200 bg-white"
    >
      {children}
    </div>
  );
}

export function Seitenkopf({
  titel,
  unterzeile,
  rechts,
  testId,
}: {
  titel: string;
  unterzeile?: ReactNode;
  rechts?: ReactNode;
  testId?: string;
}) {
  const resolvedTestId = testId ?? `page-header-${slugify(titel)}`;
  return (
    <header
      data-testid={resolvedTestId}
      className="mb-6 flex flex-wrap items-end justify-between gap-4"
    >
      <div>
        <h1
          data-testid={`${resolvedTestId}-title`}
          className="text-2xl font-semibold tracking-tight text-slate-900 sm:text-3xl"
        >
          {titel}
        </h1>
        {unterzeile && <p className="mt-1 text-slate-600">{unterzeile}</p>}
      </div>
      {rechts}
    </header>
  );
}
