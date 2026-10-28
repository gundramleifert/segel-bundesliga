import { Button, Card } from "@heroui/react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router-dom";

import { useReadInvitation, useRedeemInvitation } from "../api/generated/sbl";
import type { InvitationLinkOut } from "../api/generated/model/invitationLinkOut";
import { setToken } from "../api/session";
import { useAsync } from "../api/useApi";
import { Async } from "../components/Async";
import { ErrorMessage, PageHeader } from "../components/Blocks";
import { Field } from "../components/Form";
import { INPUT_CLASS, errorText } from "../lib/admin";

/** Story V-16, Journey step J-3.13: the page a club's invitation link opens. It shows the
 *  name as the club entered it; the person confirms or corrects it and gets an account —
 *  the address verified by the link having reached them — and is a member of the club,
 *  signed in. A lapsed, used or replaced link says so, naming the club to ask. */
export function Invitation() {
  const { t } = useTranslation("account");
  const { token = "" } = useParams();
  const invitation = useAsync(useReadInvitation(token, { query: { retry: false } }));
  const [joined, setJoined] = useState(false);

  return (
    <>
      <PageHeader title={t("invitation.title")} testId="invitation-header" />
      {joined && invitation.data ? (
        <Card data-testid="invitation-done">
          <Card.Header>
            <Card.Title>{t("invitation.doneTitle")}</Card.Title>
            <Card.Description>{t("invitation.doneText")}</Card.Description>
          </Card.Header>
          <Card.Content className="flex flex-wrap gap-3">
            <Link to={`/me/club/${invitation.data.club_id}`} className="text-link underline" data-testid="invitation-to-club">
              {t("invitation.toClub")}
            </Link>
            <Link to="/me/profile/account" className="text-link underline" data-testid="invitation-to-password">
              {t("invitation.setPassword")}
            </Link>
          </Card.Content>
        </Card>
      ) : (
        <Async state={invitation} testId="invitation">
          {(data) => (
            <Redeem
              token={token}
              invitation={data}
              onJoined={() => setJoined(true)}
            />
          )}
        </Async>
      )}
    </>
  );
}

function Redeem({
  token,
  invitation,
  onJoined,
}: {
  token: string;
  invitation: InvitationLinkOut;
  onJoined: () => void;
}) {
  const { t } = useTranslation("account");
  const [firstName, setFirstName] = useState(invitation.first_name);
  const [lastName, setLastName] = useState(invitation.last_name);
  const redeem = useRedeemInvitation({
    mutation: {
      onSuccess: (result) => {
        setToken(result.access_token);
        onJoined();
      },
    },
  });
  const field = (id: string, label: string, value: string, set: (v: string) => void) => (
    <Field label={label} testId={`invitation-${id}`}>
      <input
        className={INPUT_CLASS}
        required
        value={value}
        onChange={(e) => set(e.target.value)}
        data-testid={`invitation-${id}-input`}
      />
    </Field>
  );
  return (
    <Card data-testid="invitation-card">
      <Card.Header>
        <Card.Title>{t("invitation.heading", { club: invitation.club_name })}</Card.Title>
        <Card.Description>{t("invitation.text", { club: invitation.club_name })}</Card.Description>
      </Card.Header>
      <Card.Content>
        <form
          className="flex flex-col gap-3"
          onSubmit={(e) => {
            e.preventDefault();
            redeem.mutate({ token, data: { first_name: firstName.trim(), last_name: lastName.trim() } });
          }}
        >
          {field("first-name", t("invitation.firstName"), firstName, setFirstName)}
          {field("last-name", t("invitation.lastName"), lastName, setLastName)}
          <p className="text-sm text-muted">
            {t("invitation.email")}: <span data-testid="invitation-email">{invitation.email}</span>
          </p>
          {redeem.isError && <ErrorMessage text={errorText(redeem.error)} testId="invitation-error" />}
          <div>
            <Button
              type="submit"
              isDisabled={redeem.isPending || !firstName.trim() || !lastName.trim()}
              data-testid="invitation-accept"
            >
              {t("invitation.accept")}
            </Button>
          </div>
        </form>
      </Card.Content>
    </Card>
  );
}
