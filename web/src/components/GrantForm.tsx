import { Button } from "@heroui/react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { useGetModel, useWriteTuple } from "../api/generated/sbl";
import type { ObjectType } from "../api/generated/model/objectType";
import { Relation } from "../api/types";
import { useAsync } from "../api/useApi";
import { INPUT_CLASS, errorText } from "../lib/admin";
import { ErrorMessage } from "./Blocks";

/** Story Z-2: name one person to one or more relations on `object` — the email of their
 *  account and what they are there (a new member who is also the treasurer: both at once).
 *  The relations offered are the ones the model lets a tuple name on the object's type,
 *  read from the server rather than copied here; a club's *member* is not among them — it
 *  is a membership, not a tuple (#40) — and comes first through `addMember` when given. Each ticked relation is its own tuple, written one
 *  after the other — never a list replacing a person's rows (CLAUDE.md, Permissions). Lives
 *  in an `AddDialog`: `onWritten` refreshes what shows the tuples after each one, `onDone`
 *  closes the dialog once all are written. */
export function GrantForm({
  object,
  testId,
  addMember,
  onWritten,
  onDone,
}: {
  object: string;
  testId: string;
  /** Offers *Member* first, ticked — a club's *＋ Member*: adds the person to the club
   *  before any role is written. */
  addMember?: (email: string) => Promise<unknown>;
  /** After each tuple written — also when a later one is refused and the dialog stays. */
  onWritten: () => void;
  onDone: () => void;
}) {
  const { t } = useTranslation("admin");
  const model = useAsync(useGetModel());
  const objectType = object.split(":")[0] as ObjectType;
  const written: Relation[] = model.data?.types.find((entry) => entry.type === objectType)?.relations ?? [];
  const relations: Relation[] = addMember ? [Relation.member, ...written] : written;
  const [email, setEmail] = useState("");
  const [ticked, setTicked] = useState<Relation[]>(addMember ? [Relation.member] : []);
  const chosen = relations.filter((r) => ticked.includes(r));
  const toggle = (r: Relation) => setTicked((now) => (now.includes(r) ? now.filter((x) => x !== r) : [...now, r]));
  const write = useWriteTuple();
  const [memberError, setMemberError] = useState<unknown>(null);
  const submit = async () => {
    if (!email || !chosen.length) return;
    setMemberError(null);
    // The membership first, then one tuple after the other; a refusal stops there and
    // stays on screen. What was written before it is kept, and the list behind the
    // dialog already shows it.
    for (const relation of chosen) {
      try {
        if (relation === Relation.member && addMember) await addMember(email);
        else await write.mutateAsync({ data: { user: email, relation, object } });
        onWritten();
      } catch (error) {
        if (relation === Relation.member) setMemberError(error);
        return;
      }
    }
    onDone();
  };
  const error = memberError ?? write.error;

  return (
    <form
      className="flex flex-col gap-3"
      data-testid={`${testId}-form`}
      onSubmit={(e) => {
        e.preventDefault();
        void submit();
      }}
    >
      <label className="flex flex-col text-xs text-muted">
        {/* With a membership the address may be the person's own, not only an account's. */}
        {t(addMember ? "access.emailLabelPerson" : "access.emailLabel")}
        <input
          className={INPUT_CLASS}
          type="email"
          autoFocus
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          data-testid={`${testId}-email`}
        />
      </label>
      <fieldset className="flex flex-col gap-1 text-xs text-muted" data-testid={`${testId}-relation`}>
        <legend className="mb-1">{t("access.relationLabel")}</legend>
        {relations.map((r) => (
          <label key={r} className="flex items-center gap-2 text-sm text-foreground">
            <input
              type="checkbox"
              value={r}
              checked={ticked.includes(r)}
              onChange={() => toggle(r)}
              data-testid={`${testId}-relation-${r}`}
            />
            {t(`accounts.relationLabels.${r}`, { defaultValue: r })}
          </label>
        ))}
      </fieldset>
      {error ? <ErrorMessage text={errorText(error)} testId={`${testId}-add-error`} /> : null}
      <div className="flex justify-end">
        <Button type="submit" size="sm" isDisabled={!email || !chosen.length || write.isPending} data-testid={`${testId}-add`}>
          {t("access.addButton")}
        </Button>
      </div>
    </form>
  );
}
