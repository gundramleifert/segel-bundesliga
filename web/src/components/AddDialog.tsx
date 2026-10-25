import { Button, Modal } from "@heroui/react";
import { useState, type ReactNode } from "react";

/** The "＋" top-right of a list whose new entry has no page of its own — a member, a
 *  person named to a role: the button opens a dialog with the few fields it takes, and
 *  the list stays where it was.
 *
 *  The same sign in the same corner as `AddButton`, which leads to a page instead: a thing
 *  with a page of its own (an event, a series, a club, a sailor) is created there, where it
 *  can be linked to and returned to. A form written out under the list was the third way,
 *  and the one this replaced: it made a second table of the same people below the first,
 *  and asked for input before anyone wanted to add anything.
 *
 *  `children` gets `close`, to call once the entry is saved; an error stays in the dialog
 *  beside the fields that caused it. */
export function AddDialog({
  label,
  title,
  testId,
  children,
}: {
  /** The button's words after the "＋" — the thing added, "Member", "Person". */
  label: string;
  /** The dialog's heading. */
  title: string;
  testId: string;
  children: (close: () => void) => ReactNode;
}) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button size="sm" onPress={() => setOpen(true)} data-testid={`${testId}-open`}>
        <span aria-hidden="true" className="mr-1 text-base leading-none">
          ＋
        </span>
        {label}
      </Button>
      <Modal.Backdrop isOpen={open} onOpenChange={setOpen}>
        <Modal.Container placement="center" size="md">
          <Modal.Dialog data-testid={`${testId}-dialog`}>
            <Modal.CloseTrigger />
            <Modal.Header>
              <Modal.Heading>{title}</Modal.Heading>
            </Modal.Header>
            <Modal.Body>{open && children(() => setOpen(false))}</Modal.Body>
          </Modal.Dialog>
        </Modal.Container>
      </Modal.Backdrop>
    </>
  );
}
