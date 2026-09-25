import { Button } from "@heroui/react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import {
  getReadTuplesQueryKey,
  useDeleteTuple,
  useGetModel,
  useReadTuples,
  useWriteTuple,
} from "../api/generated/sbl";
import type { Relation } from "../api/generated/model/relation";
import type { ObjectType } from "../api/generated/model/objectType";
import { useAsync, useInvalidate } from "../api/useApi";
import { INPUT_CLASS, errorText } from "../lib/admin";
import { Section } from "./Form";
import { Empty, ErrorMessage, Loading } from "./Blocks";

/** Story Z-2: who holds what on one object — FGA's "read" for `object`, e.g. `event:3`.
 *
 *  One line per tuple (relation · person) with a remove, and a row to add a person by the
 *  email of their account. The relations offered are the ones the model defines for this
 *  object type, read from the server rather than copied here. Shown to whoever may see the
 *  object's admin panel; the backend lets only the site's admin and the object's managers
 *  write, and the error text says so to everyone else. */
export function AccessPanel({
  object,
  testId,
  onChange,
}: {
  object: string;
  testId: string;
  /** Called after a tuple was written or removed — for a screen that shows a projection of
   *  them (a club's roster) and has to refetch it. */
  onChange?: () => void;
}) {
  const { t } = useTranslation("admin");
  const invalidate = useInvalidate();
  const tuples = useAsync(useReadTuples({ object }));
  const model = useAsync(useGetModel());
  const objectType = object.split(":")[0] as ObjectType;
  const relations: Relation[] =
    model.data?.types.find((entry) => entry.type === objectType)?.relations ?? [];
  const refresh = () => {
    invalidate(getReadTuplesQueryKey({ object }), "/api/auth/users");
    onChange?.();
  };
  const remove = useDeleteTuple({ mutation: { onSuccess: refresh } });
  const write = useWriteTuple({ mutation: { onSuccess: () => { setEmail(""); refresh(); } } });

  const [email, setEmail] = useState("");
  const [relation, setRelation] = useState<Relation | "">("");
  const chosen = relation && relations.includes(relation) ? relation : relations[0];

  return (
    <Section title={t("access.title")} testId={testId}>
      <p className="mb-2 text-sm text-slate-600">{t("access.hint")}</p>
      {tuples.loading && <Loading testId={`${testId}-loading`} />}
      {tuples.error && <ErrorMessage text={tuples.error} testId={`${testId}-error`} />}
      {tuples.data && tuples.data.length === 0 && (
        <Empty testId={`${testId}-empty`}>{t("access.empty")}</Empty>
      )}
      {tuples.data && tuples.data.length > 0 && (
        <ul className="flex flex-col gap-1.5" data-testid={`${testId}-list`}>
          {tuples.data.map((row) => (
            <li key={row.id} className="flex items-center gap-2" data-testid={`${testId}-tuple-${row.id}`}>
              <span className="font-medium">{t(`accounts.relationLabels.${row.relation}`, { defaultValue: row.relation })}</span>
              <span>
                {row.user_name} <span className="text-slate-500">({row.user})</span>
              </span>
              <button
                type="button"
                className="text-slate-400 hover:text-red-700"
                aria-label={t("access.revoke")}
                title={t("access.revoke")}
                disabled={remove.isPending}
                onClick={() => remove.mutate({ tupleId: row.id })}
                data-testid={`${testId}-revoke-${row.id}`}
              >
                ✕
              </button>
            </li>
          ))}
        </ul>
      )}
      {remove.error && <p className="text-red-700">{errorText(remove.error)}</p>}

      <div className="mt-3 flex flex-wrap items-end gap-2">
        <label className="flex min-w-0 flex-1 flex-col text-xs text-slate-500">
          {t("access.emailLabel")}
          <input
            className={INPUT_CLASS}
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            data-testid={`${testId}-email`}
          />
        </label>
        <label className="flex flex-col text-xs text-slate-500">
          {t("access.relationLabel")}
          <select
            className={INPUT_CLASS}
            value={chosen ?? ""}
            onChange={(e) => setRelation(e.target.value as Relation)}
            data-testid={`${testId}-relation`}
          >
            {relations.map((r) => (
              <option key={r} value={r}>
                {t(`accounts.relationLabels.${r}`)}
              </option>
            ))}
          </select>
        </label>
        <Button
          size="sm"
          isDisabled={!email || !chosen || write.isPending}
          onPress={() => chosen && write.mutate({ data: { user: email, relation: chosen, object } })}
          data-testid={`${testId}-add`}
        >
          {t("access.addButton")}
        </Button>
        {write.error && <p className="w-full text-red-700">{errorText(write.error)}</p>}
      </div>
    </Section>
  );
}
