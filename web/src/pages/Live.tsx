import maplibregl, { type GeoJSONSource, type Map as MapLibreMap, Marker } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";

import {
  getGetEventLiveQueryKey,
  getGetEventQueryKey,
  useGetEvent,
  useGetEventLive,
  useLayDefaultEventCourse,
  useStartEmulation,
} from "../api/generated/sbl";
import type { Course, LiveBoat, LiveRace } from "../api/types";
import { useAccount, useAsync, useInvalidate } from "../api/useApi";
import { useLive } from "../api/useLive";
import { ErrorMessage, LiveBadge, Loading, PageHeader } from "../components/Blocks";
import { DEV_TOOLS } from "../dev/devTools";
import { errorText } from "../lib/admin";
import { boatColor } from "../lib/format";
import { clock, useNow } from "../lib/useNow";

/** Stories L-1 and L-2: the boats on a real map, with the course, their legs and a live rank.
 *
 * The map is OpenStreetMap through MapLibre; the boats are markers rotated to their course
 * over ground, each with a minute of trail; the marks and the start, gate and finish lines
 * come from the course the committee laid. Everything on the right-hand panel — leg, speed,
 * distance to go, rank, finish order — is what the server derived from the fixes; nothing is
 * computed here. Positions arrive inline over the live stream (Story B-5's one exception);
 * everything else on the page refetches on a `change` frame like every other page.
 */
export function Live() {
  const { t } = useTranslation("live");
  const { id = "" } = useParams();
  const eventId = Number(id);
  const { hasRole } = useAccount();
  const committee = hasRole("admin", "race_officer");

  const detail = useAsync(useGetEvent(eventId));
  const initial = useAsync(useGetEventLive(eventId));
  // The newest picture wins, whether it came by the first fetch or by the stream — derived
  // here rather than copied into state by an effect, so the two can never disagree.
  const [streamed, setStreamed] = useState<LiveRace | null>(null);
  const fetched = initial.data ?? null;
  const snapshot = streamed && (!fetched || streamed.t >= fetched.t) ? streamed : fetched;
  const state = useLive(
    detail.data?.event.published ? `event:${eventId}` : null,
    [getGetEventQueryKey(eventId), getGetEventLiveQueryKey(eventId)],
    { onPositions: (payload) => setStreamed(payload as LiveRace) },
  );
  const [follow, setFollow] = useState(true);
  const mapRef = useRef<MapLibreMap | null>(null);

  if (detail.loading || initial.loading) return <Loading text={t("loading")} testId="live-loading" />;
  const error = detail.error ?? initial.error;
  if (error) return <ErrorMessage text={error} testId="live-error" />;
  if (!detail.data) return null;

  return (
    <>
      <PageHeader title={`${detail.data.event.title} · ${t("title")}`} testId="live-header" />
      <div className="grid gap-4 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <div className="min-w-0">
          <RaceLine snapshot={snapshot} state={state} />
          <CourseMap snapshot={snapshot} follow={follow} mapRef={mapRef} />
          <div className="mt-2 flex flex-wrap items-center gap-3 text-sm">
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={follow}
                onChange={(e) => setFollow(e.target.checked)}
                data-testid="live-follow"
              />
              {t("controls.follow")}
            </label>
            <span className="text-xs text-slate-500">{t("attribution")}</span>
          </div>
        </div>
        <div className="min-w-0">
          <Panel snapshot={snapshot} />
          {committee && (
            <CommitteeControls eventId={eventId} mapRef={mapRef} hasCourse={Boolean(snapshot?.course)} />
          )}
        </div>
      </div>
    </>
  );
}

function RaceLine({ snapshot, state }: { snapshot: LiveRace | null; state: "live" | "reconnecting" | "off" }) {
  const { t } = useTranslation("live");
  const now = useNow();
  const race = snapshot?.race ?? null;
  return (
    <div className="mb-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm" data-testid="live-race-line">
      <span className="font-semibold text-slate-900" data-testid="live-race-heading">
        {race
          ? t(race.status === "running" ? "race.running" : "race.finished", { sequence: race.sequence })
          : t("race.none")}
      </span>
      {race?.status === "running" && race.started_at && (
        <span className="tabular-nums text-slate-600" data-testid="live-elapsed">
          {t("race.elapsed", { time: clock(now - Date.parse(race.started_at)) })}
        </span>
      )}
      {race?.signal && <span className="text-amber-800">{t("race.signal", { signal: race.signal })}</span>}
      {snapshot?.next_race && (
        <span className="text-slate-500" data-testid="live-next-race">
          {t("race.next", { sequence: snapshot.next_race.sequence })}
        </span>
      )}
      <LiveBadge state={state} testId="live-badge" />
    </div>
  );
}

