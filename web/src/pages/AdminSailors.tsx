import { Button } from "@heroui/react";
import { useMutation } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { api, type SailorAdmin, type SeriesAdmin } from "../api/client";
import { useApi, useInvalidate } from "../api/useApi";
import { ErrorMessage, Loading, Empty } from "../components/Blocks";
import { roleText } from "../lib/format";
import { INPUT_CLASS, errorText } from "../lib/admin";
import { Section, Field, Message } from "./adminBuildingBlocks";

/** Stories V-4 and V-1: Create sailors and register a squad for a series.
 *
 * Two levels that must not be confused: The **person** exists independently of
 * any competition. The **squad** is their registration for a series—from that, a lineup
 * is drawn for each matchday.
 */
export function SailorsAdmin() {
  return (
    <>
      <CreateSailor />
      <Squad />
    </>
  );
}

// ------------------------------------------------------------------------ Person

function CreateSailor() {
  const { t } = useTranslation("admin");
  const invalidate = useInvalidate();
  const [search, setSearch] = useState("");
  const [vorname, setzeVorname] = useState("");
  const [nachname, setzeNachname] = useState("");
  const [email, setzeEmail] = useState("");

  const results = useApi(["admin", "sailors", search], (signal) =>
    api.admin.sailors(search, signal),
  );

  const create = useMutation({
    mutationFn: () =>
      api.admin.createSailor({
        first_name: vorname.trim(),
        last_name: nachname.trim(),
        email: email.trim(),
      }),
    onSuccess: () => {
      setzeVorname("");
      setzeNachname("");
      setzeEmail("");
      invalidate(["admin", "sailors"]);
    },
  });

  return (
    <Section
      title={t("sailors.title")}
      hint={t("sailors.description")}
      testId="admin-sailors-section"
    >
      <form
        data-testid="admin-sailors-create-form"
        className="grid grid-cols-[minmax(0,1fr)] gap-3 sm:grid-cols-[1fr_1fr_1.4fr_auto] sm:items-end"
        onSubmit={(e: FormEvent) => {
          e.preventDefault();
          create.mutate();
        }}
      >
        <Field label={t("sailors.firstNameLabel")}>
          <input
            className={INPUT_CLASS}
            value={vorname}
            onChange={(e) => setzeVorname(e.target.value)}
            required
            data-testid="admin-sailors-first-name-input"
          />
        </Field>
        <Field label={t("sailors.lastNameLabel")}>
          <input
            className={INPUT_CLASS}
            value={nachname}
            onChange={(e) => setzeNachname(e.target.value)}
            required
            data-testid="admin-sailors-last-name-input"
          />
        </Field>
        <Field label={t("sailors.emailLabel")}>
          <input
            className={INPUT_CLASS}
            type="email"
            value={email}
            onChange={(e) => setzeEmail(e.target.value)}
            required
            placeholder={t("sailors.emailPlaceholder")}
            data-testid="admin-sailors-email-input"
          />
        </Field>
        <Button
          type="submit"
          isDisabled={
            create.isPending || !vorname.trim() || !nachname.trim() || !email.trim()
          }
          data-testid="admin-sailors-create-button"
        >
          {create.isPending ? t("sailors.creatingButton") : t("sailors.createButton")}
        </Button>
      </form>

      <Message
        testId="admin-sailors-create-message"
        error={create.isError ? errorText(create.error) : null}
        success={
          create.isSuccess
            ? t("sailors.createdMessage", { firstName: create.data?.first_name, lastName: create.data?.last_name })
            : null
        }
      />

      <Field label={t("sailors.searchLabel")} hint={t("sailors.searchHint")}>
        <input
          className={INPUT_CLASS}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder={t("sailors.searchPlaceholder")}
          data-testid="admin-sailors-search-input"
        />
      </Field>

      {results.loading && <Loading text={t("sailors.loadingText")} testId="admin-sailors-loading" />}
      {results.error && <ErrorMessage text={results.error} testId="admin-sailors-error" />}
      {results.data && <SailorList sailors={results.data} />}
    </Section>
  );
}

