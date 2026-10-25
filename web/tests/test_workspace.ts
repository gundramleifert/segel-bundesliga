import { describe, expect, test } from "vitest";

import { Relation, type MyContext, type Todo } from "../src/api/types";
import de from "../src/i18n/locales/de/space.json";
import en from "../src/i18n/locales/en/space.json";
import {
  fold,
  groupTodos,
  hasSection,
  isLive,
  liveNow,
  readVisits,
  rememberVisit,
  pushRecent,
  readRecent,
  refKey,
  SAILOR,
  rememberRecent,
  searchWorkspace,
  sectionPath,
  sectionsFor,
  showsSearch,
  sidebar,
  switcherEntries,
  WORKSPACE,
  type ContextRef,
  type GroupDecl,
  type SwitcherEntry,
  type WorkspaceKind,
} from "../src/lib/workspace";

/** Story Z-10: the declaration of the workspace (issue #30), walked against the table of
 *  real people in `docs/PLAN_NAVIGATION.md` §5 — what each of them finds in the switcher
 *  and in the sidebar of each of their contexts. */

const TODAY = "2026-10-25";

function context(kind: MyContext["kind"], id: number, name: string, extra: Partial<MyContext> = {}): MyContext {
  return { kind, id, name, relations: [], needs: [], teams: [], ...extra };
}

describe("Story Z-10: the sections each person of §5 has", () => {
  test("an adult sailor of ASVW: the club read, their team, their crew", () => {
    expect(sectionsFor("club", [Relation.member])).toEqual(["overview", "members", "squads", "crews", "my-claims"]);
    expect(sectionsFor("series", [SAILOR])).toEqual(["overview", "team", "events", "standings"]);
    expect(sectionsFor("event", [SAILOR])).toEqual(["overview", "crew"]);
  });

  test("a parent with no club: Me with My children, and nothing else in the switcher", () => {
    expect(sectionsFor("me", [Relation.guardian])).toEqual([
      "overview", "account", "waivers", "claims", "documents", "bank", "children",
    ]);
    expect(sectionsFor("me", [])).not.toContain("children");
    const s = switcherEntries({ contexts: [], today: TODAY });
    expect(s.head.map((e) => e.ref.kind)).toEqual(["me"]);
    expect([...s.clubs, ...s.series, ...s.events]).toEqual([]);
  });

  test("the team manager of ASVW: everything of the club but its page", () => {
    const sections = sectionsFor("club", [Relation.member, Relation.manager]);
    expect(sections).toEqual([
      "overview", "members", "sailors", "minors", "waivers", "squads", "crews", "hosting",
      "my-claims", "decide-claims", "payment-runs", "bank-account",
    ]);
    expect(sections).not.toContain("club-page");
  });

  test("a club admin who is also its treasurer: one Money group with all four pages, each once", () => {
    const money = sidebar("club", [Relation.member, Relation.admin, Relation.treasurer]).find((g) => g.key === "money");
    expect(money).toEqual({
      key: "money",
      sections: ["my-claims", "decide-claims", "payment-runs", "bank-account"],
      heading: true,
      folded: false,
    });
    expect(hasSection("club", "club-page", [Relation.member, Relation.admin, Relation.treasurer])).toBe(true);
  });

  test("a treasurer who is no member: the club's money, not its people", () => {
    expect(sectionsFor("club", [Relation.treasurer])).toEqual(["overview", "decide-claims", "payment-runs", "bank-account"]);
  });

  test("the event manager of act 3: set-up, race day and both kinds of claims, no editorial", () => {
    const groups = sidebar("event", [Relation.manager]);
    expect(groups.map((g) => g.key)).toEqual([null, "setup", "raceday", "money"]);
    expect(sectionsFor("event", [Relation.manager])).not.toContain("news");
    expect(groups.find((g) => g.key === "money")?.sections).toEqual(["my-claims", "decide-claims"]);
  });

  test("race officer at act 2, jury at act 3", () => {
    expect(sectionsFor("event", [Relation.race_officer])).toEqual([
      "overview", "check-in", "race-control", "results", "trackers", "notice-board", "my-claims",
    ]);
    const jury = sidebar("event", [Relation.jury]);
    expect(jury.flatMap((g) => g.sections)).toEqual(["overview", "notice-board", "my-claims"]);
    // A group with one section shows as that section, without a heading.
    expect(jury.every((g) => !g.heading)).toBe(true);
  });

  test("the series manager of the Junioren-Liga: organizing, and the series in the switcher by year", () => {
    expect(sectionsFor("series", [Relation.manager])).toEqual([
      "overview", "events", "standings", "registrations", "dates", "scoring", "officials",
    ]);
    const s = switcherEntries({
      contexts: [
        context("series", 12, "Junioren-Segelliga 2027", { relations: [Relation.manager], year: 2027, published: false }),
        context("series", 11, "Junioren-Segelliga 2026", { relations: [Relation.manager], year: 2026 }),
      ],
      today: TODAY,
    });
    expect(s.series.map((e) => e.context?.name)).toEqual(["Junioren-Segelliga 2026", "Junioren-Segelliga 2027"]);
  });

  test("the series editor: the series to read and its news, nothing to organize", () => {
    expect(sectionsFor("series", [Relation.editor])).toEqual(["overview", "events", "standings", "news"]);
  });

  test("the site editor: the league office with News and Media only", () => {
    const s = switcherEntries({ contexts: [], site: [Relation.editor], today: TODAY });
    expect(s.head.map((e) => e.ref.kind)).toEqual(["me", "office"]);
    expect(sectionsFor("office", [Relation.editor])).toEqual(["overview", "news", "media"]);
  });

  test("the site admin: the league office complete", () => {
    expect(sectionsFor("office", [Relation.admin])).toEqual([
      "overview", "clubs", "series", "events", "sailors", "accounts", "news", "media", "imports",
    ]);
    expect(sectionsFor("office", [Relation.race_officer])).toEqual(["overview", "events"]);
  });

  test("a sailor who also helps at an event: their crew and their claims", () => {
    expect(sectionsFor("event", [SAILOR, Relation.helper])).toEqual(["overview", "crew", "my-claims"]);
  });

  test("a section someone cannot use does not exist for them", () => {
    expect(hasSection("event", "race-control", [Relation.helper])).toBe(false);
    expect(hasSection("club", "minors", [Relation.member])).toBe(false);
  });
});