// ------------------------------------------------------------------------- the map

const OSM_STYLE = {
  version: 8 as const,
  sources: {
    osm: {
      type: "raster" as const,
      tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
      tileSize: 256,
      attribution: "© OpenStreetMap contributors",
    },
  },
  layers: [{ id: "osm", type: "raster" as const, source: "osm" }],
};

type LngLat = [number, number];
type Data = Parameters<GeoJSONSource["setData"]>[0];

function lngLat(mark: { lat: number; lon: number }): LngLat {
  return [mark.lon, mark.lat];
}

function centre(a: LngLat, b: LngLat): LngLat {
  return [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2];
}

/** The lines of the course: start, gate and finish lines, and the legs between them, dashed. */
function courseLines(course: Course): Data {
  const at = (role: string) => {
    const mark = course.marks.find((m) => m.role === role);
    return mark ? lngLat(mark) : null;
  };
  const committee = at("committee_boat");
  const pin = at("start_pin");
  const windward = at("windward");
  const gateLeft = at("gate_left");
  const gateRight = at("gate_right");
  const finishPin = at("finish_pin");
  const features: { type: "Feature"; geometry: { type: "LineString"; coordinates: LngLat[] }; properties: { kind: string } }[] = [];
  const line = (kind: string, points: (LngLat | null)[]) => {
    if (points.every(Boolean)) {
      features.push({ type: "Feature", geometry: { type: "LineString", coordinates: points as LngLat[] }, properties: { kind } });
    }
  };
  line("start", [committee, pin]);
  line("gate", [gateLeft, gateRight]);
  const finishAnchor = course.finish_upwind ? windward : committee;
  line("finish", [finishAnchor, finishPin]);
  if (committee && pin && windward && gateLeft && gateRight) {
    const startCentre = centre(committee, pin);
    const gateCentre = centre(gateLeft, gateRight);
    const legs: LngLat[] = [startCentre];
    for (let lap = 1; lap <= course.laps; lap += 1) {
      legs.push(windward);
      if (!(lap === course.laps && course.finish_upwind)) legs.push(gateCentre);
    }
    if (finishAnchor && finishPin) legs.push(centre(finishAnchor, finishPin));
    line("leg", legs);
  }
  return { type: "FeatureCollection", features } as Data;
}

function trails(boats: LiveBoat[]): Data {
  return {
    type: "FeatureCollection",
    features: boats
      .filter((b) => b.trail.length > 1)
      .map((b) => ({
        type: "Feature",
        geometry: { type: "LineString", coordinates: b.trail.map(([lat, lon]) => [lon, lat]) },
        properties: { color: boatColor(b.color).hex },
      })),
  } as Data;
}

function boatElement(hex: string, label: string): HTMLDivElement {
  const el = document.createElement("div");
  el.className = "flex flex-col items-center";
  const arrow = document.createElement("div");
  arrow.className = "live-arrow h-0 w-0 border-x-[8px] border-b-[22px] border-x-transparent drop-shadow";
  arrow.style.borderBottomColor = hex;
  const text = document.createElement("div");
  text.className = "mt-0.5 rounded bg-white/85 px-1 text-[10px] font-semibold leading-tight text-slate-900";
  text.textContent = label;
  el.append(arrow, text);
  return el;
}

function markElement(role: string, label: string): HTMLDivElement {
  const el = document.createElement("div");
  el.className = "flex flex-col items-center";
  const dot = document.createElement("div");
  dot.className = `size-3.5 rounded-full border-2 border-white shadow ${
    role === "committee_boat" ? "bg-slate-900" : role === "finish_pin" ? "bg-blue-600" : "bg-orange-500"
  }`;
  const text = document.createElement("div");
  text.className = "mt-0.5 rounded bg-white/85 px-1 text-[10px] font-medium leading-tight text-slate-700";
  text.textContent = label;
  el.append(dot, text);
  return el;
}

