import { Button } from "@heroui/react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { getGetCrewQueryKey, useGetCrew, useGetSquad, useSetCrew } from "../api/generated/sbl";
import type { Member } from "../api/types";
import { useAsync, useInvalidate } from "../api/useApi";
import { errorText } from "../lib/admin";
import { roleText } from "../lib/format";
import { Empty, ErrorMessage, Loading } from "./Blocks";
import { Message } from "./Form";
import { TransferList } from "./TransferList";

/** Naming the crew for one matchday — Story V-2, reached from `/club` (Story V-12).
 *
 * The same movement as entering clubs into an event: the **squad on the left**, the
 * **crew on the right**, a click moves a person across, and **Save** writes the whole
 * list. Each person on the right carries their role for the day — helm, crew or
 * reserve — preset from their role in the squad and changed in place. The rule the
 * endpoint enforces is the one the panes show: the crew is drawn from the squad of the
 * same club (the series registration, or the entry itself for an event in no series),
 * never from a search over every sailor. `crewSize` is the matchday's usual number and
 * is guidance the panel says out loud, not a limit: illness and a reserve have to get
 * through.
 *
 * `readOnly` is what a club's plain member sees: who is named, and no panes — absent
 * rather than disabled, since the server would refuse the click anyway; the squad is then
 * not requested at all.
 */
const ROLES = ["helm", "crew", "substitute"] as const;
type Role = (typeof ROLES)[number];
const ORDER: Record<Role, number> = { helm: 0, crew: 1, substitute: 2 };

type Named = { sailor_id: number; role: Role };

function asRole(value: string): Role {
  return (ROLES as readonly string[]).includes(value) ? (value as Role) : "crew";
}

