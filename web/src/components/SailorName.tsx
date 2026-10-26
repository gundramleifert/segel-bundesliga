import { Link } from "react-router-dom";
import type { Member } from "../api/types";
import { fullName } from "../lib/format";

/**
 * A sailor's name in a squad or a lineup — a link to their page, or plain text when they
 * switched that page off (Story S-4). The name itself is never hidden: it is on every
 * competition record, only the page is the sailor's to withhold.
 */
export function SailorName({
  member,
  testId,
  className = "",
}: {
  member: Pick<Member, "id" | "first_name" | "last_name" | "profile_public">;
  testId: string;
  className?: string;
}) {
  const name = fullName(member);
  if (member.profile_public === false)
    return (
      <span data-testid={testId} className={className}>
        {name}
      </span>
    );
  return (
    <Link
      to={`/sailors/${member.id}`}
      data-testid={testId}
      className={`underline-offset-2 hover:underline ${className}`}
    >
      {name}
    </Link>
  );
}
