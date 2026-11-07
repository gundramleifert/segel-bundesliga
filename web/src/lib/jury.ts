import { JuryState } from "../api/generated/model";
import type { BadgeTone } from "../components/Blocks";

/** The tone of a judge's state at an event, on both jury screens (Stories JU-3, JU-4). */
export const JURY_TONE: Record<JuryState, BadgeTone> = {
  [JuryState.invited]: "warning",
  [JuryState.available]: "brand",
  [JuryState.declined]: "muted",
  [JuryState.approved]: "success",
};
