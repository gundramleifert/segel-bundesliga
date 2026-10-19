import { Button } from "@heroui/react";
import { useState, type ReactNode } from "react";

/** An action that cannot be taken back — deleting a post, a document, the account,
 *  leaving a club — asks once more, in place: the button turns into a sentence (if
 *  given), the real action and a way out. Not the browser's `confirm`, which blocks the
 *  page and cannot be styled, and not a modal, which this site has nowhere else.
 *
 *  `testId` names the button; the others are `-confirm`, `-cancel` and `-prompt`. */
export function ConfirmButton({
  label,
  confirmLabel,
  cancelLabel,
  prompt,
  onConfirm,
  busy = false,
  busyLabel,
  size,
  testId,
}: {
  label: string;
  confirmLabel: string;
  cancelLabel: string;
  /** What is about to happen, said before the real button. */
  prompt?: ReactNode;
  onConfirm: () => void;
  /** The action is under way: its button is disabled, and says `busyLabel` if given. */
  busy?: boolean;
  busyLabel?: string;
  size?: "sm" | "md" | "lg";
  testId: string;
}) {
  const [asking, setAsking] = useState(false);
  if (!asking) {
    return (
      <Button size={size} variant="outline" onPress={() => setAsking(true)} data-testid={testId}>
        {label}
      </Button>
    );
  }
  return (
    <>
      {prompt && (
        <span className="text-sm font-medium text-slate-700" data-testid={`${testId}-prompt`}>
          {prompt}
        </span>
      )}
      <Button size={size} variant="danger" isDisabled={busy} onPress={onConfirm} data-testid={`${testId}-confirm`}>
        {busy && busyLabel ? busyLabel : confirmLabel}
      </Button>
      <Button size={size} variant="ghost" isDisabled={busy} onPress={() => setAsking(false)} data-testid={`${testId}-cancel`}>
        {cancelLabel}
      </Button>
    </>
  );
}
