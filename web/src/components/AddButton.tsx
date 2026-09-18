import { Button } from "@heroui/react";
import { useNavigate } from "react-router-dom";

/** The one way a new entry is added to a list: a "＋" and the name of the thing, top-right
 * in the list's section header (`Section`'s `action` slot), leading to the entry's own
 * page — `/admin/events/new`, `/admin/series/new`, `/admin/clubs/new`, `/admin/sailors/new`.
 *
 * Creation is a page, never a form embedded above the list: a form at the top of a tab put
 * the thing being worked on below the fold, asked for input before showing what was
 * already there, and could not be linked to or returned to with the back button. The plus
 * is always in the same corner with the same sign, so nobody has to find out where a
 * screen hides its "new".
 */
export function AddButton({
  label,
  to,
  testId,
}: {
  label: string;
  to: string;
  testId: string;
}) {
  const navigate = useNavigate();
  return (
    <Button size="sm" onPress={() => navigate(to)} data-testid={testId}>
      <span aria-hidden="true" className="mr-1 text-base leading-none">
        ＋
      </span>
      {label}
    </Button>
  );
}
