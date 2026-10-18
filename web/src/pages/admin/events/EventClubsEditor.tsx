import { Button } from "@heroui/react";
import { useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";

import {
  useListCandidateClubs,
  useListParticipants,
  useSetParticipants,
} from "../../../api/generated/sbl";
import type { Club, EventSummary } from "../../../api/types";
import { useAsync, type AsyncState } from "../../../api/useApi";
import { Async } from "../../../components/Async";
import { ClubSelector } from "../../../components/ClubSelector";
import { Message } from "../../../components/Form";
import { Stack } from "../../../components/Layouts";
import { errorText, toggleSet } from "../../../lib/admin";

interface ClubField {
  candidates: Club[];
  entered: Set<number>;
}

/** Who enters an event — the wizard's second step and the manage panel's clubs block.
 *
 *  The candidates come from the server (`GET …/candidate-clubs`, Story VA-6): an act of a
 *  series offers its series' accepted registrations, a stand-alone event every club, which
 *  is the case that makes this site a service to clubs outside the association's own series.
 *  That is the rule `PUT …/clubs` enforces (`app/services/participation.py`), asked rather
 *  than recomputed here from every series and every club.
 *
 *  `testId` names the selector (`ClubSelector`'s own ids follow from it) and its states
 *  (`${testId}-loading`, `-error`, `-empty`). `children` sit beside the save button. */
export function EventClubsEditor({
  event,
  testId,
  headingTestId,
  saveTestId,
  saveLabel,
  messageTestId,
  savedText,
  frozen = false,
  showCountHint = false,
  onSaved,
  children,
}: {
  event: EventSummary;
  testId: string;
  headingTestId?: string;
  saveTestId: string;
  saveLabel: (count: number) => string;
  messageTestId: string;
  savedText?: string;
  /** Racing has begun: the field is frozen with the configuration (Story VA-8). */
  frozen?: boolean;
  /** Says when the selection does not match the configured number of teams. */
  showCountHint?: boolean;
  onSaved: () => void;
  children?: ReactNode;
}) {
  const { t } = useTranslation("admin");
  const candidates = useAsync(useListCandidateClubs(event.id));
  const participants = useAsync(useListParticipants(event.id));
  const [selectedClubs, setSelectedClubs] = useState<Set<number> | null>(null);

  // Server state until the first click, the local set afterwards. Seeding `useState` from
  // the query instead would freeze whatever the first render happened to see — the query
  // is still pending then, so it would freeze an empty selection.
  const entered = new Set((participants.data ?? []).map((p) => p.club.id));
  const selection = selectedClubs ?? entered;
  const toggle = toggleSet((updater) => setSelectedClubs((prev) => updater(prev ?? entered)));

  const field: AsyncState<ClubField> = {
    loading: candidates.loading || participants.loading,
    error: candidates.error ?? participants.error,
    data: candidates.data && participants.data ? { candidates: candidates.data, entered } : null,
  };

  const save = useSetParticipants({
    mutation: {
      onSuccess: () => {
        setSelectedClubs(null);
        onSaved();
      },
    },
  });

  return (
    <Stack gap={3}>
      <h3 className="text-sm font-semibold text-slate-700" data-testid={headingTestId}>
        {t("manage.clubsTitle", { count: selection.size, configured: event.team_count })}
      </h3>
      <p className="text-sm text-slate-600">
        {event.series
          ? t("manage.clubsFromSeriesHint", { series: event.series.name })
          : t("manage.clubsStandaloneHint")}
      </p>
      <Async
        state={field}
        testId={testId}
        loadingText={t("manage.clubsLoadingText")}
        empty={event.series ? t("manage.seriesHasNoClubs") : t("manage.noClubsAtAll")}
        isEmpty={(data) => data.candidates.length === 0}
      >
        {(data) => (
          <ClubSelector
            clubs={data.candidates}
            selectedIds={selection}
            toggle={toggle}
            testId={testId}
          />
        )}
      </Async>
      {showCountHint && selection.size !== event.team_count && (
        <p className="text-sm text-amber-800" data-testid={`${testId}-mismatch`}>
          {t("events.clubsCountHint", { expected: event.team_count, actual: selection.size })}
        </p>
      )}
      <div className="flex flex-wrap items-center gap-3">
        <Button
          size="sm"
          isDisabled={save.isPending || frozen || field.data === null}
          onPress={() => save.mutate({ eventId: event.id, data: { clubs: [...selection] } })}
          data-testid={saveTestId}
        >
          {save.isPending ? t("manage.savingButton") : saveLabel(selection.size)}
        </Button>
        {frozen && <span className="text-sm text-slate-500">{t("manage.frozenClubsHint")}</span>}
        {children}
      </div>
      <Message
        testId={messageTestId}
        error={save.isError ? errorText(save.error) : null}
        success={save.isSuccess && savedText ? savedText : null}
      />
    </Stack>
  );
}
