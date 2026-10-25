import { Button } from "@heroui/react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import {
  getListSailorsQueryKey,
  useCreateSailor,
  useGetClub,
  useListClubGuardians,
  useUpdateSailor,
} from "../../api/generated/sbl";
import type { SailorGuardiansOut } from "../../api/generated/model/sailorGuardiansOut";
import { useAsync, useInvalidate } from "../../api/useApi";
import { Async } from "../../components/Async";
import { Badge, ErrorMessage } from "../../components/Blocks";
import { CrestEditor } from "../../components/CrestEditor";
import { Message } from "../../components/Form";
import { NewPerson } from "../../components/SquadPanel";
import { INPUT_CLASS, errorText } from "../../lib/admin";

/** Story Z-10: the club's *Sailors* and its *Club page* — two sections that were parts of
 * the Members tab, or of the league office's lists, before #32.
 */

/** The club's sailors (Story V-4): everyone who sails for it (`SailorClub`), and
 * *+ New person*, created for this club — the one way a club's organizer adds someone to
 * the register. A sailor without a date of birth can confirm no waiver (S-3), so the date
 * is set right on the row; that clears the club's `sailor_without_birth_date` to-do.
 *
 * Read from the guardians list (`GET /api/clubs/{id}/guardians`): it is exactly the
 * club's sailors, for exactly the club's organizers — a second endpoint would be a copy.
 */
export function ClubSailors({ clubId }: { clubId: number }) {
  const { t } = useTranslation("space");
  const invalidate = useInvalidate();
  const rows = useAsync(useListClubGuardians(clubId));
  const [creating, setCreating] = useState(false);
  const refresh = () => invalidate(`/api/clubs/${clubId}/guardians`, getListSailorsQueryKey(), "/api/me/contexts");
  const create = useCreateSailor({ mutation: { onSuccess: refresh } });
  const id = `my-club-sailors-${clubId}`;

  return (
    <section data-testid={id} className="grid grid-cols-[minmax(0,1fr)] gap-4">
      <p className="text-sm text-muted">{t("clubSections.sailorsHint")}</p>
      {creating ? (
        <NewPerson
          testIdPrefix="my-club-sailors-new"
          pending={create.isPending}
          error={create.isError ? errorText(create.error) : null}
          onCancel={() => {
            setCreating(false);
            create.reset();
          }}
          onCreate={(person) =>
            create.mutate({ data: { ...person, club_id: clubId } }, { onSuccess: () => setCreating(false) })
          }
        />
      ) : (
        <div>
          <Button
            size="sm"
            variant="outline"
            onPress={() => {
              create.reset();
              setCreating(true);
            }}
            data-testid="my-club-sailors-new-person"
          >
            {t("clubSections.newPerson")}
          </Button>
        </div>
      )}
      <Message
        testId="my-club-sailors-created"
        success={
          create.isSuccess && !creating
            ? t("clubSections.personCreated", { name: `${create.data.first_name} ${create.data.last_name}` })
            : null
        }
      />
      <Async state={rows} testId="my-club-sailors" empty={t("clubSections.noSailors")}>
        {(data) => (
          <ul
            className="divide-y divide-separator rounded-lg border border-separator bg-surface"
            data-testid="my-club-sailors-list"
          >
            {byName(data).map((row) => (
              <SailorRow key={row.sailor.id} row={row} onChanged={refresh} />
            ))}
          </ul>
        )}
      </Async>
    </section>
  );
}

function byName(rows: SailorGuardiansOut[]): SailorGuardiansOut[] {
  return [...rows].sort(
    (a, b) => a.sailor.last_name.localeCompare(b.sailor.last_name) || a.sailor.first_name.localeCompare(b.sailor.first_name),
  );
}

