import type { APIRequestContext, Page } from "@playwright/test";

import { describeStory, expect, test } from "./fixtures";
import { listedSections, openSwitcher } from "./layout";
import { bearer, signIn } from "./session";

/** Story Z-10, issue #35: the plan's §5 — what real people see — walked per seeded account.
 *
 * `web/tests/test_workspace.ts` proves the declaration against the §5 table with made-up
 * relations. Here the browser proves it for the seed's people as they are: signed in, the
 * switcher lists exactly their contexts with their relations, and each context's sidebar
 * exactly the sections they have there — in the order of the work, and nothing they
 * cannot use (a section that is not listed is the "notable" absence §5 names). On the
 * phone the same lists sit behind the two-button bar; `listedSections` opens it.
 *
 * A sidebar shows the sections a screen has built (`only`), so a declared section without
 * a screen yet is absent here too: the league office's *Imports* (run from the command
 * line), an event's *Trackers*.
 *
 * Rows of §5 the seed has nobody for, and a read-only spec cannot make:
 * - *Parent, no club* — no seeded account is anyone's `guardian` (the guardians spec links
 *   one and walks *My children*);
 * - *Club admin + treasurer* in one person — the seed splits them (`board@`, `treasurer@`);
 *   both are walked, and the club's admin alone already has all four *Money* pages;
 * - *Race officer at Act 2, jury at Act 3* — the seed has one of each on one event
 *   (`regatta@`, `jury@` on Warnemünde 2027), walked separately;
 * - *Sailor who also helps at an event* — no seeded sailor is a helper (`my-space.spec.ts`
 *   walks the helper; `test_workspace.ts` the sum of both).
 *
 * Read-only but for the practice season (`app/practice.py`), which the sailor's row needs —
 * the seed names no sailor in any crew — and which is built once per stack.
 */

/** An object of the seed, by its slug — ids are the database's business. */
type Ref = `club:${string}` | `series:${string}` | `event:${string}`;

type Person = {
  /** The §5 row (or the seeded person it stands for). */
  row: string;
  /** Their address, or how to find them among the seed's sailors. */
  who: string | ((request: APIRequestContext) => Promise<string>);
  /** The site relations they hold — the league office's sections; absent, no office. */
  office?: string[];
  /** Me's sections. */
  me?: string[];
  /** Every context of theirs in the switcher, with its relations as chips, and the
   *  sections of its sidebar. */
  contexts: { ref: Ref; relations: string[]; sections: string[] }[];
};

const ME = ["overview", "account", "clubs", "waivers", "claims", "documents", "bank"];
const ASVW: Ref = "club:asvw";
// The test series: `serie@` manages it, `presse@` writes about it (`app/seed_users.py`).
const LIGA2: Ref = "series:dsbl-2-2026";
// The 2. Liga's practice season, `season2` — its slugs, checked against the fixture.
const PRACTICE = "practice-2-2026";
const PRACTICE_SERIES: Ref = `series:${PRACTICE}`;
const ACT1: Ref = `event:${PRACTICE}-act-1`;
const ACT2: Ref = `event:${PRACTICE}-act-2`;
const ACT3: Ref = `event:${PRACTICE}-act-3`;
// ASVW hosts it, and the event cast holds its relations there (`app/seed_users.py`).
const WARNEMUENDE: Ref = "event:dsbl-1-2027-warnemuende";
const SERIES_ORGANIZER = ["overview", "events", "standings", "registrations", "dates", "scoring", "officials"];

/** An adult of ASVW who sails the 2. Liga's practice season and is in its acts' crews —
 *  §5's first row. Its squad's people are made by `app/practice.py`, adults all. */
async function anAdultSailor(request: APIRequestContext): Promise<string> {
  const admin = await bearer(request, "admin@sbl.example.com");
  const listed = await request.get("/api/auth/users?q=asvw.practice.example.com&limit=20", { headers: admin });
  expect(listed.ok(), await listed.text()).toBeTruthy();
  for (const user of ((await listed.json()) as { items: { email: string }[] }).items) {
    const mine = (await (await request.get("/api/me/contexts", { headers: await bearer(request, user.email) })).json()) as {
      contexts: { kind: string; relations: string[] }[];
    };
    if (mine.contexts.filter((c) => c.kind === "event" && c.relations.includes("sailor")).length === 3) return user.email;
  }
  throw new Error("no ASVW sailor in the practice season's three acts — has app/practice.py changed?");
}

