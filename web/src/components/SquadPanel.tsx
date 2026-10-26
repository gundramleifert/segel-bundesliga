import { Button } from "@heroui/react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import {
  getGetSquadQueryKey,
  getListPeopleQueryKey,
  useCreatePerson,
  useGetSquad,
  useListPeople,
  useSetSquad,
} from "../api/generated/sbl";
import { CrewRole, Role, type PersonAdmin, type PersonRegistration } from "../api/types";
import { useAccount, useAsync, useAsyncRows, useInvalidate } from "../api/useApi";
import { ErrorMessage, Loading, Empty } from "./Blocks";
import { Field, Message } from "./Form";
import { TransferList } from "./TransferList";
import { roleText } from "../lib/format";
import { INPUT_CLASS, errorText } from "../lib/admin";
import { useRosterDraft } from "../lib/useRosterDraft";
import { RoleSelect } from "./RoleSelect";

/** Registering who may sail for one team — Story V-1.
 *
 * The same movement as entering clubs into an event and naming a matchday's crew:
 * sailors on the **left**, found by name (the search goes to the server — the register
 * has hundreds of people), the **squad on the right**, a click moves a person across, the
 * role sits beside each name, and **Save** writes the whole list. A person already
 * registered for another club *in this series* is shown on the left with that reason and
 * cannot be moved (the endpoint refuses it anyway); every row says where the person
 * already sails, because eighteen people in this data share a surname.
 *
 * Used from two places on purpose: the admin screen, which reaches a team by picking a
 * series and then a club, and `/club`, where a team manager reaches their own team
 * directly (Story V-12). Two copies would drift, and the rules displayed here — the ten,
 * the single helm, which refusal means what — are the ones that took longest to get right.
 *
 * A club takes only **its own people** (Story V-4): someone who sails for another club is
 * shown greyed, with where they sail — only the league office adds them here. Who
 * is not in the register yet is created right here, for this club, and lands in the draft.
 *
 * `readOnly` is what a club's member without organizer rights sees: the squad, and no
 * panes. Absent rather than disabled — a disabled button is a promise the server will
 * not keep.
 */
/** One helm is the usual shape — guidance the screen shows, never a rule (Story V-1). The
 *  squad's *size* comes with the squad (`squad_min`, `squad_max`, set per series or per
 *  stand-alone event): the maximum is enforced on save and the left pane offers nobody
 *  once it is reached; the minimum is said in amber and saves anyway, because a squad is
 *  built up over weeks. */
const USUAL_HELM_COUNT = 1;

type Person = {
  id: number;
  first_name: string;
  last_name: string;
  registrations?: PersonRegistration[] | null;
  club_ids?: number[];
};

