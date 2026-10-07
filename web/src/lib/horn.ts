/** The phone as a start horn — a cue for whoever works the real one (Story WL-3).
 *
 * Web Audio, no sound files: one oscillator per tone — a short or a long one as the racing
 * rules count sounds, and a soft beep for the count-in before each. A browser plays
 * nothing until a tap has unlocked audio, so the tap that starts a sequence calls
 * `unlockHorn()`; tones requested before that stay silent instead of failing. Muting is a per-device choice, kept in `localStorage`.
 */

/** Before a signal: `ping` at ten seconds to go, `beep` at three, two and one. The signal
 *  itself is `short` or `long`, as the racing rules count it. */
export type Tone = "ping" | "beep" | "short" | "long";

/** Like a kart-race start light: the count-in low and plain (A4), the signal an octave
 *  higher (A5), so the ear tells "get ready" from "now" without counting. The ping is a
 *  different kind of sound altogether — a bell that fades — so "ten seconds" is never
 *  mistaken for a beep. */
const SOUND: Record<
  Tone,
  { seconds: number; hertz: number; volume: number; wave: OscillatorType; fade: boolean }
> = {
  ping: { seconds: 0.6, hertz: 1320, volume: 0.2, wave: "sine", fade: true },
  beep: { seconds: 0.2, hertz: 440, volume: 0.12, wave: "square", fade: false },
  short: { seconds: 0.6, hertz: 880, volume: 0.25, wave: "square", fade: false },
  long: { seconds: 2.0, hertz: 880, volume: 0.25, wave: "square", fade: false },
};

/** Silence between the sounds of one signal — AP up's two, a recall's two long ones. */
const SOUND_GAP = 1.0;

/** From the start of one sound of a signal to the start of the next, in seconds. */
export function soundSpacing(tone: Tone): number {
  return SOUND[tone].seconds + SOUND_GAP;
}
const MUTE_KEY = "sbl.race-control.muted";

let context: AudioContext | null = null;
/** Tones booked but not yet over — what `silenceHorn()` cancels when a sequence aborts. */
const pending = new Set<OscillatorNode>();
/** The keys of the tones booked through `hornOnce`, so none is booked twice. */
const bookedKeys = new Set<string>();

/** Call from a tap. Creates (or wakes) the audio context the tones play through. */
export function unlockHorn(): void {
  try {
    // iOS mutes web audio with the ring/silent switch unless the page declares its sound
    // as playback (Safari 17+); a horn that the silent switch swallows is no horn.
    const session = (navigator as Navigator & { audioSession?: { type: string } }).audioSession;
    if (session) session.type = "playback";
    context ??= new AudioContext();
    void context.resume();
  } catch {
    context = null; // no Web Audio here — the screen still works, silently
  }
}

/** Whether a tone would actually sound now: audio unlocked by a tap and running. After a
 *  reload — on a boat, or the dev server's — a restored sequence has had no tap yet. */
export function hornReady(): boolean {
  return context?.state === "running";
}

export function hornMuted(): boolean {
  try {
    return window.localStorage.getItem(MUTE_KEY) === "1";
  } catch {
    return false;
  }
}

export function setHornMuted(muted: boolean): void {
  try {
    window.localStorage.setItem(MUTE_KEY, muted ? "1" : "0");
  } catch {
    // private mode: the choice lasts for this page only
  }
}

/** Plays a tone `inSeconds` from now, booked on the audio clock. That clock is exact; the
 *  page's timers are not — they fire late when the tab is busy or in the background, and a
 *  tone played "when the timer noticed" turned an even count-in into an uneven one. The
 *  device's output delay (a Bluetooth speaker adds a fifth of a second) is booked away, so
 *  the tone is *heard* when the countdown on the screen turns. */
export function horn(tone: Tone, inSeconds = 0): void {
  if (!context || hornMuted()) return;
  const at = context.currentTime + Math.max(0, inSeconds - outputLatency());
  const { seconds: length, hertz, volume, wave, fade } = SOUND[tone];
  const oscillator = context.createOscillator();
  const gain = context.createGain();
  oscillator.type = wave;
  oscillator.frequency.value = hertz;
  // A few milliseconds of ramp at each end, or the tone starts and stops with a click; a
  // fading tone decays from its peak instead of holding it, which is what makes a ping.
  gain.gain.setValueAtTime(0, at);
  gain.gain.linearRampToValueAtTime(volume, at + 0.01);
  if (fade) {
    gain.gain.exponentialRampToValueAtTime(0.0001, at + length);
  } else {
    gain.gain.setValueAtTime(volume, at + length - 0.03);
    gain.gain.linearRampToValueAtTime(0, at + length);
  }
  oscillator.connect(gain).connect(context.destination);
  pending.add(oscillator);
  oscillator.onended = () => pending.delete(oscillator);
  oscillator.start(at);
  oscillator.stop(at + length);
}

/** The device's output delay, in seconds — booked away so a tone is *heard* on time. */
function outputLatency(): number {
  return context ? context.outputLatency || context.baseLatency || 0 : 0;
}

/** A signal of several sounds, as the racing rules count them — AP up is two, a recall
 *  two long ones — a second apart. Sounding *now*, the first cannot be moved earlier by
 *  the output delay; so all of them are booked as if it could not, or only the later ones
 *  would shift and the spacing come out short. */
export function hornSounds(tone: Tone, count: number): void {
  const latency = outputLatency();
  for (let i = 0; i < count; i += 1) horn(tone, latency + i * soundSpacing(tone));
}

/** Cancels every booked tone — an aborted sequence must not beep on for another second. */
/** `horn`, but at most once per `key` — a sequence's tone is its exact time and kind. The
 *  look-ahead books each window once, yet a remounted card or a re-run effect starts with no
 *  memory of what was booked; this is the one place that remembers, so a beep is never
 *  heard twice. `silenceHorn` forgets, so a re-timed sequence can book again. */
export function hornOnce(key: string, tone: Tone, inSeconds: number): void {
  if (bookedKeys.has(key)) return;
  bookedKeys.add(key);
  horn(tone, inSeconds);
}

export function silenceHorn(): void {
  bookedKeys.clear();
  for (const oscillator of pending) {
    try {
      oscillator.stop();
    } catch {
      // already over
    }
  }
  pending.clear();
}