describe("Story Z-10: the event's state orders its groups", () => {
  test("before the start Set up leads and Race day is folded; from the first race the reverse", () => {
    const before = sidebar("event", [Relation.manager]);
    expect(before.map((g) => [g.key, g.folded])).toEqual([[null, false], ["setup", false], ["raceday", true], ["money", false]]);
    const after = sidebar("event", [Relation.manager], { started: true });
    expect(after.map((g) => [g.key, g.folded])).toEqual([[null, false], ["raceday", false], ["setup", true], ["money", false]]);
  });

  test("someone with only race day has nothing folded", () => {
    expect(sidebar("event", [Relation.race_officer]).some((g) => g.folded)).toBe(false);
  });
});

describe("Story Z-10: the switcher", () => {
  const contexts = [
    context("event", 3, "Act 3 · Warnemünde", { relations: [Relation.manager], starts_on: "2026-11-06", needs: [{ code: "claims", count: 3, section: "decide-claims", severity: "soon" }] }),
    context("event", 1, "Act 1 · Berlin", { relations: [SAILOR], starts_on: "2026-05-01", ends_on: "2026-05-03" }),
    context("event", 2, "Act 2 · Kiel", { relations: [Relation.race_officer], starts_on: "2026-10-30" }),
    context("club", 8, "NRV", { relations: [Relation.member] }),
    context("club", 7, "ASVW", { relations: [Relation.member, Relation.admin] }),
    context("series", 5, "2. Segel-Bundesliga 2026", { relations: [SAILOR], year: 2026 }),
    context("series", 4, "1. Segel-Bundesliga 2025", { relations: [SAILOR], year: 2025 }),
  ];
  const s = switcherEntries({ contexts, site: [Relation.admin], meWaiting: 1, today: TODAY });

  test("Me, the league office, clubs by name, series current year first, events next first and past folded", () => {
    expect(s.head.map((e) => [e.ref.kind, e.waiting])).toEqual([["me", 1], ["office", 0]]);
    expect(s.clubs.map((e) => e.context?.name)).toEqual(["ASVW", "NRV"]);
    expect(s.series.map((e) => e.context?.year)).toEqual([2026, 2025]);
    expect(s.events.map((e) => [e.context?.id, e.past])).toEqual([[2, false], [3, false], [1, true]]);
  });

  test("each entry carries its relations and its waiting count", () => {
    const act3 = s.events.find((e) => e.context?.id === 3);
    expect(act3?.relations).toEqual([Relation.manager]);
    expect(act3?.waiting).toBe(3);
  });

  test("no league office without a site relation", () => {
    expect(switcherEntries({ contexts, today: TODAY }).head.map((e) => e.ref.kind)).toEqual(["me"]);
  });

  test("Recent keeps what was opened from inside, never what is listed already", () => {
    const recent: ContextRef[] = [{ kind: "event", id: 99 }, { kind: "club", id: 7 }, { kind: "me" }];
    expect(switcherEntries({ contexts, recent, today: TODAY }).recent).toEqual([{ kind: "event", id: 99 }]);
  });
});

