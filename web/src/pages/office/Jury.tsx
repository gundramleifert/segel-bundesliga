import { Button } from "@heroui/react";
import { keepPreviousData } from "@tanstack/react-query";
import { createColumnHelper } from "@tanstack/react-table";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import {
  useAddJudge,
  useApproveJudge,
  useInviteJudges,
  useListJudges,
  useListJuryCandidates,
  useListJuryEvents,
  useMessageJudges,
  useRemoveJudge,
  useTakeJudgeOff,
} from "../../api/generated/sbl";
import { JudgeLicence, JuryState, type JudgeOut, type JuryEventOut } from "../../api/generated/model";
import { WHOLE_LIST, errorText, useAsyncRows, useInvalidate } from "../../api/useApi";
import { AddDialog } from "../../components/AddDialog";
import { Badge, ErrorMessage } from "../../components/Blocks";
import { ConfirmButton } from "../../components/ConfirmButton";
import { DataTable } from "../../components/DataTable";
import { Field, Message, Section } from "../../components/Form";
import { Select } from "../../components/Select";
import { INPUT_CLASS } from "../../lib/admin";
import { eventDates } from "../../lib/format";
import { useListParams } from "../../lib/listParams";
import { TABLE_FEATURES } from "../../lib/table";
import { JURY_TONE } from "../../lib/jury";

/** The filter choices of an event's column (Story JU-3): a state, or `!` and a state. */
const EVENT_FILTERS = ["approved", "!approved", "available", "invited", "declined", "asked", "!asked"] as const;

/** The URL key of one event column's filter — `at_<id>`, combined into the list's one
 *  `event=<id>:<state>,…` parameter for the request. */
const atKey = (eventId: number) => `at_${eventId}`;

const column = createColumnHelper<typeof TABLE_FEATURES, JudgeOut>();

/** Stories JU-1, JU-3, JU-5: the league office's *Jury* — the pool of judges as the
 *  site's one table, each event picked a column of its own with the judge's state there
 *  and a filter in its header; judges ticked are asked for the events picked or written
 *  to, and a judge is approved for an event, or taken off, in its cell. */