function SailorList({ sailors }: { sailors: SailorAdmin[] }) {
  const { t } = useTranslation("admin");
  if (!sailors.length) return <Empty testId="admin-sailors-empty">{t("sailors.emptyText")}</Empty>;

  return (
    <ul
      data-testid="admin-sailors-list"
      className="divide-y divide-slate-100 rounded-lg border border-slate-200 text-sm"
    >
      {sailors.map((person) => (
        <li
          key={person.id}
          data-testid={`admin-sailors-row-${person.id}`}
          className="flex items-center gap-3 px-4 py-2"
        >
          <Link
            to={`/sailors/${person.id}`}
            data-testid={`admin-sailors-link-${person.id}`}
            className="font-medium underline-offset-2 hover:underline"
          >
            {person.first_name} {person.last_name}
          </Link>
          <span className="flex-1 truncate text-slate-500">{person.email ?? "—"}</span>
          <span className="shrink-0 text-slate-400">
            {person.squads === 1
              ? t("sailors.registrationsLabel")
              : t("sailors.registrationsLabelPlural", { count: person.squads ?? 0 })}
          </span>
        </li>
      ))}
    </ul>
  );
}

// ------------------------------------------------------------------------- Squad

function Squad() {
  const { t } = useTranslation("admin");
  const seriesList = useApi(["admin", "series"], (signal) => api.admin.series(signal));
  const [seriesId, setSeriesId] = useState<number | null>(null);

  const series = seriesList.data?.find((s) => s.id === seriesId) ?? null;

  return (
    <Section
      title={t("squad.title")}
      hint={t("squad.description")}
      testId="admin-squad-section"
    >
      {seriesList.loading && <Loading text={t("squad.seriesLoadingText")} testId="admin-squad-series-loading" />}
      {seriesList.error && <ErrorMessage text={seriesList.error} testId="admin-squad-series-error" />}

      {seriesList.data && (
        <Field label={t("squad.seriesLabel")}>
          <select
            className={INPUT_CLASS}
            value={seriesId ?? ""}
            onChange={(e) => setSeriesId(e.target.value ? Number(e.target.value) : null)}
            data-testid="admin-squad-series-select"
          >
            <option value="">{t("squad.seriesNone")}</option>
            {seriesList.data.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        </Field>
      )}

      {series && <SeriesSquad series={series} />}
    </Section>
  );
}

function SeriesSquad({ series }: { series: SeriesAdmin }) {
  const { t } = useTranslation("admin");
  const [teamId, setzeTeamId] = useState<number | null>(null);
  const clubs = series.clubs ?? [];
  const selectedClub = clubs.find((v) => v.team_id === teamId) ?? null;

  if (!clubs.length) {
    return <Empty testId="admin-squad-club-empty">{t("squad.clubEmptyText")}</Empty>;
  }

  return (
    <>
      <Field label={t("squad.clubLabel")}>
        <select
          className={INPUT_CLASS}
          value={teamId ?? ""}
          onChange={(e) => setzeTeamId(e.target.value ? Number(e.target.value) : null)}
          data-testid="admin-squad-club-select"
        >
          <option value="">{t("squad.clubNone")}</option>
          {clubs.map((clubName) => (
            <option key={clubName.team_id} value={clubName.team_id}>
              {clubName.name}
            </option>
          ))}
        </select>
      </Field>

      {selectedClub && <SquadManagement teamId={selectedClub.team_id} clubName={selectedClub.name} />}
    </>
  );
}

function SquadManagement({ teamId, clubName }: { teamId: number; clubName: string }) {
  const { t } = useTranslation("admin");
  const squad = useApi(["admin", "squad", teamId], (signal) =>
    api.admin.squad(teamId, signal),
  );
  const invalidate = useInvalidate();
  const [search, setSearch] = useState("");
  const results = useApi(["admin", "sailors", search], (signal) =>
    api.admin.sailors(search, signal),
  );

  const save = useMutation({
    mutationFn: (members: { sailor_id: number; role: "helm" | "crew" | "substitute" }[]) =>
      api.admin.setSquad(teamId, members),
    onSuccess: () => invalidate(["admin", "squad", teamId], ["club"], ["sailor"]),
  });

  if (squad.loading) return <Loading text={t("squad.loadingText")} testId="admin-squad-members-loading" />;
  if (squad.error) return <ErrorMessage text={squad.error} testId="admin-squad-members-error" />;
  if (!squad.data) return null;

  const members = squad.data.members ?? [];
  const currentMembers = members.map((m) => ({
    sailor_id: m.id,
    role: m.role as "helm" | "crew" | "substitute",
  }));
  const memberIds = new Set(currentMembers.map((m) => m.sailor_id));

  return (
    <div data-testid="admin-squad-management" className="grid grid-cols-[minmax(0,1fr)] gap-4 rounded-lg border border-slate-200 p-4">
      <div>
        <h3 className="font-medium">
          {t("squad.headerText", { clubName: clubName, count: members.length })}
        </h3>
        {members.length ? (
          <ul data-testid="admin-squad-members-list" className="mt-2 divide-y divide-slate-100 text-sm">
            {members.map((member) => (
              <li
                key={member.id}
                data-testid={`admin-squad-member-row-${member.id}`}
                className="flex items-center gap-3 py-1.5"
              >
                <span className="flex-1">
                  {member.first_name} {member.last_name}
                </span>
                <select
                  className="rounded border border-slate-300 px-2 py-1 text-xs"
                  value={member.role}
                  onChange={(e) =>
                    save.mutate(
                      currentMembers.map((m) =>
                        m.sailor_id === member.id
                          ? {
                              ...m,
                              role: e.target.value as "helm" | "crew" | "substitute",
                            }
                          : m,
                      ),
                    )
                  }
                  data-testid={`admin-squad-member-role-select-${member.id}`}
                >
                  {["helm", "crew", "substitute"].map((value) => (
                    <option key={value} value={value}>
                      {roleText(value)}
                    </option>
                  ))}
                </select>
                <Button
                  size="sm"
                  variant="ghost"
                  isDisabled={save.isPending}
                  onPress={() =>
                    save.mutate(currentMembers.filter((m) => m.sailor_id !== member.id))
                  }
                  data-testid={`admin-squad-member-remove-button-${member.id}`}
                >
                  {t("squad.removeButton")}
                </Button>
              </li>
            ))}
          </ul>
        ) : (
          <Empty testId="admin-squad-members-empty">{t("squad.teamEmptyText")}</Empty>
        )}
      </div>

      <Field label={t("squad.addLabel")} hint={t("squad.addHint")}>
        <input
          className={INPUT_CLASS}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder={t("squad.addPlaceholder")}
          data-testid="admin-squad-add-search-input"
        />
      </Field>

      {results.data && (
        <ul
          data-testid="admin-squad-add-list"
          className="max-h-56 divide-y divide-slate-100 overflow-y-auto rounded border border-slate-200 text-sm"
        >
          {results.data
            .filter((person) => !memberIds.has(person.id))
            .map((person) => (
              <li key={person.id} className="flex items-center gap-3 px-3 py-1.5">
                <span className="flex-1">
                  {person.first_name} {person.last_name}
                </span>
                <Button
                  size="sm"
                  variant="ghost"
                  isDisabled={save.isPending}
                  onPress={() =>
                    save.mutate([...currentMembers, { sailor_id: person.id, role: "crew" }])
                  }
                  data-testid={`admin-squad-add-button-${person.id}`}
                >
                  {t("squad.addButtonText")}
                </Button>
              </li>
            ))}
        </ul>
      )}

      {save.isError && (
        <ErrorMessage text={errorText(save.error)} testId="admin-squad-save-error" />
      )}
    </div>
  );
}