describe("Story Z-10: recent, per browser", () => {
  function memory(): Storage {
    const data = new Map<string, string>();
    return {
      getItem: (k) => data.get(k) ?? null,
      setItem: (k, v) => void data.set(k, v),
      removeItem: (k) => void data.delete(k),
      clear: () => data.clear(),
      key: () => null,
      get length() {
        return data.size;
      },
    };
  }

  test("the last five, latest first, each once", () => {
    const storage = memory();
    for (const id of [1, 2, 3, 4, 5, 6, 3]) rememberRecent({ kind: "event", id }, storage);
    expect(readRecent(storage).map(refKey)).toEqual(["event:3", "event:6", "event:5", "event:4", "event:2"]);
  });

  test("blocked or garbled storage reads as nothing and never throws", () => {
    const blocked = {
      getItem: () => {
        throw new Error("SecurityError");
      },
      setItem: () => {
        throw new Error("SecurityError");
      },
    };
    expect(readRecent(blocked)).toEqual([]);
    expect(() => rememberRecent({ kind: "me" }, blocked)).not.toThrow();
    expect(readRecent({ getItem: () => "{not json" })).toEqual([]);
    expect(readRecent({ getItem: () => JSON.stringify([{ kind: "club" }, { kind: "club", id: 7 }]) })).toEqual([
      { kind: "club", id: 7 },
    ]);
  });

  test("pushRecent is pure", () => {
    const list = [1, 2];
    expect(pushRecent(list, 3, String, 2)).toEqual([3, 1]);
    expect(list).toEqual([1, 2]);
  });
});

describe("Story Z-10: addresses and the sections a screen has", () => {
  test("each section has one address, the overview the bare one", () => {
    expect(sectionPath({ kind: "me" })).toBe("/me");
    expect(sectionPath({ kind: "me" }, "waivers")).toBe("/me/profile/waivers");
    expect(sectionPath({ kind: "club", id: 7 })).toBe("/me/club/7");
    expect(sectionPath({ kind: "club", id: 7 }, "minors")).toBe("/me/club/7/minors");
    expect(sectionPath({ kind: "office" }, "clubs")).toBe("/office/clubs");
    expect(sectionPath({ kind: "office" })).toBe("/office");
  });

  test("a declared section without a panel is not listed, and a group left with one loses its heading", () => {
    const groups = sidebar("club", [Relation.member, Relation.manager], { only: ["overview", "members", "squads", "crews"] });
    expect(groups.map((g) => [g.key, g.sections, g.heading])).toEqual([
      [null, ["overview"], false],
      ["people", ["members"], false],
      ["racing", ["squads", "crews"], true],
    ]);
  });
});

