import type { DesktopSnapshot } from "./contracts";

export interface LauncherAction {
  id: "chat.new" | "team.new" | "work.new" | "app.open" | "automation.new";
  label: string;
  capabilityId: string;
  requiresApproval: boolean;
  available: boolean;
  reasonCode: string;
}

export interface LauncherProjection {
  schema: "desktop.launcher/v1";
  generatedAt: string;
  source: DesktopSnapshot["source"];
  actions: LauncherAction[];
  reasonCode: string;
}

export function createLauncherProjection(snapshot: DesktopSnapshot, generatedAt = snapshot.generatedAt): LauncherProjection {
  const live = snapshot.source === "runtime" && snapshot.runtime.state === "healthy";
  const actions: Array<Pick<LauncherAction, "id" | "label" | "capabilityId" | "requiresApproval">> = [
    { id: "chat.new", label: "Start Chat", capabilityId: "chat.session.create", requiresApproval: false },
    { id: "team.new", label: "Create Team", capabilityId: "workspace.team.create", requiresApproval: true },
    { id: "work.new", label: "Assign Work", capabilityId: "work.item.create", requiresApproval: true },
    { id: "app.open", label: "Open App", capabilityId: "capability.open", requiresApproval: true },
    { id: "automation.new", label: "Create Automation", capabilityId: "automation.draft.create", requiresApproval: true },
  ];
  return {
    schema: "desktop.launcher/v1",
    generatedAt,
    source: snapshot.source,
    actions: actions.map((action) => ({ ...action, available: live, reasonCode: live ? "action_descriptor_verified" : "capability_unverified" })),
    reasonCode: live ? "desktop.launcher_ready" : "desktop.launcher_unavailable",
  };
}
