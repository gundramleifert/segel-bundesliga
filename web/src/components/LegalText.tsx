import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

/** Shared rendering for the two legal pages (`pages/LegalNotice.tsx`, `pages/Privacy.tsx`).
 *
 *  Both pages are pure text: a list of sections, each a heading with paragraphs and
 *  optionally a bullet list and an "open question" callout. All of it comes from the
 *  `legal` i18n namespace, so both languages render through the runtime language switcher
 *  without any German literal in the source.
 */
export interface LegalSection {
  heading: string;
  paragraphs: string[];
  /** Optional bullet list below the paragraphs. */
  items?: string[];
  /** Optional marked open question — a point that still needs a human decision
   *  (a retention period, the consent wording for the tracker) and is deliberately
   *  not guessed at. Rendered as a visibly separate callout, not as ordinary prose. */
  open?: string;
}

/** Split pattern (capturing, so the markers survive in the result) and a separate
 *  non-global pattern for testing a fragment — `RegExp.test` on a `/g` regex advances
 *  `lastIndex` and would then skip every other match. */
const PENDING_SPLIT = /(«[^»]+»)/g;
const IS_PENDING = /^«[^»]+»$/;

/** Highlights «…» markers — values that are genuinely not available yet.
 *
 *  The association's own Impressum lists its register court and register number as
 *  "[folgt]"; those two are carried over as markers rather than invented, and marking
 *  them makes an incomplete entry look incomplete instead of hiding in the prose.
 */
function withPendingMarkers(text: string): ReactNode[] {
  return text.split(PENDING_SPLIT).map((part, index) =>
    IS_PENDING.test(part) ? (
      <mark
        key={index}
        data-testid="legal-pending-value"
        className="rounded bg-amber-100 px-1 font-mono text-[0.85em] font-semibold text-amber-900 ring-1 ring-amber-300"
      >
        {part}
      </mark>
    ) : (
      part
    ),
  );
}

/** The banner on the privacy policy: its controller details are real, but the document
 *  as a whole is a draft with open points and has to be reviewed before it goes live.
 *  Deliberately loud — a half-finished privacy policy must not be mistaken for a
 *  finished one. */
export function LegalDraftNotice({ testId }: { testId: string }) {
  const { t } = useTranslation("legal");

  return (
    <div
      role="alert"
      data-testid={testId}
      className="mb-8 rounded-lg border-2 border-amber-400 bg-amber-50 px-4 py-4 text-amber-900"
    >
      <p className="flex items-center gap-2 text-base font-bold">
        <span aria-hidden>⚠</span>
        {t("draft.title")}
      </p>
      <p className="mt-2 text-sm">{t("draft.body")}</p>
      <p className="mt-2 text-sm">{t("draft.openQuestions")}</p>
    </div>
  );
}

export function LegalLastUpdated({ text, testId }: { text: string; testId: string }) {
  return (
    <p data-testid={testId} className="mb-8 text-sm text-slate-500">
      {text}
    </p>
  );
}

export function LegalSections({
  sections,
  testIdPrefix,
}: {
  sections: LegalSection[];
  testIdPrefix: string;
}) {
  const { t } = useTranslation("legal");

  return (
    <div className="grid max-w-3xl gap-8">
      {sections.map((section, index) => (
        <section key={section.heading} data-testid={`${testIdPrefix}-section-${index + 1}`}>
          <h2 className="mb-2 text-lg font-semibold text-slate-900">{section.heading}</h2>
          {section.paragraphs.map((paragraph) => (
            <p key={paragraph} className="mb-2 whitespace-pre-line text-slate-700">
              {withPendingMarkers(paragraph)}
            </p>
          ))}
          {section.items && (
            <ul className="mt-2 list-disc space-y-1 pl-5 text-slate-700">
              {section.items.map((item) => (
                <li key={item}>{withPendingMarkers(item)}</li>
              ))}
            </ul>
          )}
          {section.open && (
            <p
              data-testid={`${testIdPrefix}-open-question-${index + 1}`}
              className="mt-3 border-l-4 border-amber-400 bg-amber-50/60 py-2 pl-3 text-sm text-amber-900"
            >
              <span className="font-semibold">{t("openQuestionLabel")}</span>{" "}
              {withPendingMarkers(section.open)}
            </p>
          )}
        </section>
      ))}
    </div>
  );
}
