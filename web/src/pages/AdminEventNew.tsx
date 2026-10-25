import { useTranslation } from "react-i18next";
import { Navigate, useNavigate } from "react-router-dom";

import { CreateEventWizard } from "./admin/events/Wizard";
import { NewEntryPage, useCreateDoor } from "./AdminNewPage";

/** Story VA-6: the three steps a new event is created in, on their own page — at two
 *  addresses, one per door (Story A-11, issue #32):
 *
 * - **`/office/events/new`** for the league office (its *Events* section: the site's
 *   `admin` and race committee); leaving returns to that section, where the new event is
 *   first in the list.
 * - **`/me/event/new`** for an organizer who has no office — a series' manager adding its
 *   acts, a club's organizer an event their club hosts (Stories A-6, VA-6). Leaving
 *   returns to My space. Which series and which host they may pick is the server's answer
 *   (`GET /api/events/create-options`), read by the first step.
 *
 * An organizer sent to the office's address is passed on to theirs, query and all.
 */
export function AdminEventNew() {
  const { t } = useTranslation("admin");
  const navigate = useNavigate();
  const { atOffice, passOn } = useCreateDoor("events");

  if (passOn) return <Navigate to={passOn} replace />;
  return (
    <NewEntryPage title={t("events.wizardTitle")} area="events" outside={!atOffice} testId="admin-events-new">
      <CreateEventWizard onClose={() => navigate(atOffice ? "/office/events" : "/me")} />
    </NewEntryPage>
  );
}
