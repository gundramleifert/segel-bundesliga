import { Button } from "@heroui/react";
import { useMutation } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { api, type SailorAdmin, type SeriesAdmin } from "../api/client";
import { useApi, useInvalidieren } from "../api/useApi";
import { Fehler, Laden, Leer } from "../components/Bausteine";
import { rolle } from "../lib/format";
import { EINGABE, fehlertext } from "../lib/verwaltung";
import { Abschnitt, Feld, Meldung } from "./verwaltungBausteine";

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
  const invalidieren = useInvalidieren();
  const [suche, setzeSuche] = useState("");
  const [vorname, setzeVorname] = useState("");
  const [nachname, setzeNachname] = useState("");
  const [email, setzeEmail] = useState("");

  const treffer = useApi(["admin", "sailors", suche], (signal) =>
    api.admin.sailors(suche, signal),
  );

  const anlegen = useMutation({
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
      invalidieren(["admin", "sailors"]);
    },
  });

  return (
    <Abschnitt
      titel={t("sailors.title")}
      hinweis={t("sailors.description")}
      testId="admin-sailors-section"
    >
      <form
        data-testid="admin-sailors-create-form"
        className="grid gap-3 sm:grid-cols-[1fr_1fr_1.4fr_auto] sm:items-end"
        onSubmit={(e: FormEvent) => {
          e.preventDefault();
          anlegen.mutate();
        }}
      >
        <Feld label={t("sailors.firstNameLabel")}>
          <input
            className={EINGABE}
            value={vorname}
            onChange={(e) => setzeVorname(e.target.value)}
            required
            data-testid="admin-sailors-first-name-input"
          />
        </Feld>
        <Feld label={t("sailors.lastNameLabel")}>
          <input
            className={EINGABE}
            value={nachname}
            onChange={(e) => setzeNachname(e.target.value)}
            required
            data-testid="admin-sailors-last-name-input"
          />
        </Feld>
        <Feld label={t("sailors.emailLabel")}>
          <input
            className={EINGABE}
            type="email"
            value={email}
            onChange={(e) => setzeEmail(e.target.value)}
            required
            placeholder={t("sailors.emailPlaceholder")}
            data-testid="admin-sailors-email-input"
          />
        </Feld>
        <Button
          type="submit"
          isDisabled={
            anlegen.isPending || !vorname.trim() || !nachname.trim() || !email.trim()
          }
          data-testid="admin-sailors-create-button"
        >
          {anlegen.isPending ? t("sailors.creatingButton") : t("sailors.createButton")}
        </Button>
      </form>

      <Meldung
        testId="admin-sailors-create-message"
        fehler={anlegen.isError ? fehlertext(anlegen.error) : null}
        erfolg={
          anlegen.isSuccess
            ? t("sailors.createdMessage", { firstName: anlegen.data?.first_name, lastName: anlegen.data?.last_name })
            : null
        }
      />

      <Feld label={t("sailors.searchLabel")} hinweis={t("sailors.searchHint")}>
        <input
          className={EINGABE}
          value={suche}
          onChange={(e) => setzeSuche(e.target.value)}
          placeholder={t("sailors.searchPlaceholder")}
          data-testid="admin-sailors-search-input"
        />
      </Feld>

      {treffer.loading && <Laden text={t("sailors.loadingText")} testId="admin-sailors-loading" />}
      {treffer.error && <Fehler text={treffer.error} testId="admin-sailors-error" />}
      {treffer.data && <SailorList segler={treffer.data} />}
    </Abschnitt>
  );
}

