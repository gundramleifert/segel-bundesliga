import { useLayoutEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { Tip } from "./Tip";
import { Link, useLocation } from "react-router-dom";

import { usePageTitle } from "./breadcrumb";

/** Which nav section a path belongs to, and what to call it.
 *
 * Route-derived rather than declared per page: the first crumb is a property of *where*
 * you are, and a page that forgot to declare it would show none. Only sections that have
 * a landing page are listed — `/account` and `/legal-notice` are their own page and get
 * one crumb, which is their title.
 */
const SECTIONS: Record<string, { path: string; key: string }> = {
  series: { path: "/series", key: "series" },
  events: { path: "/events", key: "events" },
  clubs: { path: "/clubs", key: "clubs" },
  // `Admin › New event`: the create pages live under /admin and lead back to it.
  admin: { path: "/admin", key: "admin" },
};

/** Where you are, in the one place the eye already goes — Story A-12.
 *
 * `Series › 1. Segel-Bundesliga 2026`: the section from the route, the page from its own
 * `PageHeader`. On a section's landing page the two would be the same word, so only one
 * is shown.
 */
export function Breadcrumb() {
  const { t } = useTranslation();
  const { pathname } = useLocation();
  const pageTitle = usePageTitle();

  const [first, ...rest] = pathname.split("/").filter(Boolean);
  const section = first ? SECTIONS[first] : undefined;
  const onSectionLanding = Boolean(section) && rest.length === 0;

  const crumbs: { label: string; to?: string }[] = [];
  if (section) crumbs.push({ label: t(`nav.${section.key}`), to: section.path });
  if (pageTitle && !onSectionLanding) crumbs.push({ label: pageTitle });
  if (!crumbs.length) crumbs.push({ label: t("nav.start"), to: "/" });

  return (
    // `min-w-0`, or the `truncate` below can never engage: a flex child's minimum is its
    // content width, so without this the breadcrumb keeps its natural width and a long
    // page name pushes the *header* — which is outside the scrolling panel — past the
    // viewport, which is the zoom-out of Story A-10.
    <nav
      aria-label={t("breadcrumb.label")}
      data-testid="layout-breadcrumb"
      className="min-w-0"
    >
      <ol className="flex min-w-0 items-center gap-1.5 text-sm text-slate-500">
        {crumbs.map((crumb, index) => (
          <li key={`${crumb.label}-${index}`} className="flex min-w-0 items-center gap-1.5">
            {index > 0 && (
              <span aria-hidden className="text-slate-300">
                ›
              </span>
            )}
            {crumb.to && index < crumbs.length - 1 ? (
              <Link to={crumb.to} className="hover:text-slate-900 hover:underline">
                {crumb.label}
              </Link>
            ) : (
              // The last crumb is where you are — so it is not a link to itself, and it
              // is the page's `<h1>`. Since Story A-12 removed the heading block, this is
              // the only place the page states its name, and a page with no `h1` has no
              // document outline for anyone reading it with a screen reader. Small type,
              // real heading.
              <PageName label={crumb.label} />
            )}
          </li>
        ))}
      </ol>
    </nav>
  );
}

/** The page's name, with a tooltip **only when it does not fit**.
 *
 * A tooltip that repeats text the reader can already see is noise, and most page names
 * fit. Whether this one does is measured rather than guessed at from a character count:
 * it depends on the font, the language and the width of the window.
 */
function PageName({ label }: { label: string }) {
  const heading = useRef<HTMLHeadingElement>(null);
  const [clipped, setClipped] = useState(false);

  // Re-measured when the window changes, because that is the other way a name that fitted
  // stops fitting.
  useLayoutEffect(() => {
    const measure = () => {
      const el = heading.current;
      setClipped(!!el && el.scrollWidth > el.clientWidth + 1);
    };
    measure();
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, [label]);

  return (
    <Tip text={clipped ? label : null}>
      <h1
        ref={heading}
        aria-current="page"
        className="truncate text-sm font-medium text-slate-700"
      >
        {label}
      </h1>
    </Tip>
  );
}
