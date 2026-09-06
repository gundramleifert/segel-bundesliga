import { Button } from "@heroui/react";
import { useMutation } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { api, type ClubAdmin, type SeriesAdmin } from "../api/client";
import { useApi, useInvalidieren, useKonto } from "../api/useApi";
import { Fehler, Laden, Leer, Seitenkopf } from "../components/Bausteine";
import { SailorsAdmin } from "./VerwaltungSegler";
import { EINGABE, fehlertext, umschalter } from "../lib/verwaltung";
import { Abschnitt, Feld, Meldung, VereinsAuswahl } from "./verwaltungBausteine";

/** Stories A-1, A-4, and A-6: Create clubs, create series, schedule events.
 *
 * The flow is deliberately top-to-bottom: **first clubs, then a series with their
 * clubs, then events for the series.** A series without clubs has no standings,
 * and an event without a series counts toward no scoring — that's why the three
 * sections are in this order, not alphabetically.
 */
export function Admin() {
  const { t } = useTranslation("admin");
  const { konto, laedt, hatRolle } = useKonto();

  if (laedt) return <Laden />;
  if (!konto) {
    return (
      <Fehler text={t("auth.notSignedInError")} />
    );
  }
  if (!hatRolle("admin", "editor")) {
    return (
      <Fehler text={t("auth.noAccessError")} />
    );
  }

  return (
    <>
      <Seitenkopf
        titel={t("page.title")}
        unterzeile={t("page.signedInAs", { displayName: konto.display_name, roles: konto.roles.join(", ") })}
      />
      <div className="grid gap-8">
        <Clubs />
        <Series editorOnly={!hatRolle("admin")} />
        <Events />
        <SailorsAdmin />
      </div>
    </>
  );
}

// ---------------------------------------------------------------------- Clubs

function Clubs() {
  const { t } = useTranslation("admin");
  const { data, error, loading } = useApi(["admin", "clubs"], (signal) =>
    api.admin.clubs(signal),
  );
  const invalidieren = useInvalidieren();
  const [name, setzeName] = useState("");
  const [kuerzel, setzeKuerzel] = useState("");
  const [ort, setzeOrt] = useState("");

  const anlegen = useMutation({
    mutationFn: () =>
      api.admin.createClub({
        name: name.trim(),
        short_name: kuerzel.trim() || null,
        city: ort.trim() || null,
      }),
    onSuccess: () => {
      setzeName("");
      setzeKuerzel("");
      setzeOrt("");
      invalidieren(["admin", "clubs"], ["clubs"]);
    },
  });

  return (
    <Abschnitt
      titel={t("clubs.title")}
      hinweis={t("clubs.description")}
    >
      <form
        className="grid gap-3 sm:grid-cols-[2fr_1fr_1fr_auto] sm:items-end"
        onSubmit={(e: FormEvent) => {
          e.preventDefault();
          anlegen.mutate();
        }}
      >
        <Feld label={t("clubs.nameLabel")}>
          <input
            className={EINGABE}
            value={name}
            onChange={(e) => setzeName(e.target.value)}
            required
            minLength={3}
            placeholder={t("clubs.namePlaceholder")}
          />
        </Feld>
        <Feld label={t("clubs.shortNameLabel")} hinweis={t("clubs.shortNameHint")}>
          <input
            className={EINGABE}
            value={kuerzel}
            onChange={(e) => setzeKuerzel(e.target.value)}
            placeholder={t("clubs.shortNamePlaceholder")}
          />
        </Feld>
        <Feld label={t("clubs.cityLabel")} hinweis={t("clubs.cityHint")}>
          <input
            className={EINGABE}
            value={ort}
            onChange={(e) => setzeOrt(e.target.value)}
            placeholder={t("clubs.cityPlaceholder")}
          />
        </Feld>
        <Button type="submit" isDisabled={anlegen.isPending || name.trim().length < 3}>
          {anlegen.isPending ? t("clubs.creatingButton") : t("clubs.createButton")}
        </Button>
      </form>

      <Meldung
        fehler={anlegen.isError ? fehlertext(anlegen.error) : null}
        erfolg={anlegen.isSuccess ? t("clubs.createdMessage", { name: anlegen.data?.name }) : null}
      />

      {loading && <Laden text={t("clubs.loadingText")} />}
      {error && <Fehler text={error} />}
      {data && (
        <p className="text-sm text-slate-600">
          {t("clubs.statsText", { count: data.length, visible: data.filter((v) => v.visible).length })}
        </p>
      )}
    </Abschnitt>
  );
}

// ----------------------------------------------------------------------- Series

