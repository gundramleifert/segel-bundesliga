import { useTranslation } from "react-i18next";

import { PageHeader } from "../components/Blocks";
import type { LegalSection } from "../components/LegalText";
import { LegalDraftNotice, LegalLastUpdated, LegalSections } from "../components/LegalText";

/** Privacy policy ("Datenschutzerklärung") — the Art. 13 DSGVO information, written
 *  against what this system actually stores: accounts without passwords (Google and
 *  Microsoft OIDC, or a one-time code by email), sailor profiles including birth dates
 *  and photos with their extra protection for minors, waivers, club memberships, and
 *  the GPS tracking that is planned but not built yet.
 *
 *  The controller's own details are real — same legal entity as the Impressum. The
 *  document as a whole is still a **draft**: every point that depends on a decision
 *  nobody has made — retention periods, the deletion concept and consent wording for
 *  position data, whether a data protection officer is appointed — is marked as an open
 *  question instead of being guessed at, and the banner says the page needs review
 *  before it goes live.
 */
export function Privacy() {
  const { t } = useTranslation("legal");
  // See `pages/LegalNotice.tsx` on why the shape has to be asserted here.
  const sections = t("privacy.sections", { returnObjects: true }) as LegalSection[];

  return (
    <>
      <PageHeader
        title={t("privacy.title")}
        subtitle={t("privacy.subtitle")}
        testId="privacy-header"
      />
      <LegalDraftNotice testId="privacy-draft-notice" />
      <LegalLastUpdated text={t("privacy.lastUpdated")} testId="privacy-last-updated" />
      <LegalSections sections={sections} testIdPrefix="privacy" />
    </>
  );
}
