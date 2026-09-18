import { Button } from "@heroui/react";

/** The one way a new entry is added to a list: a "＋" and the name of the thing.
 *
 * Every admin list — events, series — shows what exists and offers creation from this
 * button, top-right in the section header (`Section`'s `action` slot); the create form
 * opens under the header, above the list, only once it is pressed. A screen that opened
 * on an empty form put the thing being worked on below the fold and asked for input
 * before showing what was already there. The plus is always in the same corner with the
 * same sign, so nobody has to find out where a screen hides its "new".
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
    <Button size="sm" onPress={onPress} data-testid={testId}>
      <span aria-hidden="true" className="mr-1 text-base leading-none">
        ＋
      </span>
      {label}
    </Button>
  );
}
