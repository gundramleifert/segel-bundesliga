import { Spinner } from "@heroui/react";
import { useEffect, type ReactNode } from "react";
import { useTranslation } from "react-i18next";

import type { EventSummary } from "../api/types";
import { locationText, matchdaySubtitle, statusText, eventDates } from "../lib/format";
import { setPageTitle } from "./breadcrumb";
import { LinkCard } from "./LinkCard";
import { slugify } from "../lib/testids";

export function Loading({ text, testId }: { text?: string; testId?: string }) {
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
export function ErrorMessage({ text, testId }: { text: string; testId?: string }) {
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

export function Empty({ children, testId }: { children: ReactNode; testId?: string }) {
  return (
    <p data-testid={testId ?? "empty-state"} className="py-12 text-center text-slate-500">
      {children}
    </p>
  );
}

const STATUS_STYLE: Record<string, string> = {
  planned: "bg-slate-100 text-slate-700 ring-slate-200",
  live: "bg-emerald-100 text-emerald-800 ring-emerald-300",
  final: "bg-brand-100 text-brand-800 ring-brand-200",
  cancelled: "bg-red-100 text-red-800 ring-red-200",
};

export function StatusBadge({ status, testId }: { status: string; testId?: string }) {
  return (
    <span
      data-testid={testId ?? `status-badge-${status}`}
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${
        STATUS_STYLE[status] ?? STATUS_STYLE.planned
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
export function MatchdayCard({ event, testId }: { event: EventSummary; testId?: string }) {
  const subtitle = [matchdaySubtitle(event), locationText(event)].filter(Boolean).join(" · ");

  return (
    <LinkCard
      to={`/events/${event.id}`}
      testId={testId ?? `event-card-${event.id}`}
      title={event.title}
      description={subtitle}
      lead={
        event.logo_url ? (
          <img src={event.logo_url} alt="" className="size-8 shrink-0 object-contain" />
        ) : undefined
      }
      aside={<StatusBadge status={event.status} />}
    >
      <p className="text-sm text-slate-600">{eventDates(event)}</p>
    </LinkCard>
  );
}

/** Results tables are wide. They scroll horizontally in their own box, never the whole
 *  page — see `.table-scroll` in `index.css`. Vertical scrolling stays the page's own,
 *  single scrollbar; there is deliberately no sticky table header (see that file for why
 *  one doesn't coexist cleanly with a horizontally-scrolling box here).
 *
 *  `scrollbar-none` (the same class the navbar's own horizontal scroll area already uses)
 *  hides the native scrollbar track — a plain OS scrollbar with arrow buttons reads as
 *  clutter, especially stacked visually next to the page's own vertical one. Touch swipe,
 *  wheel, and drag-to-scroll still work; only the visible track is gone.
 */
export function TableFrame({
  children,
  testId,
}: {
  children: ReactNode;
  testId?: string;
}) {
  return (
    <div
      data-testid={testId ?? "table-frame"}
      className="table-scroll scrollbar-none rounded-xl border border-slate-200 bg-white"
    >
      {children}
    </div>
  );
}

/** A page's identity, which is now entirely the breadcrumb (Story A-12).
 *
 * There is no `<h1>` here any more and no subtitle. The title was the same words the
 * breadcrumb above it already said, twice on every page, and the subtitles were mostly a
 * restatement of what the page then showed — "18 clubs" above a list of eighteen clubs.
 * What a page still needs is somewhere to put the one control that belongs to the page as
 * a whole (a status badge, a sign-out button); that is `right`.
 *
 * `title` stays in the API, and is still required, because it is what the breadcrumb
 * renders. Removing it would mean every page declaring its name a second way.
 */
export function PageHeader({
  title,
  right,
  testId,
}: {
  title: string;
  right?: ReactNode;
  testId?: string;
}) {
  const resolvedTestId = testId ?? `page-header-${slugify(title)}`;

  // Publishes this page's name to the header's breadcrumb (Story A-12). In an effect, so
  // it runs after the render that mounted this header rather than during it; the cleanup
  // clears it, so a page without a `PageHeader` shows one crumb instead of the previous
  // page's name.
  useEffect(() => {
    setPageTitle(title);
    return () => setPageTitle(null);
  }, [title]);

  // Nothing to draw on most pages — the component is mounted for the effect above, which
  // is what puts this page's name in the breadcrumb. So do not leave an empty element
  // behind: a `data-testid` on a box with no content is exactly the sort of thing a test
  // ends up waiting for, and it would say nothing about whether the page has its data.
  if (!right) return null;

  return (
    <header
      data-testid={resolvedTestId}
      className="mb-4 flex flex-wrap items-center justify-end gap-3"
    >
      {right}
    </header>
  );
}
