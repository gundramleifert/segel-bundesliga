import { Button } from "@heroui/react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import {
  getGetSquadQueryKey,
  useGetSquad,
  useListSailors,
  useSetSquad,
} from "../api/generated/sbl";
import type { SailorAdmin, SailorRegistration } from "../api/types";
import { useAsync, useAsyncRows, useInvalidate } from "../api/useApi";
import { ErrorMessage, Loading, Empty } from "./Blocks";
import { Message } from "./Form";
import { TransferList } from "./TransferList";
import { roleText } from "../lib/format";
import { errorText } from "../lib/admin";

/** Registering who may sail for one team — Story V-1.
 *
 * The same movement as entering clubs into an event and naming a matchday's crew:
 * sailors on the **left**, found by name (the search goes to the server — the register
 * has hundreds of people), the **squad on the right**, a click moves a person across, the
 * role sits beside each name, and **Save** writes the whole list. A person already
 * registered for another club *in this series* is shown on the left with that reason and
 * cannot be moved (the endpoint refuses it anyway); every row says where the person
 * already sails, because eighteen people in this data share a surname.
 *
 * Used from two places on purpose: the admin screen, which reaches a team by picking a
 * series and then a club, and `/club`, where a club manager reaches their own team
 * directly (Story V-12). Two copies would drift, and the rules displayed here — the ten,
 * the single helm, which refusal means what — are the ones that took longest to get right.
 *
 * `readOnly` is what a club's member without organizer rights sees: the squad, and no
 * panes. Absent rather than disabled — a disabled button is a promise the server will
 * not keep.
 */
const ROLES = ["helm", "crew", "substitute"] as const;
type SquadRole = (typeof ROLES)[number];
const ORDER: Record<SquadRole, number> = { helm: 0, crew: 1, substitute: 2 };

/** One helm is the usual shape — guidance the screen shows, never a rule (Story V-1). The
 *  squad's *size* comes with the squad (`squad_min`, `squad_max`, set per series or per
 *  stand-alone event): the maximum is enforced on save and the left pane offers nobody
 *  once it is reached; the minimum is said in amber and saves anyway, because a squad is
 *  built up over weeks. */
const USUAL_HELM_COUNT = 1;

type Entry = { sailor_id: number; role: SquadRole };
type Person = { id: number; first_name: string; last_name: string; registrations?: SailorRegistration[] | null };

function asRole(value: string): SquadRole {
  return (ROLES as readonly string[]).includes(value) ? (value as SquadRole) : "crew";
}

