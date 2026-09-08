import { Button } from "@heroui/react";
import { useMutation } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { api, type BoatSpec, type ClubAdmin, type SeriesAdmin } from "../api/client";
import { useApi, useInvalidieren, useKonto } from "../api/useApi";
import { Fehler, Laden, Leer, Seitenkopf } from "../components/Bausteine";
import { BOOTSFARBEN } from "../lib/format";
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
  const [beschreibung, setzeBeschreibung] = useState(serie.description ?? "");

  const speichern = useMutation({
    mutationFn: () => api.admin.setSeriesClubs(serie.id, [...gewaehlt]),
    onSuccess: () => {
      setzeOffen(false);
      nachAenderung();
    },
  });

  const beschreibungSpeichern = useMutation({
    mutationFn: () =>
      api.admin.updateSeries(serie.id, { description: beschreibung.trim() || null }),
    onSuccess: () => nachAenderung(),
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
        <div className="mt-3 grid gap-4">
          <div className="grid gap-3">
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

          <Feld label={t("series.descriptionLabel")} hinweis={t("series.descriptionHint")}>
            <textarea
              className={EINGABE}
              rows={4}
              value={beschreibung}
              onChange={(e) => setzeBeschreibung(e.target.value)}
              placeholder={t("series.descriptionPlaceholder")}
            />
          </Feld>
          <div className="flex items-center gap-3">
            <Button
              size="sm"
              isDisabled={beschreibungSpeichern.isPending}
              onPress={() => beschreibungSpeichern.mutate()}
            >
              {beschreibungSpeichern.isPending
                ? t("series.savingButton")
                : t("series.saveDescriptionButton")}
            </Button>
            {beschreibungSpeichern.isSuccess && (
              <span className="text-sm text-emerald-700">
                {t("series.descriptionSavedMessage")}
              </span>
            )}
          </div>
          {beschreibungSpeichern.isError && (
            <Fehler text={fehlertext(beschreibungSpeichern.error)} />
          )}
        </div>
      )}
    </li>
  );
}

// --------------------------------------------------------------- Events

/** The league's predefined boat colors, in pairing-list order — same codes and order as
 *  the backend's `BOAT_COLORS` (`app/models/racing.py`), reused here from `BOOTSFARBEN`
 *  (`lib/format.ts`) so the color names shown match the rest of the site (e.g. Spieltag.tsx). */
const VORDEFINIERTE_FARBEN = Object.keys(BOOTSFARBEN);

/** Sentinel select value for "type your own color" — distinct from every real color string. */
const EIGENE_FARBE = "__custom__";

interface BootZeile {
  farbe: string;
  eigeneFarbe: string;
  name: string;
}

/** The color the backend would assign by position if boats aren't configured explicitly:
 *  the predefined colors in order, nothing beyond the sixth boat. */
function vorgabeFarbe(position: number): string {
  return position <= VORDEFINIERTE_FARBEN.length ? VORDEFINIERTE_FARBEN[position - 1] : "";
}

function leereBootZeile(position: number): BootZeile {
  return { farbe: vorgabeFarbe(position), eigeneFarbe: "", name: "" };
}

/** Resizes the boat rows to a new boat count — growing appends default rows, shrinking
 *  trims from the end, and rows in between keep whatever was already entered. Called from
 *  the size selector's `onChange`, not an effect: the boat count only ever changes because
 *  of that one event, so deriving it there avoids a redundant extra render. */
function angepassteBootZeilen(vorher: BootZeile[], ziel: number): BootZeile[] {
  if (ziel === vorher.length) return vorher;
  if (ziel < vorher.length) return vorher.slice(0, ziel);
  const zusaetzliche = Array.from({ length: ziel - vorher.length }, (_, i) =>
    leereBootZeile(vorher.length + i + 1),
  );
  return [...vorher, ...zusaetzliche];
}

/** Builds the `boats` array position by position — `number` is the row's position, `color`
 *  resolves the custom-color sentinel to its free-text value. The name is required (the
 *  sail number is not collected here); `sail_number` stays null. */