const PEOPLE: Person[] = [
  {
    row: "Sailor, adult (ASVW, 2. Liga)",
    who: anAdultSailor,
    contexts: [
      { ref: ASVW, relations: ["member"], sections: ["overview", "people", "squads", "crews", "my-claims"] },
      { ref: PRACTICE_SERIES, relations: ["sailor"], sections: ["overview", "team", "events", "standings"] },
      { ref: ACT1, relations: ["sailor"], sections: ["overview", "crew"] },
      { ref: ACT2, relations: ["sailor"], sections: ["overview", "crew"] },
      { ref: ACT3, relations: ["sailor"], sections: ["overview", "crew"] },
    ],
  },
  {
    row: "Team manager, ASVW (Tom Teammanager)",
    who: "teams@asvw.example.com",
    contexts: [
      {
        ref: ASVW,
        relations: ["member", "manager"],
        // Its people and racing; the money is the treasurer's, the page and the hosted
        // events the admin's.
        sections: ["overview", "people", "minors", "waivers", "squads", "crews", "my-claims"],
      },
    ],
  },
  {
    row: "Club admin (board@)",
    who: "board@asvw.example.com",
    contexts: [
      {
        ref: ASVW,
        relations: ["member", "admin"],
        sections: [
          "overview", "people", "minors", "waivers", "squads", "crews", "hosting",
          "my-claims", "decide-claims", "payment-runs", "bank-account", "club-page",
        ],
      },
    ],
  },
  {
    row: "Treasurer (treasurer@)",
    who: "treasurer@asvw.example.com",
    contexts: [
      {
        ref: ASVW,
        relations: ["member", "treasurer"],
        // A member's reading, and the Money group — none of the people's sections.
        sections: ["overview", "people", "squads", "crews", "my-claims", "decide-claims", "payment-runs", "bank-account"],
      },
    ],
  },
  {
    row: "Event manager of Warnemünde 2027 (orga@)",
    who: "orga@sbl.example.com",
    contexts: [
      {
        ref: WARNEMUENDE,
        relations: ["manager"],
        // Set up, Race day, Money (both) — no Editorial.
        sections: [
          "overview", "general", "clubs", "boats", "pairing", "scoring", "publication", "people",
          "check-in", "race-control", "results", "notice-board", "my-claims", "decide-claims",
        ],
      },
    ],
  },
  {
    row: "Race officer at Warnemünde 2027 (regatta@)",
    who: "regatta@sbl.example.com",
    contexts: [
      {
        ref: WARNEMUENDE,
        relations: ["race_officer"],
        sections: ["overview", "check-in", "race-control", "results", "notice-board", "my-claims"],
      },
    ],
  },
  {
    row: "Jury at Warnemünde 2027 (jury@)",
    who: "jury@sbl.example.com",
    contexts: [
      { ref: WARNEMUENDE, relations: ["jury"], sections: ["overview", "notice-board", "my-claims"] },
    ],
  },
  {
    row: "Helper at Warnemünde 2027 (helfer@)",
    who: "helfer@sbl.example.com",
    contexts: [
      { ref: WARNEMUENDE, relations: ["helper"], sections: ["overview", "my-claims"] },
    ],
  },
  {
    row: "Series manager (Junioren)",
    who: "junioren@sbl.example.com",
    // The acts are reached through *Events*, not listed in the switcher.
    contexts: [
      { ref: "series:junioren-2026", relations: ["manager"], sections: SERIES_ORGANIZER },
      { ref: "series:junioren-2027", relations: ["manager"], sections: SERIES_ORGANIZER },
    ],
  },
  {
    row: "Series manager (2. Liga, and both 2027 drafts)",
    who: "serie@sbl.example.com",
    contexts: [
      { ref: LIGA2, relations: ["manager"], sections: SERIES_ORGANIZER },
      { ref: "series:dsbl-1-2027", relations: ["manager"], sections: SERIES_ORGANIZER },
      { ref: "series:dsbl-2-2027", relations: ["manager"], sections: SERIES_ORGANIZER },
    ],
  },
  {
    row: "Series editor (presse@)",
    who: "presse@sbl.example.com",
    // Me gains the regattas they write about; the series nothing to organize.
    me: [...ME, "news", "media"],
    contexts: [{ ref: LIGA2, relations: ["editor"], sections: ["overview", "events", "standings", "news"] }],
  },
  {
    row: "Site editor (redaktion@)",
    who: "redaktion@sbl.example.com",
    office: ["overview", "news", "media"],
    contexts: [],
  },
  {
    row: "Site race officer (wl@)",
    who: "wl@sbl.example.com",
    office: ["overview", "events"],
    contexts: [],
  },
  {
    row: "Site admin",
    who: "admin@sbl.example.com",
    // Complete, but for Imports, which has no screen (run from the command line).
    office: ["overview", "clubs", "series", "events", "people", "accounts", "news", "media", "jury"],
    contexts: [],
  },
  {
    row: "Guest account, no relation (gast@)",
    who: "gast@sbl.example.com",
    contexts: [],
  },
];

