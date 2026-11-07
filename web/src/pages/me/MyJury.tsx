import { Button } from "@heroui/react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { getGetMyJuryQueryKey, useAnswerJuryRequest, useGetMyJury, useSetMyLicences } from "../../api/generated/sbl";
import { JudgeLicence, JuryState, type JuryRequestOut, type MyJuryOut } from "../../api/generated/model";
import { errorText, useAsync, useInvalidate } from "../../api/useApi";
import { Async } from "../../components/Async";
import { Badge, ErrorMessage } from "../../components/Blocks";
import { Message, Section } from "../../components/Form";
import { eventDates } from "../../lib/format";
import { JURY_TONE } from "../../lib/jury";

/** Stories JU-2, JU-4: *Me › Jury* — the licences I say I hold, and my requests, each
 *  answered *I can* or *I cannot* until the jury organizer approved me. */
export function MyJury() {
  const { t } = useTranslation("space");
  const mine = useAsync(useGetMyJury());
  return (
    <Async state={mine} testId="me-jury">
      {(data) => (
        <div className="grid grid-cols-[minmax(0,1fr)] gap-6" data-testid="me-jury">
          <Licences held={data.licences} />
          <Section title={t("jury.requestsTitle")} testId="me-jury-requests">
            {data.requests.length ? (
              <Requests requests={data.requests} />
            ) : (
              <p className="text-sm text-muted" data-testid="me-jury-requests-empty">
                {t("jury.requestsEmpty")}
              </p>
            )}
          </Section>
        </div>
      )}
    </Async>
  );
}

function Licences({ held }: { held: MyJuryOut["licences"] }) {
  const { t } = useTranslation("space");
  const invalidate = useInvalidate();
  const [chosen, setChosen] = useState<Set<JudgeLicence>>(new Set(held));
  const save = useSetMyLicences({ mutation: { onSuccess: () => invalidate(getGetMyJuryQueryKey(), "/api/jury") } });
  const toggle = (licence: JudgeLicence) =>
    setChosen((now) => {
      const next = new Set(now);
      if (next.has(licence)) next.delete(licence);
      else next.add(licence);
      return next;
    });
  return (
    <Section title={t("jury.licencesTitle")} testId="me-jury-licences">
      <p className="text-sm text-muted">{t("jury.licencesHint")}</p>
      <div className="flex flex-col gap-2 text-sm">
        {Object.values(JudgeLicence).map((licence) => (
          <label key={licence} className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={chosen.has(licence)}
              onChange={() => toggle(licence)}
              data-testid={`me-jury-licence-${licence}`}
            />
            {t(`jury.licences.${licence}`)}
          </label>
        ))}
      </div>
      <div>
        <Button
          size="sm"
          isDisabled={save.isPending}
          onPress={() => save.mutate({ data: { licences: [...chosen] } })}
          data-testid="me-jury-licences-save"
        >
          {t("jury.save")}
        </Button>
      </div>
      <Message
        success={save.isSuccess ? t("jury.saved") : null}
        error={save.error ? errorText(save.error) : null}
        testId="me-jury-licences"
      />
    </Section>
  );
}

function Requests({ requests }: { requests: JuryRequestOut[] }) {
  const { t } = useTranslation("space");
  const invalidate = useInvalidate();
  const answer = useAnswerJuryRequest({
    mutation: { onSuccess: () => invalidate(getGetMyJuryQueryKey(), "/api/me/contexts", "/api/jury") },
  });
  return (
    <>
      <ul className="divide-y divide-separator text-sm" data-testid="me-jury-requests-list">
        {requests.map((request) => {
          const id = request.event.id;
          const approved = request.state === JuryState.approved;
          return (
            <li key={id} className="flex flex-wrap items-center gap-2 py-2" data-testid={`me-jury-request-${id}`}>
              <span className="min-w-0 flex-1">
                <span className="font-medium">{request.event.title}</span>
                <span className="block text-xs text-muted">
                  {[request.event.series, eventDates(request.event)].filter(Boolean).join(" · ")}
                </span>
              </span>
              <Badge tone={JURY_TONE[request.state]} testId={`me-jury-state-${id}`}>
                {t(`jury.states.${request.state}`)}
              </Badge>
              {!approved && (
                <>
                  <Button
                    size="sm"
                    variant={request.state === JuryState.available ? "primary" : "secondary"}
                    isDisabled={answer.isPending}
                    onPress={() => answer.mutate({ eventId: id, data: { available: true } })}
                    data-testid={`me-jury-available-${id}`}
                  >
                    {t("jury.available")}
                  </Button>
                  <Button
                    size="sm"
                    variant={request.state === JuryState.declined ? "primary" : "secondary"}
                    isDisabled={answer.isPending}
                    onPress={() => answer.mutate({ eventId: id, data: { available: false } })}
                    data-testid={`me-jury-decline-${id}`}
                  >
                    {t("jury.decline")}
                  </Button>
                </>
              )}
            </li>
          );
        })}
      </ul>
      {answer.error && <ErrorMessage text={errorText(answer.error)} testId="me-jury-answer-error" />}
    </>
  );
}
