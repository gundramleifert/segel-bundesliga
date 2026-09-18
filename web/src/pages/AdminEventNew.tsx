import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import { CreateEventWizard } from "./AdminEvents";
import { NewEntryPage } from "./AdminNewPage";

/** `/admin/events/new` — Story VA-6: the three steps, on their own page. Leaving the
 *  wizard, from step 1 or from the closing screen, returns to the events tab, where the
 *  new event is first in the list. */
export function AdminEventNew() {
  const { t } = useTranslation("admin");
  const navigate = useNavigate();
  return (
    <NewEntryPage title={t("events.wizardTitle")} testId="admin-events-new">
      <CreateEventWizard onClose={() => navigate("/admin?tab=events")} />
    </NewEntryPage>
  );
}