/** One sailor: the name, under 18 or not, and — without a date of birth — the date. */
function SailorRow({ row, onChanged }: { row: SailorGuardiansOut; onChanged: () => void }) {
  const { t } = useTranslation("space");
  const { t: tc } = useTranslation("club");
  const id = row.sailor.id;
  const [birthDate, setBirthDate] = useState("");
  const save = useUpdateSailor({ mutation: { onSuccess: onChanged } });
  // `minor` is null exactly when the date of birth is missing (the endpoint's contract).
  const noBirthDate = row.minor == null;

  return (
    <li data-testid={`my-club-sailor-${id}`} className="grid grid-cols-[minmax(0,1fr)] gap-2 px-4 py-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="min-w-0 flex-1 font-medium">
          {row.sailor.first_name} {row.sailor.last_name}
        </span>
        {row.minor === true && <Badge tone="warning">{tc("guardians.minor")}</Badge>}
        {noBirthDate && (
          <Badge tone="caution" testId={`my-club-sailor-no-birth-date-${id}`}>
            {t("clubSections.noBirthDate")}
          </Badge>
        )}
      </div>
      {noBirthDate && (
        <form
          className="flex flex-wrap items-center gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            save.mutate({ sailorId: id, data: { birth_date: birthDate } });
          }}
        >
          {/* A wrapper sets the width: a class appended to INPUT_CLASS may lose to its own. */}
          <div className="w-44">
            <input
              type="date"
              required
              value={birthDate}
              onChange={(e) => setBirthDate(e.target.value)}
              aria-label={t("clubSections.birthDateLabel")}
              className={INPUT_CLASS}
              data-testid={`my-club-sailor-birth-date-${id}`}
            />
          </div>
          <Button size="sm" type="submit" isDisabled={save.isPending || !birthDate} data-testid={`my-club-sailor-birth-date-save-${id}`}>
            {t("clubSections.saveBirthDate")}
          </Button>
          {save.isError && <ErrorMessage text={errorText(save.error)} testId={`my-club-sailor-birth-date-error-${id}`} />}
        </form>
      )}
    </li>
  );
}

/** The club's own page (Story V-3): its crest, kept by the club's `admin` — and its name,
 * short name, city and website as the public page shows them. Those are the league
 * office's to change (`PATCH /api/admin/clubs/{id}` is the site admin's), so they are
 * shown here, not offered as fields that would answer 403.
 */
export function ClubPageSection({ clubId }: { clubId: number }) {
  const { t } = useTranslation("space");
  const { t: tc } = useTranslation("club");
  const invalidate = useInvalidate();
  const club = useAsync(useGetClub(clubId));

  return (
    <Async state={club} testId="my-club-page">
      {(data) => (
        <div className="grid grid-cols-[minmax(0,1fr)] gap-5" data-testid={`my-club-page-${clubId}`}>
          <section className="flex flex-wrap items-center gap-3" data-testid={`my-club-crest-${clubId}-section`}>
            <CrestEditor
              club={data}
              onChanged={() => invalidate("/api/clubs", "/api/admin/clubs")}
              testIdPrefix="my-club-crest"
            >
              <p className="min-w-0 flex-1 text-sm text-muted">{tc("members.crestHint")}</p>
            </CrestEditor>
          </section>
          <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-1 text-sm" data-testid={`my-club-page-${clubId}-facts`}>
            <dt className="text-muted">{t("clubSections.name")}</dt>
            <dd>{data.name}</dd>
            <dt className="text-muted">{t("clubSections.shortName")}</dt>
            <dd>{data.short_name}</dd>
            {data.city && (
              <>
                <dt className="text-muted">{t("clubSections.city")}</dt>
                <dd>{data.city}</dd>
              </>
            )}
            {data.website && (
              <>
                <dt className="text-muted">{t("clubSections.website")}</dt>
                <dd className="break-all">{data.website}</dd>
              </>
            )}
          </dl>
          <p className="text-sm text-muted">{t("clubSections.factsByOffice")}</p>
        </div>
      )}
    </Async>
  );
}
