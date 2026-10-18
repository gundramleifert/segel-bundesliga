import type { ReactNode } from "react";

/** A row of the wizard's buttons: the way forward first, the ways out after it. */
export function StepActions({ children }: { children: ReactNode }) {
  return <div className="flex flex-wrap items-center gap-3">{children}</div>;
}
