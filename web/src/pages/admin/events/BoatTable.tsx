import { useTranslation } from "react-i18next";

import { Select } from "../../../components/Select";
import { INPUT_CLASS } from "../../../lib/admin";
import { boatColor } from "../../../lib/format";
import { CUSTOM_COLOR, PREDEFINED_COLORS, hexForPicker, sizedInput, type BoatRow } from "./setup";

/** The boats of an event as they lie at the dock — number, colour, name (Stories VA-6,
 *  VA-8). One table for the wizard's first step and the event's *Set up › Boats*: the
 *  rows are the caller's, this only edits them. */
export function BoatTable({
  rows,
  onChange,
  namesRequired = true,
}: {
  rows: BoatRow[];
  onChange: (rows: BoatRow[]) => void;
  /** The wizard asks for every name; an existing boat may stay unnamed. */
  namesRequired?: boolean;
}) {
  const { t } = useTranslation("admin");
  const boatRows = rows;
  const update = (index: number, patch: Partial<BoatRow>) =>
    onChange(rows.map((row, i) => (i === index ? { ...row, ...patch } : row)));
  return (
    <div className="overflow-x-auto rounded-md border border-separator">
      <table data-testid="admin-events-boat-table" className="data-table w-full min-w-[44rem] text-sm">
        <thead>
          <tr className="border-b border-separator bg-surface-secondary text-left text-xs font-medium uppercase tracking-wide text-muted">
            <th scope="col" className="font-medium">
              {t("events.boatNumberLabel")}
            </th>
            <th scope="col" className="font-medium">
              {t("events.boatColorLabel")}
            </th>
            <th scope="col" className="font-medium">
              {t("events.boatNameLabel")}
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-separator">
          {boatRows.map((row, index) => (
            <tr key={index}>
              <td className="text-muted">{index + 1}</td>
              <td>
                {/* `INPUT_CLASS` is `w-full` by default — every control here overrides that
                 *  to a fixed or growing-but-bounded width instead, so all three
                 *  controls stay on one line; the table's own `overflow-x-auto` wrapper
                 *  is the fallback on narrow screens, not wrapping within the row.
                 *
                 *  All three are always shown, not just once "Custom" is picked: the
                 *  select is the plain named choice, the picker is the only place the
                 *  color itself is actually visible, and the text field is the same
                 *  value as typable text. Picking a named color in the select copies its
                 *  hex into the picker/text (so "the dropdown sets the picker"); editing
                 *  the picker or the text field the other way switches the select to
                 *  "Custom" (so a hand-picked color never sits silently under a named
                 *  option it no longer matches). */}
                <div className="flex flex-nowrap items-center gap-2">
                  <Select
                    size="inline"
                    className="w-32 shrink-0"
                    aria-label={`${t("events.boatColorLabel")} ${index + 1}`}
                    value={row.color}
                    onChange={(e) => {
                      const nextColor = e.target.value;
                      update(index, {
                        color: nextColor,
                        customColor:
                          nextColor === CUSTOM_COLOR
                            ? row.customColor
                            : boatColor(nextColor).hex,
                      });
                    }}
                    testId={`admin-events-boat-color-select-${index}`}
                  >
                    {PREDEFINED_COLORS.map((code) => (
                      <option key={code} value={code}>
                        {t(`common:boatColor.${code}`)}
                      </option>
                    ))}
                    <option value={CUSTOM_COLOR}>{t("events.boatColorCustom")}</option>
                  </Select>
                  <input
                    type="color"
                    className="h-9 w-9 shrink-0 cursor-pointer rounded border border-border p-0.5"
                    value={hexForPicker(row.customColor)}
                    onChange={(e) =>
                      update(index, { color: CUSTOM_COLOR, customColor: e.target.value })
                    }
                    aria-label={t("events.boatColorPickerLabel")}
                    data-testid={`admin-events-boat-color-picker-${index}`}
                  />
                  <input
                    className={`${sizedInput("min-w-[6rem]")} flex-1`}
                    value={row.customColor}
                    onChange={(e) =>
                      update(index, { color: CUSTOM_COLOR, customColor: e.target.value })
                    }
                    placeholder={t("events.boatColorCustomPlaceholder")}
                    aria-label={t("events.boatColorCustomPlaceholder")}
                    data-testid={`admin-events-boat-color-custom-input-${index}`}
                  />
                </div>
              </td>
              <td>
                <input
                  className={INPUT_CLASS}
                  value={row.name}
                  onChange={(e) => update(index, { name: e.target.value })}
                  required={namesRequired}
                  placeholder={t("events.boatNamePlaceholder")}
                  aria-label={`${t("events.boatNameLabel")} ${index + 1}`}
                  data-testid={`admin-events-boat-name-input-${index}`}
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
