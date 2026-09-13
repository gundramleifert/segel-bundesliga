import { Button } from "@heroui/react";
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";

import {
  getListSailorsQueryKey,
  useCreateSailor,
  useListAllSeries,
  useListSailors,
} from "../api/generated/sbl";
import type { SailorAdmin, SeriesAdmin } from "../api/types";
import { useAsync, useInvalidate } from "../api/useApi";
import { ErrorMessage, Loading, Empty } from "../components/Blocks";
import { SquadPanel } from "../components/SquadPanel";
import { INPUT_CLASS, errorText } from "../lib/admin";
import { Section, Field, Message } from "../components/Form";

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

  const results = useAsync(useListSailors({ q: search || undefined }));

  const create = useCreateSailor({
    mutation: {
      onSuccess: () => {
        setzeVorname("");
        setzeNachname("");
        setzeEmail("");
        // No params: the generated key is `["/api/admin/sailors"]`, which is a prefix of
        // every search variant, so one call clears them all.
        invalidate(getListSailorsQueryKey());
      },
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
          create.mutate({
            data: {
              first_name: vorname.trim(),
              last_name: nachname.trim(),
              email: email.trim(),
            },
          });
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
  const seriesList = useAsync(useListAllSeries());
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

      {selectedClub && <SquadPanel teamId={selectedClub.team_id} title={selectedClub.name} />}
    </>
  );
}
