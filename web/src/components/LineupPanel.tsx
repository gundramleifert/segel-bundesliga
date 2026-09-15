import { Button } from "@heroui/react";
import { useTranslation } from "react-i18next";

import {
  getGetCrewQueryKey,
  useGetCrew,
  useGetSquad,
  useSetCrew,
} from "../api/generated/sbl";
import { useAsync, useInvalidate } from "../api/useApi";
import { errorText } from "../lib/admin";
import { roleText } from "../lib/format";
import { Empty, ErrorMessage, Loading } from "./Blocks";
import { Message } from "./Form";

/** Naming the crew for one matchday — Story V-2, reached from `/club` (Story V-12).
 *
 * The rule the endpoint enforces is the one the panel shows: the crew is drawn from the
 * **squad** of the same club (the series registration, or the entry itself for an event
 * in no series), so the candidates are the squad members not yet named — never a search
 * over every sailor. `crewSize` is the matchday's usual number and is guidance the panel
 * says out loud, not a limit: illness and a substitute have to get through.
 *
 * `readOnly` is what a club's plain member sees: who is named, and no controls — absent
 * rather than disabled, since the server would refuse the click anyway. The squad is
 * then not requested at all, because a member may not read it.
 */
const ROLES = ["helm", "crew", "substitute"] as const;
type Role = (typeof ROLES)[number];

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

  if (crew.loading) return <Loading testId={`${testIdPrefix}-loading`} />;
  if (crew.error) return <ErrorMessage text={crew.error} testId={`${testIdPrefix}-error`} />;
  if (!crew.data) return null;

  const members = crew.data.members ?? [];
  const current = members.map((m) => ({ sailor_id: m.id, role: m.role as Role }));
  const named = new Set(current.map((m) => m.sailor_id));
  const candidates = (squad.data?.members ?? []).filter((m) => !named.has(m.id));

  /** The whole lineup, every time — the endpoint takes the complete list, never a delta. */
  const save = (next: { sailor_id: number; role: Role }[]) =>
    setCrew.mutate({ eventId, data: { team_id: teamId, members: next } });

  return (
    <div
      data-testid={testIdPrefix}
      className="grid grid-cols-[minmax(0,1fr)] gap-4 rounded-lg border border-slate-200 p-4"
    >
      <div>
        <h4 className="font-medium">{t("lineup.title")}</h4>
        <p data-testid={`${testIdPrefix}-size-hint`} className="text-sm text-slate-500">
          {t("lineup.sizeHint", { count: members.length, usual: crewSize })}
        </p>
        {members.length ? (
          <ul data-testid={`${testIdPrefix}-list`} className="mt-2 divide-y divide-slate-100 text-sm">
            {members.map((member) => (
              <li
                key={member.id}
                data-testid={`${testIdPrefix}-row-${member.id}`}
                className="flex flex-wrap items-center gap-3 py-1.5"
              >
                <span className="min-w-[7rem] flex-1 break-words">
                  {member.first_name} {member.last_name}
                </span>
                {readOnly ? (
                  <span className="text-xs text-slate-500">{roleText(member.role)}</span>
                ) : (
                  <>
                    <select
                      className="rounded border border-slate-300 px-2 py-1 text-xs"
                      value={member.role}
                      disabled={setCrew.isPending}
                      onChange={(e) =>
                        save(
                          current.map((m) =>
                            m.sailor_id === member.id ? { ...m, role: e.target.value as Role } : m,
                          ),
                        )
                      }
                      data-testid={`${testIdPrefix}-role-${member.id}`}
                    >
                      {ROLES.map((value) => (
                        <option key={value} value={value}>
                          {roleText(value)}
                        </option>
                      ))}
                    </select>
                    <Button
                      size="sm"
                      variant="ghost"
                      isDisabled={setCrew.isPending}
                      onPress={() => save(current.filter((m) => m.sailor_id !== member.id))}
                      data-testid={`${testIdPrefix}-remove-${member.id}`}
                    >
                      {t("lineup.remove")}
                    </Button>
                  </>
                )}
              </li>
            ))}
          </ul>
        ) : (
          <Empty testId={`${testIdPrefix}-empty`}>{t("lineup.empty")}</Empty>
        )}
      </div>

      {!readOnly && (
        <div>
          <h5 className="text-sm font-medium text-slate-700">{t("lineup.fromSquad")}</h5>
          {squad.loading ? (
            <Loading testId={`${testIdPrefix}-squad-loading`} />
          ) : squad.error ? (
            <ErrorMessage text={squad.error} testId={`${testIdPrefix}-squad-error`} />
          ) : candidates.length ? (
            <ul
              data-testid={`${testIdPrefix}-candidates`}
              className="mt-2 max-h-64 divide-y divide-slate-100 overflow-y-auto rounded border border-slate-200 text-sm"
            >
              {candidates.map((person) => (
                <li
                  key={person.id}
                  data-testid={`${testIdPrefix}-candidate-${person.id}`}
                  className="flex flex-wrap items-center gap-3 px-3 py-1.5"
                >
                  <span className="min-w-[7rem] flex-1 break-words">
                    {person.first_name} {person.last_name}
                  </span>
                  <span className="text-xs text-slate-500">{roleText(person.role)}</span>
                  <Button
                    size="sm"
                    variant="ghost"
                    isDisabled={setCrew.isPending}
                    // Named in the role they hold in the squad; correct it in the row above.
                    onPress={() =>
                      save([
                        ...current,
                        {
                          sailor_id: person.id,
                          role: (ROLES as readonly string[]).includes(person.role)
                            ? (person.role as Role)
                            : "crew",
                        },
                      ])
                    }
                    data-testid={`${testIdPrefix}-add-${person.id}`}
                  >
                    {t("lineup.add")}
                  </Button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-1 text-sm text-slate-500" data-testid={`${testIdPrefix}-candidates-empty`}>
              {(squad.data?.members ?? []).length ? t("lineup.allNamed") : t("lineup.squadEmpty")}
            </p>
          )}
        </div>
      )}
      <Message testId={`${testIdPrefix}-message`} error={setCrew.isError ? errorText(setCrew.error) : null} />
    </div>
  );
}