/** The seed's ids of every object the table names, from the league office's lists. */
async function seededIds(request: APIRequestContext): Promise<Map<Ref, number>> {
  const headers = await bearer(request, "admin@sbl.example.com");
  const ids = new Map<Ref, number>();
  for (const kind of ["club", "series", "event"] as const) {
    const listed = await request.get(`/api/admin/${kind === "series" ? "series" : `${kind}s`}?limit=100`, { headers });
    expect(listed.ok(), await listed.text()).toBeTruthy();
    for (const item of ((await listed.json()) as { items: { id: number; slug: string }[] }).items) {
      ids.set(`${kind}:${item.slug}`, item.id);
    }
  }
  return ids;
}

/** The switcher's entries on screen, as `me`, `office`, `club-7` … — Recent left out. */
async function switcherEntries(page: Page): Promise<string[]> {
  await openSwitcher(page);
  const ids = await page
    .getByTestId("workspace-switcher-panel")
    .locator('a[data-testid^="workspace-switcher-"]')
    .evaluateAll((links) => links.map((a) => a.getAttribute("data-testid") ?? ""));
  return ids.filter((id) => !id.startsWith("workspace-switcher-recent-")).map((id) => id.replace("workspace-switcher-", ""));
}

describeStory("Z-10: what real people see — the plan's §5, per seeded account", () => {
  for (const person of PEOPLE) {
    test(`§5: ${person.row}`, async ({ page, request, season2 }) => {
      expect(season2.label, "the practice season's slug").toBe(PRACTICE);
      const ids = await seededIds(request);
      const email = typeof person.who === "string" ? person.who : await person.who(request);
      const entry = (ref: Ref) => {
        const [kind, slug] = ref.split(":");
        const id = ids.get(ref);
        expect(id, `${slug} is not in the seed`).toBeDefined();
        return { kind: kind!, key: `${kind}-${id}` };
      };

      await signIn(page, email);
      await page.goto("/me");

      // The switcher: Me, the league office with a site relation, then exactly theirs.
      const expected = ["me", ...(person.office ? ["office"] : []), ...person.contexts.map((c) => entry(c.ref).key)];
      expect((await switcherEntries(page)).sort()).toEqual(expected.sort());
      for (const c of person.contexts) {
        const { key } = entry(c.ref);
        const chips = await page
          .getByTestId(`workspace-switcher-${key}-relations`)
          .locator(`[data-testid^="workspace-switcher-${key}-relations-"]`)
          .evaluateAll((els) => els.map((e) => e.getAttribute("data-testid") ?? ""));
        expect(chips.map((id) => id.replace(`workspace-switcher-${key}-relations-`, "")), key).toEqual(c.relations);
      }
      await page.keyboard.press("Escape");

      // Me — the landing page's context.
      expect(await listedSections(page, "me")).toEqual(person.me ?? ME);
      await page.keyboard.press("Escape");

      // Each context, opened from the switcher, with exactly its sections.
      const opened = [...(person.office ? [{ key: "office", kind: "office", sections: person.office }] : [])];
      for (const c of person.contexts) opened.push({ ...entry(c.ref), sections: c.sections });
      for (const c of opened) {
        await openSwitcher(page);
        await page.getByTestId(`workspace-switcher-${c.key}`).click();
        expect(await listedSections(page, c.kind), c.key).toEqual(c.sections);
        await page.keyboard.press("Escape");
      }
    });
  }
});
