import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { LOOK_DEFAULT, MEDIA_MODES, applyLook, setLook, setMediaMode, useLook, useMediaMode, type Look } from "./settings";

/** The DEV button, bottom left: what is still being decided (Story B-13) — the picture as
 *  photo, fade, slide or video, and the glass over it. Built in wherever the role switcher
 *  is (`DEV_TOOLS`), so the stakeholders can try it on staging, on their own phones. */
export function DevSwitch() {
  const { t } = useTranslation("site");
  const [open, setOpen] = useState(false);
  const media = useMediaMode();
  const look = useLook();
  useEffect(() => applyLook(look), [look]);
  return (
    <div className="fixed bottom-4 left-4 z-50 text-sm" data-testid="site-dev">
      {open && (
        <div className="mb-2 max-h-[80dvh] w-64 overflow-y-auto rounded-2xl bg-slate-900/95 p-4 text-white shadow-2xl backdrop-blur">
          <Segment label={t("dev.pictures")} value={media} options={MEDIA_MODES} onChange={setMediaMode} testId="site-dev-media" />
          <LookSliders look={look} />
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

/** The glass over the pictures, live: how dark and how blurred a card is, how far the
 *  picture is darkened, how strong the secondary text is. */
function LookSliders({ look }: { look: Look }) {
  const { t } = useTranslation("site");
  const sliders: { key: keyof Look; min: number; max: number; step: number; unit?: string }[] = [
    { key: "cardAlpha", min: 0, max: 0.95, step: 0.05 },
    { key: "cardBlur", min: 0, max: 32, step: 2, unit: "px" },
    { key: "shade", min: 0, max: 0.9, step: 0.05 },
    { key: "text", min: 0.5, max: 1, step: 0.05 },
  ];
  return (
    <div className="mt-3 border-t border-white/10 pt-3" data-testid="site-dev-look">
      <p className="mb-1.5 text-xs uppercase tracking-widest text-white/50">{t("dev.look")}</p>
      {sliders.map((s) => (
        <label key={s.key} className="mb-2 block text-xs">
          <span className="flex justify-between text-white/80">
            <span>{t(`dev.${s.key}`)}</span>
            <span className="tabular-nums text-white/50">
              {look[s.key]}
              {s.unit ?? ""}
            </span>
          </span>
          <input
            type="range"
            min={s.min}
            max={s.max}
            step={s.step}
            value={look[s.key]}
            onChange={(event) => setLook({ ...look, [s.key]: Number(event.target.value) })}
            data-testid={`site-dev-look-${s.key}`}
            className="w-full accent-white"
          />
        </label>
      ))}
      <button
        type="button"
        onClick={() => setLook(LOOK_DEFAULT)}
        className="mt-1 rounded-full bg-white/10 px-3 py-1 text-xs font-semibold hover:bg-white/20"
        data-testid="site-dev-look-reset"
      >
        {t("dev.reset")}
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
