import type { DesktopSnapshot } from "./contracts";

export interface WorkspaceResource {
  id: string;
  kind: "project" | "worktree" | "file" | "profile";
  label: string;
  parentId: string | null;
  readable: boolean;
  writable: boolean;
  pathHandle: string | null;
  reasonCode: string;
}

export interface WorkspaceResourcesProjection {
  schema: "workspace.resources/v1";
  generatedAt: string;
  source: DesktopSnapshot["source"];
  resources: WorkspaceResource[];
  arbitraryFilesystemAccess: false;
  reasonCode: string;
}

export function createWorkspaceResourcesProjection(snapshot: DesktopSnapshot, generatedAt = snapshot.generatedAt): WorkspaceResourcesProjection {
  return {
    schema: "workspace.resources/v1",
    generatedAt,
    source: snapshot.source,
    resources: [
      { id: "project-simplicio", kind: "project", label: "Simplicio", parentId: null, readable: true, writable: false, pathHandle: "project://simplicio", reasonCode: "workspace_handle_preview" },
      { id: "profile-default", kind: "profile", label: "Personal", parentId: null, readable: true, writable: false, pathHandle: "profile://personal", reasonCode: "workspace_handle_preview" },
    ],
    arbitraryFilesystemAccess: false,
    reasonCode: snapshot.source === "runtime" ? "workspace.resources_projection_ready" : "workspace.resources_projection_unavailable",
  };
}
