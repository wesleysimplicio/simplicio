import type { DesktopSnapshot } from "./contracts";

export type FlagshipAppId = "video" | "browser" | "computer" | "research" | "files_pdf" | "code_build";

export interface FlagshipApp {
  id: FlagshipAppId;
  name: string;
  capabilityIds: string[];
  available: boolean;
  reasonCode: string;
}

export interface FlagshipProjection {
  schema: "flagship.apps/v1";
  requestSchema: "capability.request/v1";
  generatedAt: string;
  source: DesktopSnapshot["source"];
  apps: FlagshipApp[];
  sharedOutputs: Array<"chat" | "work_item" | "live" | "artifact" | "token_report">;
  reasonCode: string;
}

export function createFlagshipProjection(snapshot: DesktopSnapshot, generatedAt = snapshot.generatedAt): FlagshipProjection {
  const live = snapshot.source === "runtime" && snapshot.runtime.state === "healthy";
  const definitions: Array<Pick<FlagshipApp, "id" | "name" | "capabilityIds">> = [
    { id: "video", name: "Video Studio", capabilityIds: ["video.studio"] },
    { id: "browser", name: "Browser", capabilityIds: ["browser.open"] },
    { id: "computer", name: "Computer", capabilityIds: ["computer.use"] },
    { id: "research", name: "Research", capabilityIds: ["research.run"] },
    { id: "files_pdf", name: "Files & PDF", capabilityIds: ["files.read", "pdf.analyze"] },
    { id: "code_build", name: "Code & Build", capabilityIds: ["workspace.build"] },
  ];
  return {
    schema: "flagship.apps/v1",
    requestSchema: "capability.request/v1",
    generatedAt,
    source: snapshot.source,
    apps: definitions.map((app) => ({ ...app, available: live, reasonCode: live ? "flagship_capability_verified" : "flagship_capability_unavailable" })),
    sharedOutputs: ["chat", "work_item", "live", "artifact", "token_report"],
    reasonCode: live ? "flagship.apps_projection_ready" : "flagship.apps_projection_unavailable",
  };
}
