/** The league's start sequence as a state machine (Story WL-3): 3-2-1-0.
 *
 *   idle ──start (in 10 s | next full minute)──▶ armed(warningAt)
 *   armed ──start──▶ armed(new warningAt)      restart: the same event again
 *   armed ──abort──▶ idle                      also what hoisting AP does
 *   idle  ──AP down (in 10 s | full minute)──▶ armed(postponed)
 *                                              AP down then, the club flag a minute later
 *   armed ──AP up──▶ armed(apUpAt)             AP in 10 s, at the latest 3 s before the
 *                                              start; refused in the last 8 s (5 s to get
 *                                              ready, 3 s before the start)
 *   armed ──clock reaches apUpAt──▶ idle       the screen hoists AP and aborts
 *   idle  ──choose──▶ idle(flag)               the preparatory flag; fixed once armed,
 *                                              because it decides the penalty
 *
 * The state is *when the club flag goes up* and the chosen flag; which flag is up, what
 * the next signal is, whether AP is due down or the start due — all derived from the clock,
 * so the screen cannot get out of step with the sequence it shows. AP down and the start
 * are race actions on the server, fired by the screen when the clock reaches them.
 */
import { useCallback, useEffect, useState } from "react";

import { soundSpacing, type Tone } from "./horn";
import type { PreparatoryFlag } from "./results";

export const MINUTE = 60_000;
/** A sequence never begins sooner than this after the tap — time to reach the flags, and
 *  room for the count-in. */
export const LEAD = 10_000;
/** Before each signal, so the horn is ready on time: a ping at ten seconds to go, then a
 *  beep at three, two and one. */
const PING_BEFORE = 10_000;
const BEEPS_BEFORE = [3000, 2000, 1000];
/** AP up during a sequence: never later than this before the start … */
const AP_UP_BEFORE_START = 3000;
/** … and never sooner than this after the tap — the time to get the flag ready. */
const AP_UP_PREPARE = 5000;

export type SequenceState =
  | { kind: "idle"; preparatory: PreparatoryFlag }
  | {
      kind: "armed";
      preparatory: PreparatoryFlag;
      /** When the club flag goes up — the first signal of 3-2-1-0. */
      warningAt: number;
      /** Started by hauling AP down: AP comes down one minute before `warningAt`. */
      postponed: boolean;
      /** AP was tapped during the sequence: it goes up at this time, ending it. */
      apUpAt: number | null;
      /** When the committee last tapped this plan into being: a ping that would fall at
       *  or before it plays at the tap instead — "a flag in ten seconds or less" is
       *  announced at once. */
      tappedAt: number;
    };
export type ArmedSequence = Extract<SequenceState, { kind: "armed" }>;

export type SequenceEvent =
  | { type: "choose"; preparatory: PreparatoryFlag }
  | { type: "start"; now: number; at: "now" | "minute" }
  | { type: "abort" }
  | { type: "postponementDown"; now: number; at: "now" | "minute" }
  | { type: "postpone"; now: number };

/** When a sequence tapped at `now` sends its first signal: 10 s later, or on the first
 *  full minute of the clock that is at least 10 s away (tapped at 14:04:52 → 14:06:00). */
export function warningTime(now: number, at: "now" | "minute"): number {
  return at === "now" ? now + LEAD : Math.ceil((now + LEAD) / MINUTE) * MINUTE;
}

export function sequenceReducer(state: SequenceState, event: SequenceEvent): SequenceState {
  const preparatory = state.preparatory;
  switch (event.type) {
    case "choose":
      return state.kind === "idle" ? { kind: "idle", preparatory: event.preparatory } : state;
    case "start":
      return {
        kind: "armed",
        preparatory,
        warningAt: warningTime(event.now, event.at),
        postponed: false,
        apUpAt: null,
        tappedAt: event.now,
      };
    case "abort":
      return { kind: "idle", preparatory };
    case "postponementDown":
      return {
        kind: "armed",
        preparatory,
        // AP comes down when a sequence would have begun; the club flag a minute later.
        warningAt: warningTime(event.now, event.at) + MINUTE,
        postponed: true,
        apUpAt: null,
        tappedAt: event.now,
      };
    case "postpone": {
      const at = state.kind === "armed" ? apUpTime(state, event.now) : null;
      return state.kind === "armed" && at !== null && state.apUpAt === null
        ? { ...state, apUpAt: at, tappedAt: event.now }
        : state;
    }
  }
  return state;
}

/** When AP tapped at `now` would go up during this sequence: 10 s later, but at the latest
 *  3 s before the start — and null when that leaves less than 5 s to get ready, i.e. in the
 *  last 8 s. Between 13 and 8 s before the start, AP goes up 3 s before it. */
export function apUpTime(sequence: ArmedSequence, now: number): number | null {
  const at = Math.min(now + LEAD, sequence.warningAt + SEQUENCE_LENGTH - AP_UP_BEFORE_START);
  return at >= now + AP_UP_PREPARE ? at : null;
}

/** One signal: when (relative to the club flag going up), what the committee does, the
 *  sound and how many of it, and the flags that are up from then on. */
export interface Signal {
  after: number;
  action: "apUp" | "apDown" | "clubUp" | "preparatoryUp" | "preparatoryDown" | "start";
  tone: "short" | "long";
  sounds: number;
  club: boolean;
  preparatory: boolean;
}

const AP_DOWN: Signal = {
  after: -MINUTE,
  action: "apDown",
  tone: "short",
  sounds: 1,
  club: false,
  preparatory: false,
};

