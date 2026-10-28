import { Button } from "@heroui/react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import {
  getListEventAnnouncementsQueryKey,
  useListEventAnnouncements,
  useListEventDocuments,
  usePublishAnnouncement,
  useRetractAnnouncement,
} from "../../../api/generated/sbl";
import {
  AnnouncementIssuer,
  type Announcement,
  type EventDocument,
  type EventSummary,
} from "../../../api/types";
import { errorText, useAsync, useEventAccess, useInvalidate } from "../../../api/useApi";
import { Async } from "../../../components/Async";
import { ConfirmButton } from "../../../components/ConfirmButton";
import { Field, Message } from "../../../components/Form";
import { Select } from "../../../components/Select";
import { Card, Columns, tone } from "../../../components/site/Cards";
import { Block, Expand } from "../../../components/site/Frame";
import { INPUT_CLASS } from "../../../lib/admin";
import { noticeTime } from "../../../lib/format";

/** An event's notice board (Story VA-11): what its race committee, jury and organizer
 *  announced, newest first, and its documents. Those who may speak for the event publish
 *  here too — the form appears for whoever the access answer names an issuer for. The
 *  page's live stream refetches the list when a notice goes up or comes down. */
export function NoticeBoard({ event }: { event: Pick<EventSummary, "id"> }) {
  const { t } = useTranslation("site");
  const access = useEventAccess(event.id);
  const announceAs = access.announce_as ?? [];
  const announcements = useAsync(useListEventAnnouncements(event.id));
  const documents = useAsync(useListEventDocuments(event.id));
  return (
    <Columns split="twoToOne">
      <Block title={t("noticeBoard.announcements")} testId="site-act-announcements">
        {announceAs.length > 0 && <PublishForm eventId={event.id} issuers={announceAs} />}
        <Async state={announcements} testId="site-act-notices" empty={t("noticeBoard.noAnnouncements")}>
          {(list) => (
            <Card className="px-4">
              {list.map((a, i) => (
                <Notice key={a.id} announcement={a} open={i === 0} mayRetract={announceAs.includes(a.issuer)} />
              ))}
            </Card>
          )}
        </Async>
      </Block>
      <Block title={t("noticeBoard.documents")} testId="site-act-documents">
        <Async state={documents} testId="site-act-document-list" empty={t("noticeBoard.noDocuments")}>
          {(docs) => (
            <Card className="p-4">
              <Documents docs={docs} />
            </Card>
          )}
        </Async>
      </Block>
    </Columns>
  );
}

/** The newest announcement, on the live view (Story VA-11) — "AP ashore" is the first
 *  thing a spectator watching an empty course wants to know. Nothing while none exists. */
export function LatestNotice({ eventId }: { eventId: number }) {
  const latest = useListEventAnnouncements(eventId).data?.[0];
  if (!latest) return null;
  return (
    <div className="mb-3 rounded-lg border border-separator p-3 text-sm" data-testid="live-latest-notice">
      <NoticeHeader announcement={latest} />
      {latest.body && <p className="mt-1 whitespace-pre-line text-muted">{latest.body}</p>}
    </div>
  );
}

const ISSUER_TONE: Record<AnnouncementIssuer, string> = {
  [AnnouncementIssuer.jury]: "bg-warning-soft text-warning-soft-foreground",
  [AnnouncementIssuer.organizer]: "bg-surface-tertiary text-muted",
  [AnnouncementIssuer.race_committee]: "bg-accent-soft text-link",
};

/** "No. 3 · Race committee · Malte Rackow · Sat 10:15" and the title — a notice is named
 *  by its number and signed by whoever put it up, on the board and on the live view. */
function NoticeHeader({ announcement: a }: { announcement: Announcement }) {
  const { t } = useTranslation("site");
  return (
    <span className="flex flex-col gap-1">
      <span className={`flex flex-wrap items-baseline gap-x-2 text-sm ${tone.faint}`}>
        <span className={`font-semibold ${tone.text}`} data-testid={`notice-number-${a.id}`}>
          {t("noticeBoard.number", { number: a.number })}
        </span>
        <span className={`rounded-full px-2 text-xs font-semibold ${ISSUER_TONE[a.issuer]}`}>
          {t(`noticeBoard.from.${a.issuer}`)}
        </span>
        {a.author && <span data-testid={`notice-author-${a.id}`}>{a.author}</span>}
        <span>{noticeTime(a.created_at)}</span>
      </span>
      <span className="font-medium">{a.title}</span>
    </span>
  );
}

