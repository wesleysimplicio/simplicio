import type { DesktopSnapshot } from "./contracts";

export type AmbientMode = "off" | "suggestions_only" | "ask_before_acting" | "autonomous_within_policy";

export interface AmbientControlsProjection {
  schema: "ambient.controls/v1";
  generatedAt: string;
  source: DesktopSnapshot["source"];
  mode: AmbientMode;
  availableModes: AmbientMode[];
  emergencyStop: { available: boolean; reasonCode: string };
  persistInRuntime: boolean;
  reasonCode: string;
}

export function createAmbientControlsProjection(snapshot: DesktopSnapshot, generatedAt = snapshot.generatedAt): AmbientControlsProjection {
  const live = snapshot.source === "runtime" && snapshot.runtime.state === "healthy";
  return {
    schema: "ambient.controls/v1",
    generatedAt,
    source: snapshot.source,
    mode: "suggestions_only",
    availableModes: ["off", "suggestions_only", "ask_before_acting", "autonomous_within_policy"],
    emergencyStop: { available: live, reasonCode: live ? "emergency_stop_verified" : "emergency_stop_unavailable" },
    persistInRuntime: live,
    reasonCode: live ? "ambient.controls_ready" : "ambient.controls_unavailable",
  };
}
