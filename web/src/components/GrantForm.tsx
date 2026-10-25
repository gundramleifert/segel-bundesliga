import { Button } from "@heroui/react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { useGetModel, useWriteTuple } from "../api/generated/sbl";
import type { ObjectType } from "../api/generated/model/objectType";
import type { Relation } from "../api/generated/model/relation";
import { useAsync } from "../api/useApi";
import { INPUT_CLASS, errorText } from "../lib/admin";
import { ErrorMessage } from "./Blocks";

/** Story Z-2: name one person to one or more relations on `object` — the email of their
 *  account and what they are there (a new member who is also the treasurer: both at once).
 *  The relations offered are the ones the model defines for the object's type, read from
 *  the server rather than copied here. Each ticked relation is its own tuple, written one
 *  after the other — never a list replacing a person's rows (CLAUDE.md, Permissions). Lives
 *  in an `AddDialog`: `onWritten` refreshes what shows the tuples after each one, `onDone`
 *  closes the dialog once all are written. */
export function GrantForm({
  object,
  testId,
  initialRelation,
  onWritten,
  onDone,
}: {
  object: string;
  testId: string;
  /** Ticked from the start when the model offers it — a club's *＋ Member* starts at `member`. */
  initialRelation?: Relation;
  /** After each tuple written — also when a later one is refused and the dialog stays. */
  onWritten: () => void;
  onDone: () => void;
}) {
  const { t } = useTranslation("admin");
  const model = useAsync(useGetModel());
  const objectType = object.split(":")[0] as ObjectType;
  const relations: Relation[] = model.data?.types.find((entry) => entry.type === objectType)?.relations ?? [];
  const [email, setEmail] = useState("");
  const [ticked, setTicked] = useState<Relation[]>(initialRelation ? [initialRelation] : []);
  const chosen = relations.filter((r) => ticked.includes(r));
  const toggle = (r: Relation) => setTicked((now) => (now.includes(r) ? now.filter((x) => x !== r) : [...now, r]));
  const write = useWriteTuple();
  const submit = async () => {
    if (!email || !chosen.length) return;
    // One tuple after the other; a refusal stops there and stays on screen. What was
    // written before it is kept, and the list behind the dialog already shows it.
    for (const relation of chosen) {
      try {
        await write.mutateAsync({ data: { user: email, relation, object } });
        onWritten();
      } catch {
        return;
      }
    }
    onDone();
  };

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
        {t("access.emailLabel")}
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
      {write.error && <ErrorMessage text={errorText(write.error)} testId={`${testId}-add-error`} />}
      <div className="flex justify-end">
        <Button type="submit" size="sm" isDisabled={!email || !chosen.length || write.isPending} data-testid={`${testId}-add`}>
          {t("access.addButton")}
        </Button>
      </div>
    </form>
  );
}
