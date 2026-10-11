import { useState } from "react";
import { useTranslation } from "react-i18next";

import {
  CHAPTER_MODES,
  DETAIL_MODES,
  MEDIA_MODES,
  setChapterMode,
  setDetailMode,
  setMediaMode,
  useChapterMode,
  useDetailMode,
  useMediaMode,
} from "./settings";

/** The DEV button, bottom left: the variants of the site structure still being decided
 *  (Story B-13) — chapters snapping or scrolling freely, pictures as photo, fade, slide or
 *  video, and the depth page's frame. Built in wherever the role switcher is (`DEV_TOOLS`),
 *  so the stakeholders can switch on staging, on their own phones. */
export function DevSwitch() {
  const { t } = useTranslation("site");
  const [open, setOpen] = useState(false);
  const chapters = useChapterMode();
  const media = useMediaMode();
  const detail = useDetailMode();
  return (
    <div className="fixed bottom-4 left-4 z-50 text-sm" data-testid="site-dev">
      {open && (
        <div className="mb-2 w-64 rounded-2xl bg-slate-900/95 p-4 text-white shadow-2xl backdrop-blur">
          <Segment label={t("dev.chapters")} value={chapters} options={CHAPTER_MODES} onChange={setChapterMode} testId="site-dev-chapters" />
          <Segment label={t("dev.pictures")} value={media} options={MEDIA_MODES} onChange={setMediaMode} testId="site-dev-media" />
          <Segment label={t("dev.detail")} value={detail} options={DETAIL_MODES} onChange={setDetailMode} testId="site-dev-detail" />
        </div>
      )}
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        data-testid="site-dev-button"
        className="rounded-full bg-slate-900/90 px-4 py-2 font-mono text-xs font-semibold tracking-widest text-white shadow-xl backdrop-blur"
      >
        DEV {open ? "×" : "⚙"}
      </button>
    </div>
  );
}

function Segment<T extends string>({
  label,
  value,
  options,
  onChange,
  testId,
}: {
  label: string;
  value: T;
  options: readonly T[];
  onChange: (value: T) => void;
  testId: string;
}) {
  const { t } = useTranslation("site");
  return (
    <div className="mb-3 last:mb-0">
      <p className="mb-1.5 text-xs uppercase tracking-widest text-white/50">{label}</p>
      <div role="radiogroup" aria-label={label} className="flex rounded-full bg-white/10 p-0.5" data-testid={testId}>
        {options.map((v) => (
          <button
            key={v}
            type="button"
            role="radio"
            aria-checked={value === v}
            onClick={() => onChange(v)}
            data-testid={`${testId}-${v}`}
            className={`flex-1 rounded-full px-2 py-1 text-xs font-semibold ${value === v ? "bg-white text-slate-900" : "text-white/70 hover:text-white"}`}
          >
            {t(`dev.${v}`)}
          </button>
        ))}
      </div>
    </div>
  );
}
