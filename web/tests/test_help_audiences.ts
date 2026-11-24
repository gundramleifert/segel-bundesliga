import { describe, expect, test } from "vitest";

import type { Account, MyContext } from "../src/api/types";
import { AUDIENCES, type HelpPage } from "../src/handbook";
import { audiencesOf, isForMe } from "../src/lib/helpAudiences";

/** Story B-18 (2026-11-24): I see the help for what I may do, and only that. */

const someone = { id: 1, email: "a@example.com", roles: [] } as unknown as Account;
const context = (kind: MyContext["kind"], relations: string[]): MyContext =>
  ({ kind, id: 1, name: "x", relations, needs: [], teams: [] }) as unknown as MyContext;
const page = (audience: string[]) => ({ audience }) as unknown as HelpPage;

describe("Story B-18: the help a person sees follows what they may do", () => {
  test("a guest has no audience", () => {
    expect([...audiencesOf(null, [], [])]).toEqual([]);
  });

  test("an account with no relation has the sailor's help only", () => {
    expect([...audiencesOf(someone, [], [])]).toEqual(["sailor"]);
  });

  test("a club's manager or admin has the club's; a treasurer the treasurer's", () => {
    expect(audiencesOf(someone, [context("club", ["manager"])], []).has("club")).toBe(true);
    const admin = audiencesOf(someone, [context("club", ["admin"])], []);
    expect(admin.has("club") && admin.has("treasurer")).toBe(true);  // it decides the money too
    const treasurer = audiencesOf(someone, [context("club", ["treasurer"])], []);
    expect(treasurer.has("treasurer")).toBe(true);
    expect(treasurer.has("club")).toBe(false);
  });

  test("an event's manager or helper organizes; its race officer or jury is the race committee", () => {
    expect(audiencesOf(someone, [context("event", ["manager"])], []).has("event-organizer")).toBe(true);
    expect(audiencesOf(someone, [context("event", ["helper"])], []).has("event-organizer")).toBe(true);
    expect(audiencesOf(someone, [context("event", ["race_officer"])], []).has("race-committee")).toBe(true);
  });

  test("the site's relations come from the league office, never from the summary roles", () => {
    const withRoles = { ...someone, roles: ["admin", "treasurer"] } as unknown as Account;
    expect([...audiencesOf(withRoles, [], [])]).toEqual(["sailor"]);
    expect(audiencesOf(someone, [], ["race_officer"]).has("race-committee")).toBe(true);
    expect(audiencesOf(someone, [], ["editor"]).has("administration")).toBe(true);
  });

  test("the site's admin may do everything, so reads everything", () => {
    expect([...audiencesOf(someone, [], ["admin"])].sort()).toEqual([...AUDIENCES].sort());
  });

  test("a page is mine when it is written for one of my audiences", () => {
    const mine = new Set(["sailor", "club"] as const);
    expect(isForMe(page(["club"]), mine)).toBe(true);
    expect(isForMe(page(["treasurer", "sailor"]), mine)).toBe(true);
    expect(isForMe(page(["treasurer"]), mine)).toBe(false);
  });
});