export function LineupPanel({
  eventId,
  teamId,
  squadTeamId,
  crewSize,
  readOnly = false,
  testIdPrefix = "lineup",
}: {
  eventId: number;
  /** The club's entry to this event — where the lineup is recorded. */
  teamId: number;
  /** Where the crew is drawn from. */
  squadTeamId: number;
  crewSize: number;
  readOnly?: boolean;
  testIdPrefix?: string;
}) {
  const { t } = useTranslation("club");
  const invalidate = useInvalidate();
  const crew = useAsync(useGetCrew(eventId, teamId));
  const squad = useAsync(useGetSquad(squadTeamId, { query: { enabled: !readOnly } }));
  const setCrew = useSetCrew({
    mutation: {
      // The public matchday page shows the crews too (`/api/events/{id}/crew`).
      onSuccess: () =>
        invalidate(getGetCrewQueryKey(eventId, teamId), `/api/events/${eventId}/`, "/api/clubs"),
    },
  });

  // The draft: what the right pane shows until Save. Reset whenever the saved crew
  // arrives or changes — the same rule as the clubs panel.
  const saved = crew.data?.members ?? null;
  const [draft, setDraft] = useState<Named[] | null>(null);
  useEffect(() => {
    if (saved) setDraft(saved.map((m) => ({ sailor_id: m.id, role: asRole(m.role) })));
  }, [saved]);

  if (crew.loading || (draft === null && !crew.error)) {
    return <Loading testId={`${testIdPrefix}-loading`} />;
  }
  if (crew.error) return <ErrorMessage text={crew.error} testId={`${testIdPrefix}-error`} />;
  if (!saved || draft === null) return null;

  const people = new Map<number, Member>();
  for (const m of saved) people.set(m.id, m);
  for (const m of squad.data?.members ?? []) people.set(m.id, m);

  const named = new Set(draft.map((d) => d.sailor_id));
  const selected = [...draft]
    .sort((a, b) => ORDER[a.role] - ORDER[b.role])
    .map((d) => people.get(d.sailor_id))
    .filter((m): m is Member => Boolean(m));
  const available = (squad.data?.members ?? []).filter((m) => !named.has(m.id));
  const roleOf = (id: number) => draft.find((d) => d.sailor_id === id)?.role ?? "crew";
  const dirty =
    draft.length !== saved.length ||
    draft.some((d) => saved.find((m) => m.id === d.sailor_id)?.role !== d.role);

  const save = () => setCrew.mutate({ eventId, data: { team_id: teamId, members: draft } });

  return (
    <div
      data-testid={testIdPrefix}
      className="grid grid-cols-[minmax(0,1fr)] gap-4 rounded-lg border border-slate-200 p-4"
    >
      <div>
        <h4 className="font-medium">{t("lineup.title")}</h4>
        <p data-testid={`${testIdPrefix}-size-hint`} className="text-sm text-slate-500">
          {t("lineup.sizeHint", { count: draft.length, usual: crewSize })}
          {!readOnly && !draft.some((d) => d.role === "helm") && draft.length > 0 && (
            <>
              {" · "}
              <span className="text-amber-700" data-testid={`${testIdPrefix}-no-helm`}>
                {t("lineup.noHelm")}
              </span>
            </>
          )}
        </p>
      </div>

      {readOnly ? (
        selected.length ? (
          <ul data-testid={`${testIdPrefix}-list`} className="divide-y divide-slate-100 text-sm">
            {selected.map((member) => (
              <li
                key={member.id}
                data-testid={`${testIdPrefix}-row-${member.id}`}
                className="flex items-center gap-3 py-1.5"
              >
                <span className="min-w-0 flex-1">
                  {member.first_name} {member.last_name}
                </span>
                <span className="text-xs text-slate-500">{roleText(roleOf(member.id))}</span>
              </li>
            ))}
          </ul>
        ) : (
          <Empty testId={`${testIdPrefix}-empty`}>{t("lineup.empty")}</Empty>
        )
      ) : squad.loading ? (
        <Loading testId={`${testIdPrefix}-squad-loading`} />
      ) : squad.error ? (
        <ErrorMessage text={squad.error} testId={`${testIdPrefix}-squad-error`} />
      ) : (
        <>
          {!(squad.data?.members ?? []).length && (
            <p className="text-sm text-slate-500" data-testid={`${testIdPrefix}-squad-empty`}>
              {t("lineup.squadEmpty")}
            </p>
          )}
          <TransferList
            testId={`${testIdPrefix}-panes`}
            available={available}
            selected={selected}
            label={(m) => `${m.first_name} ${m.last_name}`}
            secondary={(m) => roleText(m.role)}
            matches={(m, term) => `${m.first_name} ${m.last_name}`.toLowerCase().includes(term)}
            // Named in the role they hold in the squad; corrected in place on the right.
            onSelect={(m) => setDraft([...draft, { sailor_id: m.id, role: asRole(m.role) }])}
            onDeselect={(m) => setDraft(draft.filter((d) => d.sailor_id !== m.id))}
            selectedExtra={(m) => (
              <select
                className="shrink-0 rounded border border-slate-300 px-1.5 py-0.5 text-xs"
                value={roleOf(m.id)}
                aria-label={t("lineup.roleLabel")}
                onChange={(e) =>
                  setDraft(
                    draft.map((d) =>
                      d.sailor_id === m.id ? { ...d, role: e.target.value as Role } : d,
                    ),
                  )
                }
                data-testid={`${testIdPrefix}-role-${m.id}`}
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
              isDisabled={setCrew.isPending || !dirty}
              onPress={save}
              data-testid={`${testIdPrefix}-save`}
            >
              {setCrew.isPending ? t("lineup.saving") : t("lineup.save")}
            </Button>
            {dirty && (
              <span className="text-xs text-slate-500" data-testid={`${testIdPrefix}-unsaved`}>
                {t("lineup.unsaved")}
              </span>
            )}
          </div>
          <Message
            testId={`${testIdPrefix}-message`}
            error={setCrew.isError ? errorText(setCrew.error) : null}
            success={setCrew.isSuccess && !dirty ? t("lineup.saved") : null}
          />
        </>
      )}
    </div>
  );
}
