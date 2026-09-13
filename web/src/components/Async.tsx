import type { ReactNode } from "react";

import type { AsyncState } from "../api/useApi";
import { Empty, ErrorMessage, Loading } from "./Blocks";

/** One request, rendered — the three states every screen here has to handle.
 *
 *     <Async state={clubs} testId="clubs" empty={t("noClubs")}>
 *       {(data) => <ul>{data.map(...)}</ul>}
 *     </Async>
 *
 * Twelve pages wrote this out by hand, each with the same shape and the same testid
 * convention (`clubs-loading`, `clubs-error`, `clubs-empty`) — which is exactly why it
 * belongs in one place: the convention already existed, only its enforcement did not. A
 * hand-written copy is where the empty case goes missing, or a page renders `null` on a
 * failed request and looks like it simply has nothing.
 *
 * `children` is a function, so it is called only once there is data — and `data` inside it
 * is non-null without a check.
 */
export function Async<T>({
  state,
  testId,
  children,
  loadingText,
  empty,
  isEmpty = defaultIsEmpty,
}: {
  state: AsyncState<T>;
  /** Names all three states: `${testId}-loading`, `-error`, `-empty`. */
  testId: string;
  children: (data: T) => ReactNode;
  loadingText?: string;
  /** Shown instead of `children` when the answer arrived and holds nothing. Omitted, an
   *  empty answer simply renders `children` — right for a page that draws its own empty
   *  state inside a frame it wants to keep. */
  empty?: ReactNode;
  /** What "nothing" means for this payload. An empty list by default; pass your own for a
   *  record whose emptiness is a field. */
  isEmpty?: (data: T) => boolean;
}) {
  if (state.loading) return <Loading text={loadingText} testId={`${testId}-loading`} />;
  if (state.error) return <ErrorMessage text={state.error} testId={`${testId}-error`} />;
  // No data and no error: the query is disabled, or has not been asked. Nothing to draw
  // and nothing to say.
  if (state.data === null) return null;
  if (empty !== undefined && isEmpty(state.data)) {
    return <Empty testId={`${testId}-empty`}>{empty}</Empty>;
  }
  return <>{children(state.data)}</>;
}

function defaultIsEmpty(data: unknown): boolean {
  return Array.isArray(data) && data.length === 0;
}
