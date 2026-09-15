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

  // Story L-1: an event whose live view is hosted elsewhere sends the reader there — the
  // map here would be empty, and two live pictures of one race is one too many.
  if (detail.data.event.live_url) {
    return (
      <>
        <PageHeader title={`${detail.data.event.title} · ${t("title")}`} testId="live-header" />
        <div className="rounded-xl border border-slate-200 p-4" data-testid="live-external">
          <p className="text-sm text-slate-700">{t("external.text")}</p>
          <a
            href={detail.data.event.live_url}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-3 inline-block rounded-md bg-brand-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-700"
            data-testid="live-external-link"
          >
            {t("external.open")}
          </a>
          <p className="mt-2 break-all text-xs text-slate-500">{detail.data.event.live_url}</p>
        </div>
      </>
    );
  }

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
      {snapshot?.wind_from_deg != null && (
        <span className="text-slate-600" data-testid="live-wind">
          {t("race.wind", { deg: Math.round(snapshot.wind_from_deg) })}
        </span>
      )}
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

const METRES_PER_DEGREE = 111_320;

/** A point `east`/`north` metres from `origin` — flat-earth, which over a course is exact
 *  to the centimetre. The server does the real geometry; this only draws. */
function offsetMetres(origin: LngLat, east: number, north: number): LngLat {
  const lat = (origin[1] * Math.PI) / 180;
  return [origin[0] + east / (METRES_PER_DEGREE * Math.cos(lat)), origin[1] + north / METRES_PER_DEGREE];
}

function circle(at: LngLat, radiusM: number, points = 48): LngLat[] {
  const ring: LngLat[] = [];
  for (let i = 0; i <= points; i += 1) {
    const a = (2 * Math.PI * i) / points;
    ring.push(offsetMetres(at, radiusM * Math.sin(a), radiusM * Math.cos(a)));
  }
  return ring;
}

/** The zone (RRS 18) — three hull lengths — around every mark boats round or finish at.
 *  Not around the start line's ends: rule 18 does not apply at a starting mark, and the
 *  committee boat gets its zone only when it is also the finish line's end. */
function zones(course: Course, radiusM: number): Data {
  const zoned = course.marks.filter(
    (m) => m.role !== "start_pin" && !(m.role === "committee_boat" && course.finish_upwind),
  );
  return {
    type: "FeatureCollection",
    features: zoned.map((m) => ({
      type: "Feature",
      geometry: { type: "Polygon", coordinates: [circle(lngLat(m), radiusM)] },
      properties: { role: m.role },
    })),
  } as Data;
}

/** Each boat as a hull polygon at its true size, bow on the course over ground — so the map
 *  shows how a 7 m boat fits a 21 m zone. Below {@link HULL_ZOOM} it is a speck and the
 *  arrow marker carries the boat instead. */
interface Pose {
  lat: number;
  lon: number;
  cog: number;
  color: string;
}

/** The plan view of a hull the way one draws a sailing boat: two curved sides meeting at
 *  the bow, a straight transom behind. Widest a little aft of midships, the transom about
 *  seven tenths of the beam — near enough a J/70. `x` across, `y` forward, in metres. */
function hullShape(lengthM: number, beamM: number): [number, number][] {
  const half = lengthM / 2;
  const halfBeam = beamM / 2;
  const widest = 0.4; // fraction of the length from the stern
  const transom = 0.7;
  const side: [number, number][] = [];
  const steps = 10;
  for (let i = 0; i <= steps; i += 1) {
    const s = i / steps; // 0 at the stern, 1 at the bow
    const w =
      s < widest
        ? halfBeam * (transom + (1 - transom) * (1 - ((widest - s) / widest) ** 2))
        : halfBeam * (1 - ((s - widest) / (1 - widest)) ** 2) ** 0.6;
    side.push([w, -half + s * lengthM]);
  }
  side[side.length - 1] = [0, half]; // the bow is a point
  const starboard = side;
  const port = side.slice(0, -1).reverse().map(([x, y]) => [-x, y] as [number, number]);
  // Starboard side stern→bow, port side bow→stern, and the ring closes across the transom.
  return [...starboard, ...port, starboard[0]];
}