export function JuryOffice() {
  const { t } = useTranslation("space");
  const list = useListParams();
  const invalidate = useInvalidate();
  const refresh = () => invalidate("/api/jury");

  const open = useAsyncRows(useListJuryEvents({ limit: WHOLE_LIST }));
  const picked = list
    .filter("events")
    .split(",")
    .filter(Boolean)
    .map(Number);
  const pickedEvents = picked
    .map((id) => open.data?.find((e) => e.id === id))
    .filter((e): e is JuryEventOut => e !== undefined);
  const eventFilter = picked
    .filter((id) => list.filter(atKey(id)))
    .map((id) => `${id}:${list.filter(atKey(id))}`)
    .join(",");

  const pool = useListJudges(
    {
      ...list.request,
      q: list.q || undefined,
      sort: list.sort ?? undefined,
      licence: (list.filter("licence") as JudgeLicence) || undefined,
      events: picked.join(",") || undefined,
      event: eventFilter || undefined,
    },
    { query: { placeholderData: keepPreviousData } },
  );

  const [ticked, setTicked] = useState<Set<number>>(new Set());
  const tick = (id: number) =>
    setTicked((now) => {
      const next = new Set(now);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  const approve = useApproveJudge({ mutation: { onSuccess: refresh } });
  const takeOff = useTakeJudgeOff({ mutation: { onSuccess: refresh } });
  const remove = useRemoveJudge({ mutation: { onSuccess: refresh } });
  const busy = approve.isPending || takeOff.isPending || remove.isPending;
  const failed = approve.error ?? takeOff.error ?? remove.error;

  const setPicked = (ids: number[], dropped?: number) => {
    if (dropped !== undefined) list.setFilter(atKey(dropped), "");
    list.setFilter("events", ids.join(","));
  };

  const rows = pool.data?.items ?? [];
  const columns = useMemo(
    () =>
      column.columns([
        column.display({
          id: "tick",
          header: () => (
            <input
              type="checkbox"
              aria-label={t("jury.tickAll")}
              checked={rows.length > 0 && rows.every((r) => ticked.has(r.user_id))}
              onChange={(e) => setTicked(e.target.checked ? new Set(rows.map((r) => r.user_id)) : new Set())}
              data-testid="office-jury-tick-all"
            />
          ),
          cell: ({ row }) => (
            <input
              type="checkbox"
              aria-label={row.original.name}
              checked={ticked.has(row.original.user_id)}
              onChange={() => tick(row.original.user_id)}
              data-testid={`office-jury-tick-${row.original.user_id}`}
            />
          ),
        }),
        column.accessor("name", {
          id: "display_name",
          header: t("jury.name"),
          enableSorting: true,
          cell: ({ row }) => (
            <span>
              <span className="font-medium">{row.original.name}</span>
              <span className="block text-xs text-muted">{row.original.email}</span>
            </span>
          ),
        }),
        column.accessor("licences", {
          header: t("jury.licencesTitle"),
          enableSorting: false,
          meta: {
            filters: [
              {
                param: "licence",
                label: t("jury.licencesTitle"),
                options: Object.values(JudgeLicence).map((l) => ({ value: l, label: t(`jury.licences.${l}`) })),
              },
            ],
          },
          cell: ({ row }) => (
            <span className="flex flex-wrap gap-1">
              {row.original.licences.map((l) => (
                <Badge key={l} tone="neutral">
                  {t(`jury.licences.${l}`)}
                </Badge>
              ))}
            </span>
          ),
        }),
        ...pickedEvents.map((event) =>
          column.display({
            id: `event_${event.id}`,
            header: () => (
              <span className="inline-flex items-center gap-1">
                {event.title}
                <button
                  type="button"
                  className="text-muted hover:text-foreground"
                  aria-label={t("jury.dropEvent", { event: event.title })}
                  onClick={() => setPicked(picked.filter((id) => id !== event.id), event.id)}
                  data-testid={`office-jury-drop-${event.id}`}
                >
                  ×
                </button>
              </span>
            ),
            meta: {
              filters: [
                {
                  param: atKey(event.id),
                  label: event.title,
                  options: EVENT_FILTERS.map((value) => ({ value, label: t(`jury.filters.${value}`) })),
                },
              ],
            },
            cell: ({ row }) => {
              const state = row.original.states[String(event.id)];
              const testId = `office-jury-${event.id}-${row.original.user_id}`;
              const ids = { eventId: event.id, userId: row.original.user_id };
              return (
                <span className="inline-flex flex-wrap items-center gap-1">
                  {state ? (
                    <Badge tone={JURY_TONE[state]} testId={`${testId}-state`}>
                      {t(`jury.states.${state}`)}
                    </Badge>
                  ) : (
                    <span className="text-faint" data-testid={`${testId}-state`}>
                      —
                    </span>
                  )}
                  {state === JuryState.approved ? (
                    <Button size="sm" variant="ghost" isDisabled={busy} onPress={() => takeOff.mutate(ids)} data-testid={`${testId}-off`}>
                      {t("jury.takeOff")}
                    </Button>
                  ) : (
                    <Button size="sm" variant="secondary" isDisabled={busy} onPress={() => approve.mutate(ids)} data-testid={`${testId}-approve`}>
                      {t("jury.approve")}
                    </Button>
                  )}
                </span>
              );
            },
          }),
        ),
        column.display({
          id: "remove",
          header: "",
          cell: ({ row }) => (
            <ConfirmButton
              size="sm"
              label={t("jury.remove")}
              prompt={t("jury.removeConfirm")}
              confirmLabel={t("jury.remove")}
              cancelLabel={t("jury.cancel")}
              busy={busy}
              onConfirm={() => remove.mutate({ userId: row.original.user_id })}
              testId={`office-jury-remove-${row.original.user_id}`}
            />
          ),
        }),
      ]),
    // The event columns and the ticks are part of what is drawn.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [t, pickedEvents.map((e) => e.id).join(","), rows, ticked, busy],
  );

  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-6" data-testid="office-jury">
      <Section
        title={t("jury.poolTitle")}
        testId="office-jury-pool"
        action={
          <AddDialog label={t("jury.addJudge")} title={t("jury.addJudge")} testId="office-jury-add">
            {() => <Candidates onAdded={refresh} />}
          </AddDialog>
        }
      >
        <EventPicker events={open.data ?? []} picked={picked} onPick={(id) => setPicked([...picked, id])} />
        {pool.error && <ErrorMessage text={errorText(pool.error)} testId="office-jury-error" />}
        <DataTable
          columns={columns}
          page={pool.data ?? null}
          params={list}
          testId="office-jury"
          empty={t("jury.poolEmpty")}
          search={t("jury.search")}
          rowTestId={(judge) => judge.user_id}
        />
        {failed && <ErrorMessage text={errorText(failed)} testId="office-jury-action-error" />}
      </Section>
      {ticked.size > 0 && (
        <Ticked
          userIds={[...ticked]}
          events={pickedEvents}
          onDone={() => {
            refresh();
          }}
        />
      )}
    </div>
  );
}

/** The events offered as columns: every one not over, drafts included (JU-3). */
function EventPicker({ events, picked, onPick }: { events: JuryEventOut[]; picked: number[]; onPick: (id: number) => void }) {
  const { t } = useTranslation("space");
  const rest = events.filter((e) => !picked.includes(e.id));
  return (
    <Field label={t("jury.pickEvent")} testId="office-jury-events">
      <Select value="" onChange={(e) => e.target.value && onPick(Number(e.target.value))} testId="office-jury-pick">
        <option value="">{t("jury.pickEventNone")}</option>
        {rest.map((e) => (
          <option key={e.id} value={e.id}>
            {[e.series, e.title, eventDates(e)].filter(Boolean).join(" · ")}
            {e.published ? "" : ` (${t("jury.draft")})`}
          </option>
        ))}
      </Select>
    </Field>
  );
}

/** What is done with the judges ticked: asked for the events picked (one mail each,
 *  naming every event newly asked), or written to. */
function Ticked({ userIds, events, onDone }: { userIds: number[]; events: JuryEventOut[]; onDone: () => void }) {
  const { t } = useTranslation("space");
  const [note, setNote] = useState("");
  const [subject, setSubject] = useState("");
  const [text, setText] = useState("");
  const invite = useInviteJudges({ mutation: { onSuccess: onDone } });
  const message = useMessageJudges({
    mutation: {
      onSuccess: () => {
        setSubject("");
        setText("");
      },
    },
  });
  return (
    <Section title={t("jury.tickedTitle", { count: userIds.length })} testId="office-jury-ticked">
      <Field label={t("jury.note")}>
        <textarea className={INPUT_CLASS} rows={2} value={note} onChange={(e) => setNote(e.target.value)} data-testid="office-jury-note" />
      </Field>
      <div>
        <Button
          size="sm"
          isDisabled={!events.length || invite.isPending}
          onPress={() => invite.mutate({ data: { event_ids: events.map((e) => e.id), user_ids: userIds, note: note || null } })}
          data-testid="office-jury-invite"
        >
          {events.length ? t("jury.invite", { count: events.length }) : t("jury.inviteNoEvent")}
        </Button>
      </div>
      <Message
        success={invite.data ? t("jury.invited", { ...invite.data }) : null}
        error={invite.error ? errorText(invite.error) : null}
        testId="office-jury-invite"
      />
      <Field label={t("jury.subject")}>
        <input className={INPUT_CLASS} value={subject} onChange={(e) => setSubject(e.target.value)} data-testid="office-jury-subject" />
      </Field>
      <Field label={t("jury.text")}>
        <textarea className={INPUT_CLASS} rows={4} value={text} onChange={(e) => setText(e.target.value)} data-testid="office-jury-text" />
      </Field>
      <div>
        <Button
          size="sm"
          variant="secondary"
          isDisabled={!subject.trim() || !text.trim() || message.isPending}
          onPress={() => message.mutate({ data: { user_ids: userIds, subject, text } })}
          data-testid="office-jury-message"
        >
          {t("jury.send")}
        </Button>
      </div>
      <Message
        success={message.data ? t("jury.sent", { ...message.data }) : null}
        error={message.error ? errorText(message.error) : null}
        testId="office-jury-message"
      />
    </Section>
  );
}

/** Finding an account to put in the pool (JU-1) — searched on the server. */
function Candidates({ onAdded }: { onAdded: () => void }) {
  const { t } = useTranslation("space");
  const invalidate = useInvalidate();
  const [q, setQ] = useState("");
  const found = useListJuryCandidates({ q: q || undefined, limit: 8 }, { query: { enabled: q.length >= 2 } });
  const add = useAddJudge({
    mutation: {
      onSuccess: () => {
        onAdded();
        invalidate("/api/jury/candidates");
      },
    },
  });
  return (
    <div className="flex flex-col gap-3">
      <Field label={t("jury.candidateSearch")}>
        <input className={INPUT_CLASS} value={q} onChange={(e) => setQ(e.target.value)} data-testid="office-jury-candidate-search" />
      </Field>
      {q.length >= 2 && (
        <ul className="flex flex-col gap-2 text-sm" data-testid="office-jury-candidates">
          {(found.data?.items ?? []).map((c) => (
            <li key={c.user_id} className="flex flex-wrap items-center gap-3" data-testid={`office-jury-candidate-${c.user_id}`}>
              <span className="min-w-0 flex-1">
                {c.name}
                <span className="block text-xs text-muted">{c.email}</span>
              </span>
              <Button
                size="sm"
                isDisabled={add.isPending}
                onPress={() => add.mutate({ data: { user_id: c.user_id } })}
                data-testid={`office-jury-candidate-add-${c.user_id}`}
              >
                {t("jury.add")}
              </Button>
            </li>
          ))}
          {found.data && !found.data.items.length && <li className="text-muted">{t("jury.noCandidates")}</li>}
        </ul>
      )}
      {add.error && <ErrorMessage text={errorText(add.error)} testId="office-jury-add-error" />}
    </div>
  );
}