function SailorList({ segler }: { segler: SailorAdmin[] }) {
  const { t } = useTranslation("admin");
  if (!segler.length) return <Leer testId="admin-sailors-empty">{t("sailors.emptyText")}</Leer>;

  return (
    <ul
      data-testid="admin-sailors-list"
      className="divide-y divide-slate-100 rounded-lg border border-slate-200 text-sm"
    >
      {segler.map((person) => (
        <li
          key={person.id}
          data-testid={`admin-sailors-row-${person.id}`}
          className="flex items-center gap-3 px-4 py-2"
        >
          <Link
            to={`/segler/${person.id}`}
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
  const serien = useApi(["admin", "series"], (signal) => api.admin.series(signal));
  const [serieId, setzeSerieId] = useState<number | null>(null);

  const serie = serien.data?.find((s) => s.id === serieId) ?? null;

  return (
    <Abschnitt
      titel={t("squad.title")}
      hinweis={t("squad.description")}
      testId="admin-squad-section"
    >
      {serien.loading && <Laden text={t("squad.seriesLoadingText")} testId="admin-squad-series-loading" />}
      {serien.error && <Fehler text={serien.error} testId="admin-squad-series-error" />}

      {serien.data && (
        <Feld label={t("squad.seriesLabel")}>
          <select
            className={EINGABE}
            value={serieId ?? ""}
            onChange={(e) => setzeSerieId(e.target.value ? Number(e.target.value) : null)}
            data-testid="admin-squad-series-select"
          >
            <option value="">{t("squad.seriesNone")}</option>
            {serien.data.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        </Feld>
      )}

      {serie && <SeriesSquad serie={serie} />}
    </Abschnitt>
  );
}

function SeriesSquad({ serie }: { serie: SeriesAdmin }) {
  const { t } = useTranslation("admin");
  const [teamId, setzeTeamId] = useState<number | null>(null);
  const vereine = serie.clubs ?? [];
  const gewaehlt = vereine.find((v) => v.team_id === teamId) ?? null;

  if (!vereine.length) {
    return <Leer testId="admin-squad-club-empty">{t("squad.clubEmptyText")}</Leer>;
  }

  return (
    <>
      <Feld label={t("squad.clubLabel")}>
        <select
          className={EINGABE}
          value={teamId ?? ""}
          onChange={(e) => setzeTeamId(e.target.value ? Number(e.target.value) : null)}
          data-testid="admin-squad-club-select"
        >
          <option value="">{t("squad.clubNone")}</option>
          {vereine.map((verein) => (
            <option key={verein.team_id} value={verein.team_id}>
              {verein.name}
            </option>
          ))}
        </select>
      </Feld>

      {gewaehlt && <SquadManagement teamId={gewaehlt.team_id} verein={gewaehlt.name} />}
    </>
  );
}

function SquadManagement({ teamId, verein }: { teamId: number; verein: string }) {
  const { t } = useTranslation("admin");
  const kader = useApi(["admin", "kader", teamId], (signal) =>
    api.admin.squad(teamId, signal),
  );
  const invalidieren = useInvalidieren();
  const [suche, setzeSuche] = useState("");
  const treffer = useApi(["admin", "sailors", suche], (signal) =>
    api.admin.sailors(suche, signal),
  );

  const speichern = useMutation({
    mutationFn: (members: { sailor_id: number; role: "helm" | "crew" | "substitute" }[]) =>
      api.admin.setSquad(teamId, members),
    onSuccess: () => invalidieren(["admin", "kader", teamId], ["club"], ["sailor"]),
  });

  if (kader.loading) return <Laden text={t("squad.loadingText")} testId="admin-squad-members-loading" />;
  if (kader.error) return <Fehler text={kader.error} testId="admin-squad-members-error" />;
  if (!kader.data) return null;

  const mitglieder = kader.data.members ?? [];
  const aktuell = mitglieder.map((m) => ({
    sailor_id: m.id,
    role: m.role as "helm" | "crew" | "substitute",
  }));
  const imKader = new Set(aktuell.map((m) => m.sailor_id));

  return (
    <div data-testid="admin-squad-management" className="grid gap-4 rounded-lg border border-slate-200 p-4">
      <div>
        <h3 className="font-medium">
          {t("squad.headerText", { clubName: verein, count: mitglieder.length })}
        </h3>
        {mitglieder.length ? (
          <ul data-testid="admin-squad-members-list" className="mt-2 divide-y divide-slate-100 text-sm">
            {mitglieder.map((mitglied) => (
              <li
                key={mitglied.id}
                data-testid={`admin-squad-member-row-${mitglied.id}`}
                className="flex items-center gap-3 py-1.5"
              >
                <span className="flex-1">
                  {mitglied.first_name} {mitglied.last_name}
                </span>
                <select
                  className="rounded border border-slate-300 px-2 py-1 text-xs"
                  value={mitglied.role}
                  onChange={(e) =>
                    speichern.mutate(
                      aktuell.map((m) =>
                        m.sailor_id === mitglied.id
                          ? {
                              ...m,
                              role: e.target.value as "helm" | "crew" | "substitute",
                            }
                          : m,
                      ),
                    )
                  }
                  data-testid={`admin-squad-member-role-select-${mitglied.id}`}
                >
                  {["helm", "crew", "substitute"].map((value) => (
                    <option key={value} value={value}>
                      {rolle(value)}
                    </option>
                  ))}
                </select>
                <Button
                  size="sm"
                  variant="ghost"
                  isDisabled={speichern.isPending}
                  onPress={() =>
                    speichern.mutate(aktuell.filter((m) => m.sailor_id !== mitglied.id))
                  }
                  data-testid={`admin-squad-member-remove-button-${mitglied.id}`}
                >
                  {t("squad.removeButton")}
                </Button>
              </li>
            ))}
          </ul>
        ) : (
          <Leer testId="admin-squad-members-empty">{t("squad.teamEmptyText")}</Leer>
        )}
      </div>

      <Feld label={t("squad.addLabel")} hinweis={t("squad.addHint")}>
        <input
          className={EINGABE}
          value={suche}
          onChange={(e) => setzeSuche(e.target.value)}
          placeholder={t("squad.addPlaceholder")}
          data-testid="admin-squad-add-search-input"
        />
      </Feld>

      {treffer.data && (
        <ul
          data-testid="admin-squad-add-list"
          className="max-h-56 divide-y divide-slate-100 overflow-y-auto rounded border border-slate-200 text-sm"
        >
          {treffer.data
            .filter((person) => !imKader.has(person.id))
            .map((person) => (
              <li key={person.id} className="flex items-center gap-3 px-3 py-1.5">
                <span className="flex-1">
                  {person.first_name} {person.last_name}
                </span>
                <Button
                  size="sm"
                  variant="ghost"
                  isDisabled={speichern.isPending}
                  onPress={() =>
                    speichern.mutate([...aktuell, { sailor_id: person.id, role: "crew" }])
                  }
                  data-testid={`admin-squad-add-button-${person.id}`}
                >
                  {t("squad.addButtonText")}
                </Button>
              </li>
            ))}
        </ul>
      )}

      {speichern.isError && (
        <Fehler text={fehlertext(speichern.error)} testId="admin-squad-save-error" />
      )}
    </div>
  );
}
