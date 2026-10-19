/** What a picture is of — an event, a series, or nothing (Story R-2). One of the two ids,
 *  never both: an event implies its series. */
export type MediaContext = { event_id: number | null; series_id: number | null };

export const NO_CONTEXT: MediaContext = { event_id: null, series_id: null };
