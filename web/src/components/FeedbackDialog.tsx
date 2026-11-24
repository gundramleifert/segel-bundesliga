import { Button, Modal } from "@heroui/react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useLocation } from "react-router-dom";

import { useSendFeedback } from "../api/generated/sbl";
import { FeedbackCategory } from "../api/generated/model/feedbackCategory";
import { errorText } from "../api/useApi";
import { INPUT_CLASS } from "../lib/admin";
import { version } from "../lib/environment";
import { Field, Message } from "./Form";
import { Select } from "./Select";

/** The longest message the server takes (`FEEDBACK_MAX_LENGTH`, Story S-9). */
const FEEDBACK_MAX_LENGTH = 5000;

/** Story S-9: a message to the league office, from the page it is opened on. What the
 *  person does not type goes along — the page (path and query), the language, the release
 *  the footer names, the window's size; the server adds the browser and who sent it.
 *  Controlled: the account menu holds `open`, since the menu itself closes as the dialog
 *  opens. */
export function FeedbackDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const { t } = useTranslation();
  return (
    <Modal.Backdrop isOpen={open} onOpenChange={onOpenChange}>
      <Modal.Container placement="center" size="md">
        <Modal.Dialog data-testid="feedback-dialog">
          <Modal.CloseTrigger />
          <Modal.Header>
            <Modal.Heading>{t("feedback.title")}</Modal.Heading>
          </Modal.Header>
          <Modal.Body>{open && <FeedbackForm onSent={() => onOpenChange(false)} />}</Modal.Body>
        </Modal.Dialog>
      </Modal.Container>
    </Modal.Backdrop>
  );
}

function FeedbackForm({ onSent }: { onSent: () => void }) {
  const { t, i18n } = useTranslation();
  const { pathname, search } = useLocation();
  const [category, setCategory] = useState<FeedbackCategory>(FeedbackCategory.bug);
  const [message, setMessage] = useState("");
  const [thanked, setThanked] = useState(false);
  const send = useSendFeedback({
    mutation: {
      onSuccess: () => {
        setThanked(true);
        window.setTimeout(onSent, 1500);
      },
    },
  });
  const over = message.length - FEEDBACK_MAX_LENGTH;

  if (thanked) return <Message success={t("feedback.thanks")} testId="feedback" />;

  return (
    <form
      className="flex flex-col gap-3 pb-2"
      onSubmit={(e) => {
        e.preventDefault();
        send.mutate({
          data: {
            category,
            message,
            path: `${pathname}${search}`,
            locale: i18n.resolvedLanguage ?? i18n.language,
            app_version: version,
            viewport_width: window.innerWidth,
            viewport_height: window.innerHeight,
          },
        });
      }}
    >
      <p className="text-sm text-muted">{t("feedback.intro")}</p>
      <Field label={t("feedback.categoryLabel")}>
        <Select
          value={category}
          onChange={(e) => setCategory(e.target.value as FeedbackCategory)}
          testId="feedback-category"
        >
          {Object.values(FeedbackCategory).map((value) => (
            <option key={value} value={value}>
              {t(`feedback.categories.${value}`)}
            </option>
          ))}
        </Select>
      </Field>
      <Field label={t("feedback.messageLabel")}>
        <textarea
          className={`${INPUT_CLASS} min-h-32`}
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          placeholder={t("feedback.messagePlaceholder")}
          data-testid="feedback-message"
        />
      </Field>
      {over > 0 && (
        <p className="text-xs text-danger" data-testid="feedback-too-long">
          {t("feedback.tooLong", { count: over })}
        </p>
      )}
      <Message error={send.error ? errorText(send.error) : null} testId="feedback" />
      <div className="flex justify-end">
        <Button
          type="submit"
          isDisabled={!message.trim() || over > 0 || send.isPending}
          data-testid="feedback-send"
        >
          {t("feedback.send")}
        </Button>
      </div>
    </form>
  );
}
