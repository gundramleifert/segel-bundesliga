/** The league's start sequence as a state machine (Story WL-3): 3-2-1-0.
 *
 *   idle ──start (in 10 s | next full minute)──▶ armed(warningAt)
 *   armed ──start──▶ armed(new warningAt)      restart: the same event again
 *   armed ──abort──▶ idle                      also what hoisting AP does
 *   any   ──general recall──▶ idle(1st Sub)    the First Substitute is up
 *   idle  ──lower AP or 1st Substitute (in 10 s | full minute)──▶ armed(lowering)
 *                                              the flag down then, the club flag a minute
 *                                              later
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

import type { StartSequence } from "../api/generated/model/startSequence";
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

/** A flag that stops the sequence and is lowered to start it again, one minute before the
 *  club flag: AP after a postponement, the First Substitute after a general recall. */
export type Lowering = "AP" | "firstSubstitute";

export type SequenceState =
  | {
      kind: "idle";
      preparatory: PreparatoryFlag;
      /** A general recall left the First Substitute up. Not a race signal on the server:
       *  the recall is the transition, the flag is the committee's next step. */
      firstSubstitute: boolean;
    }
  | {
      kind: "armed";
      preparatory: PreparatoryFlag;
      /** When the club flag goes up — the first signal of 3-2-1-0. */
      warningAt: number;
      /** Started by lowering AP or the First Substitute, one minute before `warningAt`. */
      lowering: Lowering | null;
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
  | { type: "lower"; flag: Lowering; now: number; at: "now" | "minute" }
  | { type: "postpone"; now: number }
  | { type: "recall" };

/** When a sequence tapped at `now` sends its first signal: 10 s later, or on the first
 *  full minute of the clock that is at least 10 s away (tapped at 14:04:52 → 14:06:00). */
export function warningTime(now: number, at: "now" | "minute"): number {
  return at === "now" ? now + LEAD : Math.ceil((now + LEAD) / MINUTE) * MINUTE;
}

export function sequenceReducer(state: SequenceState, event: SequenceEvent): SequenceState {
  const preparatory = state.preparatory;
  switch (event.type) {
    case "choose":
      return state.kind === "idle" ? { ...state, preparatory: event.preparatory } : state;
    case "start":
      return {
        kind: "armed",
        preparatory,
        warningAt: warningTime(event.now, event.at),
        lowering: null,
        apUpAt: null,
        tappedAt: event.now,
      };
    case "abort":
      // Aborting the lowering of the First Substitute leaves it up; anything else ends
      // with no flag of ours up (hoisting AP over it hands the lead to AP).
      return {
        kind: "idle",
        preparatory,
        firstSubstitute: state.kind === "armed" && state.lowering === "firstSubstitute",
      };
    case "lower":
      return {
        kind: "armed",
        preparatory,
        // The flag comes down when a sequence would have begun; the club flag a minute later.
        warningAt: warningTime(event.now, event.at) + MINUTE,
        lowering: event.flag,
        apUpAt: null,
        tappedAt: event.now,
      };
    case "recall":
      return { kind: "idle", preparatory, firstSubstitute: true };
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
  action:
    | "apUp"
    | "apDown"
    | "firstSubstituteDown"
    | "clubUp"
    | "preparatoryUp"
    | "preparatoryDown"
    | "start";
  tone: "short" | "long";
  sounds: number;
  club: boolean;
  preparatory: boolean;
}

/** Lowering AP or the First Substitute: one sound, a minute before the club flag. */
function lowered(flag: Lowering): Signal {
  return {
    after: -MINUTE,
    action: flag === "AP" ? "apDown" : "firstSubstituteDown",
    tone: "short",
    sounds: 1,
    club: false,
    preparatory: false,
  };
}

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

/** The signals this sequence will still make: the lowered flag first, if any; and once
 *  AP is tapped, everything from its count-in on gives way to AP up, two sounds. */
function signalsOf(sequence: ArmedSequence): readonly Signal[] {
  const all = sequence.lowering ? [lowered(sequence.lowering), ...SEQUENCE] : [...SEQUENCE];
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
  /** A sequence lowering AP whose time to haul it down has come. */
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
    apDown: sequence.lowering === "AP" && now >= sequence.warningAt - MINUTE,
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

/** What the server keeps of a sequence, for the live page (Stories WL-3, B-5): the armed
 *  sequence, or the First Substitute left up by a recall — null when neither. */
export function toServer(state: SequenceState): StartSequence | null {
  if (state.kind === "armed") {
    return {
      preparatory: state.preparatory,
      first_signal_at: state.warningAt,
      lowering: state.lowering,
      ap_up_at: state.apUpAt,
      first_substitute: false,
    };
  }
  if (!state.firstSubstitute) return null;
  return {
    preparatory: state.preparatory,
    first_signal_at: null,
    lowering: null,
    ap_up_at: null,
    first_substitute: true,
  };
}

/** The live page's side: the stored sequence as one the clock can be read against —
 *  `phaseAt` then says which flags are up and what comes next, exactly as it does on the
 *  committee's screen. Null when nothing is armed. */
export function fromServer(stored: StartSequence | null | undefined): ArmedSequence | null {
  if (!stored?.first_signal_at) return null;
  return {
    kind: "armed",
    preparatory: stored.preparatory,
    warningAt: stored.first_signal_at,
    lowering: stored.lowering ?? null,
    apUpAt: stored.ap_up_at ?? null,
    tappedAt: 0,
  };
}

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
    // Older versions saved `postponed` instead of `lowering`, and no `tappedAt`.
    const stored = JSON.parse(window.localStorage.getItem(key) ?? "null") as
      | (SequenceState & { postponed?: boolean })
      | null;
    if (stored?.preparatory) {
      if (stored.kind === "armed") {
        const live = scheduled && Date.now() < stored.warningAt + SEQUENCE_LENGTH;
        if (live) {
          return {
            ...stored,
            lowering: stored.lowering ?? (stored.postponed ? "AP" : null),
            tappedAt: stored.tappedAt ?? 0,
          };
        }
      }
      // The First Substitute stays up across a reload — while the race waits for its start.
      const firstSubstitute = scheduled && stored.kind === "idle" && Boolean(stored.firstSubstitute);
      return { kind: "idle", preparatory: stored.preparatory, firstSubstitute };
    }
  } catch {
    // unreadable: start from idle
  }
  return { kind: "idle", preparatory: "P", firstSubstitute: false };
}