function bootsspezifikationen(zeilen: BootZeile[]): BoatSpec[] {
  return zeilen.map((zeile, index) => ({
    number: index + 1,
    color: zeile.farbe === EIGENE_FARBE ? zeile.eigeneFarbe.trim() || null : zeile.farbe || null,
    name: zeile.name.trim(),
    sail_number: null,
  }));
}

/** Whether every row has the name it now requires — gates the submit button. */
function bootNamenVollstaendig(zeilen: BootZeile[]): boolean {
  return zeilen.every((zeile) => zeile.name.trim().length > 0);
}

/** Identifies a catalog size for the <select> — teams, boats and flights together. */
function katalogSchluessel(eintrag: { teams: number; boats: number; flights: number }): string {
  return `${eintrag.teams}-${eintrag.boats}-${eintrag.flights}`;
}

function Events() {
  const { t } = useTranslation("admin");
  const serien = useApi(["admin", "series"], (signal) => api.admin.series(signal));
  const vereine = useApi(["admin", "clubs"], (signal) => api.admin.clubs(signal));
  // Only pre-computed sizes are offered here — picking a free combination of teams,
  // boats and flights would mean drawing a pairing list from scratch later, an
  // optimization run that takes minutes, not seconds (see app/pairing/catalog.py).
  // What can still be varied per event without recomputing is the seed that shuffles
  // starting positions — that's a separate step once the event exists, not part of
  // creating it.
  const katalog = useApi(["admin", "pairingCatalog"], (signal) => api.admin.pairingCatalog(signal));
  const invalidieren = useInvalidieren();

  const [titel, setzeTitel] = useState("");
  const [von, setzeVon] = useState("");
  const [bis, setzeBis] = useState("");
  const [serie, setzeSerie] = useState("");
  const [ausrichter, setzeAusrichter] = useState("");
  const [teams, setzeTeams] = useState("18");
  const [boote, setzeBoote] = useState("6");
  const [flights, setzeFlights] = useState("16");
  const [bootZeilen, setzeBootZeilen] = useState<BootZeile[]>(() =>
    Array.from({ length: 6 }, (_, i) => leereBootZeile(i + 1)),
  );

  const aktualisiereBoot = (index: number, patch: Partial<BootZeile>) =>
    setzeBootZeilen((vorher) =>
      vorher.map((zeile, i) => (i === index ? { ...zeile, ...patch } : zeile)),
    );

  const anlegen = useMutation({
    mutationFn: () =>
      api.admin.createEvent({
        title: titel.trim(),
        starts_on: von,
        ends_on: bis || null,
        series: serie ? Number(serie) : null,
        host_club_id: ausrichter ? Number(ausrichter) : null,
        team_count: Number(teams),
        boat_count: Number(boote),
        flight_count: Number(flights),
        boats: bootsspezifikationen(bootZeilen),
      }),
    onSuccess: () => {
      setzeTitel("");
      setzeVon("");
      setzeBis("");
      setzeBootZeilen(Array.from({ length: Number(boote) || 6 }, (_, i) => leereBootZeile(i + 1)));
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
        <div className="grid gap-3 sm:grid-cols-[2fr_1fr_1fr]">
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
          <Feld label={t("events.startsLabel")}>
            <input
              className={EINGABE}
              type="date"
              value={von}
              onChange={(e) => setzeVon(e.target.value)}
              required
            />
          </Feld>
          <Feld label={t("events.endsLabel")} hinweis={t("events.endsHint")}>
            <input
              className={EINGABE}
              type="date"
              value={bis}
              onChange={(e) => setzeBis(e.target.value)}
              min={von || undefined}
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

        <Feld label={t("events.setupLabel")} hinweis={t("events.setupHint")}>
          {katalog.loading && <Laden text={t("events.catalogLoadingText")} />}
          {katalog.error && <Fehler text={katalog.error} />}
          {katalog.data && katalog.data.length > 0 && (
            <select
              className={EINGABE}
              value={katalogSchluessel({ teams: Number(teams), boats: Number(boote), flights: Number(flights) })}
              onChange={(e) => {
                const eintrag = katalog.data?.find(
                  (kandidat) => katalogSchluessel(kandidat) === e.target.value,
                );
                if (!eintrag) return;
                setzeTeams(String(eintrag.teams));
                setzeBoote(String(eintrag.boats));
                setzeFlights(String(eintrag.flights));
                setzeBootZeilen((vorher) => angepassteBootZeilen(vorher, eintrag.boats));
              }}
            >
              {katalog.data.map((eintrag) => (
                <option key={katalogSchluessel(eintrag)} value={katalogSchluessel(eintrag)}>
                  {t("events.catalogOption", {
                    teams: eintrag.teams,
                    boats: eintrag.boats,
                    flights: eintrag.flights,
                  })}
                </option>
              ))}
            </select>
          )}
          {katalog.data && katalog.data.length === 0 && (
            <Fehler text={t("events.catalogEmptyText")} />
          )}
        </Feld>

        <p className="text-sm text-slate-500">
          {t("events.formatText", { teams, boats: boote, races: Math.ceil(Number(teams) / Number(boote)) || 0 })}
        </p>
        <p className="text-sm text-slate-500">
          {t("events.catalogContactHint")}{" "}
          <a
            href="https://github.com/gundramleifert"
            target="_blank"
            rel="noreferrer"
            className="underline"
          >
            github.com/gundramleifert
          </a>
        </p>

        <Feld label={t("events.boatSetupLabel")} hinweis={t("events.boatSetupHint")}>
          <div className="overflow-x-auto rounded-md border border-slate-200">
            <table className="w-full min-w-[36rem] text-sm">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50 text-left text-xs font-medium uppercase tracking-wide text-slate-500">
                  <th scope="col" className="px-3 py-2 font-medium">
                    {t("events.boatNumberLabel")}
                  </th>
                  <th scope="col" className="px-3 py-2 font-medium">
                    {t("events.boatColorLabel")}
                  </th>
                  <th scope="col" className="px-3 py-2 font-medium">
                    {t("events.boatNameLabel")}
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {bootZeilen.map((zeile, index) => (
                  <tr key={index}>
                    <td className="px-3 py-2 text-slate-500">{index + 1}</td>
                    <td className="px-3 py-2">
                      <div className="flex items-center gap-2">
                        <select
                          className={EINGABE}
                          aria-label={`${t("events.boatColorLabel")} ${index + 1}`}
                          value={zeile.farbe}
                          onChange={(e) => aktualisiereBoot(index, { farbe: e.target.value })}
                        >
                          <option value="">{t("events.boatColorNone")}</option>
                          {VORDEFINIERTE_FARBEN.map((code) => (
                            <option key={code} value={code}>
                              {t(`common:boatColor.${code}`)}
                            </option>
                          ))}
                          <option value={EIGENE_FARBE}>{t("events.boatColorCustom")}</option>
                        </select>
                        {zeile.farbe === EIGENE_FARBE && (
                          <input
                            className={EINGABE}
                            value={zeile.eigeneFarbe}
                            onChange={(e) =>
                              aktualisiereBoot(index, { eigeneFarbe: e.target.value })
                            }
                            placeholder={t("events.boatColorCustomPlaceholder")}
                            aria-label={t("events.boatColorCustomPlaceholder")}
                          />
                        )}
                      </div>
                    </td>
                    <td className="px-3 py-2">
                      <input
                        className={EINGABE}
                        value={zeile.name}
                        onChange={(e) => aktualisiereBoot(index, { name: e.target.value })}
                        required
                        placeholder={t("events.boatNamePlaceholder")}
                        aria-label={`${t("events.boatNameLabel")} ${index + 1}`}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Feld>

        <div>
          <Button
            type="submit"
            isDisabled={
              anlegen.isPending ||
              titel.trim().length < 3 ||
              !von ||
              !katalog.data?.length ||
              !bootNamenVollstaendig(bootZeilen)
            }
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