describe("Story Z-10: Live now, To do, Last visited", () => {
  const event = (id: number, relations: string[], extra: Partial<MyContext> = {}) =>
    context("event", id, `Act ${id}`, { relations: relations as MyContext["relations"], ...extra });

  test("an event is live while running, or on a race day still planned — not when over or called off", () => {
    expect(isLive(event(1, [], { status: "live", starts_on: "2026-10-01" }), TODAY)).toBe(true);
    expect(isLive(event(2, [], { status: "planned", starts_on: "2026-10-24", ends_on: "2026-10-26" }), TODAY)).toBe(true);
    expect(isLive(event(3, [], { status: "planned", starts_on: "2026-11-06" }), TODAY)).toBe(false);
    expect(isLive(event(4, [], { status: "cancelled", starts_on: TODAY }), TODAY)).toBe(false);
    expect(isLive(event(5, [], { status: "final", starts_on: TODAY }), TODAY)).toBe(false);
  });

  test("Live now offers what my relations give there, race control first for the race committee", () => {
    const contexts = [
      event(1, [Relation.race_officer], { status: "live" }),
      event(2, [Relation.jury], { status: "live" }),
      event(3, [SAILOR, Relation.helper], { status: "live" }),
      event(4, [Relation.race_officer], { status: "planned", starts_on: "2027-01-01" }),
    ];
    const blocks = liveNow(contexts, TODAY);
    expect(blocks.map((b) => [b.context.id, b.sections, b.publicLive])).toEqual([
      [1, ["race-control", "results", "check-in", "notice-board"], false],
      [2, ["notice-board"], false],
      [3, ["overview", "my-claims", "crew"], true],
    ]);
  });

  test("the to-dos are grouped by context, each group where its most urgent one came", () => {
    const todo = (kind: string, id: number | null, code: string): Todo =>
      ({ code, count: 1, section: "overview", severity: "soon", context: { kind, id } }) as Todo;
    const groups = groupTodos([todo("event", 3, "checkin_waivers_missing"), todo("club", 7, "minor_without_guardian"), todo("event", 3, "claims"), todo("me", null, "waiver")]);
    expect(groups.map((g) => [refKey(g.ref), g.todos.map((t) => t.code)])).toEqual([
      ["event:3", ["checkin_waivers_missing", "claims"]],
      ["club:7", ["minor_without_guardian"]],
      ["me", ["waiver"]],
    ]);
  });

  test("last visited keeps five sections, the latest first, each once", () => {
    const data = new Map<string, string>();
    const storage = { getItem: (k: string) => data.get(k) ?? null, setItem: (k: string, v: string) => void data.set(k, v) };
    for (const section of ["members", "squads", "crews", "waivers", "hosting", "members", "my-claims"]) {
      rememberVisit({ ref: { kind: "club", id: 7 }, section, name: "ASVW", label: section }, storage);
    }
    expect(readVisits(storage).map((v) => v.section)).toEqual(["my-claims", "members", "hosting", "waivers", "crews"]);
  });
});

