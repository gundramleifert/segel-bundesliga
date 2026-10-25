import { keepPreviousData } from "@tanstack/react-query";
import { useEffect, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Link, Navigate, useNavigate } from "react-router-dom";

import { useListAllClubs, useListAllEvents, useListAllSeries, useListSailors } from "../../api/generated/sbl";
import { Relation, type Need } from "../../api/types";
import { setPageCrumbs, type Crumb } from "../../components/breadcrumb";
import { INPUT_CLASS } from "../../lib/admin";
import { useDisclosure } from "../../lib/useDisclosure";
import { useMediaQuery } from "../../lib/useMediaQuery";
import {
  readRecent,
  refKey,
  rememberRecent,
  rememberVisit,
  searchWorkspace,
  sectionPath,
  showsSearch,
  sidebar,
  switcherEntries,
  type ContextRef,
  type WorkspaceKind,
  type SidebarGroup,
  type SwitcherEntry,
} from "../../lib/workspace";
import { RelationChips } from "./Chips";
import { useMySpace } from "./shared";

/** Story Z-10: the frame of every page in My space — the context switcher, the section
 *  sidebar of the one context I am in, and the breadcrumb joining them (issue #31).
 *
 * **Laptop first**: from 1100 px the sidebar stands left (248 px), the switcher at its top
 * naming the context. Narrower — a tablet, a phone — one bar of two buttons above the
 * content, *context ▾* and *section ▾*, each opening its list: two taps to any section,
 * and the bar says where I am. (The plan's icon-only rail for 768–1100 px waits for an
 * icon set; until then those widths get the bar.) Only one of the two is in the DOM
 * (`useMediaQuery`), so a test id is never on two elements.
 *
 * **What the sidebar lists is `lib/workspace.ts`'s answer**, limited to the sections this
 * screen has built (`only`) — never a role. A section that needs me carries its count.
 */

/** One section of a context page: its key (from `lib/workspace.ts`), its words, the to-do
 *  codes it is where to act on, and its panel. A `notice` is no section: it stands above
 *  every section, and only while one of its `needs` is there (an unsigned waiver, S-1). */
export type WorkspaceSection = {
  key: string;
  label: string;
  needs?: string[];
  notice?: boolean;
  render: () => ReactNode;
};

const WIDE = "(min-width: 1100px)";

export function WorkspaceFrame({
  current,
  name,
  shortName,
  relations,
  needs,
  sections,
  active,
  started,
}: {
  current: ContextRef;
  name: string;
  /** What the breadcrumb calls it — `ASVW` rather than the club's full name, which a
   *  phone's header has no room for. */
  shortName?: string | null;
  relations: readonly string[];
  needs: readonly Need[];
  sections: WorkspaceSection[];
  /** The section in the URL; none — the overview. */
  active?: string;
  /** An event that has started puts *Race day* first (VA-8). */
  started?: boolean;
}) {
  const { t } = useTranslation("space");
  const wide = useMediaQuery(WIDE);
  const kind = current.kind;
  const panels = sections.filter((s) => !s.notice);
  const groups = sidebar(kind, relations, { only: panels.map((s) => s.key), started });
  const key = active ?? "overview";
  const section = groups.some((g) => g.sections.includes(key)) ? panels.find((s) => s.key === key) : undefined;
  const group = groups.find((g) => g.sections.includes(key));
  const notices = sections.filter((s) => s.notice && needs.some((n) => s.needs?.includes(n.code)));
  // Each to-do names the section that clears it (#33): that section carries its count.
  const count = (k: string) => needs.filter((n) => n.section === k).reduce((sum, n) => sum + n.count, 0);

  const label = (k: string) => (k === "overview" ? t("workspace.overview") : (panels.find((s) => s.key === k)?.label ?? k));
  const crumbs: Crumb[] = [{ label: shortName || name, to: sectionPath(current) }];
  if (key !== "overview") {
    if (group?.heading && group.key) crumbs.push({ label: t(`workspace.groups.${group.key}`) });
    crumbs.push({ label: label(key) });
  }
  const trail = JSON.stringify(crumbs);
  useEffect(() => {
    setPageCrumbs(JSON.parse(trail) as Crumb[]);
    return () => setPageCrumbs(null);
  }, [trail]);

  // Primitives, not `current`: that is a new object on every render.
  const id = "id" in current ? current.id : null;
  const recentName = shortName || name;
  useEffect(() => {
    if (id !== null && (kind === "club" || kind === "series" || kind === "event")) rememberRecent({ kind, id }, undefined, recentName);
  }, [kind, id, recentName]);
  // *Last visited* on the landing page: the sections, not the overviews (§4).
  const visitLabel = section && key !== "overview" ? label(key) : null;
  const visitName = shortName || name;
  useEffect(() => {
    if (!visitLabel) return;
    const ref: ContextRef = id === null ? { kind: kind as "me" | "office" } : { kind: kind as "club" | "series" | "event", id };
    rememberVisit({ ref, section: key, name: visitName, label: visitLabel });
  }, [kind, id, key, visitLabel, visitName]);

  // A section I do not have, or one this screen has not built: its context's overview,
  // rather than an empty page or a panel I may not use.
  if (!section) return <Navigate to={sectionPath(current)} replace />;

  const nav = (
    <SectionList
      kind={kind}
      groups={groups}
      active={key}
      label={label}
      count={count}
      to={(k) => sectionPath(current, k)}
    />
  );

  return (
    <div
      data-testid={`workspace-${kind}`}
      className={wide ? "grid grid-cols-[248px_minmax(0,1fr)] items-start gap-8" : "grid grid-cols-[minmax(0,1fr)] gap-5"}
    >
      {wide ? (
        <aside className="flex flex-col gap-4" data-testid="workspace-sidebar">
          <Switcher current={current} name={name} />
          {nav}
        </aside>
      ) : (
        <div className="grid grid-cols-2 gap-2" data-testid="workspace-bar">
          <Switcher current={current} name={name} />
          <SectionsButton label={label(key)}>{nav}</SectionsButton>
        </div>
      )}
      <div className="flex min-w-0 flex-col gap-5" data-testid={`workspace-content-${kind}-${key}`}>
        {notices.map((s) => (
          <section
            key={s.key}
            aria-label={s.label}
            className="rounded-xl border-2 border-warning/50 bg-warning-soft p-1"
            data-testid={`me-context-${s.key}-notice`}
          >
            {s.render()}
          </section>
        ))}
        {section.render()}
      </div>
    </div>
  );
}

