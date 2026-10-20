import { Button } from "@heroui/react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";

import {
  getDownloadPairingPdfUrl,
  getGetReadinessQueryKey,
  useGetPairing,
  useGetReadiness,
  usePublishEvent,
  useUnpublishEvent,
} from "../../../api/generated/sbl";
import type { EventSummary } from "../../../api/types";
import { useAsync, useInvalidate } from "../../../api/useApi";
import { Async } from "../../../components/Async";
import { Message } from "../../../components/Form";
import { Stack } from "../../../components/Layouts";
import { Steps } from "../../../components/Steps";
import { errorText } from "../../../lib/admin";
import { DrawControl } from "./DrawControl";
import { EventClubsEditor } from "./EventClubsEditor";
import { GeneralDataStep } from "./GeneralDataStep";
import { PublicationBadge } from "./PublicationBadge";
import { ReadinessReasons } from "./ReadinessReasons";
import { StepActions } from "./StepActions";

type WizardStep = 1 | 2 | 3 | "done";

/** The three steps a new event is created in, in the order the work happens (Story VA-6):
 *  general data, the clubs that enter, the pairing list — on its own page,
 *  `/admin/events/new` (`AdminEventNew`). The event **exists after step 1**
 *  — the create request is that step's submit — so everything after it works on a saved
 *  event through the same endpoints the manage panel uses, and each later step can be
 *  skipped and finished there. The closing screen says whether the event is ready and
 *  offers publication, because the calendar entry often precedes the field. */