function Series({ editorOnly }: { editorOnly: boolean }) {
  const { t } = useTranslation("admin");
  const serien = useApi(["admin", "series"], (signal) => api.admin.series(signal));
  const vereine = useApi(["admin", "clubs"], (signal) => api.admin.clubs(signal));
  const invalidieren = useInvalidieren();

  const [name, setzeName] = useState("");
  // No default: the year is optional, not implicitly "this year". An admin planning
  // ahead should be able to leave it blank rather than having to clear a prefilled value.
  const [jahr, setzeJahr] = useState("");
  const [von, setzeVon] = useState("");
  const [bis, setzeBis] = useState("");
  const [gewaehlt, setzeGewaehlt] = useState<Set<number>>(new Set());

  const umschalten = umschalter(setzeGewaehlt);

  const anlegen = useMutation({
    mutationFn: () =>
      api.admin.createSeries({
        name: name.trim(),
        year: jahr ? Number(jahr) : null,
        starts_on: von || null,
        ends_on: bis || null,
        clubs: [...gewaehlt],
      }),
    onSuccess: () => {
      setzeName("");
      setzeJahr("");
      setzeVon("");
      setzeBis("");
      setzeGewaehlt(new Set());
      invalidieren(["admin", "series"], ["series"], ["clubs"]);
    },
  });

  if (editorOnly) {
    return (
      <Abschnitt titel={t("series.title")}>
        <Leer>{t("series.editOnlyAdmin")}</Leer>
      </Abschnitt>
    );
  }

  return (
    <Abschnitt
      titel={t("series.title")}
      hinweis={t("series.description")}
    >
      <form
        className="grid gap-3"
        onSubmit={(e: FormEvent) => {
          e.preventDefault();
          anlegen.mutate();
        }}
      >
        <div className="grid gap-3 sm:grid-cols-[2fr_1fr]">
          <Feld label={t("series.nameLabel")}>
            <input
              className={EINGABE}
              value={name}
              onChange={(e) => setzeName(e.target.value)}
              required
              minLength={3}
              placeholder={t("series.namePlaceholder")}
            />
          </Feld>
          <Feld label={t("series.yearLabel")} hinweis={t("series.yearHint")}>
            <input
              className={EINGABE}
              type="number"
              value={jahr}
              onChange={(e) => setzeJahr(e.target.value)}
              min={1900}
              max={2200}
              placeholder={String(new Date().getFullYear())}
            />
          </Feld>
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          <Feld label={t("series.startsLabel")} hinweis={t("series.startsHint")}>
            <input
              className={EINGABE}
              type="date"
              value={von}
              onChange={(e) => setzeVon(e.target.value)}
            />
          </Feld>
          <Feld label={t("series.endsLabel")} hinweis={t("series.endsHint")}>
            <input
              className={EINGABE}
              type="date"
              value={bis}
              onChange={(e) => setzeBis(e.target.value)}
            />
          </Feld>
        </div>

        <Feld label={t("series.clubsLabel")} hinweis={t("series.clubsHint", { count: gewaehlt.size })}>
          {vereine.loading && <Laden text={t("clubs.loadingText")} />}
          {vereine.data && (
            <VereinsAuswahl
              vereine={vereine.data}
              gewaehlt={gewaehlt}
              umschalten={umschalten}
            />
          )}
        </Feld>

        <div>
          <Button type="submit" isDisabled={anlegen.isPending || name.trim().length < 3}>
            {anlegen.isPending ? t("series.creatingButton") : t("series.createButton")}
          </Button>
        </div>
      </form>

      <Meldung
        fehler={anlegen.isError ? fehlertext(anlegen.error) : null}
        erfolg={
          anlegen.isSuccess
            ? t("series.createdMessage", { name: anlegen.data?.name, count: anlegen.data?.clubs?.length ?? 0 })
            : null
        }
      />

      {serien.loading && <Laden text={t("series.loadingText")} />}
      {serien.error && <Fehler text={serien.error} />}
      {serien.data &&
        (serien.data.length ? (
          <ul className="divide-y divide-slate-100 rounded-lg border border-slate-200">
            {serien.data.map((serie) => (
              <SeriesRow
                key={serie.id}
                serie={serie}
                vereine={vereine.data ?? []}
                nachAenderung={() => invalidieren(["admin", "series"], ["series"], ["clubs"])}
              />
            ))}
          </ul>
        ) : (
          <Leer>{t("series.emptyText")}</Leer>
        ))}
    </Abschnitt>
  );
}

function SeriesRow({
  serie,
  vereine,
  nachAenderung,
}: {
  serie: SeriesAdmin;
  vereine: ClubAdmin[];
  nachAenderung: () => void;
}) {
  const { t } = useTranslation("admin");
  const [offen, setzeOffen] = useState(false);
  const [gewaehlt, setzeGewaehlt] = useState<Set<number>>(
    () => new Set((serie.clubs ?? []).map((c) => c.id)),
  );

  const speichern = useMutation({
    mutationFn: () => api.admin.setSeriesClubs(serie.id, [...gewaehlt]),
    onSuccess: () => {
      setzeOffen(false);
      nachAenderung();
    },
  });

  return (
    <li className="px-4 py-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <Link
            to={`/tabelle/${serie.id}`}
            className="font-medium underline-offset-2 hover:underline"
          >
            {serie.name}
          </Link>
          <p className="text-sm text-slate-600">
            {t("series.itemText", { count: serie.clubs?.length ?? 0, events: serie.event_count })}
          </p>
        </div>
        <Button size="sm" variant="ghost" onPress={() => setzeOffen((o) => !o)}>
          {offen ? t("series.closeButton") : t("series.editButton")}
        </Button>
      </div>

      {offen && (
        <div className="mt-3 grid gap-3">
          <VereinsAuswahl
            vereine={vereine}
            gewaehlt={gewaehlt}
            umschalten={umschalter(setzeGewaehlt)}
          />
          <div className="flex items-center gap-3">
            <Button
              size="sm"
              isDisabled={speichern.isPending}
              onPress={() => speichern.mutate()}
            >
              {speichern.isPending ? t("series.savingButton") : t("series.saveButton", { count: gewaehlt.size })}
            </Button>
            <span className="text-sm text-slate-500">
              {t("series.saveHint")}
            </span>
          </div>
          {speichern.isError && <Fehler text={fehlertext(speichern.error)} />}
        </div>
      )}
    </li>
  );
}

