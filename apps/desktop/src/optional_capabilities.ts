import type { DesktopSnapshot } from "./contracts";

export type OptionalCapabilityId = "voice" | "computer" | "learning" | "insights";

export interface OptionalCapability {
  id: OptionalCapabilityId;
  label: string;
  available: boolean;
  reasonCode: string;
  action: "open" | "unavailable";
}

export interface OptionalCapabilitiesProjection {
  schema: "optional.capabilities/v1";
  generatedAt: string;
  source: DesktopSnapshot["source"];
  capabilities: OptionalCapability[];
  reasonCode: string;
}

export function createOptionalCapabilitiesProjection(snapshot: DesktopSnapshot, generatedAt = snapshot.generatedAt): OptionalCapabilitiesProjection {
  const runtime = snapshot.source === "runtime" && snapshot.runtime.state === "healthy";
  const labels: Array<[OptionalCapabilityId, string]> = [["voice", "Voice"], ["computer", "Computer"], ["learning", "Learning Journey"], ["insights", "Insights"]];
  return {
    schema: "optional.capabilities/v1",
    generatedAt,
    source: snapshot.source,
    capabilities: labels.map(([id, label]) => ({ id, label, available: runtime, reasonCode: runtime ? "optional_capability_verified" : `${id}_backend_unavailable`, action: runtime ? "open" : "unavailable" })),
    reasonCode: runtime ? "optional.capabilities_ready" : "optional.capabilities_unavailable",
  };
}