/** The sections of one context, in groups; a group of one has no heading (§1, rule 5). */
function SectionList({
  kind,
  groups,
  active,
  label,
  count,
  to,
}: {
  kind: string;
  groups: SidebarGroup[];
  active: string;
  label: (key: string) => string;
  count: (key: string) => number;
  to: (key: string) => string;
}) {
  const { t } = useTranslation("space");
  return (
    <nav aria-label={t("workspace.sections")} data-testid="workspace-sections">
      <ul className="flex flex-col gap-3">
        {groups.map((g) => (
          <li key={g.key ?? "head"} className="flex flex-col gap-0.5">
            {g.heading && g.key && (
              <span className="px-3 pb-1 text-xs font-semibold uppercase tracking-wide text-muted">
                {t(`workspace.groups.${g.key}`)}
              </span>
            )}
            <ul className="flex flex-col gap-0.5">
              {g.sections.map((s) => {
                const n = count(s);
                const here = s === active;
                return (
                  <li key={s}>
                    <Link
                      to={to(s)}
                      aria-current={here ? "page" : undefined}
                      data-testid={`workspace-section-${kind}-${s}`}
                      className={`flex items-center justify-between gap-2 rounded-md px-3 py-1.5 text-sm ${
                        here ? "bg-accent-soft font-medium text-accent-soft-foreground" : "text-foreground hover:bg-surface-tertiary"
                      }`}
                    >
                      <span className="truncate">{label(s)}</span>
                      {n > 0 && (
                        <span
                          className="rounded-full bg-warning-soft px-2 text-xs font-medium text-warning-soft-foreground"
                          data-testid={`workspace-section-${kind}-${s}-count`}
                        >
                          {n}
                        </span>
                      )}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </li>
        ))}
      </ul>
    </nav>
  );
}

/** On a narrow screen: the section I am in, opening the list of the others. */
function SectionsButton({ label, children }: { label: string; children: ReactNode }) {
  const { t } = useTranslation("space");
  const menu = useDisclosure("workspace-sections-panel");
  return (
    <div className="relative min-w-0">
      <button
        type="button"
        {...menu.triggerProps}
        aria-label={`${t("workspace.sections")}: ${label}`}
        data-testid="workspace-sections-button"
        className={TRIGGER}
      >
        <span className="truncate">{label}</span>
        <span aria-hidden>▾</span>
      </button>
      {menu.open && (
        <div {...menu.panelProps} className={`${PANEL} right-0`} data-testid="workspace-sections-panel">
          {children}
        </div>
      )}
    </div>
  );
}

const TRIGGER =
  "flex w-full min-w-0 items-center justify-between gap-2 rounded-lg bg-surface px-3 py-2 text-left text-sm font-medium text-foreground ring-1 ring-border hover:bg-surface-tertiary";
const PANEL = "absolute z-50 mt-2 max-h-[70vh] w-[min(20rem,calc(100vw-2rem))] overflow-y-auto rounded-xl bg-overlay p-2 shadow-xl ring-1 ring-foreground/5";

/** The context switcher (§2): *Me*, the league office with a site relation, then mine —
 *  clubs, series, events (the next first, past folded) — and what this browser opened
 *  from inside another, under Recent. Each with my relations and its waiting count. */
function Switcher({ current, name }: { current: ContextRef; name: string }) {
  const { t } = useTranslation("space");
  const { space } = useMySpace();
  const menu = useDisclosure("workspace-switcher-panel");
  const [showPast, setShowPast] = useState(false);
  const data = space.data;
  // The league office with a site relation only — the model's `office`, never a summary
  // role: `race_officer` as a role means "on something", not "the site's" (#32).
  const site = data?.office?.relations ?? [];
  const switcher = data
    ? switcherEntries({ contexts: data.contexts, site, meWaiting: data.me.needs.reduce((s, n) => s + n.count, 0), recent: readRecent(), today: today() })
    : null;
  const here = refKey(current);

  const entry = (e: SwitcherEntry) => {
    const k = refKey(e.ref);
    const title = e.context?.name ?? t(`workspace.kinds.${e.ref.kind}`);
    return (
      <li key={k}>
        <Link
          to={sectionPath(e.ref)}
          aria-current={k === here ? "page" : undefined}
          data-testid={`workspace-switcher-${k.replace(":", "-")}`}
          className={`flex flex-col gap-1 rounded-md px-3 py-2 text-sm ${k === here ? "bg-accent-soft" : "hover:bg-surface-tertiary"}`}
        >
          <span className="flex items-center justify-between gap-2">
            <span className="truncate font-medium text-foreground">{title}</span>
            {e.waiting > 0 && (
              <span className="rounded-full bg-warning-soft px-2 text-xs font-medium text-warning-soft-foreground">{e.waiting}</span>
            )}
          </span>
          {e.relations.length > 0 && <RelationChips relations={[...e.relations]} testId={`workspace-switcher-${k.replace(":", "-")}-relations`} />}
        </Link>
      </li>
    );
  };
  const group = (title: string, testId: string, entries: SwitcherEntry[]) =>
    entries.length > 0 && (
      <li className="flex flex-col gap-0.5" data-testid={testId}>
        <span className="px-3 pt-2 text-xs font-semibold uppercase tracking-wide text-muted">{title}</span>
        <ul className="flex flex-col gap-0.5">{entries.map(entry)}</ul>
      </li>
    );

  const upcoming = switcher?.events.filter((e) => !e.past) ?? [];
  const past = switcher?.events.filter((e) => e.past) ?? [];
  const kindLabel = t(`workspace.kinds.${current.kind}`);

  return (
    <div className="relative min-w-0">
      <button
        type="button"
        {...menu.triggerProps}
        aria-label={`${t("workspace.switcher")}: ${kindLabel} · ${name}`}
        data-testid="workspace-switcher"
        className={TRIGGER}
      >
        <span className="flex min-w-0 flex-col">
          <span className="text-xs font-normal text-muted">{kindLabel}</span>
          <span className="truncate">{name}</span>
        </span>
        <span aria-hidden>▾</span>
      </button>
      {menu.open && switcher && (
        <div {...menu.panelProps} className={`${PANEL} left-0`} data-testid="workspace-switcher-panel">
          <SwitcherSearch
            show={showsSearch(switcher, Boolean(data?.office))}
            entries={[...switcher.head, ...switcher.clubs, ...switcher.series, ...switcher.events]}
            office={(data?.office?.relations ?? []).includes(Relation.admin)}
          >
            <ul className="flex flex-col gap-1">
              {switcher.head.map(entry)}
              {group(t("overview.clubs"), "workspace-switcher-clubs", switcher.clubs)}
              {group(t("overview.series"), "workspace-switcher-series", switcher.series)}
              {group(t("workspace.events"), "workspace-switcher-events", upcoming)}
              {past.length > 0 && (
                <li className="flex flex-col gap-0.5">
                  <button
                    type="button"
                    onClick={() => setShowPast(!showPast)}
                    aria-expanded={showPast}
                    data-testid="workspace-switcher-earlier"
                    className="rounded-md px-3 py-1.5 text-left text-sm text-muted hover:bg-surface-tertiary"
                  >
                    {showPast ? "▾" : "▸"} {t("workspace.earlier", { count: past.length })}
                  </button>
                  {showPast && <ul className="flex flex-col gap-0.5">{past.map(entry)}</ul>}
                </li>
              )}
              {switcher.recent.length > 0 && (
                <li className="flex flex-col gap-0.5" data-testid="workspace-switcher-recent">
                  <span className="px-3 pt-2 text-xs font-semibold uppercase tracking-wide text-muted">{t("workspace.recent")}</span>
                  <ul className="flex flex-col gap-0.5">
                    {switcher.recent.map((r) => (
                      <li key={refKey(r)}>
                        <Link
                          to={sectionPath(r)}
                          className="block rounded-md px-3 py-2 text-sm text-foreground hover:bg-surface-tertiary"
                          data-testid={`workspace-switcher-recent-${refKey(r).replace(":", "-")}`}
                        >
                          {r.name ?? `${t(`workspace.kinds.${r.kind}`)} ${"id" in r ? `#${r.id}` : ""}`}
                        </Link>
                      </li>
                    ))}
                  </ul>
                </li>
              )}
            </ul>
          </SwitcherSearch>
        </div>
      )}
    </div>
  );
}

/** One line the switcher's search offers: where it leads and how it reads. */
type Hit = { id: string; to: string; label: string; detail?: string };
type HitGroup = { key: string; title: string; hits: Hit[] };

/** How long the typing has to pause before the league office's search asks the server,
 *  and how many of each kind it shows — a jump, not a list (§2). */
const SEARCH_PAUSE_MS = 250;
const SEARCH_LIMIT = 4;

/** The search at the top of the switcher (Story Z-10, #34). Empty, it shows the switcher's
 *  own list (`children`); typed into, the hits instead: my contexts and the sections of
 *  them by their words (`searchWorkspace`), and for the site's `admin` (`office`) any
 *  club, series, event and sailor from the admin lists' search. Lives inside the panel,
 *  so closing the switcher forgets the query. Arrow keys move, Enter opens; Escape is the
 *  panel's own (`useDisclosure`). */
function SwitcherSearch({
  show,
  entries,
  office,
  children,
}: {
  show: boolean;
  entries: SwitcherEntry[];
  office: boolean;
  children: ReactNode;
}) {
  const { t } = useTranslation("space");
  const navigate = useNavigate();
  const input = useRef<HTMLInputElement>(null);
  const [query, setQuery] = useState("");
  const [marked, setMarked] = useState(0);
  const [asked, setAsked] = useState("");

  useEffect(() => {
    if (show) input.current?.focus();
  }, [show]);
  useEffect(() => {
    const timer = window.setTimeout(() => setAsked(query.trim()), SEARCH_PAUSE_MS);
    return () => window.clearTimeout(timer);
  }, [query]);

  const remote = office && asked.length > 0;
  const page = { q: asked, limit: SEARCH_LIMIT };
  const options = { query: { enabled: remote, placeholderData: keepPreviousData } };
  const clubs = useListAllClubs(page, options);
  const series = useListAllSeries(page, options);
  const events = useListAllEvents(page, options);
  const sailors = useListSailors(page, options);

  if (!show) return <>{children}</>;

  const nameOf = (e: SwitcherEntry) => e.context?.name ?? t(`workspace.kinds.${e.ref.kind}`);
  const found = searchWorkspace(query, entries, (kind: WorkspaceKind, section) => t(`workspace.sectionLabels.${kind}.${section}`), nameOf);
  const idOf = (ref: ContextRef) => refKey(ref).replace(":", "-");
  const mine = new Set(entries.map((e) => refKey(e.ref)));
  const objects = (kind: "club" | "series" | "event", rows: { id: number; label: string; detail?: string }[] | undefined): Hit[] =>
    remote
      ? (rows ?? [])
          .filter((r) => !mine.has(`${kind}:${r.id}`))
          .map((r) => ({ id: `${kind}-${r.id}`, to: sectionPath({ kind, id: r.id }), label: r.label, detail: r.detail }))
      : [];

  const groups: HitGroup[] = [
    {
      key: "mine",
      title: t("workspace.search.mine"),
      hits: found.contexts.map((e) => ({ id: idOf(e.ref), to: sectionPath(e.ref), label: nameOf(e), detail: t(`workspace.kinds.${e.ref.kind}`) })),
    },
    {
      key: "sections",
      title: t("workspace.search.sections"),
      hits: found.sections.map((h) => ({
        id: `${idOf(h.entry.ref)}-${h.section}`,
        to: sectionPath(h.entry.ref, h.section),
        label: h.label,
        detail: h.entry.context?.short_name || nameOf(h.entry),
      })),
    },
    {
      key: "clubs",
      title: t("workspace.search.clubs"),
      hits: objects("club", clubs.data?.items.map((c) => ({ id: c.id, label: c.name, detail: c.short_name }))),
    },
    {
      key: "series",
      title: t("workspace.search.series"),
      hits: objects("series", series.data?.items.map((s) => ({ id: s.id, label: s.name }))),
    },
    {
      key: "events",
      title: t("workspace.search.events"),
      hits: objects("event", events.data?.items.map((e) => ({ id: e.id, label: e.title, detail: e.starts_on ?? undefined }))),
    },
    {
      key: "sailors",
      title: t("workspace.search.sailors"),
      hits: remote
        ? (sailors.data?.items ?? []).map((s) => ({ id: `sailor-${s.id}`, to: `/sailors/${s.id}`, label: `${s.first_name} ${s.last_name}` }))
        : [],
    },
  ].filter((g) => g.hits.length > 0);
  const hits = groups.flatMap((g) => g.hits);
  const at = Math.min(marked, Math.max(hits.length - 1, 0));
  const waiting = remote && (asked !== query.trim() || [clubs, series, events, sailors].some((q) => q.isFetching));

  const onKey = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      if (hits.length === 0) return;
      const step = event.key === "ArrowDown" ? 1 : -1;
      setMarked((at + step + hits.length) % hits.length);
    } else if (event.key === "Enter" && hits[at]) {
      event.preventDefault();
      navigate(hits[at].to);
    }
  };
  const hitTestId = (h: Hit) => `workspace-switcher-search-hit-${h.id}`;

  return (
    <>
      <input
        ref={input}
        type="search"
        value={query}
        onChange={(e) => {
          setQuery(e.target.value);
          setMarked(0);
        }}
        onKeyDown={onKey}
        role="combobox"
        aria-expanded={query.trim().length > 0}
        aria-controls="workspace-switcher-search-hits"
        aria-activedescendant={hits[at] ? hitTestId(hits[at]) : undefined}
        aria-label={t("workspace.search.label")}
        placeholder={t(office ? "workspace.search.officePlaceholder" : "workspace.search.placeholder")}
        data-testid="workspace-switcher-search"
        className={`${INPUT_CLASS} mb-2 bg-surface text-foreground placeholder:text-muted`}
      />
      {query.trim() === "" ? (
        children
      ) : (
        <ul id="workspace-switcher-search-hits" role="listbox" className="flex flex-col gap-1" data-testid="workspace-switcher-search-hits">
          {groups.map((g) => (
            <li key={g.key} role="presentation" className="flex flex-col gap-0.5" data-testid={`workspace-switcher-search-group-${g.key}`}>
              <span className="px-3 pt-2 text-xs font-semibold uppercase tracking-wide text-muted">{g.title}</span>
              <ul role="presentation" className="flex flex-col gap-0.5">
                {g.hits.map((h) => {
                  const here = hits[at] === h;
                  return (
                    <li key={h.id} role="presentation">
                      <Link
                        to={h.to}
                        id={hitTestId(h)}
                        role="option"
                        aria-selected={here}
                        onMouseEnter={() => setMarked(hits.indexOf(h))}
                        data-testid={hitTestId(h)}
                        className={`flex items-center justify-between gap-2 rounded-md px-3 py-2 text-sm text-foreground ${
                          here ? "bg-surface-tertiary" : ""
                        }`}
                      >
                        <span className="truncate font-medium">{h.label}</span>
                        {h.detail && <span className="shrink-0 truncate text-xs text-muted">{h.detail}</span>}
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </li>
          ))}
          {hits.length === 0 && (
            <li className="px-3 py-2 text-sm text-muted" data-testid="workspace-switcher-search-empty">
              {t(waiting ? "workspace.search.searching" : "workspace.search.empty")}
            </li>
          )}
        </ul>
      )}
    </>
  );
}

function today(): string {
  const now = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

