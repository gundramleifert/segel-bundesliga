import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import type { MyContext, MySpace } from "../../api/types";
import { Async } from "../../components/Async";
import { Empty, PageHeader } from "../../components/Blocks";
import { Stack } from "../../components/Layouts";
import { eventDates } from "../../lib/format";
import { groupTodos, liveNow, readVisits, refKey, sectionPath, type ContextRef } from "../../lib/workspace";
import { MeFrame } from "./Contexts";
import { TodoList, todoTestId } from "./Todos";
import { useMySpace } from "./shared";

/** Story Z-10 (§4): *Me › Overview*, the landing page after sign-in.
 *
 * In the order decided on 2026-10-25: **Live now** while an event I work on is live —
 * the sections my relations give me there, race control first for the race committee —
 * then **To do**, every to-do of every context grouped by context, most urgent first,
 * each line a link to the section that clears it; then **Last visited**, the last five
 * sections this browser opened. With nothing to do, one line says so and *Last visited*
 * moves up. The contexts themselves are in the switcher, no longer cards here.
 */
export function MySpaceOverview() {
  const { t } = useTranslation("space");
  const { space } = useMySpace();
  return (
    <MeFrame
      active="overview"
      overview={
        <Stack gap={8} testId="me-overview">
          <PageHeader title={t("title")} />
          <Async state={space} testId="me">
            {(data) => <Landing data={data} />}
          </Async>
        </Stack>
      }
    />
  );
}

function Landing({ data }: { data: MySpace }) {
  const { t } = useTranslation("space");
  const live = liveNow(data.contexts, today());
  const groups = groupTodos(data.todos);
  const visits = readVisits();
  const nameOf = (ref: ContextRef) => {
    if (!("id" in ref)) return t(`workspace.kinds.${ref.kind}`);
    const c = data.contexts.find((x) => x.kind === ref.kind && x.id === ref.id);
    return c?.short_name || c?.name || t(`workspace.kinds.${ref.kind}`);
  };

  return (
    <>
      {live.length > 0 && (
        <section className="flex flex-col gap-3" data-testid="me-live">
          <h2 className="text-lg font-semibold">{t("workspace.liveNow")}</h2>
          <ul className="flex flex-col gap-3">
            {live.map((block) => (
              <LiveBlock key={block.context.id} context={block.context} sections={block.sections} publicLive={block.publicLive} />
            ))}
          </ul>
        </section>
      )}

      <section className="flex flex-col gap-3" data-testid="me-todo">
        <h2 className="text-lg font-semibold">{t("workspace.toDo")}</h2>
        {groups.length ? (
          <ul className="flex flex-col gap-4">
            {groups.map((group) => (
              <li key={refKey(group.ref)} className="flex flex-col gap-1.5">
                <Link to={sectionPath(group.ref)} className="w-fit font-medium hover:underline" data-testid={todoTestId("me-todo-context", group.ref)}>
                  {nameOf(group.ref)}
                </Link>
                <TodoList context={group.ref} needs={group.todos} testId={todoTestId("me-todo", group.ref)} />
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted" data-testid="me-todo-nothing">
            {t("workspace.nothingWaits")}
          </p>
        )}
      </section>

      {visits.length > 0 && (
        <section className="flex flex-col gap-3" data-testid="me-visited">
          <h2 className="text-lg font-semibold">{t("workspace.lastVisited")}</h2>
          <ul className="flex flex-col gap-1.5">
            {visits.map((v) => (
              <li key={`${refKey(v.ref)}/${v.section}`} className="text-sm">
                <Link
                  to={sectionPath(v.ref, v.section)}
                  className="hover:underline"
                  data-testid={`me-visited-${refKey(v.ref).replace(":", "-")}-${v.section}`}
                >
                  {v.name} <span className="text-faint">›</span> {v.label}
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      {!data.contexts.length && !groups.length && (
        // Someone part of nothing needs to know where joining starts (Story V-7).
        <Empty testId="me-empty">
          {t("overview.none")}{" "}
          <Link to="/clubs" className="underline underline-offset-2">
            {t("overview.noneLink")}
          </Link>
        </Empty>
      )}
    </>
  );
}

/** One live event: its name and dates, and a button per section the day needs. */
function LiveBlock({ context, sections, publicLive }: { context: MyContext; sections: string[]; publicLive: boolean }) {
  const { t } = useTranslation("space");
  const ref = { kind: "event" as const, id: context.id };
  const testId = `me-live-event-${context.id}`;
  const link = "rounded-lg bg-surface px-3 py-2 text-sm font-medium text-foreground ring-1 ring-border hover:bg-surface-tertiary";
  return (
    <li className="flex flex-col gap-2 rounded-xl bg-accent-soft p-4" data-testid={testId}>
      <div className="flex flex-wrap items-baseline gap-x-3">
        <Link to={sectionPath(ref)} className="font-semibold text-accent-soft-foreground hover:underline">
          {context.name}
        </Link>
        <span className="text-sm text-muted">{eventDates(context)}</span>
      </div>
      <div className="flex flex-wrap gap-2">
        {sections.map((s) => (
          <Link
            key={s}
            // Race control is a full-screen tool of its own (§7), reached from here directly.
            to={s === "race-control" ? `/events/${context.id}/race-control` : sectionPath(ref, s)}
            className={link}
            data-testid={`${testId}-${s}`}
          >
            {t(`workspace.live.${s}`)}
          </Link>
        ))}
        {publicLive && (
          <Link to={`/events/${context.id}/live`} className={link} data-testid={`${testId}-public-live`}>
            {t("workspace.live.publicLive")}
          </Link>
        )}
      </div>
    </li>
  );
}

function today(): string {
  const now = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}
