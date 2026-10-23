import { Button } from "@heroui/react";
import { useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";

import {
  useListCandidateClubs,
  useListParticipants,
  useSetParticipants,
  useUpdateEvent,
} from "../../../api/generated/sbl";
import type { Club, EventSummary } from "../../../api/types";
import { useAsync, type AsyncState } from "../../../api/useApi";
import { Async } from "../../../components/Async";
import { ClubSelector } from "../../../components/ClubSelector";
import { Field, Message } from "../../../components/Form";
import { Stack } from "../../../components/Layouts";
import { INPUT_CLASS, errorText, toggleSet } from "../../../lib/admin";
import { Select } from "../../../components/Select";

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
 *  A club enters one team, or as many as the event's *Teams per club* allows (Story VA-13):
 *  the request lists a club's id once per team, and a selected club then gets a count.
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
  const [chosenCounts, setChosenCounts] = useState<Map<number, number> | null>(null);
  const [chosenPerClub, setChosenPerClub] = useState<string | null>(null);
  // What this block last stored: the `event` prop catches up only when its refetch lands,
  // and a second save before that would compare against the old number.
  const [savedPerClub, setSavedPerClub] = useState<number | null>(null);

  // Server state until the first click, the local set afterwards. Seeding `useState` from
  // the query instead would freeze whatever the first render happened to see — the query
  // is still pending then, so it would freeze an empty selection.
  const entered = new Set((participants.data ?? []).map((p) => p.club.id));
  const selection = selectedClubs ?? entered;
  const toggle = toggleSet((updater) => setSelectedClubs((prev) => updater(prev ?? entered)));

  const storedPerClub = savedPerClub ?? event.teams_per_club ?? 1;
  const perClubText = chosenPerClub ?? String(storedPerClub);
  const perClub = Math.max(1, Math.min(Number(perClubText) || 1, event.team_count));
  const enteredCounts = new Map<number, number>();
  for (const p of participants.data ?? []) {
    enteredCounts.set(p.club.id, Math.max(enteredCounts.get(p.club.id) ?? 0, p.number ?? 1));
  }
  const counts = chosenCounts ?? enteredCounts;
  const teamsOf = (clubId: number) => Math.min(counts.get(clubId) ?? 1, perClub);
  const requested = [...selection].flatMap((id) => Array<number>(teamsOf(id)).fill(id));
  const setCount = (clubId: number, count: number) =>
    setChosenCounts(new Map(counts).set(clubId, count));
  const names = new Map((candidates.data ?? []).map((club) => [club.id, club.short_name]));

  const field: AsyncState<ClubField> = {
    loading: candidates.loading || participants.loading,
    error: candidates.error ?? participants.error,
    data: candidates.data && participants.data ? { candidates: candidates.data, entered } : null,
  };

  const save = useSetParticipants({
    mutation: {
      onSuccess: () => {
        setSelectedClubs(null);
        setChosenCounts(null);
        setChosenPerClub(null);
        onSaved();
      },
    },
  });
  const update = useUpdateEvent();
  const busy = save.isPending || update.isPending;

  // The organizer's parameter and the teams it limits, saved in the order the server
  // accepts: a higher number before the extra teams, the extra teams away before a lower
  // number (`teams-per-club-below-entered`).
  async function submit() {
    const current = storedPerClub;
    if (perClub > current) {
      await update.mutateAsync({ eventId: event.id, data: { teams_per_club: perClub } });
      setSavedPerClub(perClub);
    }
    await save.mutateAsync({ eventId: event.id, data: { clubs: requested } });
    if (perClub < current) {
      await update.mutateAsync({ eventId: event.id, data: { teams_per_club: perClub } });
      setSavedPerClub(perClub);
      // The clubs' save refreshed the event before the lower number was stored.
      onSaved();
    }
  }

  return (
    <Stack gap={3}>
      <h3 className="text-sm font-semibold text-foreground" data-testid={headingTestId}>
        {t("manage.clubsTitle", { count: requested.length, configured: event.team_count })}
      </h3>
      <Field label={t("manage.teamsPerClubLabel")} hint={t("manage.teamsPerClubHint")}>
        <input
          className={`${INPUT_CLASS} max-w-[8rem]`}
          type="number"
          min={1}
          max={event.team_count}
          value={perClubText}
          disabled={frozen}
          onChange={(e) => setChosenPerClub(e.target.value)}
          data-testid={`${testId}-teams-per-club`}
        />
      </Field>
      <p className="text-sm text-muted">
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
          <Stack gap={3}>
            <ClubSelector
              clubs={data.candidates}
              selectedIds={selection}
              toggle={toggle}
              testId={testId}
            />
            {perClub > 1 && selection.size > 0 && (
              <ul className="flex flex-wrap gap-3" data-testid={`${testId}-team-counts`}>
                {[...selection].map((clubId) => (
                  <li key={clubId}>
                    <Field label={t("manage.teamsOfClubLabel", { club: names.get(clubId) ?? clubId })}>
                      <Select
                        size="inline"
                        value={String(teamsOf(clubId))}
                        onChange={(e) => setCount(clubId, Number(e.target.value))}
                        testId={`${testId}-team-count-${clubId}`}
                      >
                        {Array.from({ length: perClub }, (_, i) => i + 1).map((n) => (
                          <option key={n} value={n}>
                            {n}
                          </option>
                        ))}
                      </Select>
                    </Field>
                  </li>
                ))}
              </ul>
            )}
          </Stack>
        )}
      </Async>
      {showCountHint && requested.length !== event.team_count && (
        <p className="text-sm text-warning-soft-foreground" data-testid={`${testId}-mismatch`}>
          {t("events.clubsCountHint", { expected: event.team_count, actual: requested.length })}
        </p>
      )}
      <div className="flex flex-wrap items-center gap-3">
        <Button
          size="sm"
          isDisabled={busy || frozen || field.data === null}
          onPress={() => void submit().catch(() => undefined)}
          data-testid={saveTestId}
        >
          {busy ? t("manage.savingButton") : saveLabel(requested.length)}
        </Button>
        {frozen && <span className="text-sm text-muted">{t("manage.frozenClubsHint")}</span>}
        {children}
      </div>
      <Message
        testId={messageTestId}
        error={save.isError ? errorText(save.error) : update.isError ? errorText(update.error) : null}
        success={save.isSuccess && savedText ? savedText : null}
      />
    </Stack>
  );
}
