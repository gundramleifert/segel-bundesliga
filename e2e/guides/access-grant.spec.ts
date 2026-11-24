import type { APIRequestContext } from "@playwright/test";

import { bearer } from "../session";
import { guide, say, ui } from "./guide";

/** "Grant access" — the league office makes someone a club's admin: Journey J-2, step
 * J-2.3 (Story A-8), on the Access tab (Story Z-2). The person is the seeded guest, who
 * holds nothing; the club is the test club ASVW. */

const ADMIN = "admin@sbl.example.com";
const PERSON = "gast@sbl.example.com";

type Account = { id: number; tuples: { id: number; relation: string; object_type: string }[] };

async function account(request: APIRequestContext): Promise<Account> {
  const found = await request.get(`/api/auth/users?q=${encodeURIComponent(PERSON)}`, {
    headers: await bearer(request, ADMIN),
  });
  return (await found.json()).items[0] as Account;
}

async function asvw(request: APIRequestContext): Promise<string> {
  const found = await request.get("/api/clubs?q=ASVW&limit=10", { headers: await bearer(request, ADMIN) });
  const clubs = (await found.json()).items as { name: string; short_name: string }[];
  return clubs.find((c) => c.short_name === "ASVW")!.name;
}

const tid = (id: string) => `[data-testid="${id}"]`;

guide(
  {
    id: "guide-access-grant",
    source: "e2e/guides/access-grant.spec.ts",
    title: { en: "Make someone a club's admin", de: "Jemanden zur Verwaltung eines Vereins machen" },
    audience: ["administration"],
    order: 240,
    stories: ["A-8", "Z-2"],
    steps: ["J-2.3"],
    tags: ["access", "zugriff", "grant", "vergeben", "club admin", "vereinsverwaltung", "onboarding"],
    as: ADMIN,
    // The guest holds nothing before each language's walk.
    async reset(request) {
      const headers = await bearer(request, ADMIN);
      for (const row of (await account(request)).tuples) {
        await request.delete(`/api/auth/tuples/${row.id}`, { headers });
      }
    },
    intro: {
      en:
        "A new club gets its first admin from the league office. The person needs an " +
        "account first — they register, or sign in once with a code. From then on the club's " +
        "admin takes in the club's people and names its team manager.",
      de:
        "Ein neuer Verein bekommt seine erste Verwaltung vom Ligabüro. Die Person braucht " +
        "zuerst ein Konto — sie registriert sich oder meldet sich einmal mit einem Code an. " +
        "Danach nimmt die Vereinsverwaltung die Personen des Vereins auf und benennt das " +
        "Teammanagement.",
    },
    after: {
      en:
        "The access applies at once, without signing in again. The club's admin first " +
        "accepts the data processing agreement, then works under *My space* › the club. " +
        "A club always keeps one admin: to hand it over, grant the next one first.",
      de:
        "Der Zugriff gilt sofort, ohne neue Anmeldung. Die Vereinsverwaltung nimmt zuerst " +
        "den Auftragsverarbeitungsvertrag an und arbeitet dann unter *Mein Bereich* › der " +
        "Verein. Ein Verein behält immer eine Verwaltung: Zum Übergeben zuerst die nächste " +
        "benennen.",
    },
  },
  async ({ page, step, result }) => {
    const person = await account(page.request);
    const club = await asvw(page.request);
    await page.goto("/me");

    await step(
      { en: "Open the account menu, top right.", de: "Oben rechts das Kontomenü öffnen." },
      tid("layout-profile-button"),
      () => page.getByTestId("layout-profile-button").click(),
    );
    await step(
      say((l, locale) => (locale === "en" ? `Choose *${l.office}*.` : `*${l.office}* wählen.`), {
        office: ui("common", "userMenu.office"),
      }),
      tid("layout-user-menu-office"),
      () => page.getByTestId("layout-user-menu-office").click(),
    );
    await step(
      say(
        (l, locale) =>
          locale === "en" ? `In the sidebar, choose *${l.access}*.` : `In der Seitenleiste *${l.access}* wählen.`,
        { access: ui("space", "workspace.sectionLabels.office.accounts") },
      ),
      tid("workspace-section-office-accounts"),
      () => page.getByTestId("workspace-section-office-accounts").click(),
    );
    await step(
      { en: "Search the person by name or email.", de: "Die Person nach Name oder E-Mail suchen." },
      tid("admin-accounts-search-input"),
      async () => {
        await page.getByTestId("admin-accounts-search-input").fill(PERSON);
        await page.getByTestId(`admin-accounts-tuples-${person.id}`).waitFor();
      },
    );
    await step(
      say(
        (l, locale) => (locale === "en" ? `Beside the person: *＋ ${l.add}*.` : `Neben der Person: *＋ ${l.add}*.`),
        { add: ui("admin", "accounts.tupleAdd") },
      ),
      tid(`admin-accounts-tuple-add-${person.id}`),
      () => page.getByTestId(`admin-accounts-tuple-add-${person.id}`).click(),
    );
    await step(
      say((l) => `*${l.for}*: *${l.club}*.`, {
        for: ui("admin", "accounts.tupleTypeLabel"),
        club: ui("admin", "accounts.objectTypeLabels.club"),
      }),
      tid(`admin-accounts-tuple-type-${person.id}`),
      () => page.getByTestId(`admin-accounts-tuple-type-${person.id}`).selectOption("club"),
    );
    await step(
      say((l) => `*${l.as}*: *${l.admin}*.`, {
        as: ui("admin", "accounts.tupleRelationLabel"),
        admin: ui("admin", "accounts.relationLabels.admin"),
      }),
      tid(`admin-accounts-tuple-relation-${person.id}`),
      () => page.getByTestId(`admin-accounts-tuple-relation-${person.id}`).selectOption("admin"),
    );
    await step(
      say(
        (l, locale) => (locale === "en" ? `*${l.which}*: the club.` : `*${l.which}*: der Verein.`),
        { which: ui("admin", "accounts.tupleObjectLabel") },
      ),
      tid(`admin-accounts-tuple-object-${person.id}`),
      () => page.getByTestId(`admin-accounts-tuple-object-${person.id}`).selectOption({ label: club }),
    );
    await step(
      say((l) => `*${l.grant}*.`, { grant: ui("admin", "accounts.tupleButton") }),
      tid(`admin-accounts-tuple-submit-${person.id}`),
      () => page.getByTestId(`admin-accounts-tuple-submit-${person.id}`).click(),
    );
    await result(
      {
        en: "The new line shows the role and the club.",
        de: "Die neue Zeile zeigt die Rolle und den Verein.",
      },
      tid(`admin-accounts-tuples-${person.id}`),
    );
  },
);
