import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";

import {
  getGetAdminRacesQueryKey,
  getGetEventQueryKey,
  useAbandonRace,
  useGetAdminRaces,
  useGetEvent,
  usePutRaceResult,
  useRecallRace,
  useSetRaceSignal,
  useStartEvent,
  useStartRace,
} from "../api/generated/sbl";
import type { AdminRace, BoatOut, EventSummary, StandingRow } from "../api/types";
import { useAccount, useAsync, useInvalidate } from "../api/useApi";
import { useLive } from "../api/useLive";
import { ErrorMessage, LiveBadge, Loading, PageHeader } from "../components/Blocks";
import { FinishOrderPad, useFinishOrder } from "../components/FinishOrderPad";
import { Stack } from "../components/Layouts";
import { errorText } from "../lib/admin";
import { clock, useNow } from "../lib/useNow";
import { boatColor } from "../lib/format";
import {
  OVER_EARLY_CODE,
  PREPARATORY_FLAGS,
  type PreparatoryFlag,
  resultComplete,
} from "../lib/results";

/** WL-3: the race committee's screen on the water — one race at a time, big targets.
 *
 * A page, not a Matchday tab: on a rocking boat it has to be full-screen and must not share
 * a screen with three tables. The results tab stays the *correction* screen. Everything on
 * this page is sized by the event — its boats, its flights — never by a league's numbers.
 *
 * The state machine is the server's (`services/race_state.py`); this page only offers the
 * transitions that apply to the race's status right now and reports refusals verbatim.
 * Taps on the finish pad stay on this device until "Finish" (mirrored to `localStorage`,
 * so a reload does not lose them), which is what keeps a mis-tap on the last boat from
 * ending the race by itself.
 */
export function RaceControl() {
  const { t } = useTranslation("racecontrol");
  const { id = "" } = useParams();
  const eventId = Number(id);
  const { hasRole, loading: accountLoading } = useAccount();
  const allowed = hasRole("admin", "race_officer");

  const detail = useAsync(useGetEvent(eventId));
  const races = useAsync(useGetAdminRaces(eventId, { query: { enabled: allowed } }));
  // Another device — the results tab ashore, a second phone — may change the same race.
  useLive(detail.data?.event.published ? `event:${eventId}` : null, [
    getGetEventQueryKey(eventId),
    getGetAdminRacesQueryKey(eventId),
  ]);

  // Which race is on screen, relative to the current one: −1 to correct the previous,
  // +1 to preview the next, nothing further.
  const [offset, setOffset] = useState(0);
  const [banner, setBanner] = useState<number | null>(null);

  if (accountLoading) return <Loading text={t("loading")} testId="race-control-loading" />;
  if (!allowed) return <ErrorMessage text={t("forbidden")} testId="race-control-forbidden" />;
  if (detail.loading || races.loading) {
    return <Loading text={t("loading")} testId="race-control-loading" />;
  }
  const error = detail.error ?? races.error;
  if (error) return <ErrorMessage text={error} testId="race-control-error" />;
  if (!detail.data || !races.data) return null;

  const { event, standings } = detail.data;
  const list = races.data.races;
  const boats = races.data.boats;

  if (event.status !== "live") {
    return (
      <>
        <PageHeader title={t("title")} testId="race-control-header" />
        <EventGate event={event} eventId={eventId} />
      </>
    );
  }
  if (!list.length) {
    return (
      <>
        <PageHeader title={t("title")} testId="race-control-header" />
        <p className="text-slate-600" data-testid="race-control-no-races">
          {t("noRaces")}
        </p>
      </>
    );
  }

  // The current race is the first one neither finished nor abandoned — the same rule the
  // results tab uses. With every race done, the last one stays on screen.
  const currentIndex = list.findIndex(stillOpen);
  const allDone = currentIndex === -1;
  const base = allDone ? list.length - 1 : currentIndex;
  const index = Math.min(list.length - 1, Math.max(0, base + offset));
  const race = list[index];
  const done = list.filter((r) => !stillOpen(r)).length;

  return (
    <>
      <PageHeader title={t("title")} testId="race-control-header" />

      <Stack gap={4}>
        <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
          <div>
            <h2 className="text-2xl font-bold text-slate-900" data-testid="race-control-heading">
              {t("raceHeading", { sequence: race.sequence })}
            </h2>
            <p className="text-sm text-slate-600">
              {t("flightOf", { flight: race.flight, total: event.flight_count })}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <NavButton
              label={t("previous")}
              disabled={index === 0 || offset <= -1}
              onClick={() => setOffset((o) => o - 1)}
              testId="race-control-prev"
            >
              ‹
            </NavButton>
            {offset !== 0 && (
              <button
                type="button"
                onClick={() => setOffset(0)}
                className="text-sm underline underline-offset-2"
                data-testid="race-control-back"
              >
                {t("backToCurrent")}
              </button>
            )}
            <NavButton
              label={t("next")}
              disabled={index === list.length - 1 || offset >= 1}
              onClick={() => setOffset((o) => o + 1)}
              testId="race-control-next"
            >
              ›
            </NavButton>
          </div>
        </div>

        {/* WL-1: progress through the day is visible at any time. */}
        <div data-testid="race-control-progress" className="space-y-1">
          <div className="flex items-center justify-between text-sm text-slate-600">
            <span>{t("progress", { done, total: list.length })}</span>
            <LiveBadge state={"live"} testId="race-control-live" />
          </div>
          <div className="h-2 w-full overflow-hidden rounded-full bg-slate-200">
            <div
              className="h-full bg-brand-600 transition-all"
              style={{ width: `${(done / list.length) * 100}%` }}
            />
          </div>
        </div>

        {banner !== null && (
          <p
            role="status"
            data-testid="race-control-banner"
            className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-2 text-sm text-emerald-800"
          >
            {t("finishedBanner", { sequence: banner })}
          </p>
        )}
        {allDone && offset === 0 && (
          <p className="text-slate-600" data-testid="race-control-all-done">
            {t("allDone")}
          </p>
        )}

        {/* Keyed on status and version too: after a transition the card re-mounts with the
            server's state instead of keeping the previous race's taps. */}
        <RaceCard
          key={`${race.id}-${race.status}-${race.version}`}
          eventId={eventId}
          race={race}
          boats={boats}
          standings={standings}
          onFinished={(sequence) => {
            setBanner(sequence);
            setOffset(0);
            window.setTimeout(() => setBanner(null), 4000);
          }}
        />
      </Stack>
    </>
  );
}