export function SquadPanel({
  teamId,
  title,
  readOnly = false,
}: {
  teamId: number;
  /** Names what this squad belongs to — a club on the admin screen, a series on `/club`. */
  title: string;
  readOnly?: boolean;
}) {
  const { t } = useTranslation("admin");
  const squad = useAsync(useGetSquad(teamId));
  const invalidate = useInvalidate();
  const [search, setSearch] = useState("");
  // A page of matches is what a search wants; the left pane shows them as they come.
  const results = useAsyncRows(
    useListSailors({ q: search.trim() || undefined }, { query: { enabled: !readOnly } }),
  );

  const setSquad = useSetSquad({
    mutation: {
      // The squad shows up on every club page and on each member's sailor page, so both
      // are stale the moment it changes — hence the path prefixes rather than one key.
      onSuccess: () => invalidate(getGetSquadQueryKey(teamId), "/api/clubs", "/api/sailors"),
    },
  });

  // The draft: the right pane until Save. Reset whenever the saved squad arrives or changes.
  const saved = squad.data?.members ?? null;
  const [draft, setDraft] = useState<Entry[] | null>(null);
  useEffect(() => {
    if (saved) setDraft(saved.map((m) => ({ sailor_id: m.id, role: asRole(m.role) })));
  }, [saved]);

  if (squad.loading || (draft === null && !squad.error)) {
    return <Loading text={t("squad.loadingText")} testId="admin-squad-members-loading" />;
  }
  if (squad.error) {
    return <ErrorMessage text={squad.error} testId="admin-squad-members-error" />;
  }
  if (!squad.data || !saved || draft === null) return null;

  const seriesId = squad.data.series_id;
  const people = new Map<number, Person>();
  for (const m of saved) people.set(m.id, m);
  for (const p of results.data ?? []) people.set(p.id, p);

  const inDraft = new Set(draft.map((d) => d.sailor_id));
  const roleOf = (id: number) => draft.find((d) => d.sailor_id === id)?.role ?? "crew";
  const selected = [...draft]
    .sort((a, b) => ORDER[a.role] - ORDER[b.role])
    .map((d) => people.get(d.sailor_id))
    .filter((p): p is Person => Boolean(p));
  const available = (results.data ?? []).filter((p) => !inDraft.has(p.id));
  const helmCount = draft.filter((d) => d.role === "helm").length;
  const { squad_min: squadMin, squad_max: squadMax } = squad.data;
  const full = draft.length >= squadMax;
  const dirty =
    draft.length !== saved.length ||
    draft.some((d) => saved.find((m) => m.id === d.sailor_id)?.role !== d.role);

  /** Where this person already sails, and whether that rules them out here.
   *
   *  A person is legitimately registered in several clubs — one row per series
   *  registration — and only twice *within one series* is forbidden. The endpoint still
   *  refuses it; this is a courtesy, not the enforcement. */
  const clash = (person: SailorAdmin | Person): SailorRegistration | undefined =>
    seriesId == null ? undefined : person.registrations?.find((r) => r.series.id === seriesId);
  const sailsFor = (person: Person) =>
    person.registrations?.length
      ? person.registrations
          .map((r) => `${r.club.short_name || r.club.name} · ${r.series.name}`)
          .join(" — ")
      : t("squad.noRegistrations");

  /** Writes the whole squad. The endpoint takes the complete list, never a delta. */
  const save = () => setSquad.mutate({ teamId, data: { members: draft } });

  return (
    <div
      data-testid="admin-squad-management"
      className="grid grid-cols-[minmax(0,1fr)] gap-4 rounded-lg border border-slate-200 bg-slate-50 p-4"
    >
      <div>
        <h3 className="font-medium">
          {t("squad.headerText", { clubName: title, count: draft.length })}
        </h3>
        {/* Guidance, not validation — and said out loud, so that being at nine does not
            look like an oversight and being at eleven does not look like a bug. */}
        <p data-testid="admin-squad-size-hint" className="text-sm text-slate-500">
          {t("squad.sizeHint", { count: draft.length, min: squadMin, max: squadMax })}
          {draft.length < squadMin && (
            <>
              {" · "}
              <span data-testid="admin-squad-min-hint" className="text-amber-700">
                {t("squad.belowMinHint", { min: squadMin })}
              </span>
            </>
          )}
          {full && (
            <>
              {" · "}
              <span data-testid="admin-squad-max-hint">{t("squad.atMaxHint", { max: squadMax })}</span>
            </>
          )}
          {helmCount !== USUAL_HELM_COUNT && (
            <>
              {" · "}
              <span data-testid="admin-squad-helm-hint" className="text-amber-700">
                {helmCount === 0 ? t("squad.noHelmHint") : t("squad.manyHelmsHint", { count: helmCount })}
              </span>
            </>
          )}
        </p>
      </div>

      {readOnly ? (
        selected.length ? (
          <ul data-testid="admin-squad-members-list" className="divide-y divide-slate-100 text-sm">
            {selected.map((member) => (
              <li
                key={member.id}
                data-testid={`admin-squad-member-row-${member.id}`}
                className="flex items-center gap-3 py-1.5"
              >
                <span className="min-w-0 flex-1 truncate">
                  {member.first_name} {member.last_name}
                </span>
                <span data-testid={`admin-squad-member-role-${member.id}`} className="text-xs text-slate-500">
                  {roleText(roleOf(member.id))}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <Empty testId="admin-squad-members-empty">{t("squad.teamEmptyText")}</Empty>
        )
      ) : (
        <>
          <TransferList
            testId="admin-squad-panes"
            available={available}
            selected={selected}
            label={(p) => `${p.first_name} ${p.last_name}`}
            detail={sailsFor}
            disabledReason={(p) => {
              const taken = clash(p);
              if (taken) return t("squad.alreadyInSeries", { club: taken.club.name });
              return full ? t("squad.fullReason", { max: squadMax }) : null;
            }}
            filterValue={search}
            onFilterChange={setSearch}
            filterPlaceholder={t("squad.addPlaceholder")}
            availableLoading={results.loading}
            onSelect={(p) => setDraft([...draft, { sailor_id: p.id, role: "crew" }])}
            onDeselect={(p) => setDraft(draft.filter((d) => d.sailor_id !== p.id))}
            selectedExtra={(p) => (
              <select
                className="shrink-0 rounded border border-slate-300 px-1.5 py-0.5 text-xs"
                value={roleOf(p.id)}
                aria-label={t("squad.addRoleLabel")}
                onChange={(e) =>
                  setDraft(
                    draft.map((d) =>
                      d.sailor_id === p.id ? { ...d, role: e.target.value as SquadRole } : d,
                    ),
                  )
                }
                data-testid={`admin-squad-role-${p.id}`}
              >
                {ROLES.map((value) => (
                  <option key={value} value={value}>
                    {roleText(value)}
                  </option>
                ))}
              </select>
            )}
          />
          <div className="flex flex-wrap items-center gap-3">
            <Button
              size="sm"
              isDisabled={setSquad.isPending || !dirty}
              onPress={save}
              data-testid="admin-squad-save"
            >
              {setSquad.isPending ? t("squad.saving") : t("squad.save")}
            </Button>
            {dirty && (
              <span className="text-xs text-slate-500" data-testid="admin-squad-unsaved">
                {t("squad.unsaved")}
              </span>
            )}
          </div>
          <Message
            testId="admin-squad-message"
            error={setSquad.isError ? errorText(setSquad.error) : null}
            success={setSquad.isSuccess && !dirty ? t("squad.saved") : null}
          />
        </>
      )}
    </div>
  );
}
