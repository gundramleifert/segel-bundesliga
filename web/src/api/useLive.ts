/** The browser half of Story B-5: one open stream per page, and a refetch on every change.
 *
 * `useLive("event:12", [getGetEventQueryKey(12), "/api/events/12/"])` opens an
 * `EventSource` on the event's stream and, whenever a `change` frame arrives, invalidates
 * the given targets — the same generated keys and path prefixes `useInvalidate` takes after
 * a mutation. The stream carries a version token, never the data: the page refetches
 * through the generated client, so nothing here can disagree with what a reload would show.
 *
 * Three states, for the badge:
 *
 * - `"live"` — the stream is open. Changes arrive within a second or two.
 * - `"reconnecting"` — the browser lost the stream and is reconnecting on its own
 *   (`EventSource` does that, with the `retry:` the server sent). The table stays on
 *   screen; only the badge changes.
 * - `"off"` — repeated failures, or the server refused the stream: the hook falls back to
 *   **polling** every {@link POLL_MILLIS} and tries the stream again after
 *   {@link RETRY_STREAM_MILLIS}. A proxy that buffers streams degrades the page to this;
 *   it never breaks it.
 *
 * `/api/live` is the one API path written by hand in the frontend: the endpoint is kept
 * out of the OpenAPI document on purpose, because a generated hook for a
 * `text/event-stream` would resolve once with a body it cannot parse.
 */
import { useEffect, useRef, useState } from "react";

import { useInvalidate } from "./useApi";

export type LiveState = "live" | "reconnecting" | "off";

type Target = readonly unknown[] | string;

/** Failed connects in a row before the hook stops trusting the stream and polls instead. */
const FAILURES_BEFORE_POLLING = 3;
/** How often the page refetches while polling. Twenty seconds is a race's finish spread. */
export const POLL_MILLIS = 20_000;
/** How long the hook polls before giving the stream another chance. */
const RETRY_STREAM_MILLIS = 60_000;

interface LiveOptions {
  /** Called with the payload of every inline frame — today only `positions` (Story L-1),
   *  the one payload that travels in the stream instead of behind a refetch. */
  onPositions?: (payload: unknown) => void;
}

export function useLive(
  topic: string | null,
  targets: Target[],
  options: LiveOptions = {},
): LiveState {
  const invalidate = useInvalidate();
  const [state, setState] = useState<LiveState>(topic ? "reconnecting" : "off");

  // The targets are rebuilt on every render (they are arrays); reading them through a ref
  // keeps the effect keyed on the topic alone, so the stream is not torn down and reopened
  // each time the page re-renders.
  const targetsRef = useRef(targets);
  targetsRef.current = targets;
  const invalidateRef = useRef(invalidate);
  invalidateRef.current = invalidate;
  const optionsRef = useRef(options);
  optionsRef.current = options;

  useEffect(() => {
    if (!topic) {
      setState("off");
      return;
    }

    let source: EventSource | null = null;
    let failures = 0;
    let everOpened = false;
    let poll: ReturnType<typeof setInterval> | null = null;
    let retry: ReturnType<typeof setTimeout> | null = null;

    // Spread, not passed as one array: `useInvalidate` is variadic, and an array handed
    // over as a single target matches no query and invalidates nothing, silently.
    const refetch = () => invalidateRef.current(...targetsRef.current);

    function stopPolling() {
      if (poll) clearInterval(poll);
      if (retry) clearTimeout(retry);
      poll = retry = null;
    }

    function startPolling() {
      setState("off");
      poll = setInterval(refetch, POLL_MILLIS);
      retry = setTimeout(() => {
        stopPolling();
        failures = 0;
        connect();
      }, RETRY_STREAM_MILLIS);
    }

    function connect() {
      const stream = new EventSource(`/api/live?topic=${encodeURIComponent(topic!)}`);
      source = stream;
      setState("reconnecting");
      stream.onopen = () => {
        failures = 0;
        setState("live");
        // A *re*connect may have missed a change. The browser sends `Last-Event-ID` only
        // when the same EventSource reconnects by itself; after polling this is a new
        // one, so one refetch on open settles it. Not on the first open: the page has
        // just loaded its data.
        if (everOpened) refetch();
        everOpened = true;
      };
      stream.addEventListener("change", refetch);
      stream.addEventListener("positions", (frame) => {
        try {
          optionsRef.current.onPositions?.(JSON.parse((frame as MessageEvent).data));
        } catch {
          // A frame that does not parse is dropped; the next one is a second away.
        }
      });
      stream.onerror = () => {
        failures += 1;
        // CLOSED means the browser gave up (a non-200 answer, a 404 for a draft); anything
        // else is a reconnect in progress, which we tolerate a few times.
        if (stream.readyState === EventSource.CLOSED || failures >= FAILURES_BEFORE_POLLING) {
          stream.close();
          source = null;
          startPolling();
        } else {
          setState("reconnecting");
        }
      };
    }

    connect();
    return () => {
      source?.close();
      stopPolling();
    };
  }, [topic]);

  return state;
}
