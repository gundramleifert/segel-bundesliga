/** The sound of a running start sequence — booked by its own timer, not by the screen.
 *
 * The race-control card used to book tones from an effect that ran on every tick of the
 * page. That tied the horn to React: a page that fell behind (a busy phone, the dev build
 * re-rendering twenty times a second) booked late, and a card that remounted mid-sequence
 * booked again what it found due — a beep a second late, a signal twice. Here a plain
 * interval books ahead on the audio clock (`LOOKAHEAD`), the card only says which sequence
 * is armed, and a remount saying the same thing again changes nothing.
 */
import { audioTime, hornOnce } from "./horn";
import { LOOKAHEAD, tonesBetween, type ArmedSequence } from "./startSequence";

/** Often enough that the look-ahead never runs dry, even with a background tab's timers
 *  throttled to one a second. */
const INTERVAL = 200;
/** AP's second sound lies 1.6 s after its first — beyond the look-ahead — and the
 *  sequence is over the moment AP is up, so its sounds are booked this far ahead. */
const AP_UP_TAIL = 5000;

let current: ArmedSequence | null = null;
let bookedUntil = 0;
let timer: number | undefined;

/** Plays this sequence's sounds; `null` stops booking (what is booked still sounds — the
 *  start's own tone must not be cut off; an abort silences through `silenceHorn`). The
 *  same sequence again — a remounted card — is a no-op. */
export function playSequence(sequence: ArmedSequence | null): void {
  if (JSON.stringify(sequence) === JSON.stringify(current)) return;
  current = sequence;
  if (!sequence) {
    window.clearInterval(timer);
    timer = undefined;
    return;
  }
  // From just before the tap: a ping due at the tap itself is booked at once.
  bookedUntil = sequence.tappedAt - 1;
  book();
  timer ??= window.setInterval(book, INTERVAL);
}

function book(): void {
  if (!current) return;
  const now = Date.now();
  // A tone more than half a second overdue — a phone waking from sleep — is skipped
  // rather than blown late.
  const from = Math.max(bookedUntil, now - 500);
  let until = now + LOOKAHEAD;
  if (current.apUpAt !== null && until >= current.apUpAt) {
    until = Math.max(until, current.apUpAt + AP_UP_TAIL);
  }
  bookedUntil = Math.max(bookedUntil, until);
  // One reading of each clock for the whole batch, so the tones keep their spacing.
  const base = audioTime();
  for (const { at, tone } of tonesBetween(current, from, until)) {
    hornOnce(`${at}:${tone}`, tone, (at - now) / 1000, base);
  }
}