function hulls(boats: Pose[], lengthM: number, beamM: number): Data {
  const shape = hullShape(lengthM, beamM);
  return {
    type: "FeatureCollection",
    features: boats.map((b) => {
      const c = (b.cog * Math.PI) / 180;
      const at: LngLat = [b.lon, b.lat];
      const ring = shape.map(([x, y]) => offsetMetres(at, x * Math.cos(c) + y * Math.sin(c), -x * Math.sin(c) + y * Math.cos(c)));
      return {
        type: "Feature",
        geometry: { type: "Polygon", coordinates: [ring] },
        properties: { color: b.color },
      };
    }),
  } as Data;
}

/** From this zoom a 7 m hull is about ten pixels long, and the drawn hull replaces the arrow. */
const HULL_ZOOM = 17;

// ------------------------------------------------------------- smooth positions
//
// Fixes arrive once a second or so, and a marker that jumps to each one looks like a slide
// show. SAP Sailing Analytics answers "where was the boat at time t" by interpolating
// between the two fixes around t, and only extrapolates along course and speed past the
// last one; its viewer shows the picture a moment behind real time so that it nearly
// always interpolates. The same here: every animation frame draws each boat at
// `now − RENDER_DELAY` on the server's clock, between the fixes it has, and dead-reckons
// for at most EXTRAPOLATE_MAX when the stream is late — then the boat stops rather than
// sailing off on a guess.

interface Sample {
  t: number;
  lat: number;
  lon: number;
  cog: number;
  /** Speed over ground in m/s. */
  sog: number;
}

const RENDER_DELAY_MS = 1500;
const EXTRAPOLATE_MAX_MS = 3000;
const SAMPLES_KEPT = 8;
const KNOT_MS = 1852 / 3600;

function lerpAngle(a: number, b: number, f: number): number {
  const d = ((b - a + 540) % 360) - 180;
  return (a + d * f + 360) % 360;
}

function estimate(samples: Sample[], t: number): Omit<Sample, "sog"> | null {
  if (!samples.length) return null;
  const last = samples[samples.length - 1];
  if (t >= last.t) {
    const dt = Math.min(t - last.t, EXTRAPOLATE_MAX_MS) / 1000;
    const d = last.sog * dt;
    const c = (last.cog * Math.PI) / 180;
    const [lon, lat] = offsetMetres([last.lon, last.lat], d * Math.sin(c), d * Math.cos(c));
    return { t, lat, lon, cog: last.cog };
  }
  if (t <= samples[0].t) return samples[0];
  let i = samples.length - 2;
  while (i > 0 && samples[i].t > t) i -= 1;
  const a = samples[i];
  const b = samples[i + 1];
  const f = (t - a.t) / (b.t - a.t);
  return {
    t,
    lat: a.lat + (b.lat - a.lat) * f,
    lon: a.lon + (b.lon - a.lon) * f,
    cog: lerpAngle(a.cog, b.cog, f),
  };
}

type LineFeature = {
  type: "Feature";
  geometry: { type: "LineString"; coordinates: LngLat[] };
  properties: { kind: string };
};

/** The start and finish lines. Nothing joins the gate marks — a gate is two marks with
 *  water between them — and no leg line: the boats' trails and the laylines show the way. */
function courseLines(course: Course): Data {
  const at = (role: string) => {
    const mark = course.marks.find((m) => m.role === role);
    return mark ? lngLat(mark) : null;
  };
  const committee = at("committee_boat");
  const pin = at("start_pin");
  const windward = at("windward");
  const finishPin = at("finish_pin");
  const features: LineFeature[] = [];
  const line = (kind: string, points: (LngLat | null)[]) => {
    if (points.every(Boolean)) {
      features.push({ type: "Feature", geometry: { type: "LineString", coordinates: points as LngLat[] }, properties: { kind } });
    }
  };
  line("start", [committee, pin]);
  line("finish", [course.finish_upwind ? windward : committee, finishPin]);
  return { type: "FeatureCollection", features } as Data;
}

/** Laylines to the windward mark and from the gate marks (server-derived, from the polar's
 *  angles), plus the leader's line square to its leg — what a tactician draws. */
