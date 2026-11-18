import { Button } from "@heroui/react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import {
  getEventWaiversQueryKey,
  getGetWaiverScanUrl,
  useCheckInTeam,
  useEventWaivers,
  useUndoCheckInTeam,
} from "../../../api/generated/sbl";
import type { EventWaiverList } from "../../../api/types";
import { useAsync, useInvalidate } from "../../../api/useApi";
import { Async } from "../../../components/Async";
import { ErrorMessage, TableFrame } from "../../../components/Blocks";
import { Stack } from "../../../components/Layouts";
import { WaiverName, WaiverStatus } from "../../../components/WaiverStatus";
import { errorText } from "../../../lib/admin";
import { openFile } from "../../../lib/files";

/** Stories VA-2, VA-5: every entered team, checked in or not — a team checks in only
 * once everyone in its named crew has cleared the waiver (review 5.7, 2026-11-13); the
 * server refuses otherwise and says who holds it up. */
function TeamCheckIns({ eventId, list }: { eventId: number; list: EventWaiverList }) {
  const { t } = useTranslation("admin");
  const invalidate = useInvalidate();
  const [error, setError] = useState<string | null>(null);
  const refresh = {
    onSuccess: () => {
      setError(null);
      invalidate(getEventWaiversQueryKey(eventId), `/api/admin/events/${eventId}/crew`);
    },
    onError: (err: unknown) => setError(errorText(err)),
  };
  const checkIn = useCheckInTeam({ mutation: refresh });
  const undo = useUndoCheckInTeam({ mutation: refresh });
  const names = new Map(list.people.map((p) => [p.person_id, `${p.first_name} ${p.last_name}`]));
  if (list.teams.length === 0) return null;
  return (
    <>
      <TableFrame testId={`admin-manage-event-checkin-${eventId}`}>
        <table className="data-table w-full border-collapse text-sm">
          <thead>
            <tr className="text-left text-xs uppercase tracking-wide text-muted">
              <th className="px-3 py-2">{t("manage.checkInColTeam")}</th>
              <th className="px-3 py-2">{t("manage.checkInColCrew")}</th>
              <th className="px-3 py-2">{t("manage.checkInColStatus")}</th>
            </tr>
          </thead>
          <tbody>
            {list.teams.map((team) => {
              const blocked = team.crew === 0 || team.not_cleared.length > 0;
              return (
                <tr
                  key={team.team_id}
                  className="border-t border-separator"
                  data-testid={`admin-manage-event-checkin-row-${eventId}-${team.team_id}`}
                  data-checked-in={team.checked_in_at != null}
                >
                  <td className="px-3 py-2">{team.name}</td>
                  <td className="px-3 py-2 text-muted">
                    {team.crew === 0
                      ? t("manage.checkInNoCrew")
                      : team.not_cleared.length === 0
                        ? t("manage.checkInCrewCleared", { count: team.crew })
                        : t("manage.checkInCrewBlocked", {
                            names: team.not_cleared.map((id) => names.get(id) ?? `#${id}`).join(", "),
                          })}
                  </td>
                  <td className="px-3 py-2">
                    {team.checked_in_at != null ? (
                      <Button
                        size="sm"
                        variant="ghost"
                        isDisabled={undo.isPending}
                        onPress={() => undo.mutate({ eventId, teamId: team.team_id })}
                        data-testid={`admin-manage-event-checkin-undo-${eventId}-${team.team_id}`}
                      >
                        {t("manage.checkInUndo")}
                      </Button>
                    ) : (
                      <Button
                        size="sm"
                        isDisabled={blocked || checkIn.isPending}
                        onPress={() => checkIn.mutate({ eventId, teamId: team.team_id })}
                        data-testid={`admin-manage-event-checkin-button-${eventId}-${team.team_id}`}
                      >
                        {t("manage.checkInButton")}
                      </Button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </TableFrame>
      {error && <ErrorMessage text={error} />}
    </>
  );
}

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
            <TeamCheckIns eventId={eventId} list={data} />
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
                        <WaiverName person={row} />
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
