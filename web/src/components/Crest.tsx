/** A club's crest, or an event's logo (which defaults to its host's crest) — Story V-3.
 *
 * Four screens had drawn it by hand, each at its size with its own frame, two with the
 * abbreviation standing in for a missing crest and two with nothing. One component: the
 * size is the screen's choice, everything else is not.
 *
 * - `sm` — inline beside a name (a crew card, a matchday card): no frame.
 * - `md` — a list's card (the clubs): framed on white, so a crest drawn for a dark
 *   background still reads.
 * - `lg` — a page's header (the club page): framed, larger.
 *
 * Without a crest, `short` (the club's abbreviation) stands in on brand blue, rather than
 * a grey placeholder that says nothing. Without `short` either, nothing is drawn.
 */
const SIZES = {
  sm: { box: "size-8", frame: "", fallback: "rounded text-[0.6rem]" },
  md: { box: "size-10", frame: "rounded-lg bg-white p-1 ring-1 ring-slate-200", fallback: "rounded-lg text-xs" },
  lg: { box: "size-20", frame: "rounded-xl bg-white p-2 ring-1 ring-slate-200", fallback: "rounded-xl text-lg" },
} as const;

export function Crest({
  src,
  short,
  size = "md",
  testId,
}: {
  src?: string | null;
  /** The club's abbreviation, shown when there is no crest. */
  short?: string;
  size?: keyof typeof SIZES;
  testId?: string;
}) {
  const { box, frame, fallback } = SIZES[size];
  if (src) {
    return <img src={src} alt="" className={`${box} shrink-0 object-contain ${frame}`} data-testid={testId} />;
  }
  if (!short) return null;
  return (
    <span
      aria-hidden
      className={`${box} ${fallback} grid shrink-0 place-items-center bg-brand-600 font-bold text-white`}
      data-testid={testId}
    >
      {short.slice(0, 4)}
    </span>
  );
}
