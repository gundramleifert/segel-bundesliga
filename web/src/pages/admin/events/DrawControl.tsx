import { Button } from "@heroui/react";
import { useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { usePairingFromCatalog } from "../../../api/generated/sbl";
import { Field, Message } from "../../../components/Form";
import { errorText } from "../../../lib/admin";
import { sizedInput } from "./setup";

/** The backend's own default seed (`PairingJobRequest.seed` in app/schemas/admin.py) —
 *  same seed, same draw, reproducible if it ever needs proving. */
const DEFAULT_SEED = 1240;

/** The draw from the catalog (Story VA-7): a seed and the button — in the wizard's third
 *  step and in the manage panel, which must not drift apart on the seed or on when the
 *  draw is allowed. Disabled while the setup is not ready or the configuration is frozen
 *  (Story VA-8): a refusal is never something to discover by pressing. `children` sit
 *  beside the button (the panel's pairing link, the wizard's back and skip). */
export function DrawControl({
  eventId,
  ready,
  frozen = false,
  hasPairing = false,
  testIds,
  seedHint,
  hint,
  successText,
  onDrawn,
  children,
}: {
  eventId: number;
  ready: boolean;
  frozen?: boolean;
  hasPairing?: boolean;
  testIds: { field: string; seed: string; button: string; message: string };
  seedHint?: string;
  /** A line under the row, before the message — why the button is disabled. */
  hint?: ReactNode;
  successText?: string;
  onDrawn: () => void;
  children?: ReactNode;
}) {
  const { t } = useTranslation("admin");
  const [seed, setSeed] = useState(String(DEFAULT_SEED));
  const draw = usePairingFromCatalog({ mutation: { onSuccess: onDrawn } });

  return (
    <>
      <div className="flex flex-wrap items-end gap-3">
        <Field label={t("events.seedLabel")} hint={seedHint} testId={testIds.field}>
          <input
            className={sizedInput("w-28")}
            type="number"
            value={seed}
            onChange={(e) => setSeed(e.target.value)}
            data-testid={testIds.seed}
          />
        </Field>
        <Button
          size="sm"
          isDisabled={draw.isPending || frozen || !ready}
          onPress={() => draw.mutate({ eventId, data: { seed: Number(seed) || DEFAULT_SEED } })}
          data-testid={testIds.button}
        >
          {draw.isPending
            ? t("manage.drawingButton")
            : hasPairing
              ? t("manage.redrawButton")
              : t("manage.drawButton")}
        </Button>
        {children}
      </div>
      {hint}
      <Message
        testId={testIds.message}
        error={draw.isError ? errorText(draw.error) : null}
        success={draw.isSuccess && successText ? successText : null}
      />
    </>
  );
}
