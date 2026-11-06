import { Button } from "@heroui/react";
import { useTranslation } from "react-i18next";

import { useFetchResultsFromSap, useSendEventToSap, useUpdateEvent } from "../../../api/generated/sbl";
import { ResultsSource, type EventSummary } from "../../../api/types";
import { useEventAccess, useInvalidate } from "../../../api/useApi";
import { Field, Message } from "../../../components/Form";
import { Stack } from "../../../components/Layouts";
import { SapAttribution } from "../../../components/SapAttribution";
import { Select } from "../../../components/Select";
import { errorText } from "../../../lib/admin";

/** *Set up › Scoring* — where the event's results come from (Story VA-14): this site, or
 *  SAP Sailing. With SAP, the event is sent there (VA-15), its race committee works in
 *  SAP's Race Manager app, and its results are taken back (WL-5) — by the server every
 *  few seconds while live, or here on request. SAP is offered only where this
 *  installation has SAP's account (`EventAccess.sap`). */
export function EventScoring({ event }: { event: EventSummary }) {
  const { t } = useTranslation("space");
  const invalidate = useInvalidate();
  const access = useEventAccess(event.id);
  const refresh = () => invalidate("/api/admin/events", "/api/events", "/api/me/contexts");
  const save = useUpdateEvent({ mutation: { onSuccess: refresh } });
  const send = useSendEventToSap({ mutation: { onSuccess: refresh } });
  const fetch = useFetchResultsFromSap({ mutation: { onSuccess: refresh } });
  const onSap = event.results_source === ResultsSource.sap;
  const offered = onSap || Boolean(access.sap);
  const sent = send.data;
  const taken = fetch.data;
  return (
    <Stack gap={4}>
      <Field label={t("scoring.sourceLabel")}>
        <Select
          value={event.results_source ?? ResultsSource.site}
          disabled={save.isPending || !offered}
          onChange={(e) => save.mutate({ eventId: event.id, data: { results_source: e.target.value as ResultsSource } })}
          testId="me-event-scoring-source"
        >
          <option value={ResultsSource.site}>{t("scoring.site")}</option>
          <option value={ResultsSource.sap}>{t("scoring.sap")}</option>
        </Select>
      </Field>
      <p className="text-sm text-muted" data-testid="me-event-scoring-hint">
        {onSap ? t("scoring.onSap") : offered ? t("scoring.onSite") : t("scoring.sapUnavailable")}
      </p>
      <Message testId="me-event-scoring-save" error={save.isError ? errorText(save.error) : null} />
      {onSap && (
        <Stack gap={3}>
          <p className="text-sm" data-testid="me-event-scoring-leaderboard">
            {event.sap_leaderboard
              ? t("scoring.leaderboard", { name: event.sap_leaderboard })
              : t("scoring.notSent")}
            {event.sap_leaderboard_url && (
              <>
                {" "}
                <a href={event.sap_leaderboard_url} target="_blank" rel="noopener noreferrer" className="underline" data-testid="me-event-scoring-viewer">
                  {t("scoring.openAtSap")}
                </a>
              </>
            )}
          </p>
          <div className="flex flex-wrap gap-2">
            <Button
              size="sm"
              isDisabled={send.isPending}
              onPress={() => send.mutate({ eventId: event.id })}
              data-testid="me-event-scoring-send"
            >
              {send.isPending ? t("scoring.sending") : t("scoring.send")}
            </Button>
            {event.sap_leaderboard && (
              <Button
                size="sm"
                variant="outline"
                isDisabled={fetch.isPending}
                onPress={() => fetch.mutate({ eventId: event.id })}
                data-testid="me-event-scoring-fetch"
              >
                {fetch.isPending ? t("scoring.fetching") : t("scoring.fetch")}
              </Button>
            )}
          </div>
          <Message
            testId="me-event-scoring-send"
            error={send.isError ? errorText(send.error) : null}
            success={
              sent
                ? t("scoring.sent", { leaderboard: sent.leaderboard, created: sent.teams_created, kept: sent.teams_kept, races: sent.races })
                : null
            }
          />
          <Message
            testId="me-event-scoring-fetch"
            error={fetch.isError ? errorText(fetch.error) : null}
            success={taken ? t("scoring.fetched", { count: taken.results, warnings: taken.warnings.length }) : null}
          />
          <SapAttribution href={event.sap_leaderboard_url} testId="me-event-scoring-sap-attribution" />
        </Stack>
      )}
    </Stack>
  );
}
