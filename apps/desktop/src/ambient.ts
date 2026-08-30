import type { DesktopSnapshot } from "./contracts";

export type AmbientState = "quiet" | "working" | "attention" | "unavailable";

export interface AmbientProjection {
  schema: "ambient.state/v1";
  generatedAt: string;
  source: DesktopSnapshot["source"];
  state: AmbientState;
  reasonCode: string;
  pulse: false;
}

/** Derive only a visual hint; work lifecycle remains in Runtime receipts. */
export function createAmbientProjection(snapshot: DesktopSnapshot, generatedAt = snapshot.generatedAt): AmbientProjection {
  const state: AmbientState = snapshot.runtime.state === "offline"
    ? "unavailable"
    : snapshot.activity.some((item) => item.status === "attention")
      ? "attention"
      : snapshot.activity.some((item) => item.status === "running")
        ? "working"
        : "quiet";
  return {
    schema: "ambient.state/v1",
    generatedAt,
    source: snapshot.source,
    state,
    reasonCode: snapshot.source === "runtime" ? "ambient.state_projection_ready" : "ambient.state_projection_unavailable",
    pulse: false,
  };
}