function stillOpen(race: AdminRace): boolean {
  return race.status !== "finished" && race.status !== "abandoned";
}

function NavButton({
  label,
  disabled,
  onClick,
  testId,
  children,
}: {
  label: string;
  disabled: boolean;
  onClick: () => void;
  testId: string;
  children: string;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      disabled={disabled}
      onClick={onClick}
      data-testid={testId}
      className="flex size-12 items-center justify-center rounded-lg border border-slate-300 text-2xl disabled:opacity-30"
    >
      {children}
    </button>
  );
}

/** The event's own gate, reused: a planned event offers the one button that starts it, a
 *  closed one says so and points at the manage screen's reopen. No state of its own. */
function EventGate({ event, eventId }: { event: EventSummary; eventId: number }) {
  const { t } = useTranslation("racecontrol");
  const invalidate = useInvalidate();
  const start = useStartEvent({
    mutation: { onSuccess: () => invalidate(getGetEventQueryKey(eventId)) },
  });
  if (event.status === "planned") {
    return (
      <Stack gap={3}>
        <p className="text-slate-700" data-testid="race-control-event-planned">
          {t("event.planned")}
        </p>
        <button
          type="button"
          className={BIG_PRIMARY}
          disabled={start.isPending}
          onClick={() => start.mutate({ eventId })}
          data-testid="race-control-event-start"
        >
          {t("event.startMatchday")}
        </button>
        <p className="text-sm text-slate-500">{t("event.startHint")}</p>
        {start.isError && <ErrorMessage text={errorText(start.error)} testId="race-control-event-error" />}
      </Stack>
    );
  }
  return (
    <Stack gap={3}>
      <p className="text-slate-700" data-testid={`race-control-event-${event.status}`}>
        {event.status === "final" ? t("event.final") : t("event.cancelled")}
      </p>
      <Link to="/admin?tab=events" className="underline underline-offset-2">
        {t("event.manageLink")}
      </Link>
    </Stack>
  );
}

