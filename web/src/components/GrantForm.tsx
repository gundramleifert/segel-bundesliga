import { Button } from "@heroui/react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { useGetModel, useWriteTuple } from "../api/generated/sbl";
import type { ObjectType } from "../api/generated/model/objectType";
import type { Relation } from "../api/generated/model/relation";
import { useAsync } from "../api/useApi";
import { INPUT_CLASS, errorText } from "../lib/admin";
import { ErrorMessage } from "./Blocks";

/** Story Z-2: name one person to one relation on `object` — the email of their account and
 *  what they are there. The relations offered are the ones the model defines for the
 *  object's type, read from the server rather than copied here. Lives in an `AddDialog`;
 *  `onDone` closes it and refreshes what shows the tuples. */
export function GrantForm({
  object,
  testId,
  initialRelation,
  onDone,
}: {
  object: string;
  testId: string;
  /** Preselected when the model offers it — a club's *＋ Member* starts at `member`. */
  initialRelation?: Relation;
  onDone: () => void;
}) {
  const { t } = useTranslation("admin");
  const model = useAsync(useGetModel());
  const objectType = object.split(":")[0] as ObjectType;
  const relations: Relation[] = model.data?.types.find((entry) => entry.type === objectType)?.relations ?? [];
  const [email, setEmail] = useState("");
  const [relation, setRelation] = useState<Relation | "">(initialRelation ?? "");
  const chosen = relation && relations.includes(relation) ? relation : relations[0];
  const write = useWriteTuple({ mutation: { onSuccess: onDone } });
  const submit = () => chosen && email && write.mutate({ data: { user: email, relation: chosen, object } });

  return (
    <form
      className="flex flex-col gap-3"
      data-testid={`${testId}-form`}
      onSubmit={(e) => {
        e.preventDefault();
        submit();
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
              type="radio"
              name={`${testId}-relation`}
              value={r}
              checked={chosen === r}
              onChange={() => setRelation(r)}
              data-testid={`${testId}-relation-${r}`}
            />
            {t(`accounts.relationLabels.${r}`, { defaultValue: r })}
          </label>
        ))}
      </fieldset>
      {write.error && <ErrorMessage text={errorText(write.error)} testId={`${testId}-add-error`} />}
      <div className="flex justify-end">
        <Button type="submit" size="sm" isDisabled={!email || !chosen || write.isPending} data-testid={`${testId}-add`}>
          {t("access.addButton")}
        </Button>
      </div>
    </form>
  );
}
