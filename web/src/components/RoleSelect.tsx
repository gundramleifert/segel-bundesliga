import { ROSTER_ROLES, type RosterRole } from "../lib/useRosterDraft";
import { roleText } from "../lib/format";

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
    <select
      className="shrink-0 rounded border border-slate-300 px-1.5 py-0.5 text-xs"
      value={value}
      aria-label={label}
      onChange={(e) => onChange(e.target.value as RosterRole)}
      data-testid={testId}
    >
      {ROSTER_ROLES.map((role) => (
        <option key={role} value={role}>
          {roleText(role)}
        </option>
      ))}
    </select>
  );
}