describe("Story Z-10: the switcher's search (#34)", () => {
  type Lang = { workspace: { sectionLabels: Record<string, Record<string, string>>; kinds: Record<string, string> } };
  const asvw = context("club", 7, "Akademischer Segler-Verein in Warnemünde", {
    short_name: "ASVW",
    relations: [Relation.member, Relation.admin],
  });
  const series = context("series", 3, "2. Segel-Bundesliga 2026", { relations: [SAILOR], year: 2026 });
  const event = context("event", 11, "Act 3 · Warnemünde", { relations: [Relation.helper], starts_on: "2026-11-01" });
  const all = (contexts: MyContext[], site?: string[]) => {
    const s = switcherEntries({ contexts, site, today: TODAY });
    return [...s.head, ...s.clubs, ...s.series, ...s.events];
  };
  const hits = (query: string, entries: SwitcherEntry[], lang: Lang = en) => {
    const r = searchWorkspace(
      query,
      entries,
      (kind: WorkspaceKind, section: string) => lang.workspace.sectionLabels[kind][section],
      (e) => e.context?.name ?? lang.workspace.kinds[e.ref.kind],
    );
    return {
      contexts: r.contexts.map((e) => refKey(e.ref)),
      sections: r.sections.map((h) => `${refKey(h.entry.ref)}/${h.section}`),
    };
  };

  test("every declared section of every context has its label, in English and in German", () => {
    for (const lang of [en, de] as Lang[]) {
      for (const [kind, groups] of Object.entries(WORKSPACE)) {
        for (const g of groups as readonly GroupDecl[]) {
          for (const section of Object.keys(g.sections)) {
            expect(lang.workspace.sectionLabels[kind]?.[section], `${kind}.${section}`).toBeTruthy();
          }
        }
      }
    }
  });

  test("a club's admin types minors and is offered ASVW's minors — in German too, accents ignored", () => {
    const entries = all([asvw, series, event]);
    expect(hits("minors", entries)).toEqual({ contexts: [], sections: ["club:7/minors"] });
    expect(hits("MINDERJÄHRIGE", entries, de).sections).toEqual(["club:7/minors"]);
    expect(hits("minderjahrige", entries, de).sections).toEqual(["club:7/minors"]);
  });

  test("a section I do not have is never offered", () => {
    const member = { ...asvw, relations: [Relation.member] };
    expect(hits("minors", all([member])).sections).toEqual([]);
    // The helper has their claims on the event, not its results.
    expect(hits("results", all([event])).sections).toEqual([]);
    expect(hits("claims", all([event])).sections).toEqual(["me/claims", "event:11/my-claims"]);
  });

  test("contexts by name or short name; several words narrow, across name and label", () => {
    const entries = all([asvw, series, event]);
    expect(hits("warnemunde", entries).contexts).toEqual(["club:7", "event:11"]);
    expect(hits("asvw", entries)).toEqual({ contexts: ["club:7"], sections: [] });
    expect(hits("asvw claims", entries).sections).toEqual(["club:7/my-claims", "club:7/decide-claims"]);
    expect(hits("claims", entries).sections).toEqual([
      "me/claims", "club:7/my-claims", "club:7/decide-claims", "event:11/my-claims",
    ]);
    expect(hits("   ", entries)).toEqual({ contexts: [], sections: [] });
  });

  test("the league office's own sections are found by the site's admin, not by editorial", () => {
    expect(hits("imports", all([], [Relation.admin])).sections).toEqual(["office/imports"]);
    expect(hits("imports", all([], [Relation.editor])).sections).toEqual([]);
  });

  test("the box: from 8 entries on, and always with a site relation", () => {
    const few = switcherEntries({ contexts: [asvw, series], today: TODAY });
    expect(showsSearch(few, false)).toBe(false);
    expect(showsSearch(few, true)).toBe(true);
    const many = switcherEntries({
      contexts: Array.from({ length: 7 }, (_, i) => context("event", i + 1, `Event ${i}`)),
      today: TODAY,
    });
    expect(showsSearch(many, false)).toBe(true);
  });

  test("fold drops case and accents", () => {
    expect(fold("Straße Überlingen")).toBe("strasse uberlingen");
  });
});