function Notice({ announcement: a, open, mayRetract }: { announcement: Announcement; open: boolean; mayRetract: boolean }) {
  const { t } = useTranslation("site");
  const invalidate = useInvalidate();
  const retract = useRetractAnnouncement({
    mutation: { onSuccess: () => invalidate(getListEventAnnouncementsQueryKey(a.event_id)) },
  });
  return (
    <Expand
      open={open}
      testId={`site-act-notice-${a.id}`}
      summary={<NoticeHeader announcement={a} />}
    >
      {a.body && <p className="whitespace-pre-line">{a.body}</p>}
      {mayRetract && (
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <ConfirmButton
            size="sm"
            label={t("noticeBoard.publish.retract")}
            prompt={t("noticeBoard.publish.retractPrompt")}
            confirmLabel={t("noticeBoard.publish.retractConfirm")}
            cancelLabel={t("noticeBoard.publish.cancel")}
            busy={retract.isPending}
            onConfirm={() => retract.mutate({ eventId: a.event_id, announcementId: a.id })}
            testId={`site-act-notice-retract-${a.id}`}
          />
          {retract.error && <span className="text-sm text-danger">{errorText(retract.error)}</span>}
        </div>
      )}
    </Expand>
  );
}

function PublishForm({ eventId, issuers }: { eventId: number; issuers: AnnouncementIssuer[] }) {
  const { t } = useTranslation("site");
  const invalidate = useInvalidate();
  const [issuer, setIssuer] = useState<AnnouncementIssuer>(issuers[0]);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const publish = usePublishAnnouncement({
    mutation: {
      onSuccess: () => {
        setTitle("");
        setBody("");
        invalidate(getListEventAnnouncementsQueryKey(eventId));
      },
    },
  });
  // The access answer may change under the form (a tuple removed); keep the choice valid.
  const chosen = issuers.includes(issuer) ? issuer : issuers[0];
  return (
    <Card className="mb-4 p-4">
      <form
        data-testid="site-act-publish"
        className="grid grid-cols-[minmax(0,1fr)] gap-3"
        onSubmit={(e) => {
          e.preventDefault();
          publish.mutate({ eventId, data: { issuer: chosen, title: title.trim(), body: body.trim() } });
        }}
      >
        <p className={`font-semibold ${tone.text}`}>{t("noticeBoard.publish.title")}</p>
        {issuers.length > 1 && (
          <Field label={t("noticeBoard.publish.issuer")} testId="site-act-publish-issuer-field">
            <Select
              value={chosen}
              testId="site-act-publish-issuer"
              onChange={(e) => setIssuer(e.target.value as AnnouncementIssuer)}
            >
              {issuers.map((i) => (
                <option key={i} value={i}>
                  {t(`noticeBoard.from.${i}`)}
                </option>
              ))}
            </Select>
          </Field>
        )}
        <Field label={t("noticeBoard.publish.heading")} testId="site-act-publish-title-field">
          <input
            type="text"
            required
            maxLength={200}
            className={INPUT_CLASS}
            placeholder={t("noticeBoard.publish.headingPlaceholder")}
            data-testid="site-act-publish-title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
        </Field>
        <Field label={t("noticeBoard.publish.body")} testId="site-act-publish-body-field">
          <textarea
            rows={3}
            maxLength={4000}
            className={INPUT_CLASS}
            data-testid="site-act-publish-body"
            value={body}
            onChange={(e) => setBody(e.target.value)}
          />
        </Field>
        <div>
          <Button
            type="submit"
            isDisabled={!title.trim() || publish.isPending}
            data-testid="site-act-publish-submit"
          >
            {t("noticeBoard.publish.submit")}
          </Button>
        </div>
        <Message
          success={publish.isSuccess ? t("noticeBoard.publish.done") : null}
          error={publish.error ? errorText(publish.error) : null}
          testId="site-act-publish-message"
        />
      </form>
    </Card>
  );
}

/** Links to where each document was published (Story A-14) — the file stays there. An
 *  act's notice board and the season's (`/:league/notice-board`) list them alike. */
export function Documents({ docs, testId = "site-act-document" }: { docs: EventDocument[]; testId?: string }) {
  return (
    <ul className="space-y-1.5">
      {docs.map((doc) => (
        <li key={doc.id} className="flex items-center gap-3" data-testid={`${testId}-${doc.id}`}>
          <span className="grid size-8 shrink-0 place-items-center rounded-md bg-default text-[10px] font-bold uppercase text-muted">
            {doc.extension ?? "—"}
          </span>
          <a href={doc.url} target="_blank" rel="noopener noreferrer" className={`flex-1 ${tone.link}`}>
            {doc.title}
          </a>
        </li>
      ))}
    </ul>
  );
}
