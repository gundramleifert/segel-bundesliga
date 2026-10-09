import { Link, useParams } from "react-router-dom";

import { PHOTOS, VIDEOS } from "./data";
import { Img, Switcher } from "./kit";
import { OPTIONS, wireHref } from "./nav";
import { Option1 } from "./Option1";
import { Option2 } from "./Option2";
import { Option3 } from "./Option3";
import { Option4 } from "./Option4";
import { Option5 } from "./Option5";
import { Option6 } from "./Option6";
import { Option7 } from "./Option7";
import { Option8 } from "./Option8";
import { Option9 } from "./Option9";
import { Option10 } from "./Option10";
import { Option11 } from "./Option11";

const PAGES = { 1: Option1, 2: Option2, 3: Option3, 4: Option4, 5: Option5, 6: Option6, 7: Option7, 8: Option8, 9: Option9, 10: Option10, 11: Option11 } as const;
const PREVIEW = [PHOTOS.alster, PHOTOS.helga2022, PHOTOS.helgaBahn, PHOTOS.stMoritz, PHOTOS.helgaNrv, PHOTOS.kiel4, PHOTOS.kiel10, PHOTOS.kiel7, PHOTOS.helgaBahn, PHOTOS.kiel12, PHOTOS.eckernfoerde];

/** Five homepage options to compare in the browser (issue #13). Outside the site's
 *  `Layout` on purpose: the header is what is being compared. Throwaway — the chosen
 *  option becomes a story and is rebuilt on real data; then this folder goes. */
export function WireframeOption() {
  const { option } = useParams();
  const Page = PAGES[Number(option) as keyof typeof PAGES];
  if (!Page) return <WireframeIndex />;
  return (
    <div className="pb-20">
      <Page />
      <Switcher />
    </div>
  );
}

export function WireframeIndex() {
  return (
    <main className="min-h-dvh bg-page px-4 py-10 text-ink">
      <div className="mx-auto max-w-5xl">
        <h1 className="text-3xl font-extrabold tracking-tight">Homepage wireframes</h1>
        <p className="mt-2 max-w-3xl text-slate-600">
          Eleven options for the new site structure: a thin bar at the very top switches between the leagues — DSBL (1. and 2. Liga on one page), Junioren-Liga, DSL-Pokal —
          every league is one page with its own URL, the logo leads home, and the personal area sits top right. Each option has the
          homepage and a league page — click a league in the top bar. Content is invented; photos and videos are freely
          licensed from Wikimedia Commons.
        </p>

        <ul className="mt-8 grid grid-cols-[minmax(0,1fr)] gap-5 sm:grid-cols-2">
          {OPTIONS.map((o, i) => (
            <li key={o.n}>
              <Link to={wireHref(o.n)} data-testid={`wf-option-${o.n}`} className="group block overflow-hidden rounded-2xl bg-white shadow-sm ring-1 ring-slate-200 hover:shadow-md">
                <div className="aspect-[16/7] overflow-hidden"><Img photo={PREVIEW[i]} className="transition group-hover:scale-105" /></div>
                <div className="p-5">
                  <p className="text-xs font-semibold uppercase tracking-wide text-brand-600">Option {o.n} · after {o.inspiredBy}</p>
                  <h2 className="mt-1 text-xl font-bold">{o.name}</h2>
                  <p className="mt-1 text-sm text-slate-600">{o.summary}</p>
                  <p className="mt-3 text-sm font-semibold text-brand-700">
                    Home → · <span className="font-normal">league page: {wireHref(o.n, "dsbl")}</span>
                  </p>
                </div>
              </Link>
            </li>
          ))}
        </ul>

        <section id="credits" className="mt-12 break-all text-xs text-slate-500">
          <h2 className="mb-2 text-sm font-semibold text-slate-700">Credits</h2>
          <ul className="space-y-1">
            {[...Object.values(PHOTOS), ...VIDEOS].map((m) => (
              <li key={m.page}>
                <a href={m.page} target="_blank" rel="noopener noreferrer" className="underline">
                  {decodeURIComponent(m.page.split("File:")[1])}
                </a>{" "}
                — {m.credit}, {m.license}, via Wikimedia Commons
              </li>
            ))}
          </ul>
        </section>
      </div>
    </main>
  );
}
