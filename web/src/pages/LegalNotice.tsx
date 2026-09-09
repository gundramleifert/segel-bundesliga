import { useTranslation } from "react-i18next";

import { PageHeader } from "../components/Blocks";
import type { LegalSection } from "../components/LegalText";
import { LegalLastUpdated, LegalSections } from "../components/LegalText";

/** Legal notice ("Impressum") — the provider information § 5 DDG requires of a German
 *  public website, plus the editorially responsible person under § 18 Abs. 2 MStV, which
 *  applies once the site carries news posts.
 *
 *  The values are the association's own, taken from what Deutsche Segel-Liga e.V.
 *  publishes itself. Two of them — register court and association register number — are
 *  listed as "[folgt]" on that page too; they are carried over as «…» markers rather than
 *  invented, and § 5 DDG does require them for a registered association, so they remain
 *  a real gap to close.
 */
export function LegalNotice() {
  const { t } = useTranslation("legal");
  // There is no typed resource declaration in this project (see `pages/Help.tsx`), so the
  // shape of a `returnObjects` lookup can't be inferred from the key and is asserted here.
  const sections = t("legalNotice.sections", { returnObjects: true }) as LegalSection[];

  return (
    <>
      <PageHeader
        title={t("legalNotice.title")}
        subtitle={t("legalNotice.subtitle")}
        testId="legal-notice-header"
      />
      <LegalLastUpdated
        text={t("legalNotice.lastUpdated")}
        testId="legal-notice-last-updated"
      />
      <LegalSections sections={sections} testIdPrefix="legal-notice" />
    </>
  );
}
