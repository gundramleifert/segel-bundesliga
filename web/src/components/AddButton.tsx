import { Button } from "@heroui/react";

/** The one way a new entry is added to a list: a "＋" and the name of the thing.
 *
 * Every admin list — events, series — shows what exists first and offers creation after
 * it, from this button; the create form appears only once it is pressed. A screen that
 * opened on an empty form put the thing being worked on below the fold and asked for
 * input before showing what was already there. The plus is always present, always in the
 * same place after the list, so nobody has to find out where a screen hides its "new".
 */
export function AddButton({
  label,
  onPress,
  testId,
}: {
  label: string;
  onPress: () => void;
  testId: string;
}) {
  return (
    <div>
      <Button onPress={onPress} data-testid={testId}>
        <span aria-hidden="true" className="mr-1 text-base leading-none">
          ＋
        </span>
        {label}
      </Button>
    </div>
  );
}
