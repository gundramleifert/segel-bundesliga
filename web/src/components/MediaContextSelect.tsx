import { useTranslation } from "react-i18next";

import { useListAllEvents, useListAllSeries } from "../api/generated/sbl";
import { WHOLE_LIST, useAsyncRows } from "../api/useApi";
import { NO_CONTEXT, type MediaContext } from "../lib/mediaContext";
import { Select } from "./Select";

const encode = (c: MediaContext) => (c.event_id ? `e${c.event_id}` : c.series_id ? `s${c.series_id}` : "");
const decode = (value: string): MediaContext =>
  value.startsWith("e")
    ? { event_id: Number(value.slice(1)), series_id: null }
    : value.startsWith("s")
      ? { event_id: null, series_id: Number(value.slice(1)) }
      : NO_CONTEXT;

/** Each series, and under it its events — so a regatta is found under its season. */
export function MediaContextSelect({
  value,
  onChange,
  noneLabel,
  testId,
  size = "field",
}: {
  value: MediaContext;
  onChange: (context: MediaContext) => void;
  /** The empty choice: "all pictures" for a filter, "none" for a picture. */
  noneLabel: string;
  testId: string;
  size?: "field" | "inline";
}) {
  const { t } = useTranslation("admin");
  const series = useAsyncRows(useListAllSeries({ limit: WHOLE_LIST }));
  const events = useAsyncRows(useListAllEvents({ limit: WHOLE_LIST }));
  const lone = (events.data ?? []).filter((e) => !e.series);

  return (
    <Select size={size} value={encode(value)} onChange={(e) => onChange(decode(e.target.value))} testId={testId} aria-label={t("media.contextLabel")}>
      <option value="">{noneLabel}</option>
      {(series.data ?? []).map((s) => (
        <optgroup key={s.id} label={s.name}>
          <option value={`s${s.id}`}>{t("media.contextWholeSeries", { name: s.name })}</option>
          {(events.data ?? [])
            .filter((e) => e.series?.id === s.id)
            .map((e) => (
              <option key={e.id} value={`e${e.id}`}>
                {e.title}
              </option>
            ))}
        </optgroup>
      ))}
      {lone.length > 0 && (
        <optgroup label={t("media.contextLoneEvents")}>
          {lone.map((e) => (
            <option key={e.id} value={`e${e.id}`}>
              {e.title}
            </option>
          ))}
        </optgroup>
      )}
    </Select>
  );
}