const SEQUENCE: readonly Signal[] = [
  { after: 0, action: "clubUp", tone: "short", sounds: 1, club: true, preparatory: false },
  { after: MINUTE, action: "preparatoryUp", tone: "short", sounds: 1, club: true, preparatory: true },
  {
    after: 2 * MINUTE,
    action: "preparatoryDown",
    tone: "long",
    sounds: 1,
    club: true,
    preparatory: false,
  },
  { after: 3 * MINUTE, action: "start", tone: "short", sounds: 1, club: false, preparatory: false },
];

export const SEQUENCE_LENGTH = 3 * MINUTE;

/** The signals this sequence will still make: AP down first for a postponed one; and once
 *  AP is tapped, everything from its count-in on gives way to AP up, two sounds. */
function signalsOf(sequence: ArmedSequence): readonly Signal[] {
  const all = sequence.postponed ? [AP_DOWN, ...SEQUENCE] : [...SEQUENCE];
  if (sequence.apUpAt === null) return all;
  const apUp: Signal = {
    after: sequence.apUpAt - sequence.warningAt,
    action: "apUp",
    tone: "short",
    sounds: 2,
    club: false,
    preparatory: false,
  };
  return [...all.filter((s) => sequence.warningAt + s.after < sequence.apUpAt!), apUp];
}

export interface Phase {
  club: boolean;
  preparatory: boolean;
  /** The next signal and when it is due; null once the start is reached. */
  next: Signal | null;
  nextAt: number | null;
  startAt: number;
  /** A postponed sequence whose AP is due down. */
  apDown: boolean;
  /** AP tapped during the sequence, and its time to go up has come. */
  apUp: boolean;
}

export function phaseAt(sequence: ArmedSequence, now: number): Phase {
  const signals = signalsOf(sequence);
  const done = signals.filter((s) => sequence.warningAt + s.after <= now);
  const last = done[done.length - 1];
  const next = signals[done.length];
  return {
    club: last?.club ?? false,
    preparatory: last?.preparatory ?? false,
    next: next ?? null,
    nextAt: next ? sequence.warningAt + next.after : null,
    startAt: sequence.warningAt + SEQUENCE_LENGTH,
    apDown: sequence.postponed && now >= sequence.warningAt - MINUTE,
    apUp: sequence.apUpAt !== null && now >= sequence.apUpAt,
  };
}

/** The sounds due in `(from, to]`, each with its exact time: the count-in (ping, beeps) before
 *  each signal, and the signal's own tone. The screen books them ahead (`LOOKAHEAD`). */
export function tonesBetween(
  sequence: ArmedSequence,
  from: number,
  to: number,
): { at: number; tone: Tone }[] {
  const tones: { at: number; tone: Tone; apUp: boolean }[] = [];
  for (const signal of signalsOf(sequence)) {
    const at = sequence.warningAt + signal.after;
    const apUp = signal.action === "apUp";
    // A signal ten seconds or less after the tap gets its ping at the tap.
    if (at > sequence.tappedAt) {
      tones.push({ at: Math.max(at - PING_BEFORE, sequence.tappedAt), tone: "ping", apUp });
    }
    for (const before of BEEPS_BEFORE) tones.push({ at: at - before, tone: "beep", apUp });
    for (let i = 0; i < signal.sounds; i += 1) {
      tones.push({ at: at + i * soundSpacing(signal.tone) * 1000, tone: signal.tone, apUp });
    }
  }
  // Once AP is coming, its count-in owns the last seconds: the sequence's own beeps from
  // then on would only blur it.
  const cutoff =
    sequence.apUpAt === null ? Infinity : Math.min(sequence.apUpAt - PING_BEFORE, sequence.tappedAt);
  return tones
    .filter((t) => (t.apUp || t.at < cutoff) && t.at > from && t.at <= to)
    .map(({ at, tone }) => ({ at, tone }));
}

/** How far ahead the screen books tones on the audio clock. Longer than the second a
 *  background tab's timers may be throttled to, so no tone is booked late. */
export const LOOKAHEAD = 1500;

/** The sequence of one race, mirrored to this device — the chosen flag included. The
 *  race-control card remounts on every change of the race (hoisting AP is one), and a phone
 *  on a boat reloads; without the mirror either would silently drop a running sequence or
 *  reset the flag to P (docs/gotchas). A sequence whose start has passed is dropped rather
 *  than fired late. */
export function useStartSequence(
  raceId: number,
  scheduled: boolean,
): [SequenceState, (event: SequenceEvent) => void] {
  const key = `sbl.start-sequence.${raceId}`;
  const [state, setState] = useState<SequenceState>(() => restore(key, scheduled));
  useEffect(() => {
    try {
      window.localStorage.setItem(key, JSON.stringify(state));
    } catch {
      // private mode: the sequence lasts for this page only
    }
  }, [key, state]);
  const dispatch = useCallback(
    (event: SequenceEvent) => setState((current) => sequenceReducer(current, event)),
    [],
  );
  return [state, dispatch];
}

function restore(key: string, scheduled: boolean): SequenceState {
  try {
    const stored = JSON.parse(window.localStorage.getItem(key) ?? "null") as SequenceState | null;
    if (stored?.preparatory) {
      const live =
        scheduled && stored.kind === "armed" && Date.now() < stored.warningAt + SEQUENCE_LENGTH;
      // Saved by a version without `tappedAt`: no tap to ping at.
      if (live) return { ...stored, tappedAt: stored.tappedAt ?? 0 };
      return { kind: "idle", preparatory: stored.preparatory };
    }
  } catch {
    // unreadable: start from idle
  }
  return { kind: "idle", preparatory: "P" };
}
