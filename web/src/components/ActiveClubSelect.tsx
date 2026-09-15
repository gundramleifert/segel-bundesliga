import { useTranslation } from "react-i18next";

import { useUpdateMe } from "../api/generated/sbl";
import type { MyClub } from "../api/types";
import { useInvalidate } from "../api/useApi";
import { INPUT_CLASS, errorText } from "../lib/admin";
import { Field, Message } from "./Form";

/** Which of my clubs I act for — Story V-12.
 *
 * A person can be a member of several clubs and organize several, and both relationships
 * are per club. Everything that acts "for my club" — the squad screen, the lineup, the
 * account card — has to know which one, so the choice is **remembered on the account**
 * (`PATCH /api/auth/me`, `User.club_id`) rather than living in one page's URL. The same
 * select therefore sits on `/club` and on `/account`; the pages only differ in what they
 * do with the answer. With a single club there is nothing to choose, and the caller shows
 * a sentence instead.
 */
export function ActiveClubSelect({
  entries,
  value,
  onChange,
  testId = "active-club-select",
}: {
  entries: MyClub[];
  value: number;
  /** Called after the choice is saved; the caller updates whatever it shows for the club. */
  onChange?: (clubId: number) => void;
  testId?: string;
}) {
  const { t } = useTranslation("club");
  const invalidate = useInvalidate();
  const save = useUpdateMe({
    // `useAccount` keys the account by token, so the generated key alone would miss it;
    // the path prefix covers both.
    mutation: { onSuccess: () => invalidate("/api/auth/me") },
  });

  const roleOf = (item: MyClub) =>
    item.may_manage ? t("mine.roleOrganizer") : t("mine.roleMember");

  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-1">
      <Field label={t("mine.clubLabel")} hint={t("mine.activeClubHint")}>
        <select
          className={INPUT_CLASS}
          value={value}
          disabled={save.isPending}
          onChange={(e) => {
            const clubId = Number(e.target.value);
            onChange?.(clubId);
            save.mutate({ data: { club_id: clubId } });
          }}
          data-testid={testId}
        >
          {entries.map((item) => (
            <option key={item.club.id} value={item.club.id}>
              {item.club.name} — {roleOf(item)}
            </option>
          ))}
        </select>
      </Field>
      <Message testId={`${testId}-message`} error={save.isError ? errorText(save.error) : null} />
    </div>
  );
}