// --------------------------------------------------------------- Events

function Events() {
  const { t } = useTranslation("admin");
  const serien = useApi(["admin", "series"], (signal) => api.admin.series(signal));
  const vereine = useApi(["admin", "clubs"], (signal) => api.admin.clubs(signal));
  const invalidieren = useInvalidieren();

  const [titel, setzeTitel] = useState("");
  const [datum, setzeDatum] = useState("");
  const [serie, setzeSerie] = useState("");
  const [ausrichter, setzeAusrichter] = useState("");
  const [teams, setzeTeams] = useState("18");
  const [boote, setzeBoote] = useState("6");
  const [flights, setzeFlights] = useState("16");

  const anlegen = useMutation({
    mutationFn: () =>
      api.admin.createEvent({
        title: titel.trim(),
        starts_on: datum,
        series: serie ? Number(serie) : null,
        host_club_id: ausrichter ? Number(ausrichter) : null,
        team_count: Number(teams),
        boat_count: Number(boote),
        flight_count: Number(flights),
      }),
    onSuccess: () => {
      setzeTitel("");
      setzeDatum("");
      invalidieren(["admin", "series"], ["events"], ["series"]);
    },
  });

  return (
    <Abschnitt
      titel={t("events.title")}
      hinweis={t("events.description")}
    >
      <form
        className="grid gap-3"
        onSubmit={(e: FormEvent) => {
          e.preventDefault();
          anlegen.mutate();
        }}
      >
        <div className="grid gap-3 sm:grid-cols-[2fr_1fr]">
          <Feld label={t("events.nameLabel")}>
            <input
              className={EINGABE}
              value={titel}
              onChange={(e) => setzeTitel(e.target.value)}
              required
              minLength={3}
              placeholder={t("events.namePlaceholder")}
            />
          </Feld>
          <Feld label={t("events.dateLabel")}>
            <input
              className={EINGABE}
              type="date"
              value={datum}
              onChange={(e) => setzeDatum(e.target.value)}
              required
            />
          </Feld>
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          <Feld label={t("events.seriesLabel")} hinweis={t("events.seriesHint")}>
            <select
              className={EINGABE}
              value={serie}
              onChange={(e) => setzeSerie(e.target.value)}
            >
              <option value="">{t("events.seriesNone")}</option>
              {serien.data?.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </Feld>
          <Feld label={t("events.hostLabel")} hinweis={t("events.hostHint")}>
            <select
              className={EINGABE}
              value={ausrichter}
              onChange={(e) => setzeAusrichter(e.target.value)}
            >
              <option value="">{t("events.hostNone")}</option>
              {vereine.data?.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.name}
                </option>
              ))}
            </select>
          </Feld>
        </div>

        <div className="grid gap-3 sm:grid-cols-3">
          <Feld label={t("events.teamsLabel")}>
            <input
              className={EINGABE}
              type="number"
              min={2}
              max={64}
              value={teams}
              onChange={(e) => setzeTeams(e.target.value)}
            />
          </Feld>
          <Feld label={t("events.boatsLabel")}>
            <input
              className={EINGABE}
              type="number"
              min={2}
              max={20}
              value={boote}
              onChange={(e) => setzeBoote(e.target.value)}
            />
          </Feld>
          <Feld label={t("events.flightsLabel")}>
            <input
              className={EINGABE}
              type="number"
              min={1}
              max={40}
              value={flights}
              onChange={(e) => setzeFlights(e.target.value)}
            />
          </Feld>
        </div>

        <p className="text-sm text-slate-500">
          {t("events.formatText", { teams, boats: boote, races: Math.ceil(Number(teams) / Number(boote)) || 0 })}
        </p>

        <div>
          <Button
            type="submit"
            isDisabled={anlegen.isPending || titel.trim().length < 3 || !datum}
          >
            {anlegen.isPending ? t("events.creatingButton") : t("events.createButton")}
          </Button>
        </div>
      </form>

      <Meldung
        fehler={anlegen.isError ? fehlertext(anlegen.error) : null}
        erfolg={anlegen.isSuccess ? t("events.createdMessage", { title: anlegen.data?.title }) : null}
      />
    </Abschnitt>
  );
}
