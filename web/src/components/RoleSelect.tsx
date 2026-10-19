import { ROSTER_ROLES, type RosterRole } from "../lib/useRosterDraft";
import { roleText } from "../lib/format";
import { Select } from "./Select";

/** The role beside a name on the right pane of a squad or a lineup — changed in place. */
export function RoleSelect({
  value,
  onChange,
  label,
  testId,
}: {
  value: RosterRole;
  onChange: (role: RosterRole) => void;
  /** The accessible name — there is no visible label beside a row's select. */
  label: string;
  testId: string;
}) {
  return (
    <Select
      size="row"
      value={value}
      aria-label={label}
      onChange={(e) => onChange(e.target.value as RosterRole)}
      testId={testId}
    >
      {ROSTER_ROLES.map((role) => (
        <option key={role} value={role}>
          {roleText(role)}
        </option>
      ))}
    </Select>
  );
}
