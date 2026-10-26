import { Button } from "@heroui/react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { useLinkGuardian, useListClubGuardians, useUnlinkGuardian } from "../api/generated/sbl";
import { useAsync, useInvalidate } from "../api/useApi";
import { INPUT_CLASS, errorText } from "../lib/admin";
import { Async } from "./Async";
import { Badge, ErrorMessage } from "./Blocks";
import { fullName } from "../lib/format";

/** Story V-13: the club's young sailors and their guardians, for the club's organizer.
 *
 * A guardian is a parent's account linked to a sailor (`user:guardian:sailor`); from then
 * on the parent accepts the child's liability waiver online (Story S-8). Only the club
 * links — never the parent, who could claim any child. The minors come first: theirs is
 * the waiver a guardian signs; an adult's guardian is listed but has nothing to sign.
 */
export function GuardiansPanel({ clubId }: { clubId: number }) {
  const { t } = useTranslation("club");
  const invalidate = useInvalidate();
  const rows = useAsync(useListClubGuardians(clubId));
  const refresh = () => invalidate(`/api/clubs/${clubId}/guardians`);
  const link = useLinkGuardian({ mutation: { onSuccess: refresh } });
  const unlink = useUnlinkGuardian({ mutation: { onSuccess: refresh } });
  const [adding, setAdding] = useState<number | null>(null);
  const [email, setEmail] = useState("");

  return (
    <section data-testid={`my-club-guardians-${clubId}`} className="grid grid-cols-[minmax(0,1fr)] gap-3">
      <div>
        <h3 className="font-medium">{t("guardians.title")}</h3>
        <p className="text-sm text-muted">{t("guardians.hint")}</p>
      </div>
      <Async state={rows} testId="my-club-guardians" empty={t("guardians.empty")}>
        {(data) => (
          <ul className="divide-y divide-separator rounded-lg border border-separator bg-surface">
            {minorsFirst(data).map((row) => (
              <li
                key={row.person.id}
                data-testid={`my-club-guardians-row-${row.person.id}`}
                className="grid grid-cols-[minmax(0,1fr)] gap-2 px-4 py-3"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <span className="min-w-0 flex-1 font-medium">
                    {fullName(row.person)}
                  </span>
                  {row.minor === true && (
                    <Badge tone="warning">{t("guardians.minor")}</Badge>
                  )}
                  <Button
                    size="sm"
                    variant="ghost"
                    onPress={() => {
                      setAdding(adding === row.person.id ? null : row.person.id);
                      setEmail("");
                      link.reset();
                    }}
                    data-testid={`my-club-guardians-add-${row.person.id}`}
                  >
                    {t("guardians.add")}
                  </Button>
                </div>
                {row.guardians.length > 0 && (
                  <ul className="flex flex-wrap gap-2">
                    {row.guardians.map((g) => (
                      <li
                        key={g.id}
                        data-testid={`my-club-guardian-${row.person.id}-${g.id}`}
                        className="flex items-center gap-1 rounded-full bg-surface-tertiary py-0.5 pl-3 pr-1 text-sm"
                      >
                        <span>{g.display_name || g.email}</span>
                        <button
                          type="button"
                          aria-label={t("guardians.remove", { name: g.display_name || g.email })}
                          disabled={unlink.isPending}
                          onClick={() => unlink.mutate({ personId: row.person.id, tupleId: g.id })}
                          className="rounded-full px-1.5 text-muted hover:bg-default-hover hover:text-foreground"
                          data-testid={`my-club-guardian-remove-${row.person.id}-${g.id}`}
                        >
                          ×
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
                {adding === row.person.id && (
                  <form
                    className="flex flex-wrap items-center gap-2"
                    onSubmit={(e) => {
                      e.preventDefault();
                      link.mutate(
                        { personId: row.person.id, data: { email } },
                        { onSuccess: () => setAdding(null) },
                      );
                    }}
                  >
                    <input
                      type="email"
                      required
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder={t("guardians.emailPlaceholder")}
                      aria-label={t("guardians.emailPlaceholder")}
                      className={`${INPUT_CLASS} min-w-0 flex-1`}
                      data-testid={`my-club-guardians-email-${row.person.id}`}
                    />
                    <Button
                      size="sm"
                      type="submit"
                      isDisabled={link.isPending || !email.trim()}
                      data-testid={`my-club-guardians-submit-${row.person.id}`}
                    >
                      {t("guardians.link")}
                    </Button>
                    {link.isError && (
                      <ErrorMessage
                        text={errorText(link.error)}
                        testId={`my-club-guardians-error-${row.person.id}`}
                      />
                    )}
                  </form>
                )}
              </li>
            ))}
          </ul>
        )}
      </Async>
      {unlink.isError && <ErrorMessage text={errorText(unlink.error)} />}
    </section>
  );
}

/** The minors first: theirs is the waiver a guardian signs. */
function minorsFirst<T extends { minor?: boolean | null }>(rows: T[]): T[] {
  return [...rows].sort((a, b) => Number(b.minor === true) - Number(a.minor === true));
}