export function SquadPanel({
  teamId,
  title,
  readOnly = false,
}: {
  teamId: number;
  /** Names what this squad belongs to — a club on the admin screen, a series on `/club`. */
  title: string;
  readOnly?: boolean;
}) {
  const { t } = useTranslation("admin");
  const squad = useAsync(useGetSquad(teamId));
  const invalidate = useInvalidate();
  const [search, setSearch] = useState("");
  // A page of matches is what a search wants; the left pane shows them as they come.
  const results = useAsyncRows(
    useListPeople({ q: search.trim() || undefined }, { query: { enabled: !readOnly } }),
  );

  const { hasRole } = useAccount();
  const [creating, setCreating] = useState(false);
  // People created here: the search may not match them, the squad needs their names.
  const [created, setCreated] = useState<Person[]>([]);
  const createPerson = useCreatePerson({
    mutation: { onSuccess: () => invalidate(getListPeopleQueryKey()) },
  });

  const setSquad = useSetSquad({
    mutation: {
      // The squad shows up on every club page and on each member's sailor page, so both
      // are stale the moment it changes — hence the path prefixes rather than one key.
      onSuccess: () => invalidate(getGetSquadQueryKey(teamId), "/api/clubs", "/api/sailors", "/api/me/contexts"),
    },
  });

  // The draft: the right pane until Save. Back to the saved squad whenever that changes.
  const saved = squad.data?.members ?? null;
  const roster = useRosterDraft(saved);
  const { draft, dirty, roleOf } = roster;

  if (squad.loading || (draft === null && !squad.error)) {
    return <Loading text={t("squad.loadingText")} testId="admin-squad-members-loading" />;
  }
  if (squad.error) {
    return <ErrorMessage text={squad.error} testId="admin-squad-members-error" />;
  }
  if (!squad.data || !saved || draft === null) return null;

  const seriesId = squad.data.series_id;
  const people = new Map<number, Person>();
  for (const m of saved) people.set(m.id, m);
  for (const p of results.data ?? []) people.set(p.id, p);
  for (const p of created) people.set(p.id, p);

  const inDraft = new Set(draft.map((d) => d.person_id));
  const selected = roster
    .ordered()
    .map((d) => people.get(d.person_id))
    .filter((p): p is Person => Boolean(p));
  const available = (results.data ?? []).filter((p) => !inDraft.has(p.id));
  const helmCount = draft.filter((d) => d.role === CrewRole.helm).length;
  const { squad_min: squadMin, squad_max: squadMax } = squad.data;
  const full = draft.length >= squadMax;
  const clubId = squad.data.club_id;
  /** Sails for a club, and not this one — the league office alone takes them anyway. */
  const otherClubs = (person: Person) =>
    !hasRole(Role.admin) && Boolean(person.club_ids?.length) && !person.club_ids?.includes(clubId);

  /** Where this person already sails, and whether that rules them out here.
   *
   *  A person is legitimately registered in several clubs — one row per series
   *  registration — and only twice *within one series* is forbidden. The endpoint still
   *  refuses it; this is a courtesy, not the enforcement. */
  const clash = (person: PersonAdmin | Person): PersonRegistration | undefined =>
    seriesId == null ? undefined : person.registrations?.find((r) => r.series.id === seriesId);
  const sailsFor = (person: Person) =>
    person.registrations?.length
      ? person.registrations
          .map((r) => `${r.club.short_name || r.club.name} · ${r.series.name}`)
          .join(" — ")
      : t("squad.noRegistrations");

  /** Writes the whole squad. The endpoint takes the complete list, never a delta. */
  const save = () => setSquad.mutate({ teamId, data: { members: draft } });

  return (
    <div
      data-testid="admin-squad-management"
      className="grid grid-cols-[minmax(0,1fr)] gap-4 rounded-lg border border-separator bg-surface-secondary p-4"
    >
      <div>
        <h3 className="font-medium">
          {t("squad.headerText", { clubName: title, count: draft.length })}
        </h3>
        {/* Guidance, not validation — and said out loud, so that being at nine does not
            look like an oversight and being at eleven does not look like a bug. */}
        <p data-testid="admin-squad-size-hint" className="text-sm text-muted">
          {t("squad.sizeHint", { count: draft.length, min: squadMin, max: squadMax })}
          {draft.length < squadMin && (
            <>
              {" · "}
              <span data-testid="admin-squad-min-hint" className="text-warning-soft-foreground">
                {t("squad.belowMinHint", { min: squadMin })}
              </span>
            </>
          )}
          {full && (
            <>
              {" · "}
              <span data-testid="admin-squad-max-hint">{t("squad.atMaxHint", { max: squadMax })}</span>
            </>
          )}
          {helmCount !== USUAL_HELM_COUNT && (
            <>
              {" · "}
              <span data-testid="admin-squad-helm-hint" className="text-warning-soft-foreground">
                {helmCount === 0 ? t("squad.noHelmHint") : t("squad.manyHelmsHint", { count: helmCount })}
              </span>
            </>
          )}
        </p>
      </div>

      {readOnly ? (
        selected.length ? (
          <ul data-testid="admin-squad-members-list" className="divide-y divide-separator text-sm">
            {selected.map((member) => (
              <li
                key={member.id}
                data-testid={`admin-squad-member-row-${member.id}`}
                className="flex items-center gap-3 py-1.5"
              >
                <span className="min-w-0 flex-1 truncate">
                  {member.first_name} {member.last_name}
                </span>
                <span data-testid={`admin-squad-member-role-${member.id}`} className="text-xs text-muted">
                  {roleText(roleOf(member.id))}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <Empty testId="admin-squad-members-empty">{t("squad.teamEmptyText")}</Empty>
        )
      ) : (
        <>
          <TransferList
            testId="admin-squad-panes"
            available={available}
            selected={selected}
            label={(p) => `${p.first_name} ${p.last_name}`}
            detail={sailsFor}
            disabledReason={(p) => {
              const taken = clash(p);
              if (taken) return t("squad.alreadyInSeries", { club: taken.club.name });
              if (otherClubs(p)) return t("squad.otherClub");
              return full ? t("squad.fullReason", { max: squadMax }) : null;
            }}
            filterValue={search}
            onFilterChange={setSearch}
            filterPlaceholder={t("squad.addPlaceholder")}
            availableLoading={results.loading}
            onSelect={(p) => roster.add(p.id, "crew")}
            onDeselect={(p) => roster.remove(p.id)}
            selectedExtra={(p) => (
              <RoleSelect
                value={roleOf(p.id)}
                onChange={(role) => roster.setRole(p.id, role)}
                label={t("squad.addRoleLabel")}
                testId={`admin-squad-role-${p.id}`}
              />
            )}
          />
          {creating ? (
            <NewPerson
              pending={createPerson.isPending}
              error={createPerson.isError ? errorText(createPerson.error) : null}
              onCancel={() => {
                setCreating(false);
                createPerson.reset();
              }}
              onCreate={(person) =>
                createPerson.mutate(
                  { data: { ...person, club_id: clubId } },
                  {
                    onSuccess: (sailor) => {
                      setCreated((list) => [...list, sailor]);
                      roster.add(sailor.id, "crew");
                      setCreating(false);
                    },
                  },
                )
              }
            />
          ) : (
            <div>
              <Button
                size="sm"
                variant="ghost"
                isDisabled={full}
                onPress={() => setCreating(true)}
                data-testid="admin-squad-new-person"
              >
                {t("squad.newPerson")}
              </Button>
            </div>
          )}
          <div className="flex flex-wrap items-center gap-3">
            <Button
              size="sm"
              isDisabled={setSquad.isPending || !dirty}
              onPress={save}
              data-testid="admin-squad-save"
            >
              {setSquad.isPending ? t("squad.saving") : t("squad.save")}
            </Button>
            {dirty && (
              <span className="text-xs text-muted" data-testid="admin-squad-unsaved">
                {t("squad.unsaved")}
              </span>
            )}
          </div>
          <Message
            testId="admin-squad-message"
            error={setSquad.isError ? errorText(setSquad.error) : null}
            success={setSquad.isSuccess && !dirty ? t("squad.saved") : null}
          />
        </>
      )}
    </div>
  );
}

/** Someone not in the register yet: name and address, created for the squad's club — and,
 *  from a club's *Sailors* section (Story Z-10), for that club. */
export function NewPerson({
  pending,
  error,
  onCreate,
  onCancel,
  testIdPrefix = "admin-squad-new",
}: {
  pending: boolean;
  error: string | null;
  onCreate: (person: { first_name: string; last_name: string; email: string }) => void;
  onCancel: () => void;
  testIdPrefix?: string;
}) {
  const { t } = useTranslation("admin");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const ready = firstName.trim() && lastName.trim() && email.trim();
  return (
    <form
      data-testid={`${testIdPrefix}-person-form`}
      className="grid grid-cols-[minmax(0,1fr)] gap-3 rounded-lg border border-separator bg-surface p-3 sm:grid-cols-[1fr_1fr_1.4fr] sm:items-end"
      onSubmit={(e) => {
        e.preventDefault();
        onCreate({ first_name: firstName.trim(), last_name: lastName.trim(), email: email.trim() });
      }}
    >
      <Field label={t("sailors.firstNameLabel")}>
        <input
          className={INPUT_CLASS}
          value={firstName}
          onChange={(e) => setFirstName(e.target.value)}
          required
          data-testid={`${testIdPrefix}-first-name`}
        />
      </Field>
      <Field label={t("sailors.lastNameLabel")}>
        <input
          className={INPUT_CLASS}
          value={lastName}
          onChange={(e) => setLastName(e.target.value)}
          required
          data-testid={`${testIdPrefix}-last-name`}
        />
      </Field>
      <Field label={t("sailors.emailLabel")}>
        <input
          className={INPUT_CLASS}
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          placeholder={t("sailors.emailPlaceholder")}
          data-testid={`${testIdPrefix}-email`}
        />
      </Field>
      <div className="flex flex-wrap items-center gap-3 sm:col-span-3">
        <Button type="submit" size="sm" isDisabled={pending || !ready} data-testid={`${testIdPrefix}-create`}>
          {pending ? t("sailors.creatingButton") : t("squad.newPersonCreate")}
        </Button>
        <Button size="sm" variant="ghost" onPress={onCancel} data-testid={`${testIdPrefix}-cancel`}>
          {t("squad.newPersonCancel")}
        </Button>
        {error && <ErrorMessage text={error} testId={`${testIdPrefix}-error`} />}
      </div>
    </form>
  );
}
