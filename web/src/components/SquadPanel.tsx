import { Button } from "@heroui/react";
import { useState } from "react";
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
import { roleText } from "../lib/format";
import { INPUT_CLASS, errorText } from "../lib/admin";
import { Field } from "./Form";

/** Registering who may sail for one team — Story V-1.
 *
 * Used from two places on purpose: the admin screen, which reaches a team by picking a
 * series and then a club, and `/club`, where a club manager reaches their own team
 * directly (Story V-12). Two copies would drift, and the rules displayed here — the ten,
 * the single helm, which refusal means what — are the ones that took longest to get right.
 *
 * `readOnly` is what a club's member without organizer rights sees: the squad, and no
 * controls. Absent rather than disabled — a disabled button is a promise the server will
 * not keep.
 */
const ROLES = ["helm", "crew", "substitute"] as const;
type SquadRole = (typeof ROLES)[number];

/** What a squad is normally made of. Both numbers are **guidance the screen shows, never
 *  a rule it enforces** (Story V-1): illness and late registration have to get through,
 *  and a panel that refused the eleventh person would be wrong more often than right. */
const USUAL_SQUAD_SIZE = 10;
const USUAL_HELM_COUNT = 1;

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
  const [addRole, setAddRole] = useState<SquadRole>("crew");
  // A page of matches is what a search wants; the picker below shows them as they come.
  const results = useAsyncRows(useListSailors({ q: search || undefined }));

  const setSquad = useSetSquad({
    mutation: {
      // The squad shows up on every club page and on each member's sailor page, so both
      // are stale the moment it changes — hence the path prefixes rather than one key.
      onSuccess: () => invalidate(getGetSquadQueryKey(teamId), "/api/clubs", "/api/sailors"),
    },
  });

  /** Writes the whole squad. The endpoint takes the complete list, never a delta: an
   *  "add one" call would have to be ordered against a concurrent "remove one", and the
   *  screen has the full list in front of it anyway. */
  const save = (members: { sailor_id: number; role: SquadRole }[]) =>
    setSquad.mutate({ teamId, data: { members } });

  if (squad.loading) {
    return <Loading text={t("squad.loadingText")} testId="admin-squad-members-loading" />;
  }
  if (squad.error) {
    return <ErrorMessage text={squad.error} testId="admin-squad-members-error" />;
  }
  if (!squad.data) return null;

  const members = squad.data.members ?? [];
  const current = members.map((m) => ({ sailor_id: m.id, role: m.role as SquadRole }));
  const memberIds = new Set(current.map((m) => m.sailor_id));
  const helmCount = current.filter((m) => m.role === "helm").length;
  const seriesId = squad.data.series_id;

  /** Where this person already sails, and whether that rules them out here.
   *
   *  A person is legitimately registered in several clubs — one row per series
   *  registration — and only twice *within one series* is forbidden. So the list has to
   *  show the registrations (eighteen people in this data share a surname, and a name on
   *  its own identifies nobody) and single out the one that clashes. The endpoint still
   *  refuses it; this is a courtesy, not the enforcement. */
  const clash = (person: SailorAdmin): SailorRegistration | undefined =>
    seriesId == null
      ? undefined
      : person.registrations?.find((r) => r.series.id === seriesId);

  return (
    <div
      data-testid="admin-squad-management"
      className="grid grid-cols-[minmax(0,1fr)] gap-4 rounded-lg border border-slate-200 p-4"
    >
      <div>
        <h3 className="font-medium">
          {t("squad.headerText", { clubName: title, count: members.length })}
        </h3>
        {/* Guidance, not validation — and said out loud, so that being at nine does not
            look like an oversight and being at eleven does not look like a bug. */}
        <p data-testid="admin-squad-size-hint" className="text-sm text-slate-500">
          {t("squad.sizeHint", { count: members.length, usual: USUAL_SQUAD_SIZE })}
          {helmCount !== USUAL_HELM_COUNT && (
            <>
              {" · "}
              <span data-testid="admin-squad-helm-hint" className="text-amber-700">
                {helmCount === 0 ? t("squad.noHelmHint") : t("squad.manyHelmsHint", { count: helmCount })}
              </span>
            </>
          )}
        </p>

        {members.length ? (
          <ul data-testid="admin-squad-members-list" className="mt-2 divide-y divide-slate-100 text-sm">
            {members.map((member) => (
              <li
                key={member.id}
                data-testid={`admin-squad-member-row-${member.id}`}
                className="flex flex-wrap items-center gap-3 py-1.5"
              >
                <span className="min-w-0 flex-1 truncate">
                  {member.first_name} {member.last_name}
                </span>
                {readOnly ? (
                  <span
                    data-testid={`admin-squad-member-role-${member.id}`}
                    className="text-xs text-slate-500"
                  >
                    {roleText(member.role)}
                  </span>
                ) : (
                  <>
                    <select
                      className="rounded border border-slate-300 px-2 py-1 text-xs"
                      value={member.role}
                      onChange={(e) =>
                        save(
                          current.map((m) =>
                            m.sailor_id === member.id
                              ? { ...m, role: e.target.value as SquadRole }
                              : m,
                          ),
                        )
                      }
                      data-testid={`admin-squad-member-role-select-${member.id}`}
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
                      isDisabled={setSquad.isPending}
                      onPress={() => save(current.filter((m) => m.sailor_id !== member.id))}
                      data-testid={`admin-squad-member-remove-button-${member.id}`}
                    >
                      {t("squad.removeButton")}
                    </Button>
                  </>
                )}
              </li>
            ))}
          </ul>
        ) : (
          <Empty testId="admin-squad-members-empty">{t("squad.teamEmptyText")}</Empty>
        )}
      </div>

      {!readOnly && (
        <>
          <div className="flex flex-wrap items-end gap-3">
            <div className="min-w-0 flex-1">
              <Field label={t("squad.addLabel")} hint={t("squad.addHint")}>
                <input
                  className={INPUT_CLASS}
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder={t("squad.addPlaceholder")}
                  data-testid="admin-squad-add-search-input"
                />
              </Field>
            </div>
            {/* The role is chosen before adding, not corrected afterwards: everyone used
                to arrive as crew, so registering a helm was always two steps. */}
            <Field label={t("squad.addRoleLabel")}>
              <select
                className={INPUT_CLASS}
                value={addRole}
                onChange={(e) => setAddRole(e.target.value as SquadRole)}
                data-testid="admin-squad-add-role-select"
              >
                {ROLES.map((value) => (
                  <option key={value} value={value}>
                    {roleText(value)}
                  </option>
                ))}
              </select>
            </Field>
          </div>

          {results.data && (
            <ul
              data-testid="admin-squad-add-list"
              className="max-h-56 divide-y divide-slate-100 overflow-y-auto rounded border border-slate-200 text-sm"
            >
              {results.data
                .filter((person) => !memberIds.has(person.id))
                .map((person) => {
                  const taken = clash(person);
                  return (
                    <li
                      key={person.id}
                      data-testid={`admin-squad-candidate-${person.id}`}
                      className="flex flex-wrap items-center gap-x-3 gap-y-1 px-3 py-1.5"
                    >
                      <span className="min-w-0 flex-1 truncate">
                        {person.first_name} {person.last_name}
                      </span>
                      {taken ? (
                        <span
                          data-testid={`admin-squad-candidate-taken-${person.id}`}
                          className="text-xs text-amber-700"
                        >
                          {t("squad.alreadyInSeries", { club: taken.club.name })}
                        </span>
                      ) : (
                        <Button
                          size="sm"
                          variant="ghost"
                          isDisabled={setSquad.isPending}
                          onPress={() =>
                            save([...current, { sailor_id: person.id, role: addRole }])
                          }
                          data-testid={`admin-squad-add-button-${person.id}`}
                        >
                          {t("squad.addButtonText")}
                        </Button>
                      )}
                      {/* Every registration, not only the clashing one: this is what
                          tells two people with the same surname apart. */}
                      <span
                        data-testid={`admin-squad-candidate-clubs-${person.id}`}
                        className="w-full text-xs text-slate-500"
                      >
                        {person.registrations?.length
                          ? person.registrations
                              .map((r) => `${r.club.short_name || r.club.name} · ${r.series.name}`)
                              .join(" — ")
                          : t("squad.noRegistrations")}
                      </span>
                    </li>
                  );
                })}
            </ul>
          )}
        </>
      )}

      {setSquad.isError && (
        <ErrorMessage text={errorText(setSquad.error)} testId="admin-squad-save-error" />
      )}
    </div>
  );
}