export function CreateEventWizard({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation("admin");
  const [step, setStep] = useState<WizardStep>(1);
  const [event, setEvent] = useState<EventSummary | null>(null);

  return (
    <Stack gap={4} testId="admin-events-wizard">
      <Steps
        testId="admin-events-steps"
        current={step === "done" ? 4 : step}
        steps={[t("events.stepGeneral"), t("events.stepClubs"), t("events.stepPairing")]}
      />
      {/* The creation message stays up through the later steps: the event is saved, and
          the steps that follow are refinements of it, not conditions on it. */}
      {event && (
        <Message
          testId="admin-events-create-message"
          error={null}
          success={t("events.createdMessage", { title: event.title })}
        />
      )}
      {step === 1 && (
        <GeneralDataStep
          onCreated={(created) => {
            setEvent(created);
            setStep(2);
          }}
          onCancel={onClose}
        />
      )}
      {step === 2 && event && (
        <ClubsStep event={event} onNext={() => setStep(3)} onSkip={() => setStep("done")} />
      )}
      {step === 3 && event && (
        <PairingStep
          event={event}
          onDone={() => setStep("done")}
          onBack={() => setStep(2)}
          onSkip={() => setStep("done")}
        />
      )}
      {step === "done" && event && (
        <ReadyStep
          event={event}
          onChanged={setEvent}
          onAnother={() => {
            setEvent(null);
            setStep(1);
          }}
          onClose={onClose}
        />
      )}
    </Stack>
  );
}

/** Step 2: who enters — the same editor as the manage panel's. A series' registrations
 *  were adopted at creation, so they arrive pre-selected; the step is then a confirmation,
 *  not a search. */
function ClubsStep({
  event,
  onNext,
  onSkip,
}: {
  event: EventSummary;
  onNext: () => void;
  onSkip: () => void;
}) {
  const { t } = useTranslation("admin");
  const invalidate = useInvalidate();

  return (
    <EventClubsEditor
      event={event}
      testId="admin-events-clubs"
      headingTestId="admin-events-clubs-count"
      saveTestId="admin-events-clubs-next-button"
      saveLabel={(count) => t("events.clubsNextButton", { count })}
      messageTestId="admin-events-clubs-message"
      showCountHint
      onSaved={() => {
        invalidate("/api/admin/events", "/api/events");
        onNext();
      }}
    >
      {/* The field can be entered later — a standalone regatta collects its clubs over
          weeks, and the manage panel has the same selector. */}
      <Button size="sm" variant="ghost" onPress={onSkip} data-testid="admin-events-clubs-skip-button">
        {t("events.skipButton")}
      </Button>
    </EventClubsEditor>
  );
}

/** Step 3: the draw (Story VA-7). Refused visibly while the setup is incomplete — the
 *  same readiness reasons the server would answer with — rather than fired blind the
 *  way the old automatic draw was, which for a new event without clubs failed every time
 *  and made that failure the first thing the organizer read. */
function PairingStep({
  event,
  onDone,
  onBack,
  onSkip,
}: {
  event: EventSummary;
  onDone: () => void;
  onBack: () => void;
  onSkip: () => void;
}) {
  const { t } = useTranslation("admin");
  const invalidate = useInvalidate();
  const readiness = useAsync(useGetReadiness(event.id));

  return (
    <Stack gap={3}>
      <h3 className="text-sm font-semibold text-foreground">{t("manage.pairingTitle")}</h3>
      <p className="text-sm text-muted">{t("manage.pairingMissingHint")}</p>
      <Async state={readiness} testId="admin-events-draw-readiness" loadingText={t("manage.readinessLoadingText")}>
        {(data) =>
          !data.ready && (
            <div
              data-testid="admin-events-draw-blocked"
              className="rounded-md bg-warning-soft px-3 py-2 text-sm text-warning-soft-foreground"
            >
              <p>{t("events.drawBlockedHint")}</p>
              <ReadinessReasons
                reasons={data.reasons ?? []}
                testId="admin-events-draw-reasons"
                reasonTestId="admin-events-draw-reason"
              />
            </div>
          )
        }
      </Async>
      <DrawControl
        eventId={event.id}
        ready={readiness.data?.ready ?? false}
        testIds={{
          field: "admin-events-draw-seed-field",
          seed: "admin-events-draw-seed-input",
          button: "admin-events-draw-button",
          message: "admin-events-draw-message",
        }}
        seedHint={t("events.seedHint")}
        onDrawn={() => {
          invalidate("/api/admin/events", "/api/events", getGetReadinessQueryKey(event.id));
          onDone();
        }}
      >
        <Button size="sm" variant="ghost" onPress={onBack} data-testid="admin-events-draw-back-button">
          {t("events.backButton")}
        </Button>
        <Button size="sm" variant="ghost" onPress={onSkip} data-testid="admin-events-draw-skip-button">
          {t("events.skipButton")}
        </Button>
      </DrawControl>
    </Stack>
  );
}

/** The closing screen: ready 🚀, or what is still missing and where it is finished. It
 *  offers publication here because the calendar entry often precedes the field (Story
 *  VA-8), and — once published with a list — the pairing list and its PDF, which are
 *  public pages and therefore exist only for a published event. */
function ReadyStep({
  event,
  onChanged,
  onAnother,
  onClose,
}: {
  event: EventSummary;
  onChanged: (event: EventSummary) => void;
  onAnother: () => void;
  onClose: () => void;
}) {
  const { t } = useTranslation("admin");
  const invalidate = useInvalidate();
  const readiness = useAsync(useGetReadiness(event.id));
  const ready = readiness.data?.ready ?? false;
  const hasPairing = readiness.data?.has_pairing_list ?? false;
  const complete = ready && hasPairing;
  const published = event.published ?? false;
  // The public pairing endpoint: a draft answers 404 there, so it is asked only once the
  // event is published — and it is what says whether this server can print (Story B-3).
  const pairing = useGetPairing(event.id, { query: { enabled: published && hasPairing } });
  const pdfAvailable = pairing.data?.pdf_available ?? false;

  const refresh = () => invalidate("/api/admin/events", "/api/events", "/api/series");
  const publishEvent = usePublishEvent({
    mutation: { onSuccess: (updated) => { refresh(); onChanged(updated); } },
  });
  const unpublishEvent = useUnpublishEvent({
    mutation: { onSuccess: (updated) => { refresh(); onChanged(updated); } },
  });
  const publish = published ? unpublishEvent : publishEvent;

  return (
    <Stack gap={3}>
      <div data-testid="admin-events-ready" data-ready={complete ? "true" : "false"}>
        <Async state={readiness} testId="admin-events-ready" loadingText={t("manage.readinessLoadingText")}>
          {(data) => (
            <>
              <h3
                data-testid="admin-events-ready-title"
                className={`text-base font-semibold ${complete ? "text-success-soft-foreground" : "text-foreground"}`}
              >
                {complete ? t("events.readyTitle") : t("events.notReadyTitle")}
              </h3>
              {!complete && (
                <>
                  <ReadinessReasons
                    reasons={data.reasons ?? []}
                    testId="admin-events-ready-reasons"
                    reasonTestId="admin-events-ready-reason"
                    className="text-sm text-warning-soft-foreground"
                  >
                    {!hasPairing && (
                      <li data-testid="admin-events-ready-missing-pairing">· {t("events.missingPairing")}</li>
                    )}
                  </ReadinessReasons>
                  <p className="mt-2 text-sm text-muted">{t("events.finishLaterHint")}</p>
                </>
              )}
            </>
          )}
        </Async>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <PublicationBadge published={published} testId="admin-events-publication" />
        <Button
          size="sm"
          variant={published ? "ghost" : "primary"}
          isDisabled={publish.isPending}
          onPress={() => publish.mutate({ eventId: event.id })}
          data-testid="admin-events-publish-button"
        >
          {published ? t("manage.unpublishButton") : t("manage.publishButton")}
        </Button>
        {published && hasPairing && (
          <Link
            to={`/events/${event.id}`}
            data-testid="admin-events-pairing-link"
            className="text-sm underline underline-offset-2"
          >
            {t("manage.openPairingLink")}
          </Link>
        )}
        {/* A plain anchor, not a generated hook: the answer is a PDF, and `api/http.ts`
            parses everything it handles as JSON. Shown only where the server can print,
            because a link whose only answer is 503 is worse than none. */}
        {published && hasPairing && pdfAvailable && (
          <a
            href={getDownloadPairingPdfUrl(event.id)}
            download
            data-testid="admin-events-pairing-pdf-link"
            className="text-sm font-medium text-link underline-offset-2 hover:underline"
          >
            {t("events.pairingPdfLink")}
          </a>
        )}
      </div>
      <p className="text-sm text-muted">
        {!published && hasPairing ? t("events.publishToShareHint") : t("manage.publishHint")}
      </p>
      <Message
        testId="admin-events-publish-message"
        error={publish.isError ? errorText(publish.error) : null}
        success={null}
      />

      <StepActions>
        <Button size="sm" onPress={onClose} data-testid="admin-events-back-button">
          {t("page.backButton")}
        </Button>
        <Button size="sm" variant="ghost" onPress={onAnother} data-testid="admin-events-another-button">
          {t("page.anotherButton")}
        </Button>
      </StepActions>
    </Stack>
  );
}