function laylineFeatures(snapshot: LiveRace): Data {
  const features: LineFeature[] = snapshot.laylines.map((l) => ({
    type: "Feature",
    geometry: { type: "LineString", coordinates: l.points.map(([lat, lon]) => [lon, lat] as LngLat) },
    properties: { kind: "layline" },
  }));
  return { type: "FeatureCollection", features } as Data;
}

/** The leader's line, moved with the leader: the server drew it through the boat's newest
 *  fix, the map shows the boat a moment behind that, so the line is shifted by the same
 *  offset each frame — otherwise it would run ahead of the boat it belongs to. */
function leaderFeature(line: LngLat[] | null, dLon: number, dLat: number): Data {
  const features: LineFeature[] = line
    ? [{ type: "Feature", geometry: { type: "LineString", coordinates: line.map(([lon, lat]) => [lon + dLon, lat + dLat]) }, properties: { kind: "leader" } }]
    : [];
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

/** A marker whose *symbol* sits exactly on the coordinate, with the label hung beneath it.
 *  The element's box is the symbol alone and the marker is anchored at its centre; a
 *  column of symbol plus label anchored at its top or centre puts the symbol's centre
 *  half a label away from the point — invisible zoomed in, a mark floating outside its
 *  own zone zoomed out. */
function symbolWithLabel(symbol: HTMLElement, label: string, labelClass: string): HTMLDivElement {
  const el = document.createElement("div");
  el.className = "relative";
  el.style.width = symbol.style.width;
  el.style.height = symbol.style.height;
  const text = document.createElement("div");
  text.className = `absolute left-1/2 top-full mt-0.5 -translate-x-1/2 whitespace-nowrap rounded bg-white/85 px-1 text-[10px] leading-tight ${labelClass}`;
  text.textContent = label;
  el.append(symbol, text);
  return el;
}

function boatElement(hex: string, label: string): HTMLDivElement {
  const arrow = document.createElement("div");
  arrow.className = "live-arrow h-0 w-0 border-x-[8px] border-b-[22px] border-x-transparent drop-shadow";
  arrow.style.borderBottomColor = hex;
  arrow.style.width = "16px";
  arrow.style.height = "22px";
  return symbolWithLabel(arrow, label, "font-semibold text-slate-900");
}

function markElement(role: string, label: string): HTMLDivElement {
  const dot = document.createElement("div");
  dot.className = `rounded-full border-2 border-white shadow ${
    role === "committee_boat" ? "bg-slate-900" : role === "finish_pin" ? "bg-blue-600" : "bg-orange-500"
  }`;
  dot.style.width = "14px";
  dot.style.height = "14px";
  return symbolWithLabel(dot, label, "font-medium text-slate-700");
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
  const samples = useRef(new Map<number, { color: string; fixes: Sample[] }>());
  const dims = useRef({ length: 7, beam: 2.25 });
  const leader = useRef<{ boat: number; at: LngLat; line: LngLat[] } | null>(null);
  /** Local clock minus the server's, measured on every picture received. */
  const clockOffset = useRef(0);

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
    // A handle for the browser console and the e2e probes, in development builds only.
    if (DEV_TOOLS) (window as unknown as { __sblMap?: MapLibreMap }).__sblMap = map;
    map.on("load", () => {
      const empty = () => ({ type: "geojson" as const, data: { type: "FeatureCollection" as const, features: [] } });
      map.addSource("zones", empty());
      map.addSource("tactics", empty());
      map.addSource("leader", empty());
      map.addSource("course", empty());
      map.addSource("trails", empty());
      map.addSource("hulls", empty());
      map.addLayer({
        id: "zones-fill",
        type: "fill",
        source: "zones",
        paint: { "fill-color": "#ea580c", "fill-opacity": 0.1 },
      });
      map.addLayer({
        id: "zones-line",
        type: "line",
        source: "zones",
        paint: { "line-color": "#ea580c", "line-width": 1.5, "line-dasharray": [3, 2], "line-opacity": 0.8 },
      });
      map.addLayer({
        id: "laylines",
        type: "line",
        source: "tactics",
        filter: ["==", ["get", "kind"], "layline"],
        paint: { "line-color": "#64748b", "line-width": 1, "line-dasharray": [4, 3], "line-opacity": 0.8 },
      });
      map.addLayer({
        id: "lines",
        type: "line",
        source: "course",
        paint: {
          "line-color": ["match", ["get", "kind"], "start", "#16a34a", "#2563eb"],
          "line-width": 3,
        },
      });
      map.addLayer({
        id: "leader",
        type: "line",
        source: "leader",
        paint: { "line-color": "#7c3aed", "line-width": 2, "line-opacity": 0.9 },
      });
      map.addLayer({
        id: "trails",
        type: "line",
        source: "trails",
        paint: { "line-color": ["get", "color"], "line-width": 2, "line-opacity": 0.7 },
      });
      map.addLayer({
        id: "hulls-fill",
        type: "fill",
        source: "hulls",
        minzoom: HULL_ZOOM,
        paint: { "fill-color": ["get", "color"], "fill-opacity": 0.9 },
      });
      map.addLayer({
        id: "hulls-line",
        type: "line",
        source: "hulls",
        minzoom: HULL_ZOOM,
        paint: { "line-color": "#ffffff", "line-width": 1 },
      });
      setReady(true);
    });
    // Once the hull is drawn at scale the arrow would sit on top of it; hide it there.
    map.on("zoom", () => {
      const scaled = map.getZoom() >= HULL_ZOOM;
      for (const entry of boatMarkers.current.values()) {
        entry.arrow.style.visibility = scaled ? "hidden" : "visible";
      }
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
    (map.getSource("zones") as GeoJSONSource | undefined)?.setData(
      course ? zones(course, snapshot.zone_radius_m) : ({ type: "FeatureCollection", features: [] } as Data),
    );
    (map.getSource("tactics") as GeoJSONSource | undefined)?.setData(laylineFeatures(snapshot));
    const first = snapshot.boats.find((b) => b.boat_number === snapshot.leader_boat);
    leader.current =
      snapshot.leader_line && first
        ? { boat: first.boat_number, at: [first.lon, first.lat], line: snapshot.leader_line.map(([lat, lon]) => [lon, lat] as LngLat) }
        : null;
    (map.getSource("trails") as GeoJSONSource | undefined)?.setData(trails(snapshot.boats));
    dims.current = { length: snapshot.boat_length_m, beam: snapshot.boat_beam_m };
    clockOffset.current = Date.now() - Date.parse(snapshot.t);

    // Marks: one marker per role, moved rather than recreated.
    const seenMarks = new Set<string>();
    for (const mark of course?.marks ?? []) {
      seenMarks.add(mark.role);
      let marker = markMarkers.current.get(mark.role);
      if (!marker) {
        marker = new Marker({ element: markElement(mark.role, t(`marks.${mark.role}`)), anchor: "center" });
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

    // Boats: one marker each, created here and *moved* by the animation frame below; the
    // arrow turns to the course over ground, the label stays upright. Each new fix joins
    // the boat's samples for the estimator.
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
        entry.arrow.style.visibility = map.getZoom() >= HULL_ZOOM ? "hidden" : "visible";
        boatMarkers.current.set(boat.boat_number, entry);
      }
      entry.text.textContent = label;
      entry.marker.getElement().dataset.lat = String(boat.lat);
      entry.marker.getElement().dataset.lon = String(boat.lon);
      let track = samples.current.get(boat.boat_number);
      if (!track) {
        track = { color: hex, fixes: [] };
        samples.current.set(boat.boat_number, track);
      }
      track.color = hex;
      const t = Date.parse(boat.t);
      const newest = track.fixes[track.fixes.length - 1];
      if (!newest || t > newest.t) {
        track.fixes.push({ t, lat: boat.lat, lon: boat.lon, cog: boat.cog, sog: boat.sog_kn * KNOT_MS });
        if (track.fixes.length > SAMPLES_KEPT) track.fixes.splice(0, track.fixes.length - SAMPLES_KEPT);
      }
    }
    for (const [number, entry] of boatMarkers.current) {
      if (!seenBoats.has(number)) {
        entry.marker.remove();
        boatMarkers.current.delete(number);
        samples.current.delete(number);
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

  // The animation frame: every boat where the estimator puts it right now.
  useEffect(() => {
    if (!ready) return;
    let frame = 0;
    const tick = () => {
      const map = mapRef.current;
      if (map) {
        const at = Date.now() - clockOffset.current - RENDER_DELAY_MS;
        const poses: Pose[] = [];
        let leaderLine: Data = leaderFeature(null, 0, 0);
        for (const [number, track] of samples.current) {
          const pose = estimate(track.fixes, at);
          if (!pose) continue;
          if (leader.current?.boat === number) {
            const { at: [lon, lat], line } = leader.current;
            leaderLine = leaderFeature(line, pose.lon - lon, pose.lat - lat);
          }
          const entry = boatMarkers.current.get(number);
          if (entry) {
            entry.marker.setLngLat([pose.lon, pose.lat]);
            entry.arrow.style.transform = `rotate(${pose.cog}deg)`;
          }
          poses.push({ lat: pose.lat, lon: pose.lon, cog: pose.cog, color: track.color });
        }
        (map.getSource("hulls") as GeoJSONSource | undefined)?.setData(
          hulls(poses, dims.current.length, dims.current.beam),
        );
        (map.getSource("leader") as GeoJSONSource | undefined)?.setData(leaderLine);
      }
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [ready, mapRef]);

  // The "nothing to show yet" notices sit on the map, not in the panel: the panel is the
  // narrow column, and a sentence there left the map with nothing to say either.
  const notice = snapshot && !snapshot.course ? "noCourse" : snapshot && !snapshot.boats.length ? "noBoats" : null;
  return (
    <div className="relative">
      <div
        ref={container}
        data-testid="live-map"
        className="h-[60vh] min-h-[320px] w-full overflow-hidden rounded-xl border border-slate-200 lg:h-[72vh]"
      />
      {notice && (
        <p
          className="pointer-events-none absolute top-3 left-3 right-14 z-10 rounded-md bg-white/90 px-3 py-2 text-sm text-slate-700 shadow"
          data-testid={notice === "noCourse" ? "live-no-course" : "live-no-boats"}
        >
          {t(notice)}
        </p>
      )}
    </div>
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
  const { t } = useTranslation("live");
  if (!snapshot?.course || !snapshot.boats.length) return null;
  const rows = [...snapshot.boats].sort(
    (a, b) => (a.rank ?? 99) - (b.rank ?? 99) || a.boat_number - b.boat_number,
  );
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
                <td
                  className="tabular-nums text-slate-600"
                  title={kind ? t(`leg.${kind}`) : undefined}
                  data-testid={`live-boat-leg-${boat.boat_number}`}
                >
                  {boat.leg == null || snapshot.leg_count == null
                    ? "–"
                    : boat.finished_at
                      ? t("leg.finished")
                      : `${Math.min(boat.leg, snapshot.leg_count)}/${snapshot.leg_count}`}
                </td>
                <td className="text-right tabular-nums" data-testid={`live-boat-speed-${boat.boat_number}`}>
                  {boat.sog_kn.toFixed(1)}
                </td>
                <td className="text-right tabular-nums text-slate-600" data-testid={`live-boat-gap-${boat.boat_number}`}>
                  {boat.finished_at || boat.to_go_m == null || boat.to_leader_m == null
                    ? "–"
                    : boat.to_leader_m === 0
                      ? `${Math.round(boat.to_go_m)} m`
                      : `${boat.to_leader_m > 0 ? "+" : ""}${Math.round(boat.to_leader_m)} m`}
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
  const [finishSide, setFinishSide] = useState<"left" | "right">("right");
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
        <label className="flex flex-col text-xs text-slate-600">
          {t("controls.finishLine")}
          <select
            value={finishSide}
            onChange={(e) => setFinishSide(e.target.value as "left" | "right")}
            className="rounded-md border border-slate-300 px-2 py-1 text-sm"
            data-testid="live-finish-side"
          >
            <option value="right">{t("controls.finishSeparate")}</option>
            <option value="left">{t("controls.finishCombined")}</option>
          </select>
        </label>
        <button
          type="button"
          className="rounded-md bg-brand-600 px-3 py-1.5 font-medium text-white hover:bg-brand-700 disabled:opacity-50"
          disabled={lay.isPending}
          onClick={() => {
            const at = mapRef.current?.getCenter();
            lay.mutate({
              eventId,
              data: { lat: at?.lat, lon: at?.lng, wind_from_deg: wind, leg_length_m: leg, finish_pin_side: finishSide },
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
