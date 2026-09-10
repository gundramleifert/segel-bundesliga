/** Display helpers. Locale-aware: they read the active i18next language at call time
 *  rather than baking one locale in, so a language switch updates dates, numbers and
 *  translated labels together with the rest of the page. */
import i18n from "../i18n";

function dateFormatter(options: Intl.DateTimeFormatOptions): Intl.DateTimeFormat {
  return new Intl.DateTimeFormat(i18n.language, options);
}

export function formatDate(iso: string): string {
  return dateFormatter({ day: "2-digit", month: "long", year: "numeric" }).format(
    new Date(iso),
  );
}

/** "12.–14. Juni 2026" / "June 12 – 14, 2026" — a matchday can span several days.
 *
 *  `formatRange` does the work: it prints only the parts the two dates *don't* share and
 *  collapses the rest, per locale. Gluing two separately formatted dates together instead
 *  produced "12.06.–14. Juni 2026" — a numeric month on one side and a written-out one on
 *  the other, plus the month and year repeated when both dates fall in the same month. */
export function dateRange(from: string, to: string): string {
  if (from === to) return formatDate(from);
  return dateFormatter({ day: "2-digit", month: "long", year: "numeric" }).formatRange(
    new Date(from),
    new Date(to),
  );
}

/** The date line of an event, which may not have one yet.
 *
 *  Since Story VA-8 an event is savable before its date is agreed with the host, so
 *  `starts_on` and `ends_on` are nullable. Passing a null straight into `dateRange` would
 *  print "Invalid Date" on the calendar; every screen that shows an event's date goes
 *  through here instead. A start with no end is a single day, which is how the backend
 *  treats it too. */
export function eventDates(event: {
  starts_on?: string | null;
  ends_on?: string | null;
}): string {
  if (!event.starts_on) return i18n.t("common:dateOpen");
  return dateRange(event.starts_on, event.ends_on ?? event.starts_on);
}

export function formatPoints(value: number): string {
  return value.toLocaleString(i18n.language, { maximumFractionDigits: 1 });
}

/** The boat colours from the pairing list as displayable colour values. Hex codes are
 *  locale-independent; only the name is translated. */
export const BOAT_COLORS: Record<string, { hex: string }> = {
  BLACK: { hex: "#1f2937" },
  GREEN: { hex: "#16a34a" },
  DARKBLUE: { hex: "#1e3a8a" },
  RED: { hex: "#dc2626" },
  GRAY: { hex: "#9ca3af" },
  ORANGE: { hex: "#f97316" },
  WHITE: { hex: "#ffffff" },
};

export function boatColor(color: string | null | undefined): { hex: string; name: string } {
  const entry = color ? BOAT_COLORS[color] : undefined;
  return {
    hex: entry?.hex ?? "#cbd5e1",
    name: color ? i18n.t(`common:boatColor.${color}`, { defaultValue: color }) : "—",
  };
}

export function statusText(status: string): string {
  return i18n.t(`common:status.${status}`, { defaultValue: status });
}

/** Where a matchday takes place.
 *
 * At creation time, often only the host club is known and the venue isn't yet — then we
 * name the club instead of leaving a gap, and say so plainly if both are missing.
 */
export function locationText(event: {
  venue?: { name: string; water?: string | null } | null;
  host_club?: { name: string } | null;
}): string {
  if (event.venue) {
    return event.venue.water ? `${event.venue.name} · ${event.venue.water}` : event.venue.name;
  }
  if (event.host_club) return i18n.t("common:hostedBy", { name: event.host_club.name });
  return i18n.t("common:venueUnknown");
}

/** How an event is subtitled.
 *
 * The act number belongs to the event, not the series — and a standalone event has none.
 * The series name already carries the year ("1st Sailing Bundesliga 2026").
 */
export function matchdaySubtitle(event: {
  matchday?: number | null;
  series?: { name: string } | null;
}): string | null {
  const parts = [
    event.matchday ? i18n.t("common:actNumber", { number: event.matchday }) : null,
    event.series?.name ?? null,
  ].filter(Boolean);
  return parts.length ? parts.join(" · ") : null;
}

export function roleText(value: string): string {
  return i18n.t(`common:crewRole.${value}`, { defaultValue: value });
}
