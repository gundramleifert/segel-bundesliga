import { useState } from "react";

import { CrewRole } from "../api/types";

/** The roles a person holds in a squad (Story V-1) or a matchday's crew (Story V-2). */
export const ROSTER_ROLES: readonly CrewRole[] = Object.values(CrewRole);
export type RosterRole = CrewRole;

/** Helm first, then crew, then substitutes — the order both lists are shown in. */
const ORDER: Record<RosterRole, number> = {
  [CrewRole.helm]: 0,
  [CrewRole.crew]: 1,
  [CrewRole.substitute]: 2,
};

/** One person on the list, as the endpoints take it. */
export type RosterEntry = { sailor_id: number; role: RosterRole };

/** The edited copy of a saved roster — the right pane of `SquadPanel` and `LineupPanel`
 *  until Save.
 *
 * The draft is **derived**, not copied in by an effect: it is the saved list until the
 * first edit, and an edit remembers which saved list it was made on. When the saved list
 * changes (it arrives, a save refetches it, someone else changed it) the old edit no
 * longer applies and the draft is the saved list again — the same reset an effect did,
 * without a render that shows the old draft first.
 *
 * `draft` is `null` exactly while `saved` is: nothing to edit yet.
 */
export function useRosterDraft(saved: readonly { id: number; role: RosterRole }[] | null) {
  const [edit, setEdit] = useState<{ on: typeof saved; entries: RosterEntry[] } | null>(null);
  const draft: RosterEntry[] | null = !saved
    ? null
    : edit && edit.on === saved
      ? edit.entries
      : saved.map((m) => ({ sailor_id: m.id, role: m.role }));

  const change = (entries: RosterEntry[]) => setEdit({ on: saved, entries });
  const current = draft ?? [];

  return {
    draft,
    /** Whether the draft differs from what is saved — what Save waits for. */
    dirty:
      saved !== null &&
      (current.length !== saved.length ||
        current.some((d) => saved.find((m) => m.id === d.sailor_id)?.role !== d.role)),
    roleOf: (id: number): RosterRole => current.find((d) => d.sailor_id === id)?.role ?? CrewRole.crew,
    /** The draft's people in display order, helm first. */
    ordered: () => [...current].sort((a, b) => ORDER[a.role] - ORDER[b.role]),
    add: (sailorId: number, role: RosterRole) => change([...current, { sailor_id: sailorId, role }]),
    remove: (sailorId: number) => change(current.filter((d) => d.sailor_id !== sailorId)),
    setRole: (sailorId: number, role: RosterRole) =>
      change(current.map((d) => (d.sailor_id === sailorId ? { ...d, role } : d))),
  };
}
