import { Button } from "@heroui/react";
import { useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Link, Navigate } from "react-router-dom";

import type { MyContext, MySpace } from "../../api/types";
import { Async } from "../../components/Async";
import { Empty, Loading, PageHeader } from "../../components/Blocks";
import { CardGrid, Stack } from "../../components/Layouts";
import { LinkCard } from "../../components/LinkCard";
import { eventDates } from "../../lib/format";
import { NeedsLine, RelationChips } from "./Chips";
import { contextPath, isPast, useMySpace } from "./shared";

/** Story Z-8: my space — everything I am part of, one card each.
 *
 * Grouped *Me · Clubs · Series · Events*, events split into what is coming and what is
 * over, the past folded behind its count: it only grows, and the page is about what to do
 * next. Each card names what I am there and what needs me there; tapping it opens my page
 * for it (Story S-7). The groups are the same whatever my roles — a treasurer, a helper
 * and a sailor read one page, which is the point: the separate screens each knew one role.
 */
export function MySpaceOverview() {
  const { t } = useTranslation("space");
  const { account, accountLoading, space } = useMySpace();

  if (accountLoading) return <Loading testId="me-loading" />;
  if (!account) return <Navigate to="/account" replace />;

  return (
    <Stack gap={6} testId="me-overview">
      <PageHeader title={t("title")} />
      <Async state={space} testId="me">
        {(data) => <Groups data={data} />}
      </Async>
    </Stack>
  );
}

function Groups({ data }: { data: MySpace }) {
  const { t } = useTranslation("space");
  const of = (kind: MyContext["kind"]) => data.contexts.filter((c) => c.kind === kind);
  const events = of("event");
  const past = events.filter((c) => isPast(c)).reverse();
  const upcoming = events.filter((c) => !isPast(c));
  // Folded only when there is something else to look at: past events alone, folded,
  // would leave a page that looks empty to someone whose season is over.
  const [showPast, setShowPast] = useState(past.length === data.contexts.length);

  return (
    <Stack gap={8}>
      <Group title={t("overview.me")} testId="me-group-me">
        <li>
          <LinkCard
            to="/me/profile"
            testId="me-card-me"
            title={data.me.name}
            description={t("overview.meDescription")}
          >
            <NeedsLine needs={data.me.needs} testId="me-needs-me" />
          </LinkCard>
        </li>
      </Group>

      {!data.contexts.length && (
        // Not an empty box: someone part of nothing needs to know where joining starts
        // (Story V-7), and this is where they look.
        <Empty testId="me-empty">
          {t("overview.none")}{" "}
          <Link to="/clubs" className="underline underline-offset-2">
            {t("overview.noneLink")}
          </Link>
        </Empty>
      )}

      <ContextGroup title={t("overview.clubs")} testId="me-group-clubs" contexts={of("club")} />
      <ContextGroup title={t("overview.series")} testId="me-group-series" contexts={of("series")} />
      <ContextGroup title={t("overview.upcoming")} testId="me-group-upcoming" contexts={upcoming} />

      {past.length > 0 && (
        <section className="flex flex-col gap-3" data-testid="me-group-past">
          <div>
            <Button size="sm" variant="ghost" onPress={() => setShowPast(!showPast)} data-testid="me-past-toggle">
              {showPast ? t("overview.pastHide") : t("overview.pastShow", { count: past.length })}
            </Button>
          </div>
          {showPast && (
            <CardGrid columns={3} testId="me-past-list">
              {past.map((context) => (
                <ContextCard key={`${context.kind}-${context.id}`} context={context} />
              ))}
            </CardGrid>
          )}
        </section>
      )}
    </Stack>
  );
}

function Group({ title, testId, children }: { title: string; testId: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-3" data-testid={testId}>
      <h2 className="text-lg font-semibold">{title}</h2>
      <CardGrid columns={3}>{children}</CardGrid>
    </section>
  );
}

/** A group with nothing in it is left out — "no series" helps nobody. */
function ContextGroup({ title, testId, contexts }: { title: string; testId: string; contexts: MyContext[] }) {
  if (!contexts.length) return null;
  return (
    <Group title={title} testId={testId}>
      {contexts.map((context) => (
        <ContextCard key={`${context.kind}-${context.id}`} context={context} />
      ))}
    </Group>
  );
}

function ContextCard({ context }: { context: MyContext }) {
  const id = `me-card-${context.kind}-${context.id}`;
  const dated = context.kind === "event" || context.starts_on;
  return (
    <li>
      <LinkCard to={contextPath(context)} testId={id} title={context.name} description={dated ? eventDates(context) : undefined}>
        <div className="flex flex-col gap-2">
          <RelationChips relations={context.relations} testId={`${id}-relations`} />
          <NeedsLine needs={context.needs} testId={`${id}-needs`} />
        </div>
      </LinkCard>
    </li>
  );
}
