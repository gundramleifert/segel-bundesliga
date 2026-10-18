import { Spinner } from "@heroui/react";
import { useEffect, type HTMLAttributes, type ReactNode } from "react";
import { useTranslation } from "react-i18next";

import type { EventSummary } from "../api/types";
import { POLL_MILLIS, type LiveState } from "../api/useLive";
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

/** What a badge's colour says. Named by meaning, not by colour, so a status map reads as
 *  a decision ("cancelled is danger") rather than as a palette. */
export type BadgeTone = "neutral" | "muted" | "success" | "warning" | "caution" | "danger" | "brand";

const TONE_STYLE: Record<BadgeTone, string> = {
  neutral: "bg-slate-100 text-slate-700 ring-slate-200",
  muted: "bg-slate-100 text-slate-500 ring-slate-200",
  success: "bg-emerald-100 text-emerald-800 ring-emerald-300",
  warning: "bg-amber-100 text-amber-800 ring-amber-300",
  caution: "bg-orange-100 text-orange-800 ring-orange-300",
  danger: "bg-red-100 text-red-800 ring-red-200",
  brand: "bg-brand-100 text-brand-800 ring-brand-200",
};

/** A small rounded label — a status, a role, a warning — in one of a few tones.
 *
 *     <Badge tone="danger" testId="doc-expired">{t("documents.expired")}</Badge>
 *
 * `pulse` adds the green dot that says "happening now". Any other attribute (`role`,
 * `data-state`, …) is passed through to the `<span>`. */
export function Badge({
  tone = "neutral",
  pulse = false,
  testId,
  children,
  ...rest
}: {
  tone?: BadgeTone;
  pulse?: boolean;
  testId?: string;
  children: ReactNode;
} & Omit<HTMLAttributes<HTMLSpanElement>, "className" | "children">) {
  return (
    <span
      {...rest}
      data-testid={testId}
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${TONE_STYLE[tone]}`}
    >
      {pulse && <span className="size-1.5 animate-pulse rounded-full bg-emerald-600" aria-hidden />}
      {children}
    </span>
  );
}

const STATUS_TONE: Record<string, BadgeTone> = {
  planned: "neutral",
  live: "success",
  final: "brand",
  cancelled: "danger",
};

export function StatusBadge({ status, testId }: { status: string; testId?: string }) {
  return (
    <Badge
      tone={STATUS_TONE[status] ?? "neutral"}
      pulse={status === "live"}
      testId={testId ?? `status-badge-${status}`}
    >
      {statusText(status)}
    </Badge>
  );
}

const LIVE_TONE: Record<LiveState, BadgeTone> = {
  live: "success",
  reconnecting: "warning",
  off: "muted",
};

/** What `useLive` reports, as a badge (Story B-5).
 *
 * The rule it renders: a lost connection is a badge, never an empty page. The table stays
 * on screen while the stream reconnects, and if it falls back to polling the badge says
 * how often — a reader must never take a stale table for a current one, and must never
 * lose the one they had. `data-state` carries the state for the tests.
 */
export function LiveBadge({ state, testId }: { state: LiveState; testId?: string }) {
  const { t } = useTranslation();
  return (
    <Badge
      tone={LIVE_TONE[state]}
      pulse={state === "live"}
      testId={testId ?? "live-badge"}
      data-state={state}
      role="status"
    >
      {t(`live.${state}`, { seconds: POLL_MILLIS / 1000 })}
    </Badge>
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
 *  page — the content panel scrolls instead (`.panel-scroll` in `index.css`), so a page
 *  with two wide tables has one horizontal scrollbar rather than two. Vertical scrolling
 *  stays the page's own,
 *  single scrollbar; there is deliberately no sticky table header (see that file for why
 *  one doesn't coexist cleanly with a horizontally-scrolling box here).
 *
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
      // Deliberately unstyled. The white surface and the rounded outline are on the
      // **table** (`.data-table` in `index.css`), because this box is sized by the
      // scrolling panel and a wider table would run off the end of it — which is exactly
      // the grey band this used to draw. See that rule for why content-sizing this box
      // instead does not work.
      className=""
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