function CourseMap({
  snapshot,
  follow,
  mapRef,
}: {
  snapshot: LiveRace | null;
  follow: boolean;
  mapRef: React.MutableRefObject<MapLibreMap | null>;
}) {
  const { t } = useTranslation("live");
  const container = useRef<HTMLDivElement | null>(null);
  const [ready, setReady] = useState(false);
  const boatMarkers = useRef(new Map<number, { marker: Marker; arrow: HTMLElement; text: HTMLElement }>());
  const markMarkers = useRef(new Map<string, Marker>());
  const fitted = useRef(false);

  useEffect(() => {
    if (!container.current || mapRef.current) return;
    const map = new maplibregl.Map({
      container: container.current,
      style: OSM_STYLE,
      center: [10.19, 54.42],
      zoom: 14,
      attributionControl: false,
    });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    map.on("load", () => {
      map.addSource("course", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
      map.addSource("trails", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
      map.addLayer({
        id: "legs",
        type: "line",
        source: "course",
        filter: ["==", ["get", "kind"], "leg"],
        paint: { "line-color": "#475569", "line-width": 1.5, "line-dasharray": [2, 2] },
      });
      map.addLayer({
        id: "lines",
        type: "line",
        source: "course",
        filter: ["!=", ["get", "kind"], "leg"],
        paint: {
          "line-color": ["match", ["get", "kind"], "start", "#16a34a", "finish", "#2563eb", "#ea580c"],
          "line-width": 3,
        },
      });
      map.addLayer({
        id: "trails",
        type: "line",
        source: "trails",
        paint: { "line-color": ["get", "color"], "line-width": 2, "line-opacity": 0.7 },
      });
      setReady(true);
    });
    mapRef.current = map;
    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, [mapRef]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready || !snapshot) return;
    const course = snapshot.course;
    (map.getSource("course") as GeoJSONSource | undefined)?.setData(
      course ? courseLines(course) : ({ type: "FeatureCollection", features: [] } as Data),
    );
    (map.getSource("trails") as GeoJSONSource | undefined)?.setData(trails(snapshot.boats));

    // Marks: one marker per role, moved rather than recreated.
    const seenMarks = new Set<string>();
    for (const mark of course?.marks ?? []) {
      seenMarks.add(mark.role);
      let marker = markMarkers.current.get(mark.role);
      if (!marker) {
        marker = new Marker({ element: markElement(mark.role, t(`marks.${mark.role}`)), anchor: "top" });
        marker.setLngLat(lngLat(mark)).addTo(map);
        markMarkers.current.set(mark.role, marker);
      } else {
        marker.setLngLat(lngLat(mark));
      }
    }
    for (const [role, marker] of markMarkers.current) {
      if (!seenMarks.has(role)) {
        marker.remove();
        markMarkers.current.delete(role);
      }
    }

    // Boats: the arrow turns to the course over ground, the label stays upright.
    const seenBoats = new Set<number>();
    for (const boat of snapshot.boats) {
      seenBoats.add(boat.boat_number);
      const hex = boatColor(boat.color).hex;
      const label = boat.team?.club.short_name ?? String(boat.boat_number);
      let entry = boatMarkers.current.get(boat.boat_number);
      if (!entry) {
        const el = boatElement(hex, label);
        const marker = new Marker({ element: el, anchor: "center" }).setLngLat([boat.lon, boat.lat]).addTo(map);
        el.dataset.testid = `live-boat-marker-${boat.boat_number}`;
        entry = { marker, arrow: el.children[0] as HTMLElement, text: el.children[1] as HTMLElement };
        boatMarkers.current.set(boat.boat_number, entry);
      }
      entry.marker.setLngLat([boat.lon, boat.lat]);
      entry.arrow.style.transform = `rotate(${boat.cog}deg)`;
      entry.text.textContent = label;
      entry.marker.getElement().dataset.lat = String(boat.lat);
      entry.marker.getElement().dataset.lon = String(boat.lon);
    }
    for (const [number, entry] of boatMarkers.current) {
      if (!seenBoats.has(number)) {
        entry.marker.remove();
        boatMarkers.current.delete(number);
      }
    }

    // Framing: the course once, then the fleet while following.
    const points: LngLat[] = [
      ...(course?.marks ?? []).map(lngLat),
      ...(follow || !fitted.current ? snapshot.boats.map((b) => [b.lon, b.lat] as LngLat) : []),
    ];
    if (points.length >= 2 && (follow || !fitted.current)) {
      const bounds = points.reduce(
        (acc, p) => acc.extend(p),
        new maplibregl.LngLatBounds(points[0], points[0]),
      );
      map.fitBounds(bounds, { padding: 48, maxZoom: 17, duration: fitted.current ? 600 : 0 });
      fitted.current = true;
    }
  }, [snapshot, ready, follow, mapRef, t]);

  return (
    <div
      ref={container}
      data-testid="live-map"
      className="h-[60vh] min-h-[320px] w-full overflow-hidden rounded-xl border border-slate-200"
    />
  );
}

// ----------------------------------------------------------------------- the panel

function legKind(name: string | null | undefined): string | null {
  if (!name) return null;
  if (name === "finished") return "finished";
  if (name.startsWith("windward")) return "windward";
  if (name.startsWith("gate")) return "gate";
  return name;
}

function Panel({ snapshot }: { snapshot: LiveRace | null }) {
  const { t, i18n } = useTranslation("live");
  if (!snapshot) return null;
  if (!snapshot.course) return <p className="text-sm text-slate-600" data-testid="live-no-course">{t("noCourse")}</p>;
  if (!snapshot.boats.length) return <p className="text-sm text-slate-600" data-testid="live-no-boats">{t("noBoats")}</p>;
  const rows = [...snapshot.boats].sort(
    (a, b) => (a.rank ?? 99) - (b.rank ?? 99) || a.boat_number - b.boat_number,
  );
  const time = new Intl.DateTimeFormat(i18n.language, { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  return (
    <div data-testid="live-panel">
      <table className="data-table w-full border-collapse text-sm">
        <thead>
          <tr className="border-b border-slate-200 bg-slate-50 text-left">
            <th scope="col" className="w-8 font-medium text-slate-600">{t("panel.rank")}</th>
            <th scope="col" className="font-medium text-slate-600">{t("panel.boat")}</th>
            <th scope="col" className="font-medium text-slate-600">{t("panel.leg")}</th>
            <th scope="col" className="text-right font-medium text-slate-600">{t("panel.speed")}</th>
            <th scope="col" className="text-right font-medium text-slate-600">{t("panel.toGo")}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((boat) => {
            const color = boatColor(boat.color);
            const kind = legKind(boat.leg_name);
            return (
              <tr key={boat.boat_number} data-testid={`live-boat-row-${boat.boat_number}`} className="border-b border-slate-100 last:border-0">
                <td className="font-semibold tabular-nums" data-testid={`live-boat-rank-${boat.boat_number}`}>
                  {boat.rank ?? "–"}
                </td>
                <td>
                  <span className="flex items-center gap-1.5">
                    <span aria-hidden className="size-2.5 shrink-0 rounded-full ring-1 ring-slate-300" style={{ backgroundColor: color.hex }} />
                    <span className="truncate">{boat.team?.club.short_name ?? color.name}</span>
                  </span>
                </td>
                <td className="text-slate-600" data-testid={`live-boat-leg-${boat.boat_number}`}>
                  {boat.finished_at
                    ? `${t("leg.finished")} ${time.format(new Date(boat.finished_at))}`
                    : kind
                      ? t(`leg.${kind}`)
                      : "–"}
                </td>
                <td className="text-right tabular-nums" data-testid={`live-boat-speed-${boat.boat_number}`}>
                  {boat.sog_kn.toFixed(1)}
                </td>
                <td className="text-right tabular-nums text-slate-600">
                  {boat.finished_at || boat.to_go_m == null ? "–" : `${Math.round(boat.to_go_m)} m`}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {snapshot.detected_finish_order.length > 0 && (
        <p className="mt-2 text-sm text-slate-700" data-testid="live-detected-order">
          {t("panel.detectedOrder", { order: snapshot.detected_finish_order.join(" · ") })}
        </p>
      )}
    </div>
  );
}

// -------------------------------------------------------------- committee controls

function CommitteeControls({
  eventId,
  mapRef,
  hasCourse,
}: {
  eventId: number;
  mapRef: React.MutableRefObject<MapLibreMap | null>;
  hasCourse: boolean;
}) {
  const { t } = useTranslation("live");
  const invalidate = useInvalidate();
  const refresh = () => invalidate(getGetEventLiveQueryKey(eventId), getGetEventQueryKey(eventId));
  const [wind, setWind] = useState(20);
  const [leg, setLeg] = useState(300);
  const [speed, setSpeed] = useState(10);
  const lay = useLayDefaultEventCourse({ mutation: { onSuccess: refresh } });
  const simulate = useStartEmulation({ mutation: { onSuccess: refresh } });

  return (
    <div className="mt-4 space-y-3 rounded-xl border border-slate-200 p-3 text-sm" data-testid="live-committee">
      <div className="flex flex-wrap items-end gap-2">
        <label className="flex flex-col text-xs text-slate-600">
          {t("controls.wind")}
          <input type="number" min={0} max={359} value={wind} onChange={(e) => setWind(Number(e.target.value))} className="w-20 rounded-md border border-slate-300 px-2 py-1 text-sm" data-testid="live-wind" />
        </label>
        <label className="flex flex-col text-xs text-slate-600">
          {t("controls.legLength")}
          <input type="number" min={50} max={5000} step={50} value={leg} onChange={(e) => setLeg(Number(e.target.value))} className="w-24 rounded-md border border-slate-300 px-2 py-1 text-sm" data-testid="live-leg" />
        </label>
        <button
          type="button"
          className="rounded-md bg-brand-600 px-3 py-1.5 font-medium text-white hover:bg-brand-700 disabled:opacity-50"
          disabled={lay.isPending}
          onClick={() => {
            const at = mapRef.current?.getCenter();
            lay.mutate({
              eventId,
              data: { lat: at?.lat, lon: at?.lng, wind_from_deg: wind, leg_length_m: leg },
            });
          }}
          data-testid="live-lay-course"
        >
          {t("controls.layCourse")}
        </button>
      </div>
      <p className="text-xs text-slate-500">{t("controls.layCourseHint")}</p>
      {lay.isSuccess && <p className="text-emerald-700" data-testid="live-course-laid">{t("controls.laid")}</p>}
      {lay.isError && <ErrorMessage text={errorText(lay.error)} testId="live-lay-error" />}

      {DEV_TOOLS && (
        <div className="space-y-2 border-t border-slate-200 pt-3">
          <div className="flex flex-wrap items-center gap-2">
            <select value={speed} onChange={(e) => setSpeed(Number(e.target.value))} className="rounded-md border border-slate-300 px-2 py-1" data-testid="live-speed">
              {[1, 5, 10, 20].map((factor) => (
                <option key={factor} value={factor}>{t("controls.speed", { factor })}</option>
              ))}
            </select>
            <button
              type="button"
              className="rounded-md border-2 border-brand-600 px-3 py-1.5 font-medium text-brand-700 hover:bg-brand-50 disabled:opacity-50"
              disabled={simulate.isPending}
              onClick={() => simulate.mutate({ data: { event_id: eventId, speed, races: 1 } })}
              data-testid="live-simulate"
            >
              {simulate.isPending ? t("controls.simulating") : t("controls.simulate")}
            </button>
            {!hasCourse && <span className="text-xs text-slate-500">{t("noCourse")}</span>}
          </div>
          <p className="text-xs text-slate-500">{t("controls.simulateHint")}</p>
          {simulate.isError && <ErrorMessage text={errorText(simulate.error)} testId="live-simulate-error" />}
        </div>
      )}
      <Link to={`/events/${eventId}/race-control`} className="inline-block underline underline-offset-2" data-testid="live-race-control-link">
        {t("controls.raceControl")}
      </Link>
    </div>
  );
}