const BIG = "min-h-16 rounded-xl px-4 text-lg font-semibold shadow-sm transition active:scale-95 disabled:opacity-40 disabled:active:scale-100";
const BIG_PRIMARY = `${BIG} bg-brand-600 text-white hover:bg-brand-700`;
const BIG_SECONDARY = `${BIG} border-2 border-slate-300 bg-white text-slate-800 hover:bg-slate-50`;
const BIG_WARN = `${BIG} border-2 border-amber-400 bg-amber-50 text-amber-900 hover:bg-amber-100`;
const BIG_DANGER = `${BIG} border-2 border-red-300 bg-red-50 text-red-900 hover:bg-red-100`;

/** Codes the committee gives on the water. RDG, ZFP and SCP need a number the jury decides
 *  and belong in the results tab. */
const ON_WATER_CODES = ["OCS", "UFD", "BFD", "DNF", "DNS", "DSQ", "DNE", "RET"] as const;

/** RRS 26: warning signal 5 minutes before the start. */
const SEQUENCE_MILLIS = 5 * 60_000;
/** When AP comes down, the warning signal follows one minute later. */
const AP_DOWN_MILLIS = 60_000;


function RaceCard({
  eventId,
  race,
  boats,
  standings,
  onFinished,
}: {
  eventId: number;
  race: AdminRace;
  boats: BoatOut[];
  standings: StandingRow[];
  onFinished: (sequence: number) => void;
}) {
  const { t } = useTranslation("racecontrol");
  const invalidate = useInvalidate();
  const refresh = () => invalidate(getGetEventQueryKey(eventId), getGetAdminRacesQueryKey(eventId));
  const now = useNow();

  const start = useStartRace({ mutation: { onSuccess: refresh } });
  const recall = useRecallRace({ mutation: { onSuccess: refresh } });
  const abandon = useAbandonRace({ mutation: { onSuccess: refresh } });
  const signal = useSetRaceSignal({ mutation: { onSuccess: refresh } });
  const order = useFinishOrder(race, standings, { mirrorKey: `sbl.finish-order.${race.id}` });
  const finish = usePutRaceResult({
    mutation: {
      onSuccess: () => {
        order.clearMirror();
        refresh();
        onFinished(race.sequence);
      },
    },
  });

  const [preparatory, setPreparatory] = useState<PreparatoryFlag>("P");
  // A running start sequence: when the gun is due. The gun fires by itself at zero.
  const [sequence, setSequence] = useState<{ startsAt: number } | null>(null);
  const fired = useRef(false);
  useEffect(() => {
    if (sequence && now >= sequence.startsAt && !fired.current) {
      fired.current = true;
      setSequence(null);
      start.mutate({ eventId, raceId: race.id, data: { preparatory } });
    }
  }, [now, sequence, start, eventId, race.id, preparatory]);

  // Abandoning is two taps: the first arms the button, the second does it.
  const [armed, setArmed] = useState<"resail" | "void" | null>(null);
  useEffect(() => {
    if (!armed) return;
    const timer = window.setTimeout(() => setArmed(null), 4000);
    return () => window.clearTimeout(timer);
  }, [armed]);

  const busy =
    start.isPending || recall.isPending || abandon.isPending || signal.isPending || finish.isPending;
  const failure = [start, recall, abandon, signal, finish].find((m) => m.isError);
  const setSignal = (value: "AP" | "X" | "S" | null) =>
    signal.mutate({ eventId, raceId: race.id, data: { signal: value } });

  const statusLine = (
    <div className="flex flex-wrap items-center gap-2">
      <span
        data-testid="race-control-status"
        data-status={race.status}
        className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-700 ring-1 ring-inset ring-slate-200"
      >
        {t(`status.${race.status}`)}
      </span>
      {race.signal && (
        <span
          data-testid="race-control-signal"
          className="rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-medium text-amber-900 ring-1 ring-inset ring-amber-300"
        >
          {t(`signal.${race.signal}`)}
        </span>
      )}
      {race.status === "running" && race.started_at && (
        <span className="text-sm tabular-nums text-slate-600" data-testid="race-control-elapsed">
          {t("elapsed", { time: clock(now - Date.parse(race.started_at)) })}
        </span>
      )}
    </div>
  );

  if (race.status === "scheduled") {
    return (
      <Stack gap={4}>
        {statusLine}
        <FinishOrderPad race={race} boats={boats} order={order} disabled testIdPrefix="race-control" />

        {sequence ? (
          <div className="rounded-xl border border-slate-200 p-4 text-center" data-testid="race-control-sequence">
            <p className="text-4xl font-bold tabular-nums">
              {sequence.startsAt - now > SEQUENCE_MILLIS
                ? t("sequence.warningIn", { time: clock(sequence.startsAt - now - SEQUENCE_MILLIS) })
                : t("sequence.startIn", { time: clock(sequence.startsAt - now) })}
            </p>
            <p className="mt-1 text-sm text-slate-500">{t("sequence.hint")}</p>
            <button
              type="button"
              className={`${BIG_SECONDARY} mt-3`}
              onClick={() => setSequence(null)}
              data-testid="race-control-cancel-sequence"
            >
              {t("buttons.cancelSequence")}
            </button>
          </div>
        ) : (
          <fieldset className="flex flex-wrap items-center gap-2">
            <legend className="mb-1 text-sm text-slate-600">{t("sequence.preparatory")}</legend>
            {PREPARATORY_FLAGS.map((flag) => (
              <button
                key={flag}
                type="button"
                aria-pressed={preparatory === flag}
                onClick={() => setPreparatory(flag)}
                data-testid={`race-control-flag-${flag}`}
                className={`min-h-12 min-w-12 rounded-lg border-2 px-3 font-semibold ${
                  preparatory === flag
                    ? "border-brand-600 bg-brand-50 text-brand-800"
                    : "border-slate-300 text-slate-700"
                }`}
              >
                {t(`flags.${flag}`)}
              </button>
            ))}
          </fieldset>
        )}

        <div className="grid grid-cols-2 gap-3">
          <button
            type="button"
            className={BIG_PRIMARY}
            disabled={busy || race.signal === "AP"}
            onClick={() => start.mutate({ eventId, raceId: race.id, data: { preparatory } })}
            data-testid="race-control-start"
          >
            {t("buttons.start")}
          </button>
          <button
            type="button"
            className={BIG_SECONDARY}
            disabled={busy || sequence !== null || race.signal === "AP"}
            onClick={() => {
              fired.current = false;
              setSequence({ startsAt: Date.now() + SEQUENCE_MILLIS });
            }}
            data-testid="race-control-start-sequence"
          >
            {t("buttons.startSequence")}
          </button>
          <button
            type="button"
            className={`${BIG_WARN} col-span-2`}
            disabled={busy}
            onClick={() => {
              if (race.signal === "AP") {
                // AP down: the warning signal follows in one minute, the gun five after.
                setSignal(null);
                fired.current = false;
                setSequence({ startsAt: Date.now() + AP_DOWN_MILLIS + SEQUENCE_MILLIS });
              } else {
                setSequence(null);
                setSignal("AP");
              }
            }}
            data-testid="race-control-ap"
          >
            {race.signal === "AP" ? t("buttons.apDown") : t("buttons.ap")}
          </button>
        </div>
        {failure && <ErrorMessage text={errorText(failure.error)} testId="race-control-error" />}
      </Stack>
    );
  }

  if (race.status === "running") {
    const overEarly = race.signal === "X" ? (OVER_EARLY_CODE[race.preparatory ?? "P"] ?? "OCS") : null;
    const canFinish = order.complete && order.duplicateBoats.size === 0 && !busy;
    return (
      <Stack gap={4}>
        {statusLine}
        {overEarly && (
          <p className="text-sm text-amber-900" data-testid="race-control-x-hint">
            {t("xHint", { code: overEarly })}
          </p>
        )}
        <FinishOrderPad
          race={race}
          boats={boats}
          order={order}
          overEarlyCode={overEarly}
          disabled={busy}
          testIdPrefix="race-control"
        />
        <p className="text-xs text-slate-500">{t("localHint")}</p>
        {order.duplicateBoats.size > 0 && (
          <p role="alert" className="text-sm text-red-700">
            {t("duplicateWarning")}
          </p>
        )}

        {/* Codes one tap below the pad: a native select opens the phone's own picker. */}
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
          {boats.map((boat) => {
            const row = order.rows[boat.number];
            if (!row) return null;
            const color = boatColor(boat.color);
            return (
              <label key={boat.number} className="flex items-center gap-2 text-sm">
                <span
                  aria-hidden
                  className="size-3 shrink-0 rounded-full ring-1 ring-slate-300"
                  style={{ backgroundColor: color.hex }}
                />
                <select
                  aria-label={t("codeLabel", { boat: color.name })}
                  className="min-h-11 flex-1 rounded-md border border-slate-300 px-2"
                  value={row.code === "FINISHED" ? "" : row.code}
                  onChange={(e) =>
                    order.setField(boat.number, {
                      code: e.target.value || "FINISHED",
                      finish_position: null,
                    })
                  }
                  data-testid={`race-control-code-${boat.number}`}
                >
                  <option value="">
                    {row.finish_position != null ? t("position", { position: row.finish_position }) : "—"}
                  </option>
                  {ON_WATER_CODES.map((code) => (
                    <option key={code} value={code}>
                      {code}
                    </option>
                  ))}
                </select>
              </label>
            );
          })}
        </div>

        <div className="grid grid-cols-2 gap-3">
          <button
            type="button"
            className={BIG_PRIMARY}
            disabled={!canFinish}
            onClick={() => finish.mutate({ eventId, raceId: race.id, data: order.body() })}
            data-testid="race-control-finish"
          >
            {t("buttons.finish")}
          </button>
          <button
            type="button"
            className={BIG_WARN}
            disabled={busy}
            onClick={() => setSignal(race.signal === "X" ? null : "X")}
            data-testid="race-control-x"
          >
            {race.signal === "X" ? t("buttons.xDown") : t("buttons.x")}
          </button>
          <button
            type="button"
            className={BIG_SECONDARY}
            disabled={busy}
            onClick={() => setSignal(race.signal === "S" ? null : "S")}
            data-testid="race-control-s"
          >
            {race.signal === "S" ? t("buttons.shortenDown") : t("buttons.shorten")}
          </button>
          <button
            type="button"
            className={BIG_WARN}
            disabled={busy}
            onClick={() => recall.mutate({ eventId, raceId: race.id })}
            data-testid="race-control-recall"
          >
            {t("buttons.recall")}
          </button>
          <button
            type="button"
            className={BIG_DANGER}
            disabled={busy}
            onClick={() => {
              if (armed === "resail") {
                setArmed(null);
                abandon.mutate({ eventId, raceId: race.id, params: { resail: true } });
              } else {
                setArmed("resail");
              }
            }}
            data-testid="race-control-abandon-resail"
          >
            {armed === "resail" ? t("buttons.confirmAbandon") : t("buttons.abandonResail")}
          </button>
          <button
            type="button"
            className={BIG_DANGER}
            disabled={busy}
            onClick={() => {
              if (armed === "void") {
                setArmed(null);
                abandon.mutate({ eventId, raceId: race.id, params: { resail: false } });
              } else {
                setArmed("void");
              }
            }}
            data-testid="race-control-abandon-void"
          >
            {armed === "void" ? t("buttons.confirmAbandon") : t("buttons.abandonVoid")}
          </button>
        </div>
        {failure && <ErrorMessage text={errorText(failure.error)} testId="race-control-error" />}
      </Stack>
    );
  }

  // Finished or abandoned: read-only, and the way to the correction screen.
  const complete = race.entries.every((entry) =>
    resultComplete({
      boat_number: entry.boat_number,
      code: entry.code ?? "FINISHED",
      finish_position: entry.finish_position ?? null,
      redress_points: entry.redress_points ?? null,
      redress_mode: "fixed",
    }),
  );
  return (
    <Stack gap={4}>
      {statusLine}
      <FinishOrderPad race={race} boats={boats} order={order} disabled testIdPrefix="race-control" />
      {race.status === "finished" && !complete && (
        <p className="text-sm text-slate-500">{t("duplicateWarning")}</p>
      )}
      <Link
        to={`/events/${eventId}?view=results`}
        className="text-sm underline underline-offset-2"
        data-testid="race-control-correct"
      >
        {t("buttons.correct")}
      </Link>
    </Stack>
  );
}
