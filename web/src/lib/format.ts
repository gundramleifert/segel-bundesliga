/** Display helpers. Locale-aware: they read the active i18next language at call time
 *  rather than baking one locale in, so a language switch updates dates, numbers and
 *  translated labels together with the rest of the page. */
import i18n from "../i18n";

function dateFormatter(options: Intl.DateTimeFormatOptions): Intl.DateTimeFormat {
  return new Intl.DateTimeFormat(i18n.language, options);
}

export function datum(iso: string): string {
  return dateFormatter({ day: "2-digit", month: "long", year: "numeric" }).format(
    new Date(iso),
  );
}

/** "May 8–10, 2026" — a matchday can span several days. */
export function zeitraum(von: string, bis: string): string {
  if (von === bis) return datum(von);
  const kurz = dateFormatter({ day: "2-digit", month: "2-digit" });
  return `${kurz.format(new Date(von))}–${datum(bis)}`;
}

export function punkte(wert: number): string {
  return wert.toLocaleString(i18n.language, { maximumFractionDigits: 1 });
}

/** The boat colours from the pairing list as displayable colour values. Hex codes are
 *  locale-independent; only the name is translated. */
export const BOOTSFARBEN: Record<string, { hex: string }> = {
  BLACK: { hex: "#1f2937" },
  GREEN: { hex: "#16a34a" },
  DARKBLUE: { hex: "#1e3a8a" },
  RED: { hex: "#dc2626" },
  GRAY: { hex: "#9ca3af" },
  ORANGE: { hex: "#f97316" },
  WHITE: { hex: "#ffffff" },
};

export function bootsfarbe(farbe: string | null | undefined): { hex: string; name: string } {
  const eintrag = farbe ? BOOTSFARBEN[farbe] : undefined;
  return {
    hex: eintrag?.hex ?? "#cbd5e1",
    name: farbe ? i18n.t(`common:boatColor.${farbe}`, { defaultValue: farbe }) : "—",
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
export function ortText(event: {
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
export function spieltagUntertitel(event: {
  matchday?: number | null;
  series?: { name: string } | null;
}): string | null {
  const teile = [
    event.matchday ? i18n.t("common:actNumber", { number: event.matchday }) : null,
    event.series?.name ?? null,
  ].filter(Boolean);
  return teile.length ? teile.join(" · ") : null;
}

export function rolle(wert: string): string {
  return i18n.t(`common:crewRole.${wert}`, { defaultValue: wert });
}
