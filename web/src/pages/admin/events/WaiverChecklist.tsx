import { useState } from "react";
import { useTranslation } from "react-i18next";

import { getGetWaiverScanUrl, useEventWaivers } from "../../../api/generated/sbl";
import { useAsync } from "../../../api/useApi";
import { Async } from "../../../components/Async";
import { ErrorMessage, TableFrame } from "../../../components/Blocks";
import { Stack } from "../../../components/Layouts";
import { WaiverName, WaiverStatus } from "../../../components/WaiverStatus";
import { errorText } from "../../../lib/admin";
import { openFile } from "../../../lib/files";

/** Story VA-5: the organizer's check-in list — who in the participating squads is cleared,
 * and the guardian's uploaded form for a minor, opened with the token (Story S-1). */
export function WaiverChecklist({ eventId }: { eventId: number }) {
  const { t } = useTranslation("admin");
  const list = useAsync(useEventWaivers(eventId));
  const [scanError, setScanError] = useState<string | null>(null);

  return (
    <Stack gap={3} testId={`admin-manage-event-waivers-section-${eventId}`}>
      <h3 className="text-sm font-semibold text-foreground">{t("manage.waiversTitle")}</h3>
      <p className="text-sm text-muted">{t("manage.waiversHint")}</p>
      <Async
        state={list}
        testId={`admin-manage-event-waivers-list-${eventId}`}
        loadingText={t("manage.waiversLoadingText")}
        empty={t("manage.waiversEmpty")}
        isEmpty={(data) => data.people.length === 0}
      >
        {(data) => (
          <>
            <p className="text-sm" data-testid={`admin-manage-event-waivers-summary-${eventId}`}>
              {data.required_version == null
                ? t("manage.waiversNoVersion")
                : t("manage.waiversSummary", {
                    cleared: data.cleared,
                    outstanding: data.outstanding,
                    version: data.required_version,
                  })}
            </p>
            <TableFrame testId={`admin-manage-event-waivers-${eventId}`}>
              <table className="data-table w-full border-collapse text-sm">
                <thead>
                  <tr className="text-left text-xs uppercase tracking-wide text-muted">
                    <th className="px-3 py-2">{t("manage.waiverColSailor")}</th>
                    <th className="px-3 py-2">{t("manage.waiverColClub")}</th>
                    <th className="px-3 py-2">{t("manage.waiverColStatus")}</th>
                  </tr>
                </thead>
                <tbody>
                  {data.people.map((row) => (
                    <tr
                      key={row.person_id}
                      className="border-t border-separator"
                      data-testid={`admin-manage-event-waiver-row-${eventId}-${row.person_id}`}
                      data-status={row.status}
                    >
                      <td className="px-3 py-2">
                        <WaiverName first={row.first_name} last={row.last_name} minor={row.minor} />
                      </td>
                      <td className="px-3 py-2 text-muted">{row.club ?? "—"}</td>
                      <td className="px-3 py-2">
                        <WaiverStatus status={row.status} />
                        {row.scan_available && row.confirmation_id != null && (
                          <button
                            type="button"
                            className="ml-2 text-xs underline underline-offset-2"
                            onClick={() => {
                              setScanError(null);
                              openFile(getGetWaiverScanUrl(row.confirmation_id!)).catch((err) =>
                                setScanError(errorText(err)),
                              );
                            }}
                            data-testid={`admin-manage-event-waiver-scan-${eventId}-${row.person_id}`}
                          >
                            {t("manage.waiverOpenScan")}
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </TableFrame>
            {scanError && <ErrorMessage text={scanError} />}
          </>
        )}
      </Async>
    </Stack>
  );
}
